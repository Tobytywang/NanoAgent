"""
Consecutive failure detection for the ReAct loop.

Detects when tool executions fail consecutively and triggers auto-rollback
to restore the agent to the last known healthy state.

Works with SnapshotManager to provide automatic recovery from cascading failures.
"""

from dataclasses import dataclass


@dataclass
class ConsecutiveFailureConfig:
    """Configuration for consecutive failure detection."""

    enabled: bool = True
    threshold: int = 3  # Consecutive failures before trigger


@dataclass
class ConsecutiveFailureResult:
    """Result of consecutive failure check."""

    triggered: bool
    consecutive_failures: int
    last_tool_name: str | None = None
    last_error: str | None = None


class ConsecutiveFailureDetector:
    """
    Detects consecutive tool execution failures in the ReAct loop.

    A simple counter that increments on failure and resets on success.
    When the counter reaches the configured threshold, the detector
    signals that auto-rollback should be triggered.
    """

    def __init__(self, config: ConsecutiveFailureConfig | None = None):
        self.config = config or ConsecutiveFailureConfig()
        self._consecutive_failures: int = 0
        self._last_failed_tool: str | None = None
        self._last_error: str | None = None

    def record_tool_result(
        self, tool_name: str, success: bool, error: str | None = None
    ) -> None:
        """Record a tool execution result."""
        if success:
            self._consecutive_failures = 0
            self._last_failed_tool = None
            self._last_error = None
        else:
            self._consecutive_failures += 1
            self._last_failed_tool = tool_name
            self._last_error = error

    def check(self) -> ConsecutiveFailureResult:
        """Check if consecutive failure threshold has been reached."""
        triggered = (
            self.config.enabled and self._consecutive_failures >= self.config.threshold
        )
        return ConsecutiveFailureResult(
            triggered=triggered,
            consecutive_failures=self._consecutive_failures,
            last_tool_name=self._last_failed_tool,
            last_error=self._last_error,
        )

    def reset(self) -> None:
        """Reset failure tracking state (called at start of each run)."""
        self._consecutive_failures = 0
        self._last_failed_tool = None
        self._last_error = None

    def get_state(self) -> dict:
        """Get state for snapshot capture."""
        return {
            "consecutive_failures": self._consecutive_failures,
            "last_failed_tool": self._last_failed_tool,
            "last_error": self._last_error,
        }

    def set_state(self, state: dict) -> None:
        """Restore state from snapshot."""
        self._consecutive_failures = state.get("consecutive_failures", 0)
        self._last_failed_tool = state.get("last_failed_tool")
        self._last_error = state.get("last_error")
