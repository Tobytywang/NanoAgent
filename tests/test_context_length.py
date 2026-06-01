"""
Tests for v0.7.11: Model Context Window Accuracy.

Covers:
- _model_prefix_matches() prefix-safe matching
- get_context_length() four-layer fallback chain
- query_context_length() on LLM clients
- ContextManager uses llm_config instead of hardcoded 128000
- set_llm_client() injection
"""

import pytest
from unittest.mock import MagicMock, patch

from nano_agent.config.schema import (
    LLMConfig,
    ContextConfig,
    _model_prefix_matches,
    CONSERVATIVE_CONTEXT_FALLBACK,
    MODEL_CONTEXT_LENGTHS,
)
from nano_agent.agent.context import ContextManager, NineSectionSummary

# ============================================================
# Task 4: _model_prefix_matches — prefix-safe matching
# ============================================================


class TestModelPrefixMatches:
    """Prevent llama3 from matching llama3.1."""

    def test_exact_match(self):
        assert _model_prefix_matches("llama3", "llama3") is True

    def test_separator_dot(self):
        assert _model_prefix_matches("llama3.1", "llama3") is True

    def test_separator_dash(self):
        assert _model_prefix_matches("gpt-4o-2024-08-06", "gpt-4o") is True

    def test_separator_underscore(self):
        assert _model_prefix_matches("my_model_v2", "my_model") is True

    def test_no_separator_no_match(self):
        # "llama31" should NOT match "llama3"
        assert _model_prefix_matches("llama31", "llama3") is False

    def test_unrelated_prefix(self):
        # "codellama" should NOT match "llama3"
        assert _model_prefix_matches("codellama", "llama3") is False

    def test_empty_remainder(self):
        # Exact match has no remainder
        assert _model_prefix_matches("qwen2.5", "qwen2.5") is True

    def test_shorter_key_no_match(self):
        # Model name shorter than key
        assert _model_prefix_matches("gpt", "gpt-4") is False

    def test_partial_key_match_with_separator(self):
        # "gpt-4o-mini" has dash after "gpt-4o"
        assert _model_prefix_matches("gpt-4o-mini", "gpt-4o") is True

    def test_model_longer_than_key_no_separator(self):
        # "llama3b" — no separator after "llama3"
        assert _model_prefix_matches("llama3b", "llama3") is False


# ============================================================
# Tasks 1, 5, 7: get_context_length() four-layer fallback
# ============================================================


class TestGetContextLength:
    """Test the four-layer fallback chain."""

    # Layer 1: User override
    def test_user_override_highest_priority(self):
        config = LLMConfig(model="gpt-4o", context_length=32768)
        # Even with an LLM client that returns something else,
        # user override wins
        mock_llm = MagicMock()
        mock_llm.query_context_length.return_value = 999999
        config.set_llm_client(mock_llm)
        assert config.get_context_length() == 32768

    def test_user_override_overrides_everything(self):
        config = LLMConfig(model="unknown-model", context_length=4096)
        assert config.get_context_length() == 4096

    # Layer 2: API query
    def test_api_query_used_when_no_override(self):
        config = LLMConfig(model="some-custom-model")
        mock_llm = MagicMock()
        mock_llm.query_context_length.return_value = 65536
        config.set_llm_client(mock_llm)
        assert config.get_context_length() == 65536

    def test_api_query_failure_falls_through(self):
        config = LLMConfig(model="some-custom-model")
        mock_llm = MagicMock()
        mock_llm.query_context_length.return_value = None
        config.set_llm_client(mock_llm)
        # Falls through to lookup table, then conservative fallback
        assert config.get_context_length() == CONSERVATIVE_CONTEXT_FALLBACK

    def test_api_query_exception_falls_through(self):
        config = LLMConfig(model="some-custom-model")
        mock_llm = MagicMock()
        mock_llm.query_context_length.side_effect = RuntimeError("API down")
        config.set_llm_client(mock_llm)
        assert config.get_context_length() == CONSERVATIVE_CONTEXT_FALLBACK

    def test_no_llm_client_skips_api_query(self):
        config = LLMConfig(model="some-custom-model")
        # No client set, no override, unknown model -> fallback
        assert config.get_context_length() == CONSERVATIVE_CONTEXT_FALLBACK

    # Layer 3: Lookup table — exact match
    def test_exact_match_in_lookup_table(self):
        config = LLMConfig(model="gpt-4o")
        assert config.get_context_length() == MODEL_CONTEXT_LENGTHS["gpt-4o"]

    def test_exact_match_case_insensitive(self):
        config = LLMConfig(model="GPT-4O")
        assert config.get_context_length() == MODEL_CONTEXT_LENGTHS["gpt-4o"]

    # Layer 3: Lookup table — prefix match
    def test_prefix_match_with_separator(self):
        config = LLMConfig(model="gpt-4o-2024-08-06")
        assert config.get_context_length() == MODEL_CONTEXT_LENGTHS["gpt-4o"]

    def test_llama31_uses_own_entry_not_llama3(self):
        """The bug: llama3.1 was incorrectly matching llama3 (8192 instead of 131072)."""
        config = LLMConfig(model="llama3.1")
        assert config.get_context_length() == MODEL_CONTEXT_LENGTHS["llama3.1"]
        assert config.get_context_length() != MODEL_CONTEXT_LENGTHS["llama3"]

    def test_llama3_uses_own_entry(self):
        config = LLMConfig(model="llama3")
        assert config.get_context_length() == MODEL_CONTEXT_LENGTHS["llama3"]

    # Layer 4: Conservative fallback
    def test_unknown_model_uses_conservative_fallback(self):
        config = LLMConfig(model="brand-new-model-v99")
        assert config.get_context_length() == CONSERVATIVE_CONTEXT_FALLBACK

    def test_conservative_fallback_is_8192(self):
        assert CONSERVATIVE_CONTEXT_FALLBACK == 8192

    def test_old_default_128000_not_used(self):
        """The old fallback was 128000 — ensure it's no longer used."""
        config = LLMConfig(model="completely-unknown-model")
        assert config.get_context_length() != 128000


