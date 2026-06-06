"""
Circuit breaker for execution mode degradation.

Detects abnormal LLM behavior (oversized response, repeated tool calls, stall)
and degrades from AUTO to SUPERVISED mode where every tool call requires
user confirmation.
"""

from .types import ExecutionMode, AgentEvent
from ..config.schema import CircuitBreakerConfig


class CircuitBreaker:
    """Detects abnormal behavior and triggers execution mode degradation.

    Three trigger conditions:
    1. LLM response too large (completion_tokens > max_response_tokens)
    2. Repeated tool calls (duplicate count >= duplicate_trigger_count)
    3. Stall detection (stall count >= stall_trigger_count)

    When triggered, degrades from AUTO to SUPERVISED mode.
    In SUPERVISED mode, every tool call requires user confirmation
    via ConfirmationManager.
    """

    def __init__(self, config, event_emitter=None):
        if config is None:
            config = CircuitBreakerConfig()
        self._config = config
        self._events = event_emitter
        self._mode = ExecutionMode.AUTO
        self._trigger_reason: str | None = None

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @property
    def trigger_reason(self) -> str | None:
        return self._trigger_reason

    @property
    def config(self):
        return self._config

    def check_llm_response(self, completion_tokens: int) -> bool:
        """Check if LLM response is oversized.

        Args:
            completion_tokens: Number of completion tokens in LLM response

        Returns:
            True if circuit breaker was triggered
        """
        if not self._config.enabled:
            return False
        if completion_tokens > self._config.max_response_tokens:
            self._trigger(
                f"LLM 响应过大 ({completion_tokens} > {self._config.max_response_tokens})"
            )
            return True
        return False

    def check_duplicate(self, duplicate_result) -> bool:
        """Check if duplicate tool calls should trigger circuit break.

        Args:
            duplicate_result: DuplicateCheckResult from DuplicateDetector

        Returns:
            True if circuit breaker was triggered
        """
        if not self._config.enabled:
            return False
        if (
            duplicate_result.is_duplicate
            and duplicate_result.count >= self._config.duplicate_trigger_count
        ):
            self._trigger(f"重复工具调用 ({duplicate_result.count} 次)")
            return True
        return False

    def check_stall(self, stall_result) -> bool:
        """Check if stall should trigger circuit break.

        Args:
            stall_result: StallResult from StallDetector

        Returns:
            True if circuit breaker was triggered
        """
        if not self._config.enabled:
            return False
        if (
            stall_result.is_stalled
            and stall_result.stalled_iterations >= self._config.stall_trigger_count
        ):
            self._trigger(f"执行停滞 ({stall_result.stalled_iterations} 次相似迭代)")
            return True
        return False

    def reset(self):
        """Reset to AUTO mode."""
        self._mode = ExecutionMode.AUTO
        self._trigger_reason = None

    def _trigger(self, reason: str):
        """Trigger circuit breaker, degrading to SUPERVISED mode."""
        if self._mode == ExecutionMode.SUPERVISED:
            return  # Already in SUPERVISED mode
        self._mode = ExecutionMode.SUPERVISED
        self._trigger_reason = reason
        if self._events:
            self._events.emit(
                AgentEvent.CIRCUIT_BREAKER,
                {"reason": reason, "mode": ExecutionMode.SUPERVISED.value},
            )
