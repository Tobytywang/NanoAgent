"""
Base LLM client interface.
"""

from abc import ABC, abstractmethod
from typing import Generator
from .messages import Message, ToolCall


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
    ) -> tuple[str, list[ToolCall]]:
        """
        Send messages and get a response.

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tool definitions in Ollama format

        Returns:
            Tuple of (text_response, tool_calls)
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
        response, _ = self.chat(messages, tools, **kwargs)
        yield response
