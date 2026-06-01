"""
Tests for Tool Definitions Caching in AnthropicLLM.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from nano_agent.llm.anthropic import AnthropicLLM
from nano_agent.llm.base import LLMUsage


class TestToolCaching:
    """Test tool definitions caching functionality."""

    def test_format_tools_with_cache_enabled(self):
        """Test that cache_control is added to the last tool when caching is enabled."""
        llm = AnthropicLLM.__new__(AnthropicLLM)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tool1",
                    "description": "Tool 1",
                    "parameters": {},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tool2",
                    "description": "Tool 2",
                    "parameters": {},
                },
            },
        ]

        result = llm._format_tools(tools, cache_tools=True)

        assert len(result) == 2
        # First tool should NOT have cache_control
        assert "cache_control" not in result[0]
        # Last tool should have cache_control
        assert "cache_control" in result[1]
        assert result[1]["cache_control"] == {"type": "ephemeral"}

    def test_format_tools_with_cache_disabled(self):
        """Test that cache_control is NOT added when caching is disabled."""
        llm = AnthropicLLM.__new__(AnthropicLLM)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tool1",
                    "description": "Tool 1",
                    "parameters": {},
                },
            },
        ]

        result = llm._format_tools(tools, cache_tools=False)

        assert len(result) == 1
        assert "cache_control" not in result[0]

    def test_format_tools_single_tool_gets_cache(self):
        """Test that a single tool gets cache_control when caching is enabled."""
        llm = AnthropicLLM.__new__(AnthropicLLM)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "single_tool",
                    "description": "Single",
                    "parameters": {},
                },
            },
        ]

        result = llm._format_tools(tools, cache_tools=True)

        assert len(result) == 1
        assert "cache_control" in result[0]
        assert result[0]["cache_control"] == {"type": "ephemeral"}

    def test_format_tools_empty_list(self):
        """Test that empty tools list returns None."""
        llm = AnthropicLLM.__new__(AnthropicLLM)

        result = llm._format_tools([], cache_tools=True)

        assert result is None

    def test_format_tools_none_input(self):
        """Test that None tools returns None."""
        llm = AnthropicLLM.__new__(AnthropicLLM)

        result = llm._format_tools(None, cache_tools=True)

        assert result is None

    def test_format_tools_preserves_tool_structure(self):
        """Test that tool structure is preserved correctly."""
        llm = AnthropicLLM.__new__(AnthropicLLM)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "file_read",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"file_path": {"type": "string"}},
                        "required": ["file_path"],
                    },
                },
            }
        ]

        result = llm._format_tools(tools, cache_tools=True)

        assert result[0]["name"] == "file_read"
        assert result[0]["description"] == "Read a file"
        assert result[0]["input_schema"]["type"] == "object"
        assert "file_path" in result[0]["input_schema"]["properties"]

    def test_chat_passes_cache_tools_parameter(self):
        """Test that chat() passes cache_tools parameter to _format_tools."""
        with patch.object(AnthropicLLM, "__init__", lambda self, **kwargs: None):
            llm = AnthropicLLM()
            llm._client = Mock()
            llm.model = "claude-sonnet-4-20250514"
            llm.max_tokens = 4096
            llm.temperature = 0.7
            llm.extra_params = {}

            # Mock the response
            mock_response = Mock()
            mock_response.content = [Mock(type="text", text="Hello")]
            mock_response.usage = Mock()
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_response.usage.cache_read_input_tokens = 0
            mock_response.usage.cache_write_input_tokens = 0
            llm._client.messages.create.return_value = mock_response

            # Spy on _format_tools
            original_format_tools = llm._format_tools
            call_args = []

            def spy_format_tools(tools, cache_tools=True):
                call_args.append((tools, cache_tools))
                return original_format_tools(tools, cache_tools)

            llm._format_tools = spy_format_tools

            # Call chat with cache_tools=False
            llm.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "test",
                            "description": "Test",
                            "parameters": {},
                        },
                    }
                ],
                cache_tools=False,
            )

            # Verify cache_tools was passed correctly
            assert len(call_args) == 1
            assert call_args[0][1] is False


class TestToolCachingIntegration:
    """Integration tests for tool caching with mock Anthropic API."""

    def test_chat_with_tools_caching_creates_correct_request(self):
        """Test that the request to Anthropic API includes cache_control on tools."""
        with patch.object(AnthropicLLM, "__init__", lambda self, **kwargs: None):
            llm = AnthropicLLM()
            llm._client = Mock()
            llm.model = "claude-sonnet-4-20250514"
            llm.max_tokens = 4096
            llm.temperature = 0.7
            llm.extra_params = {}

            # Mock the response
            mock_response = Mock()
            mock_response.content = [Mock(type="text", text="Response")]
            mock_response.usage = Mock()
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_response.usage.cache_read_input_tokens = 200  # Cache hit!
            mock_response.usage.cache_write_input_tokens = 100
            llm._client.messages.create.return_value = mock_response

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "tool1",
                        "description": "Tool 1",
                        "parameters": {},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "tool2",
                        "description": "Tool 2",
                        "parameters": {},
                    },
                },
            ]

            text, tool_calls, usage = llm.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=tools,
                cache_tools=True,
            )

            # Verify the request was made with correct tools
            call_args = llm._client.messages.create.call_args
            request_params = call_args[1]

            assert "tools" in request_params
            assert len(request_params["tools"]) == 2
            # Last tool should have cache_control
            assert "cache_control" in request_params["tools"][1]

            # Verify usage includes cache info
            assert usage.cache_read_tokens == 200
            assert usage.cache_write_tokens == 100


class TestToolCachingDefault:
    """Test that tool caching is enabled by default."""

    def test_format_tools_default_caching(self):
        """Test that caching is enabled by default in _format_tools."""
        llm = AnthropicLLM.__new__(AnthropicLLM)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tool1",
                    "description": "Tool 1",
                    "parameters": {},
                },
            },
        ]

        # Call without cache_tools parameter (should default to True)
        result = llm._format_tools(tools)

        assert "cache_control" in result[0]

    def test_chat_default_caching(self):
        """Test that chat() defaults to caching tools."""
        with patch.object(AnthropicLLM, "__init__", lambda self, **kwargs: None):
            llm = AnthropicLLM()
            llm._client = Mock()
            llm.model = "claude-sonnet-4-20250514"
            llm.max_tokens = 4096
            llm.temperature = 0.7
            llm.extra_params = {}

            mock_response = Mock()
            mock_response.content = [Mock(type="text", text="Response")]
            mock_response.usage = Mock()
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_response.usage.cache_read_input_tokens = 0
            mock_response.usage.cache_write_input_tokens = 0
            llm._client.messages.create.return_value = mock_response

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "tool1",
                        "description": "Tool 1",
                        "parameters": {},
                    },
                },
            ]

            # Call chat without cache_tools parameter
            llm.chat(messages=[{"role": "user", "content": "Hi"}], tools=tools)

            # Verify cache_control was added (default behavior)
            call_args = llm._client.messages.create.call_args
            request_params = call_args[1]
            assert "cache_control" in request_params["tools"][0]
