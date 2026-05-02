
"""
Tests for OpenAI Compatible LLM client.
"""

import json
import pytest
from unittest.mock import patch, Mock

from nano_agent.llm.openai_compatible import OpenAICompatibleLLM
from nano_agent.llm.messages import ToolCall


class TestOpenAICompatibleLLM:
    """Tests for OpenAICompatibleLLM."""

    def test_init_with_api_key(self):
        """Test initialization with direct API key."""
        llm = OpenAICompatibleLLM(
            model="gpt-4o",
            api_key="test-key"
        )
        assert llm.api_key == "test-key"
        assert llm.model == "gpt-4o"

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization with environment variable."""
        monkeypatch.setenv("TEST_API_KEY", "env-test-key")
        llm = OpenAICompatibleLLM(
            model="gpt-4o",
            api_key_env="TEST_API_KEY"
        )
        assert llm.api_key == "env-test-key"

    def test_init_api_key_priority_over_env(self, monkeypatch):
        """Test that direct API key takes priority over environment variable."""
        monkeypatch.setenv("TEST_API_KEY", "env-test-key")
        llm = OpenAICompatibleLLM(
            model="gpt-4o",
            api_key="direct-key",
            api_key_env="TEST_API_KEY"
        )
        assert llm.api_key == "direct-key"

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="API key not found"):
            OpenAICompatibleLLM(
                model="gpt-4o",
                api_key_env="NONEXISTENT_KEY"
            )

    def test_custom_base_url(self):
        """Test custom base URL configuration."""
        llm = OpenAICompatibleLLM(
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key="test-key"
        )
        assert llm.base_url == "https://api.deepseek.com/v1"
        assert llm.api_url == "https://api.deepseek.com/v1/chat/completions"

    @patch('requests.post')
    def test_chat_simple(self, mock_post):
        """Test simple chat without tools."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Hello! How can I help you?"}
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        }
        mock_post.return_value = mock_response

        llm = OpenAICompatibleLLM(model="gpt-4o", api_key="test")
        content, tool_calls, usage = llm.chat([{"role": "user", "content": "Hi"}])

        assert content == "Hello! How can I help you?"
        assert tool_calls == []
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30

        # Verify request
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "gpt-4o"
        assert call_args[1]["json"]["messages"] == [{"role": "user", "content": "Hi"}]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test"

    @patch('requests.post')
    def test_chat_with_tool_calls(self, mock_post):
        """Test chat with tool calls."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "Beijing"}'
                        }
                    }]
                }
            }],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}
        }
        mock_post.return_value = mock_response

        llm = OpenAICompatibleLLM(model="gpt-4o", api_key="test")
        content, tool_calls, usage = llm.chat([{"role": "user", "content": "Weather?"}])

        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_123"
        assert tool_calls[0].name == "get_weather"
        assert tool_calls[0].arguments == {"location": "Beijing"}
        assert usage.total_tokens == 40

    @patch('requests.post')
    def test_chat_with_tools_parameter(self, mock_post):
        """Test chat with tools parameter passed."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Let me check that."}
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}
        }
        mock_post.return_value = mock_response

        tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {}
            }
        }]

        llm = OpenAICompatibleLLM(model="gpt-4o", api_key="test")
        content, tool_calls, usage = llm.chat([{"role": "user", "content": "Test"}], tools=tools)

        call_args = mock_post.call_args
        assert "tools" in call_args[1]["json"]
        assert call_args[1]["json"]["tools"] == tools

    @patch('requests.post')
    def test_temperature_in_payload(self, mock_post):
        """Test that temperature is included in request payload."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        }
        mock_post.return_value = mock_response

        llm = OpenAICompatibleLLM(model="gpt-4o", api_key="test", temperature=0.5)
        llm.chat([{"role": "user", "content": "Hi"}])

        call_args = mock_post.call_args
        assert call_args[1]["json"]["temperature"] == 0.5


class TestToolCallFromOpenAIFormat:
    """Tests for ToolCall.from_openai_format method."""

    def test_parse_basic_tool_call(self):
        """Test parsing basic tool call."""
        data = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "search",
                "arguments": '{"query": "test"}'
            }
        }
        tool_call = ToolCall.from_openai_format(data)

        assert tool_call.id == "call_abc123"
        assert tool_call.name == "search"
        assert tool_call.arguments == {"query": "test"}

    def test_parse_empty_arguments(self):
        """Test parsing tool call with empty arguments."""
        data = {
            "id": "call_xyz",
            "type": "function",
            "function": {
                "name": "noop",
                "arguments": '{}'
            }
        }
        tool_call = ToolCall.from_openai_format(data)

        assert tool_call.arguments == {}

    def test_parse_dict_arguments(self):
        """Test parsing tool call with dict arguments (non-standard but handle it)."""
        data = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "test",
                "arguments": {"key": "value"}  # Already a dict
            }
        }
        tool_call = ToolCall.from_openai_format(data)

        assert tool_call.arguments == {"key": "value"}


class TestCreateLLM:
    """Tests for create_llm factory function."""

    def test_create_ollama_llm(self):
        """Test creating Ollama LLM."""
        from nano_agent.llm import create_llm, OllamaLLM

        llm = create_llm(provider="ollama", model="llama3")
        assert isinstance(llm, OllamaLLM)

    def test_create_openai_llm(self):
        """Test creating OpenAI-compatible LLM."""
        from nano_agent.llm import create_llm, OpenAICompatibleLLM

        llm = create_llm(provider="openai", api_key="test-key")
        assert isinstance(llm, OpenAICompatibleLLM)
        assert llm.api_key == "test-key"

    def test_create_deepseek_llm(self):
        """Test creating DeepSeek LLM with default settings."""
        from nano_agent.llm import create_llm, OpenAICompatibleLLM

        llm = create_llm(provider="deepseek", api_key="test-key")
        assert isinstance(llm, OpenAICompatibleLLM)
        assert llm.base_url == "https://api.deepseek.com/v1"

    def test_create_llm_unsupported_provider(self):
        """Test creating LLM with unsupported provider raises error."""
        from nano_agent.llm import create_llm

        with pytest.raises(ValueError, match="Unsupported provider"):
            create_llm(provider="unknown_provider")

    def test_create_llm_from_config(self):
        """Test creating LLM from config object."""
        from nano_agent.llm import create_llm_from_config
        from nano_agent.config.schema import LLMConfig

        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key"
        )
        llm = create_llm_from_config(config)

        assert llm.model == "gpt-4o"
        assert llm.api_key == "test-key"
