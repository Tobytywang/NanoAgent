"""
Message data structures for LLM communication.
"""

from dataclasses import dataclass, field
from typing import Any, Literal
import json


@dataclass
class Message:
    """Base message class."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    cache_control: dict | None = None  # For Anthropic Prompt Caching

    def to_dict(self) -> dict:
        """Convert to dictionary for API calls."""
        result = {"role": self.role, "content": self.content}
        if self.cache_control:
            result["cache_control"] = self.cache_control
        return result

    @classmethod
    def with_cache_control(
        cls,
        role: Literal["system", "user", "assistant", "tool"],
        content: str,
        cache_type: str = "ephemeral",
    ) -> "Message":
        """Create a message with cache_control for Anthropic Prompt Caching.

        Args:
            role: Message role
            content: Message content
            cache_type: Cache type, default "ephemeral" for Anthropic

        Returns:
            Message with cache_control set
        """
        return cls(role=role, content=content, cache_control={"type": cache_type})


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
            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError as e:
                # Provide diagnostic information for debugging
                preview = args_str[:100] + "..." if len(args_str) > 100 else args_str
                raise ValueError(
                    f"Failed to parse tool call arguments as JSON: {e}\n"
                    f"Tool: {func.get('name', 'unknown')}\n"
                    f"Arguments preview: {preview}\n"
                    f"This usually indicates the LLM response was truncated or malformed."
                ) from e
        else:
            arguments = args_str
        return cls(
            id=data.get("id", ""), name=func.get("name", ""), arguments=arguments
        )

    @classmethod
    def from_openai_format(cls, data: dict) -> "ToolCall":
        """Parse from OpenAI API response format."""
        func = data.get("function", {})
        args_str = func.get("arguments", "{}")
        # OpenAI format: arguments is always a JSON string
        if isinstance(args_str, str):
            # Sanitize to remove invalid Unicode characters
            try:
                args_str = args_str.encode("utf-8", errors="replace").decode("utf-8")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError as e:
                # Provide diagnostic information for debugging
                preview = args_str[:100] + "..." if len(args_str) > 100 else args_str
                raise ValueError(
                    f"Failed to parse tool call arguments as JSON: {e}\n"
                    f"Tool: {func.get('name', 'unknown')}\n"
                    f"Arguments preview: {preview}\n"
                    f"This usually indicates the LLM response was truncated or malformed."
                ) from e
        else:
            arguments = args_str
        return cls(
            id=data.get("id", ""), name=func.get("name", ""), arguments=arguments
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments)},
        }

    def to_ollama_dict(self) -> dict:
        """Convert to dictionary for Ollama API (arguments as dict, not JSON string)."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,  # Ollama expects dict, not JSON string
            },
        }


@dataclass
class StreamChunk:
    """A single chunk from a streaming LLM response.

    Unlike chat_stream() which only yields text, StreamChunk carries
    structured data including tool calls and usage information.
    """

    text: str = ""  # Incremental text content
    tool_call: ToolCall | None = None  # Complete tool call (when is_tool_call_complete)
    is_tool_call_complete: bool = False  # True when tool call fully received
    usage: Any | None = None  # LLMUsage (usually on final chunk)


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
            "tool_call_id": self.tool_call_id,
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
