"""Tests for ConsecutiveFailureDetector (v0.8.15)."""

import pytest

from nano_agent.agent.consecutive_failure_detector import (
    ConsecutiveFailureConfig,
    ConsecutiveFailureDetector,
    ConsecutiveFailureResult,
)


class TestConsecutiveFailureConfig:
    """Test ConsecutiveFailureConfig defaults and custom values."""

    def test_defaults(self):
        config = ConsecutiveFailureConfig()
        assert config.enabled is True
        assert config.threshold == 3

    def test_custom_values(self):
        config = ConsecutiveFailureConfig(
            enabled=False,
            threshold=5,
        )
        assert config.enabled is False
        assert config.threshold == 5


class TestConsecutiveFailureDetectorRecordAndReset:
    """Test record_tool_result and reset behavior."""

    def test_success_resets_counter(self):
        detector = ConsecutiveFailureDetector()
        detector.record_tool_result("tool_a", False, "error1")
        detector.record_tool_result("tool_a", False, "error2")
        assert detector._consecutive_failures == 2

        detector.record_tool_result("tool_b", True)
        assert detector._consecutive_failures == 0
        assert detector._last_failed_tool is None
        assert detector._last_error is None

    def test_failure_increments_counter(self):
        detector = ConsecutiveFailureDetector()
        detector.record_tool_result("tool_a", False, "err1")
        assert detector._consecutive_failures == 1
        assert detector._last_failed_tool == "tool_a"
        assert detector._last_error == "err1"

        detector.record_tool_result("tool_b", False, "err2")
        assert detector._consecutive_failures == 2
        assert detector._last_failed_tool == "tool_b"
        assert detector._last_error == "err2"

    def test_reset_clears_state(self):
        detector = ConsecutiveFailureDetector()
        detector.record_tool_result("tool_a", False, "error")
        detector.reset()
        assert detector._consecutive_failures == 0
        assert detector._last_failed_tool is None
        assert detector._last_error is None


class TestConsecutiveFailureDetectorCheck:
    """Test check() threshold behavior."""

    def test_not_triggered_below_threshold(self):
        detector = ConsecutiveFailureDetector(ConsecutiveFailureConfig(threshold=3))
        detector.record_tool_result("tool_a", False, "err")
        detector.record_tool_result("tool_b", False, "err")

        result = detector.check()
        assert result.triggered is False
        assert result.consecutive_failures == 2

    def test_triggered_at_threshold(self):
        detector = ConsecutiveFailureDetector(ConsecutiveFailureConfig(threshold=3))
        detector.record_tool_result("tool_a", False, "err1")
        detector.record_tool_result("tool_b", False, "err2")
        detector.record_tool_result("tool_c", False, "err3")

        result = detector.check()
        assert result.triggered is True
        assert result.consecutive_failures == 3
        assert result.last_tool_name == "tool_c"
        assert result.last_error == "err3"

    def test_triggered_above_threshold(self):
        detector = ConsecutiveFailureDetector(ConsecutiveFailureConfig(threshold=3))
        for i in range(5):
            detector.record_tool_result(f"tool_{i}", False, f"err{i}")

        result = detector.check()
        assert result.triggered is True
        assert result.consecutive_failures == 5

    def test_success_resets_then_failure_recount(self):
        detector = ConsecutiveFailureDetector(ConsecutiveFailureConfig(threshold=3))
        detector.record_tool_result("tool_a", False, "err")
        detector.record_tool_result("tool_b", True)
        detector.record_tool_result("tool_c", False, "err")

        result = detector.check()
        assert result.triggered is False
        assert result.consecutive_failures == 1

    def test_disabled_never_triggers(self):
        detector = ConsecutiveFailureDetector(
            ConsecutiveFailureConfig(enabled=False, threshold=1)
        )
        detector.record_tool_result("tool_a", False, "err")

        result = detector.check()
        assert result.triggered is False

    def test_default_config_threshold_3(self):
        detector = ConsecutiveFailureDetector()
        detector.record_tool_result("t1", False, "e")
        detector.record_tool_result("t2", False, "e")

        result = detector.check()
        assert result.triggered is False

        detector.record_tool_result("t3", False, "e")
        result = detector.check()
        assert result.triggered is True


class TestConsecutiveFailureDetectorState:
    """Test get_state/set_state for snapshot capture/restore."""

    def test_get_set_state_roundtrip(self):
        detector = ConsecutiveFailureDetector()
        detector.record_tool_result("tool_a", False, "err1")
        detector.record_tool_result("tool_b", False, "err2")

        state = detector.get_state()
        assert state["consecutive_failures"] == 2
        assert state["last_failed_tool"] == "tool_b"
        assert state["last_error"] == "err2"

        # Apply to new detector
        detector2 = ConsecutiveFailureDetector()
        detector2.set_state(state)
        assert detector2._consecutive_failures == 2
        assert detector2._last_failed_tool == "tool_b"
        assert detector2._last_error == "err2"

    def test_set_state_default_values(self):
        detector = ConsecutiveFailureDetector()
        detector.set_state({})
        assert detector._consecutive_failures == 0
        assert detector._last_failed_tool is None
        assert detector._last_error is None

    def test_state_after_reset(self):
        detector = ConsecutiveFailureDetector()
        detector.record_tool_result("tool_a", False, "err")
        detector.reset()

        state = detector.get_state()
        assert state["consecutive_failures"] == 0
        assert state["last_failed_tool"] is None
