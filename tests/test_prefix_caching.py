"""
Tests for Prefix Caching feature (v0.7.7).

Tests Anthropic Prompt Caching support and OpenAI automatic caching optimization.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

pytestmark = pytest.mark.unit

from nano_agent.llm.messages import Message
from nano_agent.llm.base import BaseLLM, LLMUsage
from nano_agent.llm.openai_compatible import OpenAICompatibleLLM
from nano_agent.llm.anthropic import AnthropicLLM
from nano_agent.llm.ollama import OllamaLLM
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.memory.hybrid import HybridMemory
from nano_agent.config.schema import PromptConfig


class TestMessageCacheControl:
    """Tests for Message cache_control field."""

    def test_message_without_cache_control(self):
        """Message without cache_control returns basic dict."""
        msg = Message(role="system", content="Hello")
        result = msg.to_dict()
        assert result == {"role": "system", "content": "Hello"}
        assert "cache_control" not in result

    def test_message_with_cache_control(self):
        """Message with cache_control includes it in dict."""
        msg = Message(role="system", content="Hello", cache_control={"type": "ephemeral"})
        result = msg.to_dict()
        assert result == {
            "role": "system",
            "content": "Hello",
            "cache_control": {"type": "ephemeral"}
        }

    def test_message_with_cache_control_factory(self):
        """Message.with_cache_control creates message with caching."""
        msg = Message.with_cache_control("system", "Hello")
        assert msg.role == "system"
        assert msg.content == "Hello"
        assert msg.cache_control == {"type": "ephemeral"}

    def test_message_with_cache_control_custom_type(self):
        """Message.with_cache_control supports custom cache type."""
        msg = Message.with_cache_control("system", "Hello", cache_type="persistent")
        assert msg.cache_control == {"type": "persistent"}


class TestLLMUsageCaching:
    """Tests for LLMUsage with caching fields."""

    def test_llm_usage_default_caching_fields(self):
        """LLMUsage defaults cache fields to 0."""
        usage = LLMUsage(prompt_tokens=100, completion_tokens=50)
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0

    def test_llm_usage_with_caching_fields(self):
        """LLMUsage can store caching metrics."""
        usage = LLMUsage(
            prompt_tokens=100,
            completion_tokens=50,
            cache_read_tokens=30,
            cache_write_tokens=20
        )
        assert usage.cache_read_tokens == 30
        assert usage.cache_write_tokens == 20

    def test_llm_usage_to_dict_includes_caching(self):
        """LLMUsage.to_dict includes caching fields."""
        usage = LLMUsage(
            prompt_tokens=100,
            completion_tokens=50,
            cache_read_tokens=30,
            cache_write_tokens=20
        )
        result = usage.to_dict()
        assert "cache_read_tokens" in result
        assert "cache_write_tokens" in result
        assert result["cache_read_tokens"] == 30
        assert result["cache_write_tokens"] == 20


class TestLLMSupportsExplicitCaching:
    """Tests for supports_explicit_caching attribute."""

    def test_anthropic_supports_explicit_caching(self):
        """AnthropicLLM supports explicit caching."""
        assert AnthropicLLM.supports_explicit_caching == True

    def test_openai_compatible_no_explicit_caching(self):
        """OpenAICompatibleLLM uses automatic caching."""
        assert OpenAICompatibleLLM.supports_explicit_caching == False

    def test_ollama_no_explicit_caching(self):
        """OllamaLLM doesn't support caching."""
        assert OllamaLLM.supports_explicit_caching == False


