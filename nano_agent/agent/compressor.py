"""
Message compression for reducing token consumption in long conversations.

Compresses old messages into summaries to keep prompt size manageable.
"""

import time
from dataclasses import dataclass, field

from ..agent.token_utils import estimate_tokens, calculate_max_chars


@dataclass
class CompressorConfig:
    """Configuration for message compression."""

    enabled: bool = True
    threshold_tokens: int = 2000  # Compress when prompt_tokens > threshold
    keep_recent: int = (
        3  # Keep recent N rounds of conversation (user + assistant pairs)
    )
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

    def should_compress(
        self,
        messages: list,
        last_prompt_tokens: int | None = None,
        calibration_factor: float = 1.0,
    ) -> bool:
        """
        Check if messages should be compressed.

        Args:
            messages: List of message dicts
            last_prompt_tokens: Real prompt_tokens from previous LLM call (v0.7.12).
                If provided, use this instead of estimate_tokens().
                If None (first iteration), fall back to estimate_tokens().
            calibration_factor: Multiplier to correct estimation bias (v0.7.13).

        Returns:
            True if compression is needed
        """
        if not self.config.enabled:
            return False

        # v0.7.12: Use real prompt_tokens if available, otherwise estimate
        if last_prompt_tokens is not None:
            tokens = last_prompt_tokens
        else:
            tokens = estimate_tokens(messages, calibration_factor)

        return tokens > self.config.threshold_tokens

    def compress(
        self,
        messages: list,
        last_prompt_tokens: int | None = None,
        calibration_factor: float = 1.0,
    ) -> list:
        """
        Compress old messages into a summary.

        Args:
            messages: List of message dicts
            last_prompt_tokens: Real prompt_tokens from previous LLM call (v0.7.12).
                Passed through to should_compress().
            calibration_factor: Multiplier to correct estimation bias (v0.7.13).

        Returns:
            Compressed message list
        """
        if not self.should_compress(
            messages,
            last_prompt_tokens=last_prompt_tokens,
            calibration_factor=calibration_factor,
        ):
            return messages

        # Keep system message
        system_messages = [m for m in messages if m.get("role") == "system"]

        # Keep recent N rounds (user + assistant pairs)
        non_system = [m for m in messages if m.get("role") != "system"]
        keep_count = self.config.keep_recent * 2  # Each round has 2 messages
        recent = (
            non_system[-keep_count:] if len(non_system) > keep_count else non_system
        )
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

        # Truncate if too long (v0.7.13: use calculate_max_chars for Chinese support)
        max_chars = calculate_max_chars(summary_text, self.config.summary_max_tokens)
        if len(summary_text) > max_chars:
            summary_text = summary_text[:max_chars] + "..."

        return {"role": "system", "content": summary_text}

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
