"""
OpenAI Compatible LLM client implementation.

Supports OpenAI, DeepSeek, Moonshot, and other OpenAI-compatible APIs.
"""

import os
import json
from typing import Generator

import requests

from .base import BaseLLM, LLMUsage
from .messages import Message, ToolCall


class OpenAICompatibleLLM(BaseLLM):
    """OpenAI-compatible LLM client."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    supports_explicit_caching = False  # OpenAI uses automatic caching

    def __init__(
        self,
        model: str = "gpt-4o",
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        timeout: int = 120,
        temperature: float = 0.7,
        **kwargs,
    ):
        """
        Initialize OpenAI-compatible client.

        Args:
            model: Model name (e.g., "gpt-4o", "deepseek-chat", "moonshot-v1-8k")
            base_url: API base URL (e.g., "https://api.openai.com/v1")
            api_key: API key directly provided (optional)
            api_key_env: Environment variable name for API key
            timeout: Request timeout in seconds
            temperature: Sampling temperature
            **kwargs: Additional parameters passed to the API
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.extra_params = kwargs

        # API Key handling: direct value > environment variable
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.environ.get(api_key_env)
            if not self.api_key:
                raise ValueError(
                    f"API key not found. Please set {api_key_env} environment variable "
                    f"or provide api_key parameter."
                )

        self.api_url = f"{self.base_url}/chat/completions"

    def _build_payload(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
    ) -> dict:
        """Build the request payload in OpenAI format.

        Args:
            messages: List of messages
            tools: Optional tool definitions
            system_stable: Stable system prompt for prefix caching
                When provided, replaces the original system message to ensure
                prefix stability for OpenAI's automatic caching.

        Returns:
            Request payload dict
        """
        formatted_messages = []

        if system_stable:
            # Use stable system prompt for prefix caching
            formatted_messages.append({"role": "system", "content": system_stable})
            # Skip original system message, add other messages
            for m in messages:
                if isinstance(m, dict):
                    if m.get("role") != "system":
                        formatted_messages.append(m)
                else:
                    if m.role != "system":
                        formatted_messages.append(m.to_dict())
        else:
            # Normal message formatting
            for m in messages:
                if isinstance(m, dict):
                    formatted_messages.append(m)
                else:
                    formatted_messages.append(m.to_dict())

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": self.temperature,
            **self.extra_params,
        }

        if tools:
            payload["tools"] = tools

        return payload

    def _get_headers(self) -> dict:
        """Get request headers with authorization."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def query_context_length(self) -> int | None:
        """Query the model's context window from OpenAI-compatible /models endpoint."""
        try:
            import requests

            base_url = self.base_url.rstrip("/")
            url = f"{base_url}/models/{self.model}"
            headers = self._get_headers()
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # OpenAI format: data.context_window or data.metadata.context_window
                context_window = data.get("context_window")
                if context_window is not None:
                    return int(context_window)
                # Some providers nest it in metadata
                metadata = data.get("metadata", {})
                if isinstance(metadata, dict):
                    context_window = metadata.get("context_window")
                    if context_window is not None:
                        return int(context_window)
        except Exception:
            pass
        return None

    def _chat_impl(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs,
    ) -> tuple[str, list[ToolCall], LLMUsage]:
        """
        Call OpenAI-compatible API and get a response.

        Args:
            messages: List of messages
            tools: Optional tool definitions in OpenAI format
            system_stable: Stable system prompt for prefix caching
                OpenAI automatically caches prefixes >= 1024 tokens.
                Providing stable system prompt ensures prefix consistency.

        Returns:
            Tuple of (text_response, tool_calls, usage)
        """
        payload = self._build_payload(messages, tools, system_stable)

        response = requests.post(
            self.api_url,
            json=payload,
            timeout=self.timeout,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        data = response.json()

        # Parse OpenAI response format
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""

        # Sanitize content to remove invalid Unicode characters (surrogates)
        if content:
            try:
                content = content.encode("utf-8", errors="replace").decode("utf-8")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass

        # Parse tool calls
        tool_calls = []
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                tool_calls.append(ToolCall.from_openai_format(tc))

        # Parse usage information
        usage_data = data.get("usage", {})
        usage = LLMUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return content, tool_calls, usage

    def chat_stream(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream the response from OpenAI-compatible API.

        Args:
            messages: List of messages
            tools: Optional tool definitions
            system_stable: Stable system prompt for prefix caching

        Yields:
            Text chunks from the response
        """
        self._apply_rate_limit()
        payload = self._build_payload(messages, tools, system_stable)
        payload["stream"] = True

        with requests.post(
            self.api_url,
            json=payload,
            timeout=self.timeout,
            stream=True,
            headers=self._get_headers(),
        ) as response:
            response.raise_for_status()
            # Use errors='replace' to handle malformed UTF-8 sequences
            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8", errors="replace")
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
