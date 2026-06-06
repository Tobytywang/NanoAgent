"""
Base LLM client interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generator
from .messages import Message, ToolCall


@dataclass
class LLMUsage:
    """LLM token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Anthropic Prompt Caching specific fields
    cache_read_tokens: int = 0  # Tokens read from cache (saved)
    cache_write_tokens: int = 0  # Tokens written to cache

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
        }


class BaseLLM(ABC):
    """Abstract base class for LLM clients."""

    # Whether this LLM supports explicit cache_control (Anthropic)
    supports_explicit_caching: bool = False

    # Retry configuration (set by AgentBuilder)
    _retry_config: "RetryConfig | None" = None
    _on_retry_callback: "Callable[[dict], None] | None" = None

    @abstractmethod
    def __init__(self, model: str, base_url: str, **kwargs):
        """Initialize the LLM client."""
        pass

    def query_context_length(self) -> int | None:
        """Query the model's actual context length from the API.

        Returns:
            Context length in tokens, or None if query failed/unavailable.
        """
        return None

    @abstractmethod
    def _chat_impl(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs,
    ) -> tuple[str, list[ToolCall], LLMUsage]:
        """Subclass implementation of chat (no retry wrapper).

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tool definitions in Ollama format
            system_stable: Stable portion of system prompt for prefix caching

        Returns:
            Tuple of (text_response, tool_calls, usage)
        """
        pass

    def chat(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs,
    ) -> tuple[str, list[ToolCall], LLMUsage]:
        """Send messages and get a response, with automatic retry on transient errors.

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tool definitions in Ollama format
            system_stable: Stable portion of system prompt for prefix caching
                - Anthropic: Will be sent with cache_control: {"type": "ephemeral"}
                - OpenAI/DeepSeek: Will replace system message for prefix stability

        Returns:
            Tuple of (text_response, tool_calls, usage)
        """
        if self._retry_config is None or not self._retry_config.enabled:
            return self._chat_impl(messages, tools, system_stable, **kwargs)

        from .retry import with_retry

        return with_retry(
            lambda: self._chat_impl(messages, tools, system_stable, **kwargs),
            config=self._retry_config,
            on_retry=self._on_retry_callback,
        )

    def chat_stream(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream the response (optional implementation).

        Args:
            messages: List of messages in the conversation
            tools: Optional list of tool definitions
            system_stable: Stable portion of system prompt for prefix caching

        Yields:
            Text chunks from the response
        """
        # Default implementation: just return the full response
        response, _, _ = self.chat(
            messages, tools, system_stable=system_stable, **kwargs
        )
        yield response
