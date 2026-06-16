"""Tests for FeedbackLoop: deviation feedback (#13) + self-correction (#14)."""

import pytest

from nano_agent.agent.feedback_loop import (
    FeedbackLoop,
    DeviationFeedbackResult,
    SelfCorrectionResult,
    _OVER_ESTIMATION_HINTS,
    _UNDER_ESTIMATION_HINTS,
)
from nano_agent.agent.estimation_audit import EstimationAuditResult
from nano_agent.agent.result_validator import ValidationResult, ValidationCheck
from nano_agent.agent.types import AgentEvent
from nano_agent.agent.events import EventEmitter
from nano_agent.config.schema import FeedbackLoopConfig

pytestmark = pytest.mark.unit


# === Helpers ===


def make_audit_result(
    deviation_pct: float = 0.0,
    is_warning: bool = False,
    direction: str = "over",
    calibration_factor: float = 1.0,
) -> EstimationAuditResult:
    return EstimationAuditResult(
        deviation_pct=deviation_pct,
        is_warning=is_warning,
        direction=direction,
        calibration_factor=calibration_factor,
    )


def make_validator_result(
    blocked: bool = False,
    failed_checks: list[ValidationCheck] | None = None,
) -> ValidationResult:
    return ValidationResult(
        original="test response",
        validated="test response",
        blocked=blocked,
        reason="Validation failed" if blocked else "",
        checks=[],
        failed_checks=failed_checks or [],
        actions_taken=[],
    )


def make_failed_check(
    check_type: str = "file_exists",
    detail: str = "File not found",
    severity: str = "high",
) -> ValidationCheck:
    return ValidationCheck(
        check_type=check_type,
        claim="test claim",
        passed=False,
        detail=detail,
        severity=severity,
    )


# === FeedbackLoopConfig ===


class TestFeedbackLoopConfig:
    def test_default_config(self):
        config = FeedbackLoopConfig()
        assert config.deviation_feedback_enabled is True
        assert config.deviation_feedback_threshold == 0.50
        assert config.deviation_feedback_cooldown == 3
        assert config.deviation_feedback_hint_injection is True
        assert config.self_correction_enabled is True
        assert config.self_correction_max_attempts == 2

    def test_custom_config(self):
        config = FeedbackLoopConfig(
            deviation_feedback_enabled=False,
            deviation_feedback_cooldown=5,
            self_correction_max_attempts=3,
        )
        assert config.deviation_feedback_enabled is False
        assert config.deviation_feedback_cooldown == 5
        assert config.self_correction_max_attempts == 3


# === #13 Deviation Feedback ===


