"""
Tests for LLM message data structures.
"""

import pytest

pytestmark = pytest.mark.unit
from nano_agent.llm.messages import (
    Message,
    ToolCall,
    AssistantMessage,
    ToolResultMessage,
    SystemMessage,
    UserMessage,
)


class TestMessage:
    """Test base Message class."""

    def test_message_to_dict(self):
        """Test message conversion to dictionary."""
        msg = Message(role="user", content="Hello")
        result = msg.to_dict()
        assert result == {"role": "user", "content": "Hello"}

    def test_system_message(self):
        """Test system message."""
        msg = SystemMessage(content="You are an assistant")
        assert msg.role == "system"
        assert msg.content == "You are an assistant"

    def test_user_message(self):
        """Test user message."""
        msg = UserMessage(content="Hi there")
        assert msg.role == "user"
        assert msg.content == "Hi there"


class TestToolCall:
    """Test ToolCall class."""

    def test_from_ollama_format_string_args(self):
        """Test parsing from Ollama format with string arguments."""
        data = {
            "id": "call_123",
            "function": {
                "name": "python_execute",
                "arguments": '{"code": "print(1+1)"}',
            },
        }
        tc = ToolCall.from_ollama_format(data)
        assert tc.id == "call_123"
        assert tc.name == "python_execute"
        assert tc.arguments == {"code": "print(1+1)"}

    def test_from_ollama_format_dict_args(self):
        """Test parsing from Ollama format with dict arguments."""
        data = {
            "id": "call_456",
            "function": {
                "name": "file_read",
                "arguments": {"file_path": "/tmp/test.txt"},
            },
        }
        tc = ToolCall.from_ollama_format(data)
        assert tc.id == "call_456"
        assert tc.name == "file_read"
        assert tc.arguments == {"file_path": "/tmp/test.txt"}

    def test_to_dict(self):
        """Test converting ToolCall to dictionary."""
        tc = ToolCall(id="call_789", name="test_tool", arguments={"arg": "value"})
        result = tc.to_dict()
        assert result["id"] == "call_789"
        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["arguments"] == '{"arg": "value"}'


class TestAssistantMessage:
    """Test AssistantMessage class."""

    def test_without_tool_calls(self):
        """Test assistant message without tool calls."""
        msg = AssistantMessage(content="Hello!")
        result = msg.to_dict()
        assert result == {"role": "assistant", "content": "Hello!"}
        assert "tool_calls" not in result

    def test_with_tool_calls(self):
        """Test assistant message with tool calls."""
        tc = ToolCall(id="call_1", name="test", arguments={"x": 1})
        msg = AssistantMessage(content="", tool_calls=[tc])
        result = msg.to_dict()
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1


class TestToolResultMessage:
    """Test ToolResultMessage class."""

    def test_to_dict(self):
        """Test tool result message conversion."""
        msg = ToolResultMessage(content="Result output", tool_call_id="call_123")
        result = msg.to_dict()
        assert result["role"] == "tool"
        assert result["content"] == "Result output"
        assert result["tool_call_id"] == "call_123"
