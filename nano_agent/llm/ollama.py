"""
Ollama LLM client implementation.
"""

import requests
import json
from typing import Generator
from .base import BaseLLM, LLMUsage
from .messages import Message, ToolCall
from ..monitoring.logger import get_logger


class OllamaLLM(BaseLLM):
    """Ollama LLM client."""

    DEFAULT_BASE_URL = "http://localhost:11434"
    supports_explicit_caching = False  # Ollama doesn't support prefix caching

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 120,
        **kwargs
    ):
        """
        Initialize Ollama client.

        Args:
            model: Model name (e.g., "llama3", "qwen2")
            base_url: Ollama API base URL
            timeout: Request timeout in seconds
            **kwargs: Additional parameters passed to the API
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_url = f"{self.base_url}/api/chat"
        self.extra_params = kwargs

    def _build_payload(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None
    ) -> dict:
        """Build the request payload for Ollama API."""
        # Handle both Message objects and dict objects
        # Convert tool_calls to Ollama format (arguments as dict, not JSON string)
        formatted_messages = []
        for m in messages:
            if isinstance(m, dict):
                # Convert tool_calls if present
                if "tool_calls" in m:
                    msg_copy = m.copy()
                    msg_copy["tool_calls"] = [
                        self._convert_tool_call_for_ollama(tc) for tc in msg_copy["tool_calls"]
                    ]
                    formatted_messages.append(msg_copy)
                else:
                    formatted_messages.append(m)
            else:
                formatted_messages.append(m.to_dict())

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
            **self.extra_params
        }
        if tools:
            payload["tools"] = tools
        return payload

    def _convert_tool_call_for_ollama(self, tool_call: dict) -> dict:
        """Convert tool call from OpenAI format to Ollama format."""
        func = tool_call.get("function", {})
        args = func.get("arguments", {})

        # If arguments is a JSON string, parse it
        if isinstance(args, str):
            import json
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        return {
            "id": tool_call.get("id", ""),
            "type": "function",
            "function": {
                "name": func.get("name", ""),
                "arguments": args  # Ollama expects dict, not JSON string
            }
        }

    def chat(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs
    ) -> tuple[str, list[ToolCall], LLMUsage]:
        """
        Call Ollama API and get a response.

        Args:
            messages: List of messages
            tools: Optional tool definitions
            system_stable: Stable system prompt (ignored for Ollama, no caching support)

        Returns:
            Tuple of (text_response, tool_calls, usage)
        """
        payload = self._build_payload(messages, tools)

        response = requests.post(
            self.api_url,
            json=payload,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"}
        )
        if not response.ok:
            logger = get_logger()
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        content = message.get("content", "")

        # Parse tool calls
        tool_calls = []
        if "tool_calls" in message:
            for i, tc in enumerate(message["tool_calls"]):
                try:
                    tool_calls.append(ToolCall.from_ollama_format(tc))
                except ValueError as e:
                    # Log the error for debugging
                    logger = get_logger()
                    logger.error(f"Failed to parse tool call #{i+1}: {e}")
                    # Re-raise with context - this will be caught by CLI and shown to user
                    raise ValueError(f"[Tool Call #{i+1}] {e}")

        # Parse usage information from Ollama response
        # Ollama returns: prompt_eval_count (input) and eval_count (output)
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        return content, tool_calls, usage

    def chat_stream(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        system_stable: str | None = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Stream the response from Ollama.

        Args:
            messages: List of messages
            tools: Optional tool definitions
            system_stable: Stable system prompt (ignored for Ollama)

        Yields:
            Text chunks from the response
        """
        payload = self._build_payload(messages, tools)
        payload["stream"] = True

        with requests.post(
            self.api_url,
            json=payload,
            timeout=self.timeout,
            stream=True,
            headers={"Content-Type": "application/json"}
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data:
                        content = data["message"].get("content", "")
                        if content:
                            yield content