class TestDeviationFeedback:
    def test_disabled_no_injection(self):
        config = FeedbackLoopConfig(deviation_feedback_enabled=False)
        fl = FeedbackLoop(config)
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.8)
        )
        assert result.should_inject is False
        assert result.hint is None

    def test_no_warning_no_injection(self):
        fl = FeedbackLoop(FeedbackLoopConfig())
        result = fl.check_deviation(
            make_audit_result(is_warning=False, deviation_pct=0.2)
        )
        assert result.should_inject is False
        assert result.hint is None

    def test_warning_with_cooldown_first_injection(self):
        """First warning (count=1, 1%3==1) should trigger injection."""
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=3))
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6)
        )
        assert result.should_inject is True
        assert result.hint is not None
        assert result.warning_count == 1

    def test_warning_with_cooldown_second_no_injection(self):
        """Second warning (count=2, 2%3!=1) should not inject."""
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=3))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6)
        )
        assert result.should_inject is False
        assert result.warning_count == 2

    def test_warning_with_cooldown_third_no_injection(self):
        """Third warning (count=3, 3%3!=1) should not inject."""
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=3))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6)
        )
        assert result.should_inject is False
        assert result.warning_count == 3

    def test_warning_with_cooldown_fourth_injection(self):
        """Fourth warning (count=4, 4%3==1) should trigger injection."""
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=3))
        for _ in range(3):
            fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6)
        )
        assert result.should_inject is True
        assert result.hint is not None
        assert result.warning_count == 4

    def test_over_estimation_hint(self):
        fl = FeedbackLoop(FeedbackLoopConfig())
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6, direction="over")
        )
        assert result.hint is not None
        assert "高估" in result.hint or "低于估算" in result.hint

    def test_under_estimation_hint(self):
        fl = FeedbackLoop(FeedbackLoopConfig())
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6, direction="under")
        )
        assert result.hint is not None
        assert "低估" in result.hint or "远超估算" in result.hint

    def test_hint_injection_disabled(self):
        """When hint_injection=False, should_inject=True but hint=None."""
        config = FeedbackLoopConfig(deviation_feedback_hint_injection=False)
        fl = FeedbackLoop(config)
        result = fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6)
        )
        assert result.should_inject is True
        assert result.hint is None

    def test_hint_cycles_through_templates(self):
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=1))
        hints = []
        for i in range(len(_OVER_ESTIMATION_HINTS) + 1):
            result = fl.check_deviation(
                make_audit_result(is_warning=True, deviation_pct=0.6, direction="over")
            )
            hints.append(result.hint)
        # After cycling, the first hint should appear again
        assert hints[0] == hints[len(_OVER_ESTIMATION_HINTS)]

    def test_deviation_pct_in_result(self):
        fl = FeedbackLoop(FeedbackLoopConfig())
        result = fl.check_deviation(make_audit_result(deviation_pct=0.75))
        assert result.deviation_pct == 0.75

    def test_event_emission(self):
        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.DEVIATION_FEEDBACK, lambda e, d: emitted.append(d))
        fl = FeedbackLoop(FeedbackLoopConfig(), events=events)
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        assert len(emitted) == 1
        assert emitted[0]["deviation_pct"] == 0.6
        assert emitted[0]["direction"] == "over"

    def test_no_event_when_not_injecting(self):
        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.DEVIATION_FEEDBACK, lambda e, d: emitted.append(d))
        fl = FeedbackLoop(FeedbackLoopConfig(), events=events)
        fl.check_deviation(make_audit_result(is_warning=False))
        assert len(emitted) == 0

    def test_deviation_injections_counter(self):
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=1))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        assert fl._deviation_injections == 3


# === #14 Self-Correction ===


