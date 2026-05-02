"""
Base LLM client interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator
from .messages import Message, ToolCall


@dataclass
class LLMUsage:
    """LLM token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class BaseLLM(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def __init__(self, model: str, base_url: str, **kwargs):
        """Initialize the LLM client."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> tuple[str, list[ToolCall], LLMUsage]:
        """
        Send messages and get a response.

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tool definitions in Ollama format

        Returns:
            Tuple of (text_response, tool_calls, usage)
        """
        pass

    def chat_stream(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Stream the response (optional implementation).

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tool definitions

        Yields:
            Text chunks from the response
        """
        # Default implementation: just return the full response
        response, _, _ = self.chat(messages, tools, **kwargs)
        yield response
