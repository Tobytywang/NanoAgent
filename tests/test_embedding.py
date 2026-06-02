"""Tests for embedding client implementations."""

import pytest
from unittest.mock import patch, MagicMock

from nano_agent.llm.embedding import (
    EmbeddingConfig,
    OllamaEmbeddingClient,
    SentenceTransformersEmbeddingClient,
    OpenAIEmbeddingClient,
    create_embedding_client,
)


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig defaults."""

    def test_default_config(self):
        config = EmbeddingConfig()
        assert config.provider == "ollama"
        assert config.model == "nomic-embed-text"
        assert config.base_url == "http://localhost:11434"
        assert config.api_key is None
        assert config.timeout == 30

    def test_custom_config(self):
        config = EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-small",
            api_key="sk-test",
            timeout=60,
        )
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-small"
        assert config.api_key == "sk-test"
        assert config.timeout == 60


class TestOllamaEmbeddingClient:
    """Tests for OllamaEmbeddingClient with mocked HTTP."""

    @patch("nano_agent.llm.embedding.requests.post")
    def test_embed_single_text(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_post.return_value = mock_response

        config = EmbeddingConfig(base_url="http://localhost:11434")
        client = OllamaEmbeddingClient(config)
        result = client.embed("hello world")

        assert result == [0.1, 0.2, 0.3]
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/embed",
            json={"model": "nomic-embed-text", "input": "hello world"},
            timeout=30,
            headers={"Content-Type": "application/json"},
        )

    @patch("nano_agent.llm.embedding.requests.post")
    def test_embed_batch(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        mock_post.return_value = mock_response

        config = EmbeddingConfig()
        client = OllamaEmbeddingClient(config)
        result = client.embed_batch(["text1", "text2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    @patch("nano_agent.llm.embedding.requests.post")
    def test_embed_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        mock_post.return_value = mock_response

        config = EmbeddingConfig()
        client = OllamaEmbeddingClient(config)

        with pytest.raises(Exception):
            client.embed("test")

    def test_base_url_trailing_slash_stripped(self):
        config = EmbeddingConfig(base_url="http://localhost:11434/")
        client = OllamaEmbeddingClient(config)
        assert client.base_url == "http://localhost:11434"


class TestCreateEmbeddingClient:
    """Tests for create_embedding_client factory function."""

    def test_creates_ollama_client(self):
        config = EmbeddingConfig(provider="ollama")
        client = create_embedding_client(config)
        assert isinstance(client, OllamaEmbeddingClient)

    def test_creates_sentence_transformers_client(self):
        config = EmbeddingConfig(provider="sentence_transformers")
        client = create_embedding_client(config)
        assert isinstance(client, SentenceTransformersEmbeddingClient)

    def test_creates_openai_client(self):
        config = EmbeddingConfig(provider="openai")
        client = create_embedding_client(config)
        assert isinstance(client, OpenAIEmbeddingClient)

    def test_unsupported_provider_raises(self):
        config = EmbeddingConfig(provider="unknown")
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            create_embedding_client(config)