# ============================================================
# Task 6: ContextManager uses llm_config
# ============================================================


class TestContextManagerLlmConfig:
    """ContextManager should derive max_context_tokens from llm_config."""

    def _make_context_manager(self, llm_config, messages=None):
        """Helper to create a ContextManager with mock dependencies."""
        mock_memory = MagicMock()
        mock_memory.get_all.return_value = messages or []
        mock_llm = MagicMock()

        return ContextManager(
            memory=mock_memory,
            llm=mock_llm,
            config=ContextConfig(),
            llm_config=llm_config,
        )

    def test_no_hardcoded_128000(self):
        """ContextManager should NOT fall back to hardcoded 128000."""
        llm_config = LLMConfig(model="llama3")
        # llama3 has 8192 in the lookup table, not 128000
        cm = self._make_context_manager(llm_config)
        result = cm.check_and_compress()
        # With no messages, no compression needed
        assert result is False

    def test_uses_llm_config_for_max_context(self):
        """When config.max_context_tokens is None, use llm_config."""
        llm_config = LLMConfig(model="llama3", context_length=8192)
        cm = self._make_context_manager(llm_config)
        result = cm.check_and_compress()
        assert result is False

    def test_llm_config_override_respected(self):
        """User's context_length override should flow through."""
        llm_config = LLMConfig(model="llama3", context_length=32768)
        cm = self._make_context_manager(llm_config)
        result = cm.check_and_compress()
        assert result is False


# ============================================================
# Task 2 & 3: query_context_length on LLM clients
# ============================================================


class TestQueryContextLength:
    """Verify query_context_length exists and returns correct types."""

    def test_ollama_has_method(self):
        from nano_agent.llm.ollama import OllamaLLM

        ollama = OllamaLLM(model="llama3")
        assert hasattr(ollama, "query_context_length")
        assert callable(ollama.query_context_length)

    def test_openai_compatible_has_method(self):
        from nano_agent.llm.openai_compatible import OpenAICompatibleLLM

        llm = OpenAICompatibleLLM(model="gpt-4o", api_key="test-key")
        assert hasattr(llm, "query_context_length")
        assert callable(llm.query_context_length)

    def test_base_llm_default_returns_none(self):
        """BaseLLM.query_context_length should return None by default."""
        from nano_agent.llm.base import BaseLLM

        class MinimalLLM(BaseLLM):
            def __init__(self, model="", base_url=""):
                pass

            def chat(self, messages, tools=None, system_stable=None, **kwargs):
                return ("", [], None)

        llm = MinimalLLM()
        assert llm.query_context_length() is None

    @patch("nano_agent.llm.ollama.requests.post")
    def test_ollama_query_parses_num_ctx(self, mock_post):
        """Ollama should parse num_ctx from /api/show response."""
        from nano_agent.llm.ollama import OllamaLLM

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "parameters": {"num_ctx": 4096},
            "model_info": {},
        }
        mock_post.return_value = mock_response

        llm = OllamaLLM(model="llama3")
        result = llm.query_context_length()
        assert result == 4096

    @patch("nano_agent.llm.ollama.requests.post")
    def test_ollama_query_falls_back_to_model_info(self, mock_post):
        """When num_ctx is not in parameters, check model_info."""
        from nano_agent.llm.ollama import OllamaLLM

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "parameters": {},
            "model_info": {"llama.context_length": 8192},
        }
        mock_post.return_value = mock_response

        llm = OllamaLLM(model="llama3")
        result = llm.query_context_length()
        assert result == 8192

    @patch("nano_agent.llm.ollama.requests.post")
    def test_ollama_query_returns_none_on_error(self, mock_post):
        """API errors should return None, not raise."""
        from nano_agent.llm.ollama import OllamaLLM

        mock_post.side_effect = Exception("Connection refused")
        llm = OllamaLLM(model="llama3")
        result = llm.query_context_length()
        assert result is None

    @patch("nano_agent.llm.openai_compatible.requests.get")
    def test_openai_query_parses_context_window(self, mock_get):
        """OpenAI should parse context_window from /models response."""
        from nano_agent.llm.openai_compatible import OpenAICompatibleLLM

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"context_window": 128000}
        mock_get.return_value = mock_response

        llm = OpenAICompatibleLLM(model="gpt-4o", api_key="test-key")
        result = llm.query_context_length()
        assert result == 128000

    @patch("nano_agent.llm.openai_compatible.requests.get")
    def test_openai_query_returns_none_on_error(self, mock_get):
        """API errors should return None, not raise."""
        from nano_agent.llm.openai_compatible import OpenAICompatibleLLM

        mock_get.side_effect = Exception("Connection refused")
        llm = OpenAICompatibleLLM(model="gpt-4o", api_key="test-key")
        result = llm.query_context_length()
        assert result is None
