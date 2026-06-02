"""Embedding client implementations for semantic similarity."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

from ..monitoring.logger import get_logger


@dataclass
class EmbeddingConfig:
    """Configuration for embedding client."""

    provider: str = "ollama"
    model: str = "nomic-embed-text"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    timeout: int = 30


class BaseEmbeddingClient(ABC):
    """Abstract base class for embedding clients."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Get embedding vector for a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embedding vectors for multiple text strings."""
        pass

    def is_available(self) -> bool:
        """Check if the embedding service is available."""
        try:
            self.embed("test")
            return True
        except Exception:
            return False


class OllamaEmbeddingClient(BaseEmbeddingClient):
    """Ollama embedding client using /api/embed endpoint."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.model = config.model
        self.timeout = config.timeout

    def embed(self, text: str) -> list[float]:
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": text},
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        if not response.ok:
            logger = get_logger()
            logger.error(
                f"Ollama embedding error: {response.status_code} - {response.text}"
            )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        if not response.ok:
            logger = get_logger()
            logger.error(
                f"Ollama embedding batch error: {response.status_code} - {response.text}"
            )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"]


class SentenceTransformersEmbeddingClient(BaseEmbeddingClient):
    """Local embedding client using sentence-transformers (optional dependency)."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._model = None
        self._model_name = config.model or "all-MiniLM-L6-v2"

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Install with: pip install 'nano-agent[embedding]'"
                )

    def embed(self, text: str) -> list[float]:
        self._load_model()
        return self._model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        return self._model.encode(texts).tolist()


class OpenAIEmbeddingClient(BaseEmbeddingClient):
    """OpenAI embedding API client."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model = config.model or "text-embedding-3-small"
        self.api_key = config.api_key
        self.timeout = config.timeout

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import os

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        if not response.ok:
            logger = get_logger()
            logger.error(
                f"OpenAI embedding error: {response.status_code} - {response.text}"
            )
        response.raise_for_status()
        data = response.json()
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]


def create_embedding_client(config: EmbeddingConfig) -> BaseEmbeddingClient:
    """Factory function to create embedding client."""
    if config.provider == "ollama":
        return OllamaEmbeddingClient(config)
    elif config.provider == "sentence_transformers":
        return SentenceTransformersEmbeddingClient(config)
    elif config.provider == "openai":
        return OpenAIEmbeddingClient(config)
    else:
        raise ValueError(
            f"Unsupported embedding provider: {config.provider}. "
            "Use 'ollama', 'sentence_transformers', or 'openai'."
        )
