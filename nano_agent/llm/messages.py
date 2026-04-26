"""
Message data structures for LLM communication.
"""

from dataclasses import dataclass, field
from typing import Literal
import json


@dataclass
class Message:
    """Base message class."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for API calls."""
        return {"role": self.role, "content": self.content}


@dataclass
class ToolCall:
    """Tool call request from the LLM."""
    id: str
    name: str
    arguments: dict  # Parsed JSON arguments

    @classmethod
    def from_ollama_format(cls, data: dict) -> "ToolCall":
        """Parse from Ollama API response format."""
        func = data.get("function", {})
        args_str = func.get("arguments", "{}")
        # Handle both string and dict formats
        if isinstance(args_str, str):
            arguments = json.loads(args_str)
        else:
            arguments = args_str
        return cls(
            id=data.get("id", ""),
            name=func.get("name", ""),
            arguments=arguments
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments)
            }
        }


@dataclass
class AssistantMessage(Message):
    """Assistant message, may contain tool calls."""
    content: str = ""
    role: Literal["assistant"] = "assistant"
    tool_calls: list[ToolCall] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {"role": self.role, "content": self.content}
        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        return result


@dataclass
class ToolResultMessage(Message):
    """Tool execution result message."""
    content: str = ""
    role: Literal["tool"] = "tool"
    tool_call_id: str = ""

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "tool_call_id": self.tool_call_id
        }


@dataclass
class SystemMessage(Message):
    """System message for setting context."""
    content: str = ""
    role: Literal["system"] = "system"


@dataclass
class UserMessage(Message):
    """User message."""
    content: str = ""
    role: Literal["user"] = "user"
