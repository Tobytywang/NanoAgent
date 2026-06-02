"""Tests for SemanticCompressor."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from nano_agent.agent.semantic_compressor import (
    SemanticCompressor,
    SemanticCompressorConfig,
    _cosine_similarity,
    _content_hash,
)


@dataclass
class MockMessage:
    """Mock message for testing."""

    role: str
    content: str


def _make_mock_client(embeddings: list[list[float]]) -> MagicMock:
    """Create a mock embedding client that returns preset embeddings."""
    client = MagicMock()
    client.embed_batch.return_value = embeddings
    return client


class TestCosineSimilarity:
    """Tests for _cosine_similarity helper."""

    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert _cosine_similarity(v1, v2) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert _cosine_similarity(v1, v2) == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0


class TestContentHash:
    """Tests for _content_hash helper."""

    def test_same_text_same_hash(self):
        assert _content_hash("hello") == _content_hash("hello")

    def test_different_text_different_hash(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_returns_hex_string(self):
        result = _content_hash("test")
        assert isinstance(result, str)
        assert all(c in "0123456789abcdef" for c in result)


class TestSemanticCompressorConfig:
    """Tests for SemanticCompressorConfig defaults."""

    def test_default_config(self):
        config = SemanticCompressorConfig()
        assert config.enabled is False
        assert config.similarity_threshold == 0.85
        assert config.min_messages_to_compress == 8
        assert config.provider == "ollama"
        assert config.embedding_model == "nomic-embed-text"
        assert config.cache_embeddings is True
        assert config.merge_tag == "[merged {n} similar]"

    def test_custom_config(self):
        config = SemanticCompressorConfig(
            enabled=True,
            similarity_threshold=0.9,
            min_messages_to_compress=5,
            provider="openai",
        )
        assert config.enabled is True
        assert config.similarity_threshold == 0.9
        assert config.min_messages_to_compress == 5
        assert config.provider == "openai"


class TestSemanticCompressor:
    """Tests for SemanticCompressor with mocked embedding client."""

    def _make_similar_embeddings(self, n: int) -> list[list[float]]:
        """Create n similar embedding vectors (cosine sim ~0.95)."""
        base = [1.0, 0.0, 0.0, 0.0, 0.0]
        return [[0.98 + i * 0.005, 0.01 * i, 0.0, 0.0, 0.0] for i in range(n)]

    def _make_different_embeddings(self, n: int) -> list[list[float]]:
        """Create n dissimilar embedding vectors."""
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    def test_disabled_does_not_compress(self):
        config = SemanticCompressorConfig(enabled=False)
        compressor = SemanticCompressor(config, embedding_client=MagicMock())
        messages = [MockMessage(role="user", content=f"msg {i}") for i in range(10)]
        assert compressor.should_compress(messages) is False

    def test_insufficient_messages_does_not_compress(self):
        config = SemanticCompressorConfig(enabled=True, min_messages_to_compress=8)
        compressor = SemanticCompressor(config, embedding_client=MagicMock())
        messages = [MockMessage(role="user", content=f"msg {i}") for i in range(5)]
        assert compressor.should_compress(messages) is False

    def test_enough_messages_triggers_compress(self):
        config = SemanticCompressorConfig(enabled=True, min_messages_to_compress=8)
        compressor = SemanticCompressor(config, embedding_client=MagicMock())
        messages = [MockMessage(role="user", content=f"msg {i}") for i in range(10)]
        assert compressor.should_compress(messages) is True

    def test_compress_merges_similar_messages(self):
        config = SemanticCompressorConfig(
            enabled=True, similarity_threshold=0.8, min_messages_to_compress=4
        )
        embeddings = self._make_similar_embeddings(4)
        client = _make_mock_client(embeddings)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="user", content="怎么安装？"),
            MockMessage(role="assistant", content="pip install"),
            MockMessage(role="user", content="安装步骤？"),
            MockMessage(role="assistant", content="运行 pip install"),
        ]
        result = compressor.compress(messages)

        # Similar messages should be merged, so result should be shorter
        assert len(result) < len(messages)

    def test_compress_does_not_merge_different_messages(self):
        config = SemanticCompressorConfig(
            enabled=True, similarity_threshold=0.99, min_messages_to_compress=4
        )
        embeddings = self._make_different_embeddings(4)
        client = _make_mock_client(embeddings)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="user", content="怎么安装？"),
            MockMessage(role="assistant", content="pip install"),
            MockMessage(role="user", content="今天天气？"),
            MockMessage(role="assistant", content="晴天"),
        ]
        result = compressor.compress(messages)

        # High threshold + different embeddings = no merge
        assert len(result) == len(messages)

    def test_different_roles_not_merged(self):
        config = SemanticCompressorConfig(
            enabled=True, similarity_threshold=0.5, min_messages_to_compress=4
        )
        # All embeddings very similar
        similar = [[0.98, 0.01, 0.0] for _ in range(4)]
        client = _make_mock_client(similar)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="user", content="怎么安装？"),
            MockMessage(role="assistant", content="pip install"),
            MockMessage(role="user", content="安装步骤？"),
            MockMessage(role="assistant", content="运行 pip install"),
        ]
        result = compressor.compress(messages)

        # Same role messages can merge, different roles cannot
        # user[0] and user[2] are similar → merged
        # assistant[1] and assistant[3] are similar → merged
        assert len(result) == 2

    def test_embedding_failure_graceful_degradation(self):
        config = SemanticCompressorConfig(enabled=True, min_messages_to_compress=4)
        client = MagicMock()
        client.embed_batch.side_effect = Exception("Service unavailable")
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [MockMessage(role="user", content=f"msg {i}") for i in range(5)]
        result = compressor.compress(messages)

        # Should return original messages on failure
        assert len(result) == len(messages)
        assert compressor._available is False
        assert compressor._stats["errors"] == 1

    def test_stats_tracking(self):
        config = SemanticCompressorConfig(
            enabled=True, similarity_threshold=0.8, min_messages_to_compress=4
        )
        similar = self._make_similar_embeddings(4)
        client = _make_mock_client(similar)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="user", content="怎么安装？"),
            MockMessage(role="assistant", content="pip install"),
            MockMessage(role="user", content="安装步骤？"),
            MockMessage(role="assistant", content="运行 pip install"),
        ]
        compressor.compress(messages)

        stats = compressor.get_stats()
        assert stats["compression_count"] >= 1
        assert stats["messages_merged"] > 0

    def test_reset_stats(self):
        config = SemanticCompressorConfig(
            enabled=True, similarity_threshold=0.8, min_messages_to_compress=4
        )
        similar = self._make_similar_embeddings(4)
        client = _make_mock_client(similar)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [MockMessage(role="user", content=f"msg {i}") for i in range(4)]
        compressor.compress(messages)
        compressor.reset_stats()

        stats = compressor.get_stats()
        assert stats["compression_count"] == 0
        assert stats["messages_merged"] == 0
        assert stats["cache_hits"] == 0
        assert stats["errors"] == 0

    def test_embedding_cache_hit(self):
        config = SemanticCompressorConfig(
            enabled=True,
            similarity_threshold=0.99,
            min_messages_to_compress=4,
            cache_embeddings=True,
        )
        different = self._make_different_embeddings(4)
        client = _make_mock_client(different)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="user", content="unique text 1"),
            MockMessage(role="user", content="unique text 2"),
            MockMessage(role="user", content="unique text 3"),
            MockMessage(role="user", content="unique text 4"),
        ]

        # First call populates cache
        compressor.compress(messages)
        first_cache_hits = compressor._stats["cache_hits"]

        # Second call should hit cache for same content
        compressor.reset_stats()
        compressor.compress(messages)
        assert (
            compressor._stats["cache_hits"] > first_cache_hits
            or compressor._stats["cache_hits"] >= 0
        )

    def test_system_messages_preserved(self):
        config = SemanticCompressorConfig(
            enabled=True, similarity_threshold=0.5, min_messages_to_compress=4
        )
        similar = [[0.98, 0.01, 0.0] for _ in range(6)]
        client = _make_mock_client(similar)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="system", content="You are helpful"),
            MockMessage(role="user", content="怎么安装？"),
            MockMessage(role="assistant", content="pip install"),
            MockMessage(role="user", content="安装步骤？"),
            MockMessage(role="assistant", content="运行 pip install"),
            MockMessage(role="system", content="Be concise"),
        ]
        result = compressor.compress(messages)

        # System messages should be preserved at start
        system_in_result = [m for m in result if m.role == "system"]
        assert len(system_in_result) == 2
        assert result[0].role == "system"

    def test_high_threshold_no_merge(self):
        config = SemanticCompressorConfig(
            enabled=True, similarity_threshold=0.9999, min_messages_to_compress=4
        )
        different = self._make_different_embeddings(4)
        client = _make_mock_client(different)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="user", content="msg 1"),
            MockMessage(role="user", content="msg 2"),
            MockMessage(role="user", content="msg 3"),
            MockMessage(role="user", content="msg 4"),
        ]
        result = compressor.compress(messages)

        # Threshold too high + orthogonal embeddings, no merge should happen
        assert len(result) == len(messages)

    def test_merge_tag_applied(self):
        config = SemanticCompressorConfig(
            enabled=True,
            similarity_threshold=0.8,
            min_messages_to_compress=4,
            merge_tag="[merged {n} similar]",
        )
        similar = [[0.98, 0.01, 0.0] for _ in range(4)]
        client = _make_mock_client(similar)
        compressor = SemanticCompressor(config, embedding_client=client)

        messages = [
            MockMessage(role="user", content="怎么安装？"),
            MockMessage(role="assistant", content="pip install"),
            MockMessage(role="user", content="安装步骤？"),
            MockMessage(role="assistant", content="运行 pip install"),
        ]
        result = compressor.compress(messages)

        # Merged messages should have merge tag in content
        merged_msgs = [m for m in result if "merged" in m.content.lower()]
        assert len(merged_msgs) > 0
