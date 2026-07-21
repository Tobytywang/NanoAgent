"""
OpenAI Compatible LLM client implementation.

Supports OpenAI, DeepSeek, Moonshot, and other OpenAI-compatible APIs.
"""

import os
import json
import httpx
from typing import AsyncGenerator, Generator

import requests

from .base import BaseLLM, LLMUsage
from .messages import Message, StreamChunk, ToolCall


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
        messages = list(messages)  # copy so we can modify iteration
        formatted_messages = []

        if system_stable:
            formatted_messages.append({"role": "system", "content": system_stable})

        # DeepSeek reasoning models (deepseek-v4-*) require reasoning_content
        # on assistant messages with tool_calls. Messages from other providers
        # or older sessions lack this field, causing 400 errors.
        # When detected, strip tool_calls and fold following tool results into
        # the assistant's text content to preserve context without triggering
        # DeepSeek's reasoning_content validation.
        i = 0
        while i < len(messages):
            m = messages[i]
            if isinstance(m, dict):
                role = m.get("role", "")
                if system_stable and role == "system":
                    i += 1
                    continue
                if (
                    role == "assistant"
                    and "tool_calls" in m
                    and "reasoning_content" not in m
                ):
                    text = (m.get("content") or "") + "\n"
                    i += 1
                    while i < len(messages):
                        next_m = messages[i]
                        nr = (
                            next_m.get("role")
                            if isinstance(next_m, dict)
                            else getattr(next_m, "role", None)
                        )
                        if nr != "tool":
                            break
                        if isinstance(next_m, dict):
                            text += f"[Tool] {next_m.get('content', '')[:200]}\n"
                        else:
                            text += f"[Tool] {getattr(next_m, 'content', '')[:200]}\n"
                        i += 1
                    formatted_messages.append(
                        {"role": "assistant", "content": text.strip()}
                    )
                    continue
                formatted_messages.append(m)
                i += 1
            else:
                if system_stable and m.role == "system":
                    i += 1
                    continue
                if (
                    m.role == "assistant"
                    and hasattr(m, "tool_calls")
                    and m.tool_calls
                    and not hasattr(m, "reasoning_content")
                ):
                    text = (m.content or "") + "\n"
                    i += 1
                    while i < len(messages):
                        nm = messages[i]
                        nr = (
                            nm.get("role")
                            if isinstance(nm, dict)
                            else (
                                getattr(nm, "role", None)
                                if hasattr(nm, "role")
                                else None
                            )
                        )
                        if nr != "tool":
                            break
                        text += f"[Tool] {nm.get('content', '')[:200] if isinstance(nm, dict) else getattr(nm, 'content', '')[:200]}\n"
                        i += 1
                    formatted_messages.append(
                        {"role": "assistant", "content": text.strip()}
                    )
                    continue
                formatted_messages.append(m.to_dict())
                i += 1

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

    async def _chat_stream_async_impl(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Async streaming chat with OpenAI-compatible API using httpx.

        OpenAI streams SSE lines. Text content arrives incrementally.
        Tool calls arrive incrementally via delta.tool_calls with index;
        arguments are accumulated and emitted when complete.
        """
        payload = self._build_payload(messages, tools, system_stable)
        payload["stream"] = True

        # Buffer for partial tool calls (keyed by index)
        partial_tool_calls: dict[int, dict] = {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self.api_url,
                json=payload,
                headers=self._get_headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    # Handle bytes lines
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})

                    # Incremental text content
                    content = delta.get("content", "")
                    if content:
                        yield StreamChunk(text=content)

                    # Incremental tool calls
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            if idx not in partial_tool_calls:
                                partial_tool_calls[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments_parts": [],
                                }
                            if "id" in tc_delta:
                                partial_tool_calls[idx]["id"] = tc_delta["id"]
                            func = tc_delta.get("function", {})
                            if "name" in func:
                                partial_tool_calls[idx]["name"] = func["name"]
                            if "arguments" in func:
                                partial_tool_calls[idx]["arguments_parts"].append(
                                    func["arguments"]
                                )

                    # Usage (if provided by provider)
                    usage_data = data.get("usage")
                    if usage_data:
                        yield StreamChunk(
                            usage=LLMUsage(
                                prompt_tokens=usage_data.get("prompt_tokens", 0),
                                completion_tokens=usage_data.get(
                                    "completion_tokens", 0
                                ),
                                total_tokens=usage_data.get("total_tokens", 0),
                            )
                        )

        # Emit completed tool calls after stream ends
        for idx in sorted(partial_tool_calls):
            tc = partial_tool_calls[idx]
            if tc["name"]:  # Only emit if we have at least a name
                yield StreamChunk(
                    tool_call=ToolCall.from_openai_format(
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": "".join(tc["arguments_parts"]),
                            },
                        }
                    ),
                    is_tool_call_complete=True,
                )