class TestSelfCorrection:
    def test_disabled_no_retry(self):
        config = FeedbackLoopConfig(self_correction_enabled=False)
        fl = FeedbackLoop(config)
        vr = make_validator_result(blocked=True, failed_checks=[make_failed_check()])
        assert fl.should_retry(vr) is False

    def test_blocked_with_attempts_remaining(self):
        fl = FeedbackLoop(FeedbackLoopConfig(self_correction_max_attempts=2))
        vr = make_validator_result(blocked=True, failed_checks=[make_failed_check()])
        assert fl.should_retry(vr) is True

    def test_all_attempts_exhausted(self):
        config = FeedbackLoopConfig(self_correction_max_attempts=2)
        fl = FeedbackLoop(config)
        fl.record_correction_attempt()
        fl.record_correction_attempt()
        vr = make_validator_result(blocked=True, failed_checks=[make_failed_check()])
        assert fl.should_retry(vr) is False

    def test_non_blocked_no_retry(self):
        fl = FeedbackLoop(FeedbackLoopConfig())
        vr = make_validator_result(blocked=False)
        assert fl.should_retry(vr) is False

    def test_feedback_message_format(self):
        fl = FeedbackLoop(FeedbackLoopConfig())
        checks = [
            make_failed_check(check_type="file_exists", detail="File foo.py not found"),
            make_failed_check(
                check_type="code_syntax", detail="Syntax error in bar.py"
            ),
        ]
        vr = make_validator_result(blocked=True, failed_checks=checks)
        msg = fl.build_correction_feedback(vr)
        assert "[Self-Correction]" in msg
        assert "file_exists" in msg
        assert "File foo.py not found" in msg
        assert "code_syntax" in msg
        assert "Syntax error in bar.py" in msg
        assert "Please verify" in msg

    def test_correction_attempt_tracking(self):
        fl = FeedbackLoop(FeedbackLoopConfig(self_correction_max_attempts=3))
        assert fl.correction_attempts_used == 0
        assert fl.remaining_correction_attempts == 3
        r1 = fl.record_correction_attempt()
        assert r1.attempt_number == 1
        assert r1.remaining_attempts == 2
        r2 = fl.record_correction_attempt()
        assert r2.attempt_number == 2
        assert fl.correction_attempts_used == 2
        assert fl.remaining_correction_attempts == 1

    def test_remaining_attempts_never_negative(self):
        fl = FeedbackLoop(FeedbackLoopConfig(self_correction_max_attempts=1))
        fl.record_correction_attempt()
        fl.record_correction_attempt()  # overshoot
        assert fl.remaining_correction_attempts == 0

    def test_event_emission(self):
        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.SELF_CORRECTION, lambda e, d: emitted.append(d))
        fl = FeedbackLoop(FeedbackLoopConfig(), events=events)
        vr = make_validator_result(blocked=True, failed_checks=[make_failed_check()])
        fl.record_correction_attempt()
        fl.emit_self_correction_event(["file_exists"])
        assert len(emitted) == 1
        assert emitted[0]["attempt"] == 1
        assert emitted[0]["max_attempts"] == 2
        assert "file_exists" in emitted[0]["failed_checks"]

    def test_termination_reason_exhausted(self):
        """When all correction attempts are used, caller should use SELF_CORRECTION_EXHAUSTED."""
        from nano_agent.agent.types import TerminationReason

        fl = FeedbackLoop(FeedbackLoopConfig(self_correction_max_attempts=2))
        fl.record_correction_attempt()
        fl.record_correction_attempt()
        assert fl.correction_attempts_used == 2
        assert fl.remaining_correction_attempts == 0
        # Caller checks correction_attempts_used > 0 → SELF_CORRECTION_EXHAUSTED
        assert (
            TerminationReason.SELF_CORRECTION_EXHAUSTED.value
            == "self_correction_exhausted"
        )


# === Reset ===


class TestFeedbackLoopReset:
    def test_reset_all_clears_all_state(self):
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=1))
        # Accumulate state
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.7))
        fl.record_correction_attempt()
        assert fl._deviation_warning_count > 0
        assert fl._deviation_injections > 0
        assert fl.correction_attempts_used > 0

        fl.reset_all()
        assert fl._deviation_warning_count == 0
        assert fl._deviation_injections == 0
        assert fl.correction_attempts_used == 0
        assert fl.remaining_correction_attempts == 2

    def test_reset_run_preserves_correction_state(self):
        """reset_run() clears deviation state but preserves correction attempts."""
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=1))
        fl.check_deviation(make_audit_result(is_warning=True, deviation_pct=0.6))
        fl.record_correction_attempt()
        assert fl._deviation_warning_count > 0
        assert fl.correction_attempts_used == 1

        fl.reset_run()
        assert fl._deviation_warning_count == 0
        assert fl._deviation_injections == 0
        assert fl._over_hint_index == 0
        assert fl._under_hint_index == 0
        assert fl.correction_attempts_used == 1  # preserved

    def test_reset_all_clears_hint_indices(self):
        fl = FeedbackLoop(FeedbackLoopConfig(deviation_feedback_cooldown=1))
        fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6, direction="over")
        )
        fl.check_deviation(
            make_audit_result(is_warning=True, deviation_pct=0.6, direction="under")
        )
        assert fl._over_hint_index > 0
        assert fl._under_hint_index > 0

        fl.reset_all()
        assert fl._over_hint_index == 0
        assert fl._under_hint_index == 0


# === SelfCorrectionResult ===


class TestSelfCorrectionResult:
    def test_result_fields(self):
        r = SelfCorrectionResult(
            attempted=True,
            attempt_number=2,
            max_attempts=3,
            remaining_attempts=1,
        )
        assert r.attempted is True
        assert r.attempt_number == 2
        assert r.max_attempts == 3
        assert r.remaining_attempts == 1
