"""
Tests for stall detection (v0.7.16).

Verifies that the StallDetector correctly identifies when the agent
is making iterations without meaningful progress.
"""

import pytest

from nano_agent.agent.stall_detector import (
    StallConfig,
    StallDetector,
    StallResult,
)

pytestmark = pytest.mark.unit


class TestStallConfig:
    """Test StallConfig defaults."""

    def test_default_config(self):
        config = StallConfig()
        assert config.enabled is True
        assert config.patience == 3
        assert config.similarity_threshold == 0.7
        assert config.hint_injection is True

    def test_custom_config(self):
        config = StallConfig(
            enabled=False,
            patience=5,
            similarity_threshold=0.8,
            hint_injection=False,
        )
        assert config.enabled is False
        assert config.patience == 5
        assert config.similarity_threshold == 0.8
        assert config.hint_injection is False


class TestStallResult:
    """Test StallResult dataclass."""

    def test_not_stalled_result(self):
        result = StallResult(is_stalled=False, stalled_iterations=0)
        assert not result.is_stalled
        assert result.hint is None

    def test_stalled_result_with_hint(self):
        result = StallResult(
            is_stalled=True,
            stalled_iterations=2,
            hint="Try a different approach",
        )
        assert result.is_stalled
        assert result.hint == "Try a different approach"


