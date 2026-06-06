"""Semantic compressor that merges similar messages using embedding similarity."""

import hashlib
import math
from dataclasses import dataclass

from ..llm.embedding import EmbeddingConfig, create_embedding_client
from ..monitoring.logger import get_logger


@dataclass
class SemanticCompressorConfig:
    """Configuration for semantic compression."""

    enabled: bool = False
    similarity_threshold: float = 0.85
    min_messages_to_compress: int = 8
    provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    cache_embeddings: bool = True
    merge_tag: str = "[merged {n} similar]"


def _msg_role(m) -> str | None:
    """Get role from a message (dict or object)."""
    if isinstance(m, dict):
        return m.get("role")
    return getattr(m, "role", None)


def _msg_content(m) -> str:
    """Get content from a message (dict or object)."""
    if isinstance(m, dict):
        return m.get("content", "")
    return getattr(m, "content", str(m))


def _set_msg_content(m, content: str):
    """Set content on a message (dict or object), returning a new message."""
    if isinstance(m, dict):
        merged = dict(m)
        merged["content"] = content
        return merged
    import copy

    merged = copy.copy(m)
    merged.content = content
    return merged


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(a * a for a in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _content_hash(text: str) -> str:
    """SHA256 hash of text content for caching."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SemanticCompressor:
    """Merges semantically similar messages to reduce token usage."""

    def __init__(
        self,
        config: SemanticCompressorConfig,
        embedding_client=None,
        llm_config=None,
    ):
        self.config = config
        self._client = embedding_client
        self._cache: dict[str, list[float]] = {}
        self._available: bool | None = None

        self._stats = {
            "compression_count": 0,
            "messages_merged": 0,
            "cache_hits": 0,
            "errors": 0,
        }
        self._max_errors = 3

        if self._client is None and config.enabled:
            self._init_client(llm_config)

    def _init_client(self, llm_config=None):
        """Initialize embedding client from config or LLM config."""
        try:
            embedding_config = EmbeddingConfig(
                provider=self.config.provider,
                model=self.config.embedding_model,
                base_url=self.config.base_url,
                api_key=self.config.api_key,
            )
            if llm_config and self.config.provider == "ollama":
                embedding_config.base_url = getattr(
                    llm_config, "base_url", embedding_config.base_url
                )
            self._client = create_embedding_client(embedding_config)
        except Exception as e:
            logger = get_logger()
            logger.warning(f"SemanticCompressor: failed to init embedding client: {e}")
            self._available = False

    def should_compress(self, messages: list) -> bool:
        """Check if semantic compression should be applied."""
        if not self.config.enabled:
            return False
        if self._available is False:
            return False
        non_system = [m for m in messages if _msg_role(m) != "system"]
        return len(non_system) >= self.config.min_messages_to_compress

    def compress(self, messages: list) -> list:
        """Compress messages by merging semantically similar ones."""
        if not self.should_compress(messages):
            return messages

        system_msgs = [m for m in messages if _msg_role(m) == "system"]
        other_msgs = [m for m in messages if _msg_role(m) != "system"]

        if not other_msgs:
            return messages

        try:
            embeddings = self._get_embeddings(other_msgs)
        except Exception as e:
            logger = get_logger()
            logger.debug(f"SemanticCompressor: embedding failed, skipping: {e}")
            self._stats["errors"] += 1
            if self._stats["errors"] >= self._max_errors:
                self._available = False
            return messages

        if len(embeddings) != len(other_msgs):
            return messages

        merged_indices = self._find_similar_groups(other_msgs, embeddings)

        if not merged_indices:
            return messages

        # Build set of all indices that were consumed (merged into another)
        consumed = set()
        for group in merged_indices.values():
            consumed.update(group)

        result = list(system_msgs)
        merged_count = 0
        for i, msg in enumerate(other_msgs):
            if i in consumed:
                continue
            group = merged_indices.get(i)
            if group is not None:
                merged_msg = self._merge_message(msg, len(group) + 1)
                result.append(merged_msg)
                merged_count += len(group)
            else:
                result.append(msg)

        if merged_count > 0:
            self._stats["compression_count"] += 1
            self._stats["messages_merged"] += merged_count

        return result

    def _get_embeddings(self, messages: list) -> list[list[float]]:
        """Get embeddings for messages, using cache when possible."""
        if self._client is None:
            raise RuntimeError("Embedding client not initialized")

        texts = [_msg_content(m) for m in messages]
        results = []
        uncached_indices = []
        uncached_texts = []

        for i, text in enumerate(texts):
            if self.config.cache_embeddings:
                key = _content_hash(text)
                if key in self._cache:
                    results.append(self._cache[key])
                    self._stats["cache_hits"] += 1
                    continue
            results.append(None)
            uncached_indices.append(i)
            uncached_texts.append(text)

        if uncached_texts:
            batch_embeddings = self._client.embed_batch(uncached_texts)
            for idx, embedding in zip(uncached_indices, batch_embeddings):
                results[idx] = embedding
                if self.config.cache_embeddings:
                    key = _content_hash(texts[idx])
                    self._cache[key] = embedding

        return results

    def _find_similar_groups(
        self, messages: list, embeddings: list[list[float]]
    ) -> dict[int, list[int]]:
        """Find groups of similar messages. Returns {keeper_index: [merged_indices...]}."""
        threshold = self.config.similarity_threshold
        merged_into: dict[int, list[int]] = {}
        consumed: set[int] = set()

        for i in range(len(messages)):
            if i in consumed:
                continue
            for j in range(i + 1, len(messages)):
                if j in consumed:
                    continue
                if _msg_role(messages[i]) != _msg_role(messages[j]):
                    continue
                sim = _cosine_similarity(embeddings[i], embeddings[j])
                if sim >= threshold:
                    if i not in merged_into:
                        merged_into[i] = []
                    merged_into[i].append(j)
                    consumed.add(j)

        return merged_into

    def _merge_message(self, original, count: int):
        """Add merge tag to a message."""
        tag = self.config.merge_tag.format(n=count - 1)
        content = _msg_content(original)
        new_content = f"{content}\n{tag}"
        return _set_msg_content(original, new_content)

    def get_stats(self) -> dict:
        """Return compression statistics."""
        return dict(self._stats)

    def reset_stats(self):
        """Reset compression statistics."""
        self._stats = {
            "compression_count": 0,
            "messages_merged": 0,
            "cache_hits": 0,
            "errors": 0,
        }