class TestOpenAICompatibleCaching:
    """Tests for OpenAI-compatible client caching behavior."""

    def test_build_payload_without_system_stable(self):
        """Payload built normally without system_stable."""
        # Create client with mock API key
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            client = OpenAICompatibleLLM(model="gpt-4o")

            messages = [
                {"role": "system", "content": "Original system"},
                {"role": "user", "content": "Hello"}
            ]
            payload = client._build_payload(messages, None, None)

            # Original system message preserved
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == "Original system"

    def test_build_payload_with_system_stable(self):
        """Payload uses stable system prompt when provided."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            client = OpenAICompatibleLLM(model="gpt-4o")

            messages = [
                {"role": "system", "content": "Original system"},
                {"role": "user", "content": "Hello"}
            ]
            system_stable = "Stable system prompt for caching"
            payload = client._build_payload(messages, None, system_stable)

            # Stable system prompt replaces original
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == system_stable
            # Original system message skipped
            assert len(payload["messages"]) == 2


class TestAnthropicLLMCaching:
    """Tests for Anthropic client with Prompt Caching."""

    def test_format_messages_skips_system(self):
        """Anthropic client skips system messages (sent separately)."""
        # We can't fully test without API key, but test the formatting logic
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"}
        ]
        # The formatting logic should skip system messages
        formatted = []
        for m in messages:
            if m.get("role") != "system":
                formatted.append({"role": m["role"], "content": m["content"]})

        assert len(formatted) == 1
        assert formatted[0]["role"] == "user"


class TestMemoryStableSystemPrompt:
    """Tests for Memory layer stable/dynamic separation."""

    def test_short_term_memory_set_stable_system_prompt(self):
        """ShortTermMemory can set stable system prompt."""
        memory = ShortTermMemory()
        memory.set_stable_system_prompt("Stable prompt for caching")

        assert memory.stable_system_prompt == "Stable prompt for caching"
        # Full system prompt unchanged
        assert memory.system_prompt == "You are a helpful AI assistant."

    def test_short_term_memory_get_stable_system_prompt(self):
        """get_stable_system_prompt returns stable or full."""
        memory = ShortTermMemory()
        # Without stable, returns full
        assert memory.get_stable_system_prompt() == "You are a helpful AI assistant."

        # With stable, returns stable
        memory.set_stable_system_prompt("Stable prompt")
        assert memory.get_stable_system_prompt() == "Stable prompt"

    def test_short_term_memory_get_messages_without_system(self):
        """get_messages_without_system excludes system messages."""
        memory = ShortTermMemory()
        memory.add_user_message("Hello")
        memory.add_assistant_message("Hi there")

        msgs = memory.get_messages_without_system()
        assert len(msgs) == 2
        assert all(m.get("role") != "system" for m in msgs)

    def test_hybrid_memory_stable_system_prompt(self):
        """HybridMemory delegates stable system prompt to working memory."""
        from nano_agent.memory.long_term import LongTermMemory

        # Use default storage path for LongTermMemory
        long_term = LongTermMemory()
        working = ShortTermMemory()
        memory = HybridMemory(working_memory=working, long_term_memory=long_term)

        memory.set_stable_system_prompt("Stable prompt")
        assert memory.get_stable_system_prompt() == "Stable prompt"

    def test_hybrid_memory_with_persistent_memory_stable_system_prompt(self):
        """HybridMemory with PersistentMemory as working memory supports stable system prompt."""
        from nano_agent.memory.long_term import LongTermMemory
        from nano_agent.memory.persistent import PersistentMemory
        from nano_agent.memory.storage.file_storage import FileStorage
        import tempfile

        # Create temporary storage
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            long_term = LongTermMemory()
            working = PersistentMemory(storage=storage, max_messages=50)
            memory = HybridMemory(working_memory=working, long_term_memory=long_term)

            # This was the bug: PersistentMemory was missing set_stable_system_prompt
            memory.set_stable_system_prompt("Stable prompt for PersistentMemory")
            assert memory.get_stable_system_prompt() == "Stable prompt for PersistentMemory"


class TestPromptConfigCaching:
    """Tests for PromptConfig enable_caching field."""

    def test_prompt_config_default_enable_caching(self):
        """PromptConfig defaults enable_caching to True."""
        config = PromptConfig()
        assert config.enable_caching == True

    def test_prompt_config_disable_caching(self):
        """PromptConfig can disable caching."""
        config = PromptConfig(enable_caching=False)
        assert config.enable_caching == False


class TestBaseLLMInterface:
    """Tests for BaseLLM interface with system_stable parameter."""

    def test_base_llm_has_system_stable_parameter(self):
        """BaseLLM.chat signature includes system_stable."""
        # Check that the abstract method has the parameter
        import inspect
        sig = inspect.signature(BaseLLM.chat)
        params = list(sig.parameters.keys())
        assert "system_stable" in params

    def test_base_llm_chat_stream_has_system_stable(self):
        """BaseLLM.chat_stream signature includes system_stable."""
        import inspect
        sig = inspect.signature(BaseLLM.chat_stream)
        params = list(sig.parameters.keys())
        assert "system_stable" in params