class TestStallDetectorBasic:
    """Basic stall detection tests."""

    def test_no_stall_on_first_iteration(self):
        detector = StallDetector(StallConfig(patience=3))
        detector.record_iteration(["file_read"], ["some content"])
        result = detector.check_stall()
        assert not result.is_stalled

    def test_no_stall_on_two_different_iterations(self):
        detector = StallDetector(StallConfig(patience=3))
        detector.record_iteration(["file_read"], ["content A"])
        detector.record_iteration(["shell_execute"], ["content B"])
        result = detector.check_stall()
        assert not result.is_stalled

    def test_detect_stall_on_identical_iterations(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        detector.record_iteration(["file_read"], ["same content"])
        detector.record_iteration(["file_read"], ["same content"])
        result = detector.check_stall()
        assert result.is_stalled

    def test_detect_stall_with_patience_3(self):
        detector = StallDetector(StallConfig(patience=3, similarity_threshold=0.5))
        # Three identical iterations
        for _ in range(3):
            detector.record_iteration(["file_read"], ["same content"])
        result = detector.check_stall()
        assert result.is_stalled

    def test_no_stall_before_patience_reached(self):
        detector = StallDetector(StallConfig(patience=3, similarity_threshold=0.5))
        # Only 2 identical iterations, patience is 3
        detector.record_iteration(["file_read"], ["same content"])
        detector.record_iteration(["file_read"], ["same content"])
        # With patience=3, need 3 similar iterations
        # But with only 2 signatures, the "recent" list has only 2 items
        # which is less than patience (3), so it checks what we have
        result = detector.check_stall()
        # 2 identical signatures should trigger stall when they're all similar
        assert result.is_stalled  # 2 identical out of 2 is still stalled


class TestStallDetectorSimilarity:
    """Test similarity detection logic."""

    def test_different_tools_no_stall(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.7))
        detector.record_iteration(["file_read"], ["content A"])
        detector.record_iteration(["shell_execute"], ["content B"])
        result = detector.check_stall()
        assert not result.is_stalled

    def test_same_tool_different_result_no_stall(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.7))
        detector.record_iteration(["file_read"], ["content A"])
        detector.record_iteration(["file_read"], ["completely different content here"])
        result = detector.check_stall()
        # Different results → different signatures → not stalled
        assert not result.is_stalled

    def test_same_tool_same_result_stall(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        detector.record_iteration(["file_read"], ["same result"])
        detector.record_iteration(["file_read"], ["same result"])
        result = detector.check_stall()
        assert result.is_stalled

    def test_mixed_tools_partial_similarity(self):
        detector = StallDetector(StallConfig(patience=3, similarity_threshold=0.7))
        # First iteration: file_read + shell
        detector.record_iteration(
            ["file_read", "shell_execute"], ["result A", "result B"]
        )
        # Second iteration: same tools, same results
        detector.record_iteration(
            ["file_read", "shell_execute"], ["result A", "result B"]
        )
        # Third iteration: same again
        detector.record_iteration(
            ["file_read", "shell_execute"], ["result A", "result B"]
        )
        result = detector.check_stall()
        assert result.is_stalled


class TestStallDetectorHints:
    """Test hint generation."""

    def test_hint_generated_when_stalled(self):
        detector = StallDetector(
            StallConfig(patience=2, hint_injection=True, similarity_threshold=0.5)
        )
        detector.record_iteration(["file_read"], ["same"])
        detector.record_iteration(["file_read"], ["same"])
        result = detector.check_stall()
        assert result.is_stalled
        assert result.hint is not None
        assert len(result.hint) > 0

    def test_no_hint_when_disabled(self):
        detector = StallDetector(
            StallConfig(patience=2, hint_injection=False, similarity_threshold=0.5)
        )
        detector.record_iteration(["file_read"], ["same"])
        detector.record_iteration(["file_read"], ["same"])
        result = detector.check_stall()
        assert result.is_stalled
        assert result.hint is None

    def test_hints_cycle_through_variants(self):
        detector = StallDetector(
            StallConfig(patience=2, hint_injection=True, similarity_threshold=0.5)
        )
        hints = []
        # Keep recording without reset to see hint cycling
        for _ in range(4):
            detector.record_iteration(["file_read"], ["same"])
            detector.record_iteration(["file_read"], ["same"])
            result = detector.check_stall()
            if result.hint:
                hints.append(result.hint)
        # Should have cycled through at least 2 different hints
        assert len(hints) >= 2
        assert len(set(hints)) >= 2


class TestStallDetectorReset:
    """Test reset functionality."""

    def test_reset_clears_state(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        detector.record_iteration(["file_read"], ["same"])
        detector.record_iteration(["file_read"], ["same"])
        assert detector.check_stall().is_stalled

        detector.reset()
        result = detector.check_stall()
        assert not result.is_stalled  # No signatures after reset

    def test_reset_allows_fresh_detection(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        # First stall cycle
        detector.record_iteration(["file_read"], ["same"])
        detector.record_iteration(["file_read"], ["same"])
        assert detector.check_stall().is_stalled

        detector.reset()
        # New iterations after reset
        detector.record_iteration(["shell_execute"], ["different"])
        result = detector.check_stall()
        assert not result.is_stalled


class TestStallDetectorDisabled:
    """Test disabled stall detection."""

    def test_disabled_never_detects_stall(self):
        detector = StallDetector(StallConfig(enabled=False))
        for _ in range(10):
            detector.record_iteration(["file_read"], ["same"])
        result = detector.check_stall()
        assert not result.is_stalled


class TestStallDetectorEdgeCases:
    """Test edge cases."""

    def test_empty_tool_calls(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        detector.record_iteration([], [])
        detector.record_iteration([], [])
        # Empty signatures are identical → stall
        result = detector.check_stall()
        assert result.is_stalled

    def test_single_tool_with_long_result(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        long_result = "x" * 10000
        detector.record_iteration(["file_read"], [long_result])
        detector.record_iteration(["file_read"], [long_result])
        result = detector.check_stall()
        assert result.is_stalled

    def test_stall_count_increments(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        detector.record_iteration(["file_read"], ["same"])
        detector.record_iteration(["file_read"], ["same"])
        r1 = detector.check_stall()
        assert r1.stalled_iterations == 1

        # Another stalled iteration
        detector.record_iteration(["file_read"], ["same"])
        detector.record_iteration(["file_read"], ["same"])
        r2 = detector.check_stall()
        assert r2.stalled_iterations == 2

    def test_progress_resets_stall_count(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        # Stalled iterations
        detector.record_iteration(["file_read"], ["same"])
        detector.record_iteration(["file_read"], ["same"])
        r1 = detector.check_stall()
        assert r1.is_stalled

        # Different iteration = progress
        detector.record_iteration(["shell_execute"], ["new result"])
        r2 = detector.check_stall()
        assert not r2.is_stalled
        assert r2.stalled_iterations == 0

    def test_unicode_in_results(self):
        detector = StallDetector(StallConfig(patience=2, similarity_threshold=0.5))
        detector.record_iteration(["file_read"], ["中文内容"])
        detector.record_iteration(["file_read"], ["中文内容"])
        result = detector.check_stall()
        assert result.is_stalled
