"""
Tests for DuplicateDetector.
"""

import pytest

from nano_agent.agent.duplicate import DuplicateDetector, DuplicateCheckResult


class FakeToolCall:
    """Minimal tool call stub for testing."""

    def __init__(self, name: str, arguments: dict):
        self.name = name
        self.arguments = arguments


class TestDuplicateDetector:
    """Tests for DuplicateDetector core logic."""

    def test_first_call_not_duplicate(self):
        det = DuplicateDetector(threshold=3)
        result = det.check(FakeToolCall("file_read", {"path": "/tmp/a.txt"}))
        assert not result.is_duplicate
        assert not result.should_skip
        assert result.count == 1

    def test_second_call_is_duplicate_but_not_skipped(self):
        det = DuplicateDetector(threshold=3)
        tc = FakeToolCall("file_read", {"path": "/tmp/a.txt"})
        det.check(tc)
        result = det.check(tc)
        assert result.is_duplicate
        assert not result.should_skip
        assert result.count == 2

    def test_threshold_exceeded_triggers_skip(self):
        det = DuplicateDetector(threshold=3)
        tc = FakeToolCall("file_read", {"path": "/tmp/a.txt"})
        for _ in range(3):
            det.check(tc)
        result = det.check(tc)
        assert result.is_duplicate
        assert result.should_skip
        assert result.count == 4

    def test_different_arguments_not_duplicate(self):
        det = DuplicateDetector(threshold=3)
        det.check(FakeToolCall("file_read", {"path": "/tmp/a.txt"}))
        result = det.check(FakeToolCall("file_read", {"path": "/tmp/b.txt"}))
        assert not result.is_duplicate
        assert result.count == 1

    def test_different_tool_names_not_duplicate(self):
        det = DuplicateDetector(threshold=3)
        det.check(FakeToolCall("file_read", {"path": "/tmp/a.txt"}))
        result = det.check(FakeToolCall("file_write", {"path": "/tmp/a.txt"}))
        assert not result.is_duplicate
        assert result.count == 1

    def test_reset_clears_history(self):
        det = DuplicateDetector(threshold=3)
        tc = FakeToolCall("file_read", {"path": "/tmp/a.txt"})
        det.check(tc)
        det.check(tc)
        det.reset()
        result = det.check(tc)
        assert not result.is_duplicate
        assert result.count == 1

    def test_reset_clears_warning(self):
        det = DuplicateDetector(threshold=3)
        det.warning_issued = True
        det.reset()
        assert not det.warning_issued

    def test_warning_issued_property(self):
        det = DuplicateDetector(threshold=3)
        assert not det.warning_issued
        det.warning_issued = True
        assert det.warning_issued

    def test_custom_threshold(self):
        det = DuplicateDetector(threshold=1)
        tc = FakeToolCall("file_read", {"path": "/tmp/a.txt"})
        det.check(tc)
        result = det.check(tc)
        assert result.should_skip
        assert result.count == 2


class TestDuplicateDetectorDeepEqual:
    """Tests for deep_equal mode vs hash mode."""

    def test_hash_mode_collisions_possible(self):
        """MD5[:8] can theoretically collide — but different args should usually differ."""
        det = DuplicateDetector(threshold=3, deep_equal=False)
        tc1 = FakeToolCall("tool", {"a": "short"})
        tc2 = FakeToolCall("tool", {"a": "completely_different_value"})
        det.check(tc1)
        result = det.check(tc2)
        # These should have different keys (almost certainly)
        assert not result.is_duplicate

    def test_deep_equal_mode_uses_full_args(self):
        det = DuplicateDetector(threshold=3, deep_equal=True)
        tc = FakeToolCall("file_read", {"path": "/tmp/a.txt"})
        result = det.check(tc)
        # Key should contain the full JSON args, not a hash
        assert "/tmp/a.txt" in result.key

    def test_deep_equal_distinguishes_similar_args(self):
        """Deep equal should distinguish args that might hash the same."""
        det = DuplicateDetector(threshold=3, deep_equal=True)
        det.check(FakeToolCall("tool", {"a": 1}))
        result = det.check(FakeToolCall("tool", {"a": 2}))
        assert not result.is_duplicate

    def test_deep_equal_treats_identical_args_as_duplicate(self):
        det = DuplicateDetector(threshold=3, deep_equal=True)
        tc = FakeToolCall("tool", {"x": [1, 2, 3]})
        det.check(tc)
        result = det.check(tc)
        assert result.is_duplicate
        assert result.count == 2

    def test_deep_equal_key_order_invariant(self):
        """JSON serialization with sort_keys should make key order irrelevant."""
        det = DuplicateDetector(threshold=3, deep_equal=True)
        tc1 = FakeToolCall("tool", {"a": 1, "b": 2})
        tc2 = FakeToolCall("tool", {"b": 2, "a": 1})
        det.check(tc1)
        result = det.check(tc2)
        assert result.is_duplicate


class TestDuplicateCheckResult:
    """Tests for DuplicateCheckResult dataclass."""

    def test_fields(self):
        result = DuplicateCheckResult(
            is_duplicate=True, should_skip=False, count=2, key="tool:abc123"
        )
        assert result.is_duplicate
        assert not result.should_skip
        assert result.count == 2
        assert result.key == "tool:abc123"
