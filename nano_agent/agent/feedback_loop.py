"""
Feedback loop: deviation backflow (#13) + self-correction (#14).

#13 Deviation Feedback: When EstimationAudit detects persistent high deviation,
injects a hint into the LLM context to adjust strategy (same pattern as StallDetector).

#14 Self-Correction Loop: When ResultValidator blocks output, injects validation
feedback into agent memory and retries execution, up to a configurable max.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .types import AgentEvent

if TYPE_CHECKING:
    from .estimation_audit import EstimationAuditResult
    from .events import EventEmitter
    from .result_validator import ValidationResult
    from ..config.schema import FeedbackLoopConfig

# Deviation hint templates (cycled to avoid repetition)
_OVER_ESTIMATION_HINTS = [
    "Token 估算偏差过高 ({pct:.0%}，高估)。请考虑缩短回复、减少工具调用次数，避免超出预算。",
    "持续高估 Token 消耗 ({pct:.0%})。请精简操作，优先使用已有信息回答。",
    "实际消耗远低于估算 ({pct:.0%}，高估)。预算充足但请避免不必要的工具调用。",
]

_UNDER_ESTIMATION_HINTS = [
    "Token 估算偏差过高 ({pct:.0%}，低估)。预算消耗比预期更快，请加快收敛。",
    "持续低估 Token 消耗 ({pct:.0%})。请立即总结已有成果，避免预算耗尽。",
    "Token 消耗远超估算 ({pct:.0%})。请停止工具调用，直接基于已知信息回答。",
]


@dataclass
class DeviationFeedbackResult:
    """Result from deviation feedback check."""

    should_inject: bool
    hint: str | None
    deviation_pct: float
    direction: str
    warning_count: int


@dataclass
class SelfCorrectionResult:
    """Result from a self-correction attempt."""

    attempted: bool
    attempt_number: int
    max_attempts: int
    remaining_attempts: int


class FeedbackLoop:
    """Feedback loop: deviation backflow + self-correction.

    #13: Checks EstimationAudit results and injects corrective hints into
    the LLM context when deviation is persistently high.

    #14: When ResultValidator blocks output, builds structured feedback
    from failed checks and enables retry with that feedback.
    """

    def __init__(
        self, config: "FeedbackLoopConfig", events: "EventEmitter | None" = None
    ):
        self._config = config
        self._events = events
        # #13 state
        self._deviation_warning_count: int = 0
        self._deviation_injections: int = 0
        self._over_hint_index: int = 0
        self._under_hint_index: int = 0
        # #14 state
        self._correction_attempts: int = 0

    @property
    def config(self) -> "FeedbackLoopConfig":
        return self._config

    @property
    def correction_attempts_used(self) -> int:
        return self._correction_attempts

    @property
    def remaining_correction_attempts(self) -> int:
        return max(
            0, self._config.self_correction_max_attempts - self._correction_attempts
        )

    # --- #13: Deviation Feedback ---

    def check_deviation(
        self, audit_result: "EstimationAuditResult"
    ) -> DeviationFeedbackResult:
        """Check if deviation feedback should be injected.

        Called from react._think() after recording calibration data.
        Follows the same pattern as StallDetector.check_stall().
        """
        if not self._config.deviation_feedback_enabled:
            return DeviationFeedbackResult(
                should_inject=False,
                hint=None,
                deviation_pct=audit_result.deviation_pct,
                direction=audit_result.direction,
                warning_count=self._deviation_warning_count,
            )

        if not audit_result.is_warning:
            return DeviationFeedbackResult(
                should_inject=False,
                hint=None,
                deviation_pct=audit_result.deviation_pct,
                direction=audit_result.direction,
                warning_count=self._deviation_warning_count,
            )

        self._deviation_warning_count += 1

        # Cooldown: only inject once per N warnings
        if self._config.deviation_feedback_cooldown <= 1:
            should_inject = True
        else:
            should_inject = (
                self._deviation_warning_count % self._config.deviation_feedback_cooldown
                == 1
            )

        hint = None
        if should_inject and self._config.deviation_feedback_hint_injection:
            hint = self._build_deviation_hint(
                audit_result.deviation_pct, audit_result.direction
            )
            self._deviation_injections += 1
            self._emit_deviation_feedback(audit_result, hint)

        return DeviationFeedbackResult(
            should_inject=should_inject,
            hint=hint,
            deviation_pct=audit_result.deviation_pct,
            direction=audit_result.direction,
            warning_count=self._deviation_warning_count,
        )

    def _build_deviation_hint(self, deviation_pct: float, direction: str) -> str:
        """Build a deviation hint message for the LLM."""
        if direction == "over":
            hint = _OVER_ESTIMATION_HINTS[
                self._over_hint_index % len(_OVER_ESTIMATION_HINTS)
            ]
            self._over_hint_index += 1
        else:
            hint = _UNDER_ESTIMATION_HINTS[
                self._under_hint_index % len(_UNDER_ESTIMATION_HINTS)
            ]
            self._under_hint_index += 1
        return hint.format(pct=deviation_pct)

    def _emit_deviation_feedback(
        self, audit_result: "EstimationAuditResult", hint: str
    ) -> None:
        """Emit event for deviation feedback injection."""
        if self._events:
            self._events.emit(
                AgentEvent.DEVIATION_FEEDBACK,
                {
                    "deviation_pct": audit_result.deviation_pct,
                    "direction": audit_result.direction,
                    "hint": hint,
                    "warning_count": self._deviation_warning_count,
                },
            )

    # --- #14: Self-Correction ---

    def should_retry(self, validator_result: "ValidationResult") -> bool:
        """Check whether a self-correction retry should be attempted.

        Only retries when:
        1. Self-correction is enabled
        2. Attempts remain
        3. Validation blocked (high-severity failure)
        """
        if not self._config.self_correction_enabled:
            return False
        if self._correction_attempts >= self._config.self_correction_max_attempts:
            return False
        if not validator_result.blocked:
            return False
        return True

    def build_correction_feedback(self, validator_result: "ValidationResult") -> str:
        """Build structured feedback from failed validation checks."""
        lines = ["[Self-Correction] Validation failed:"]
        for check in validator_result.failed_checks:
            lines.append(f"  - {check.check_type}: {check.detail}")
        lines.append("Please verify and correct the above issues.")
        return "\n".join(lines)

    def record_correction_attempt(self) -> SelfCorrectionResult:
        """Record a correction attempt and return tracking info."""
        self._correction_attempts += 1
        return SelfCorrectionResult(
            attempted=True,
            attempt_number=self._correction_attempts,
            max_attempts=self._config.self_correction_max_attempts,
            remaining_attempts=self.remaining_correction_attempts,
        )

    def emit_self_correction_event(self, failed_checks: list[str]) -> None:
        """Emit event for self-correction attempt."""
        if self._events:
            self._events.emit(
                AgentEvent.SELF_CORRECTION,
                {
                    "attempt": self._correction_attempts,
                    "max_attempts": self._config.self_correction_max_attempts,
                    "remaining": self.remaining_correction_attempts,
                    "failed_checks": failed_checks,
                },
            )

    # --- Common ---

    def reset_run(self) -> None:
        """Reset deviation state for a new run. Correction state is preserved
        across self-correction retries within the same user query."""
        self._deviation_warning_count = 0
        self._deviation_injections = 0
        self._over_hint_index = 0
        self._under_hint_index = 0

    def reset_all(self) -> None:
        """Reset all state for a new user query (called by orchestrator)."""
        self.reset_run()
        self._correction_attempts = 0
