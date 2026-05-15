"""
Message compression for reducing token consumption in long conversations.

Compresses old messages into summaries to keep prompt size manageable.
"""

import time
from dataclasses import dataclass, field

from ..agent.token_utils import estimate_tokens


@dataclass
class CompressorConfig:
    """Configuration for message compression."""

    enabled: bool = True
    threshold_tokens: int = 2000  # Compress when prompt_tokens > threshold
    keep_recent: int = 3  # Keep recent N rounds of conversation (user + assistant pairs)
    summary_max_tokens: int = 500  # Max tokens for summary


class MessageCompressor:
    """
    Compresses old messages into summaries.

    When prompt_tokens exceed threshold, old messages are compressed
    into a single summary message to reduce token consumption.
    """

    def __init__(self, config: CompressorConfig | None = None):
        self.config = config or CompressorConfig()
        self._compression_count: int = 0

    def should_compress(self, messages: list) -> bool:
        """
        Check if messages should be compressed.

        Args:
            messages: List of message dicts

        Returns:
            True if compression is needed
        """
        if not self.config.enabled:
            return False

        # Estimate current token count
        tokens = estimate_tokens(messages)

        return tokens > self.config.threshold_tokens

    def compress(self, messages: list) -> list:
        """
        Compress old messages into a summary.

        Args:
            messages: List of message dicts

        Returns:
            Compressed message list
        """
        if not self.should_compress(messages):
            return messages

        # Keep system message
        system_messages = [m for m in messages if m.get("role") == "system"]

        # Keep recent N rounds (user + assistant pairs)
        non_system = [m for m in messages if m.get("role") != "system"]
        keep_count = self.config.keep_recent * 2  # Each round has 2 messages
        recent = non_system[-keep_count:] if len(non_system) > keep_count else non_system
        old = non_system[:-keep_count] if len(non_system) > keep_count else []

        if not old:
            return messages  # Nothing to compress

        # Create summary of old messages
        summary = self._create_summary(old)

        # Build compressed message list
        compressed = system_messages + [summary] + recent

        self._compression_count += 1

        return compressed

    def _create_summary(self, old_messages: list) -> dict:
        """
        Create a summary message from old messages.

        Args:
            old_messages: List of old message dicts

        Returns:
            Summary message dict
        """
        # Extract key information from old messages
        user_queries = []
        assistant_responses = []
        tool_calls = []
        tool_results = []

        for msg in old_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                user_queries.append(content[:100])  # Truncate long queries
            elif role == "assistant":
                # Check for tool calls
                if msg.get("tool_calls"):
                    for tc in msg.get("tool_calls", []):
                        tool_calls.append(tc.get("function", {}).get("name", "unknown"))
                elif content:
                    assistant_responses.append(content[:100])
            elif role == "tool":
                tool_results.append(f"{msg.get('name', 'unknown')}: {content[:50]}")

        # Build summary text
        summary_parts = []

        if user_queries:
            queries_str = "; ".join(user_queries[-5:])  # Last 5 queries
            summary_parts.append(f"用户请求: {queries_str}")

        if tool_calls:
            tools_str = ", ".join(tool_calls[-10:])  # Last 10 tool calls
            summary_parts.append(f"工具调用: {tools_str}")

        if assistant_responses:
            responses_str = "; ".join(assistant_responses[-3:])  # Last 3 responses
            summary_parts.append(f"助手响应: {responses_str}")

        if tool_results:
            results_str = "; ".join(tool_results[-5:])  # Last 5 results
            summary_parts.append(f"工具结果: {results_str}")

        summary_text = "[历史摘要] " + " | ".join(summary_parts)

        # Truncate if too long
        if len(summary_text) > self.config.summary_max_tokens * 4:  # Rough char estimate
            summary_text = summary_text[:self.config.summary_max_tokens * 4] + "..."

        return {
            "role": "system",
            "content": summary_text
        }

    def get_stats(self) -> dict:
        """
        Get compression statistics.

        Returns:
            Dict with compression count
        """
        return {
            "compression_count": self._compression_count,
        }

    def reset_stats(self) -> None:
        """Reset compression statistics."""
        self._compression_count = 0