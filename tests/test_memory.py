"""
Tests for memory system.
"""

import pytest
from nano_agent.memory.base import BaseMemory
from nano_agent.memory.short_term import ShortTermMemory


class TestShortTermMemory:
    """Test ShortTermMemory class."""

    def test_initialization(self):
        """Test memory initialization with system prompt."""
        memory = ShortTermMemory()
        messages = memory.get_all()
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

    def test_custom_system_prompt(self):
        """Test custom system prompt."""
        memory = ShortTermMemory(system_prompt="Custom prompt")
        messages = memory.get_all()
        assert messages[0]["content"] == "Custom prompt"

    def test_add_user_message(self):
        """Test adding user message."""
        memory = ShortTermMemory()
        memory.add_user_message("Hello")
        messages = memory.get_all()
        assert len(messages) == 2
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_add_assistant_message(self):
        """Test adding assistant message."""
        memory = ShortTermMemory()
        memory.add_assistant_message("Hi there!")
        messages = memory.get_all()
        assert len(messages) == 2
        assert messages[1]["role"] == "assistant"

    def test_add_assistant_message_with_tool_calls(self):
        """Test adding assistant message with tool calls."""
        memory = ShortTermMemory()
        memory.add_assistant_message(
            "Let me check",
            tool_calls=[{"id": "1", "function": {"name": "test"}}]
        )
        messages = memory.get_all()
        assert "tool_calls" in messages[1]

    def test_add_tool_result(self):
        """Test adding tool result."""
        memory = ShortTermMemory()
        memory.add_tool_result("call_123", "Result content")
        messages = memory.get_all()
        assert messages[1]["role"] == "tool"
        assert messages[1]["tool_call_id"] == "call_123"

    def test_clear(self):
        """Test clearing memory."""
        memory = ShortTermMemory()
        memory.add_user_message("Hello")
        memory.add_assistant_message("Hi")
        memory.clear()
        messages = memory.get_all()
        assert len(messages) == 1  # Only system message remains

    def test_max_messages_limit(self):
        """Test max messages limit."""
        memory = ShortTermMemory(max_messages=5)
        # Add more messages than limit
        for i in range(10):
            memory.add_user_message(f"Message {i}")

        messages = memory.get_all()
        # Should have system + 4 recent messages = 5 total
        assert len(messages) == 5
        # System message should be preserved
        assert messages[0]["role"] == "system"
        # Most recent messages should be preserved
        assert "Message 9" in messages[-1]["content"]

    def test_set_system_prompt(self):
        """Test updating system prompt."""
        memory = ShortTermMemory()
        memory.set_system_prompt("New prompt")
        messages = memory.get_all()
        assert messages[0]["content"] == "New prompt"

    def test_get_context_with_limit(self):
        """Test getting context with limit."""
        memory = ShortTermMemory()
        for i in range(10):
            memory.add_user_message(f"Msg {i}")

        context = memory.get_context(max_messages=3)
        assert len(context) == 3
        assert context[0]["role"] == "system"

    def test_len(self):
        """Test __len__ method."""
        memory = ShortTermMemory()
        assert len(memory) == 1
        memory.add_user_message("Hello")
        assert len(memory) == 2