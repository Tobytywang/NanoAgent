"""
Tests for Token Budget with LLMUsage integration.
"""

import pytest

from nano_agent.agent.token_budget import TokenBudget, TokenBudgetConfig
from nano_agent.llm.base import LLMUsage


class TestTokenBudgetConfig:
    """Test TokenBudgetConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TokenBudgetConfig()
        assert config.initial_budget == 50000  # Updated from 20000 for longer conversations
        assert config.warning_thresholds == [0.5, 0.3, 0.2, 0.1]  # Multi-level thresholds (v0.7.8)
        assert config.warning_mode == "console"
        assert config.warning_interval == 1
        assert config.force_summarize is True
        assert config.llm_summary_enabled is True  # LLM summary enabled by default (v0.7.8)
        assert config.calibration_enabled is True
        assert config.calibration_window == 5
        assert config.min_calibration_samples == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TokenBudgetConfig(
            initial_budget=5000,
            warning_thresholds=[0.4, 0.2],
            warning_mode="silent",
            warning_interval=2,
            force_summarize=False,
            llm_summary_enabled=False,
            calibration_enabled=False,
        )
        assert config.initial_budget == 5000
        assert config.warning_thresholds == [0.4, 0.2]
        assert config.warning_mode == "silent"
        assert config.warning_interval == 2
        assert config.force_summarize is False
        assert config.llm_summary_enabled is False
        assert config.calibration_enabled is False


class TestTokenBudgetBasic:
    """Test basic TokenBudget functionality."""

    def test_initial_state(self):
        """Test initial budget state."""
        budget = TokenBudget()
        assert budget.remaining == 50000  # Updated default
        assert budget.initial_budget == 50000

    def test_consume_tokens(self):
        """Test consuming tokens."""
        budget = TokenBudget()
        budget.consume(500)
        assert budget.remaining == 49500  # 50000 - 500

    def test_consume_more_than_budget(self):
        """Test consuming more than budget."""
        budget = TokenBudget()
        budget.consume(55000)  # More than 50000
        assert budget.remaining == 0  # Should not go negative

    def test_should_warn(self):
        """Test warning threshold (backward compatible with new thresholds)."""
        config = TokenBudgetConfig(initial_budget=1000, warning_thresholds=[0.2])
        budget = TokenBudget(config)
        assert not budget.should_warn()  # 1000 remaining, 20% threshold = 200
        budget.consume(800)  # 200 remaining
        assert budget.should_warn()  # 200/1000 = 0.2 <= 0.2

    def test_should_summarize(self):
        """Test summarize trigger."""
        config = TokenBudgetConfig(initial_budget=1000, force_summarize=True)
        budget = TokenBudget(config)
        assert not budget.should_summarize()
        budget.consume(1000)
        assert budget.should_summarize()

    def test_is_exhausted(self):
        """Test exhaustion check."""
        budget = TokenBudget()
        assert not budget.is_exhausted()
        budget.consume(50000)  # Exhaust full budget
        assert budget.is_exhausted()

    def test_reset(self):
        """Test budget reset."""
        budget = TokenBudget()
        budget.consume(30000)
        budget.reset()
        assert budget.remaining == 50000  # Reset to initial budget

    def test_reset_with_new_budget(self):
        """Test reset with new budget."""
        budget = TokenBudget()
        budget.consume(10000)
        budget.reset(50000)
        assert budget.remaining == 50000
        assert budget.initial_budget == 50000


class TestTokenBudgetLLMUsageIntegration:
    """Test TokenBudget with LLMUsage integration."""

    def test_consume_usage_basic(self):
        """Test consuming LLMUsage."""
        budget = TokenBudget()
        usage = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        budget.consume_usage(usage)
        assert budget.remaining == 49850  # 50000 - 150
        assert len(budget.get_usage_history()) == 1

    def test_consume_usage_multiple(self):
        """Test consuming multiple LLMUsage."""
        budget = TokenBudget()
        usage1 = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage2 = LLMUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)
        budget.consume_usage(usage1)
        budget.consume_usage(usage2)
        assert budget.remaining == 49550  # 50000 - 150 - 300
        assert len(budget.get_usage_history()) == 2

    def test_usage_history_window(self):
        """Test that usage history is limited to window size."""
        config = TokenBudgetConfig(calibration_window=3)
        budget = TokenBudget(config)
        for i in range(5):
            usage = LLMUsage(total_tokens=100 * (i + 1))
            budget.consume_usage(usage)
        # Should only keep last 3
        assert len(budget.get_usage_history()) == 3

    def test_get_average_usage(self):
        """Test average usage calculation."""
        budget = TokenBudget()
        usage1 = LLMUsage(total_tokens=100)
        usage2 = LLMUsage(total_tokens=200)
        usage3 = LLMUsage(total_tokens=300)
        budget.consume_usage(usage1)
        budget.consume_usage(usage2)
        budget.consume_usage(usage3)
        assert budget.get_average_usage() == 200.0

    def test_get_average_usage_empty(self):
        """Test average usage with no history."""
        budget = TokenBudget()
        assert budget.get_average_usage() == 0.0


class TestTokenBudgetCalibration:
    """Test TokenBudget calibration functionality (v0.7.13: corrected formula)."""

    def test_calibration_disabled(self):
        """Test that calibration is skipped when disabled."""
        config = TokenBudgetConfig(calibration_enabled=False)
        budget = TokenBudget(config)
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=120)
        assert budget.get_calibration_factor() == 1.0

    def test_calibration_needs_min_samples(self):
        """Test that calibration needs minimum samples."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)
        # Only 2 samples
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=120)
        assert budget.get_calibration_factor() == 1.0  # Not enough samples

    def test_calibration_with_enough_samples(self):
        """Test calibration with enough samples using corrected formula."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)
        # Actual is 20% higher than estimated → factor should be ~1.2
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=120)
        factor = budget.get_calibration_factor()
        assert abs(factor - 1.2) < 0.01

    def test_calibration_factor_lower_usage(self):
        """Test calibration when actual is lower than estimated."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)
        # Actual is 50% of estimated → factor should be ~0.5 (clamped)
        budget.record_calibration_data(estimated=100, actual=50)
        budget.record_calibration_data(estimated=100, actual=50)
        budget.record_calibration_data(estimated=100, actual=50)
        factor = budget.get_calibration_factor()
        assert factor == 0.5  # Clamped to lower bound

    def test_reset_clears_calibration(self):
        """Test that reset clears calibration data."""
        budget = TokenBudget()
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=120)
        budget.reset()
        assert len(budget._calibration_data) == 0
        assert budget.get_calibration_factor() == 1.0

    def test_old_consume_usage_still_works(self):
        """consume_usage() still records usage history (backward compat)."""
        budget = TokenBudget()
        budget.consume_usage(LLMUsage(total_tokens=100))
        budget.consume_usage(LLMUsage(total_tokens=200))
        assert len(budget.get_usage_history()) == 2


