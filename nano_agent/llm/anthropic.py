"""
Anthropic Claude LLM client implementation with Prompt Caching support.

Supports Anthropic's Prompt Caching feature via cache_control parameter.
"""

import os
from typing import AsyncGenerator, Generator

from .base import BaseLLM, LLMUsage
from .messages import Message, StreamChunk, ToolCall


class AnthropicLLM(BaseLLM):
    """Anthropic Claude LLM client with Prompt Caching support."""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    supports_explicit_caching = True  # Anthropic supports explicit cache_control

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        timeout: int = 120,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ):
        """
        Initialize Anthropic client.

        Args:
            model: Model name (e.g., "claude-sonnet-4-20250514", "claude-3-opus-20240229")
            api_key: API key directly provided (optional)
            api_key_env: Environment variable name for API key
            timeout: Request timeout in seconds
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters passed to the API
        """
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
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

        # Lazy import to avoid dependency issues
        try:
            from anthropic import Anthropic

            self._client = Anthropic(
                api_key=self.api_key, timeout=timeout, max_retries=0
            )
        except ImportError:
            raise ImportError(
                "anthropic package is required for AnthropicLLM. "
                "Install it with: pip install anthropic"
            )

        # Async client (lazy, created on first use)
        self._async_client = None

    def _format_messages(self, messages: list[Message] | list[dict]) -> list[dict]:
        """Format messages for Anthropic API (skip system messages).

        Args:
            messages: List of messages

        Returns:
            List of formatted messages (without system messages)
        """
        formatted = []
        for m in messages:
            if isinstance(m, dict):
                if m.get("role") != "system":
                    formatted.append({"role": m["role"], "content": m["content"]})
            else:
                if m.role != "system":
                    formatted.append({"role": m.role, "content": m.content})
        return formatted

    def _format_tools(
        self, tools: list[dict] | None, cache_tools: bool = True
    ) -> list[dict] | None:
        """Format tools for Anthropic API with optional caching.

        Args:
            tools: Tool definitions in OpenAI format
            cache_tools: Whether to add cache_control to tool definitions

        Returns:
            Tools in Anthropic format with optional cache_control
        """
        if not tools:
            return None

        formatted_tools = []
        for i, tool in enumerate(tools):
            if tool.get("type") == "function":
                func = tool.get("function", {})
                tool_def = {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                }
                # Add cache_control to the last tool for caching all tools
                # Anthropic caches from the start up to and including the block with cache_control
                if cache_tools and i == len(tools) - 1:
                    tool_def["cache_control"] = {"type": "ephemeral"}
                formatted_tools.append(tool_def)
        return formatted_tools if formatted_tools else None

    def _parse_tool_calls(self, content_blocks: list) -> list[ToolCall]:
        """Parse tool calls from Anthropic response.

        Args:
            content_blocks: Content blocks from Anthropic response

        Returns:
            List of ToolCall objects
        """
        tool_calls = []
        for block in content_blocks:
            if hasattr(block, "type") and block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if hasattr(block, "input") else {},
                    )
                )
        return tool_calls

    def _chat_impl(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        cache_tools: bool = True,
        **kwargs,
    ) -> tuple[str, list[ToolCall], LLMUsage]:
        """
        Call Anthropic API and get a response.

        Args:
            messages: List of messages
            tools: Optional tool definitions in OpenAI format
            system_stable: Stable system prompt for Prompt Caching
                When provided, will be sent with cache_control: {"type": "ephemeral"}
                to enable Anthropic's Prompt Caching feature.
            cache_tools: Whether to cache tool definitions (default: True)
                When True, adds cache_control to the last tool definition.

        Returns:
            Tuple of (text_response, tool_calls, usage)
        """
        # Build system prompt with caching
        system_content = None
        if system_stable:
            # Use cache_control for stable system prompt
            system_content = [
                {
                    "type": "text",
                    "text": system_stable,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        # Format messages (skip system messages)
        formatted_messages = self._format_messages(messages)

        # Format tools with caching
        formatted_tools = self._format_tools(tools, cache_tools=cache_tools)

        # Build request params
        request_params = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
        }

        if system_content:
            request_params["system"] = system_content

        if formatted_tools:
            request_params["tools"] = formatted_tools

        # Add extra params (temperature, etc.)
        if self.temperature != 1.0:
            request_params["temperature"] = self.temperature

        request_params.update(self.extra_params)

        # Call Anthropic API
        response = self._client.messages.create(**request_params)

        # Parse response
        text = ""
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                text += block.text

        # Parse tool calls
        tool_calls = self._parse_tool_calls(response.content)

        # Parse usage with caching info
        usage = LLMUsage(
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            # Anthropic Prompt Caching specific fields
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0)
            or 0,
            cache_write_tokens=getattr(response.usage, "cache_write_input_tokens", 0)
            or 0,
        )

        return text, tool_calls, usage

    def chat_stream(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        cache_tools: bool = True,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream the response from Anthropic API.

        Args:
            messages: List of messages
            tools: Optional tool definitions
            system_stable: Stable system prompt for Prompt Caching
            cache_tools: Whether to cache tool definitions (default: True)

        Yields:
            Text chunks from the response
        """
        self._apply_rate_limit()
        request_params = self._build_stream_request_params(
            messages, tools, system_stable, cache_tools
        )

        # Stream response
        with self._client.messages.stream(**request_params) as stream:
            for text in stream.text_stream:
                yield text

    def _get_async_client(self):
        """Get or create the async Anthropic client."""
        if self._async_client is None:
            try:
                from anthropic import AsyncAnthropic

                self._async_client = AsyncAnthropic(
                    api_key=self.api_key, timeout=self.timeout, max_retries=0
                )
            except ImportError:
                raise ImportError(
                    "anthropic package is required for async streaming. "
                    "Install it with: pip install anthropic"
                )
        return self._async_client

    def _build_stream_request_params(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        cache_tools: bool = True,
    ) -> dict:
        """Build request params for streaming (shared by sync and async)."""
        system_content = None
        if system_stable:
            system_content = [
                {
                    "type": "text",
                    "text": system_stable,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        formatted_messages = self._format_messages(messages)
        formatted_tools = self._format_tools(tools, cache_tools=cache_tools)

        request_params = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
        }

        if system_content:
            request_params["system"] = system_content

        if formatted_tools:
            request_params["tools"] = formatted_tools

        if self.temperature != 1.0:
            request_params["temperature"] = self.temperature

        request_params.update(self.extra_params)
        return request_params

    async def _chat_stream_async_impl(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Async streaming chat with Anthropic API.

        Anthropic streams events: content_block_start → content_block_delta → content_block_stop.
        Tool call arguments arrive incrementally; emitted when block completes.
        Usage data arrives in message_delta event.
        """
        import json

        request_params = self._build_stream_request_params(
            messages, tools, system_stable
        )
        client = self._get_async_client()

        # Buffer for partial tool calls (keyed by content block id)
        partial_tool_calls: dict[str, dict] = {}
        current_tool_id = None
        prompt_tokens = 0

        async with client.messages.stream(**request_params) as stream:
            async for event in stream:
                if event.type == "message_start":
                    # Capture input_tokens from message_start
                    if hasattr(event, "message") and hasattr(event.message, "usage"):
                        prompt_tokens = getattr(event.message.usage, "input_tokens", 0)

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield StreamChunk(text=event.delta.text)
                    elif event.delta.type == "input_json_delta":
                        # Tool call arguments arriving incrementally
                        if current_tool_id and current_tool_id in partial_tool_calls:
                            partial_tool_calls[current_tool_id][
                                "arguments_parts"
                            ].append(event.delta.partial_json)

                elif event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        partial_tool_calls[current_tool_id] = {
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "arguments_parts": [],
                        }

                elif event.type == "content_block_stop":
                    if current_tool_id and current_tool_id in partial_tool_calls:
                        tc = partial_tool_calls.pop(current_tool_id)
                        args_str = "".join(tc["arguments_parts"])
                        try:
                            args = json.loads(args_str) if args_str else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield StreamChunk(
                            tool_call=ToolCall(
                                id=tc["id"], name=tc["name"], arguments=args
                            ),
                            is_tool_call_complete=True,
                        )
                        current_tool_id = None

                elif event.type == "message_delta":
                    # Usage on final delta
                    if hasattr(event, "usage") and event.usage:
                        completion_tokens = getattr(event.usage, "output_tokens", 0)
                        yield StreamChunk(
                            usage=LLMUsage(
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=prompt_tokens + completion_tokens,
                            )
                        )
