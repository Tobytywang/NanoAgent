"""
Ollama LLM client implementation.
"""

import requests
import json
from typing import Generator
from .base import BaseLLM
from .messages import Message, ToolCall


class OllamaLLM(BaseLLM):
    """Ollama LLM client."""

    DEFAULT_BASE_URL = "http://localhost:11434"

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
        """Build the request payload."""
        # Handle both Message objects and dict objects
        formatted_messages = []
        for m in messages:
            if isinstance(m, dict):
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

    def chat(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> tuple[str, list[ToolCall]]:
        """
        Call Ollama API and get a response.

        Args:
            messages: List of messages
            tools: Optional tool definitions

        Returns:
            Tuple of (text_response, tool_calls)
        """
        payload = self._build_payload(messages, tools)

        response = requests.post(
            self.api_url,
            json=payload,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        content = message.get("content", "")

        # Parse tool calls
        tool_calls = []
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                tool_calls.append(ToolCall.from_ollama_format(tc))

        return content, tool_calls

    def chat_stream(
        self,
        messages: list[Message] | list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Stream the response from Ollama.

        Args:
            messages: List of messages
            tools: Optional tool definitions

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