class TestTokenBudgetStatus:
    """Test TokenBudget status reporting."""

    def test_get_status_basic(self):
        """Test basic status."""
        budget = TokenBudget()
        status = budget.get_status()
        assert status["initial"] == 50000  # Updated default
        assert status["remaining"] == 50000
        assert status["consumed"] == 0
        assert status["percentage_remaining"] == 100.0

    def test_get_status_after_consumption(self):
        """Test status after consumption."""
        budget = TokenBudget()
        budget.consume(10000)
        status = budget.get_status()
        assert status["remaining"] == 40000  # 50000 - 10000
        assert status["consumed"] == 10000
        assert status["percentage_remaining"] == 80.0

    def test_get_status_with_calibration(self):
        """Test status includes calibration info."""
        budget = TokenBudget()
        budget.consume_usage(LLMUsage(total_tokens=100))
        budget.consume_usage(LLMUsage(total_tokens=200))
        budget.consume_usage(LLMUsage(total_tokens=300))
        status = budget.get_status()
        assert "calibration_factor" in status
        assert "average_usage" in status
        assert "samples_collected" in status
        assert status["samples_collected"] == 3
        assert status["average_usage"] == 200.0


class TestTokenBudgetEdgeCases:
    """Test edge cases for TokenBudget."""

    def test_zero_initial_budget(self):
        """Test with zero initial budget."""
        config = TokenBudgetConfig(initial_budget=0)
        budget = TokenBudget(config)
        assert budget.is_exhausted()
        assert not budget.should_warn()  # Avoid division by zero

    def test_consume_zero_tokens(self):
        """Test consuming zero tokens."""
        budget = TokenBudget()
        budget.consume(0)
        assert budget.remaining == 50000  # Unchanged

    def test_consume_usage_with_cache_tokens(self):
        """Test consuming LLMUsage with cache tokens."""
        budget = TokenBudget()
        usage = LLMUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=50,
            cache_write_tokens=20,
        )
        budget.consume_usage(usage)
        assert budget.remaining == 49850  # 50000 - 150
        # Cache tokens should be recorded in history
        history = budget.get_usage_history()
        assert history[0].cache_read_tokens == 50
        assert history[0].cache_write_tokens == 20


