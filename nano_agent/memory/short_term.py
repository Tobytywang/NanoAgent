"""
Short-term memory implementation - conversation history management.
"""

from dataclasses import dataclass, field
from typing import Literal
from .base import BaseMemory


@dataclass
class ShortTermMemory(BaseMemory):
    """Short-term memory: conversation history management."""

    max_messages: int = 50  # Maximum number of messages to keep
    system_prompt: str = "You are a helpful AI assistant."
    _messages: list = field(default_factory=list)

    def __post_init__(self):
        """Initialize with system message."""
        if not self._messages:
            self._messages = [{"role": "system", "content": self.system_prompt}]

    def add(self, message: dict) -> None:
        """Add a message to history."""
        self._messages.append(message)
        self._trim_if_needed()

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.add({"role": "user", "content": content})

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list | None = None
    ) -> None:
        """Add an assistant message, optionally with tool calls."""
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.add(msg)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool execution result."""
        self.add({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })

    def get_all(self) -> list:
        """Get all messages."""
        return self._messages.copy()

    def clear(self) -> None:
        """Clear history (keep system message)."""
        self._messages = [{"role": "system", "content": self.system_prompt}]

    def get_context(self, max_messages: int | None = None) -> list:
        """Get context, optionally limited to max_messages."""
        if max_messages is None:
            return self.get_all()

        # Always keep system message
        if len(self._messages) <= max_messages:
            return self.get_all()

        system_msg = self._messages[0]
        recent = self._messages[-(max_messages - 1):]
        return [system_msg] + recent

    def _trim_if_needed(self) -> None:
        """Trim old messages if exceeding limit."""
        if len(self._messages) > self.max_messages:
            # Keep system message and recent messages
            system_msg = self._messages[0]
            recent = self._messages[-(self.max_messages - 1):]
            self._messages = [system_msg] + recent

    def set_system_prompt(self, prompt: str) -> None:
        """Set or update the system prompt."""
        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = prompt
        else:
            self._messages.insert(0, {"role": "system", "content": prompt})

    def __len__(self) -> int:
        """Return number of messages."""
        return len(self._messages)