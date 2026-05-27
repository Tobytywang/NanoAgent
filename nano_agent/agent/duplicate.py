"""
Duplicate tool call detection.

Provides configurable detection of repeated tool calls to prevent
infinite loops while allowing legitimate repeated operations.
"""

import hashlib
import json
from dataclasses import dataclass


@dataclass
class DuplicateCheckResult:
    """Result of a duplicate check."""

    is_duplicate: bool  # True if this call has been seen before
    should_skip: bool  # True if the call should be blocked
    count: int  # How many times this key has been seen
    key: str  # The deduplication key


class DuplicateDetector:
    """
    Detects and blocks repeated tool calls.

    Supports two modes:
    - hash (default): Uses MD5[:8] of arguments for backward compatibility
    - deep_equal: Uses full JSON comparison for precise deduplication
    """

    def __init__(self, threshold: int = 3, deep_equal: bool = False):
        """
        Initialize duplicate detector.

        Args:
            threshold: Max allowed identical calls before blocking (default 3)
            deep_equal: If True, use full argument comparison instead of MD5[:8]
        """
        self.threshold = threshold
        self.deep_equal = deep_equal
        self._call_history: dict[str, int] = {}
        self.warning_issued: bool = False

    def _make_key(self, tool_call) -> str:
        """Create a deduplication key from a tool call."""
        args_str = json.dumps(tool_call.arguments, sort_keys=True)
        if self.deep_equal:
            return f"{tool_call.name}:{args_str}"
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        return f"{tool_call.name}:{args_hash}"

    def check(self, tool_call) -> DuplicateCheckResult:
        """
        Check if a tool call is a duplicate.

        Args:
            tool_call: The tool call to check

        Returns:
            DuplicateCheckResult with duplicate status and count
        """
        key = self._make_key(tool_call)
        self._call_history[key] = self._call_history.get(key, 0) + 1
        count = self._call_history[key]
        should_skip = count > self.threshold
        return DuplicateCheckResult(
            is_duplicate=count > 1,
            should_skip=should_skip,
            count=count,
            key=key,
        )

    def reset(self) -> None:
        """Reset state for a new run."""
        self._call_history = {}
        self.warning_issued = False