class TestTokenBudgetProgressiveWarnings:
    """Test progressive warning functionality (v0.7.8)."""

    def test_check_warning_no_warning_initially(self):
        """Test no warning at full budget."""
        config = TokenBudgetConfig(initial_budget=1000)
        budget = TokenBudget(config)

        warning = budget.check_warning(current_iteration=1)
        assert warning is None

    def test_check_warning_at_50_percent(self):
        """Test warning at 50% threshold."""
        config = TokenBudgetConfig(
            initial_budget=1000,
            warning_thresholds=[0.5, 0.3, 0.2, 0.1]
        )
        budget = TokenBudget(config)

        budget.consume(500)  # 50% remaining
        warning = budget.check_warning(current_iteration=1)

        assert warning is not None
        assert warning["level"] == 0
        assert warning["threshold"] == 0.5
        assert 0.49 <= warning["remaining_ratio"] <= 0.51

    def test_check_warning_progressive_levels(self):
        """Test progressive warning levels."""
        config = TokenBudgetConfig(
            initial_budget=1000,
            warning_thresholds=[0.5, 0.3, 0.2, 0.1]
        )
        budget = TokenBudget(config)

        # Level 0: 50%
        budget.consume(500)
        warning = budget.check_warning(current_iteration=1)
        assert warning["level"] == 0

        # Level 1: 30%
        budget.consume(200)  # 300 remaining = 30%
        warning = budget.check_warning(current_iteration=2)
        assert warning["level"] == 1

        # Level 2: 20%
        budget.consume(100)  # 200 remaining = 20%
        warning = budget.check_warning(current_iteration=3)
        assert warning["level"] == 2

        # Level 3: 10%
        budget.consume(100)  # 100 remaining = 10%
        warning = budget.check_warning(current_iteration=4)
        assert warning["level"] == 3

    def test_check_warning_no_duplicate(self):
        """Test no duplicate warnings at same level."""
        config = TokenBudgetConfig(
            initial_budget=1000,
            warning_thresholds=[0.5]
        )
        budget = TokenBudget(config)

        budget.consume(500)  # 50% remaining
        warning1 = budget.check_warning(current_iteration=1)
        assert warning1 is not None

        # Same level, no new warning
        warning2 = budget.check_warning(current_iteration=2)
        assert warning2 is None

    def test_check_warning_interval(self):
        """Test warning interval prevents spam."""
        config = TokenBudgetConfig(
            initial_budget=1000,
            warning_thresholds=[0.5, 0.3],
            warning_interval=2  # Need 2 iterations between warnings
        )
        budget = TokenBudget(config)

        budget.consume(500)  # 50%
        # First warning at iteration 2 (since 2 - 0 >= 2)
        warning = budget.check_warning(current_iteration=2)
        assert warning is not None
        assert warning["level"] == 0

        budget.consume(200)  # 30%
        # Same iteration, should be blocked by interval
        warning = budget.check_warning(current_iteration=2)
        assert warning is None

        # Next iteration, still blocked (3 - 2 = 1 < 2)
        warning = budget.check_warning(current_iteration=3)
        assert warning is None

        # Fourth iteration, interval passed (4 - 2 = 2 >= 2)
        warning = budget.check_warning(current_iteration=4)
        assert warning is not None
        assert warning["level"] == 1

    def test_warning_message_format(self):
        """Test warning message formatting."""
        config = TokenBudgetConfig(initial_budget=1000)
        budget = TokenBudget(config)

        budget.consume(500)  # 50%
        warning = budget.check_warning(current_iteration=1)

        assert "50%" in warning["message"]
        assert "⚠️" in warning["message"] or "⚡" in warning["message"]

    def test_silent_mode(self):
        """Test silent warning mode."""
        config = TokenBudgetConfig(
            initial_budget=1000,
            warning_mode="silent"
        )
        budget = TokenBudget(config)

        budget.consume(500)
        warning = budget.check_warning(current_iteration=1)

        # Warning still returned, but mode is silent
        assert warning is not None
        assert budget.config.warning_mode == "silent"

    def test_reset_clears_warning_state(self):
        """Test reset clears warning state."""
        config = TokenBudgetConfig(initial_budget=1000)
        budget = TokenBudget(config)

        budget.consume(500)
        budget.check_warning(current_iteration=1)
        assert budget._warnings_issued == 1

        budget.reset()
        assert budget._last_warning_level == -1
        assert budget._warnings_issued == 0
        assert budget._last_warning_iteration == 0

    def test_get_status_includes_warning_state(self):
        """Test get_status includes warning state."""
        config = TokenBudgetConfig(initial_budget=1000)
        budget = TokenBudget(config)

        budget.consume(500)
        budget.check_warning(current_iteration=1)

        status = budget.get_status()
        assert "warnings_issued" in status
        assert "last_warning_level" in status
        assert status["warnings_issued"] == 1
        assert status["last_warning_level"] == 0
