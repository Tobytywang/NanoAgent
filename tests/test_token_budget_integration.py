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
        assert config.initial_budget == 20000  # Updated from 2000 for multi-turn conversations
        assert config.warning_threshold == 0.2
        assert config.force_summarize is True
        assert config.calibration_enabled is True
        assert config.calibration_window == 5
        assert config.min_calibration_samples == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TokenBudgetConfig(
            initial_budget=5000,
            warning_threshold=0.1,
            force_summarize=False,
            calibration_enabled=False,
        )
        assert config.initial_budget == 5000
        assert config.warning_threshold == 0.1
        assert config.force_summarize is False
        assert config.calibration_enabled is False


class TestTokenBudgetBasic:
    """Test basic TokenBudget functionality."""

    def test_initial_state(self):
        """Test initial budget state."""
        budget = TokenBudget()
        assert budget.remaining == 20000  # Updated default
        assert budget.initial_budget == 20000

    def test_consume_tokens(self):
        """Test consuming tokens."""
        budget = TokenBudget()
        budget.consume(500)
        assert budget.remaining == 19500  # 20000 - 500

    def test_consume_more_than_budget(self):
        """Test consuming more than budget."""
        budget = TokenBudget()
        budget.consume(25000)  # More than 20000
        assert budget.remaining == 0  # Should not go negative

    def test_should_warn(self):
        """Test warning threshold."""
        config = TokenBudgetConfig(initial_budget=1000, warning_threshold=0.2)
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
        budget.consume(20000)  # Exhaust full budget
        assert budget.is_exhausted()

    def test_reset(self):
        """Test budget reset."""
        budget = TokenBudget()
        budget.consume(10000)
        budget.reset()
        assert budget.remaining == 20000  # Reset to initial budget

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
        assert budget.remaining == 19850  # 20000 - 150
        assert len(budget.get_usage_history()) == 1

    def test_consume_usage_multiple(self):
        """Test consuming multiple LLMUsage."""
        budget = TokenBudget()
        usage1 = LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage2 = LLMUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)
        budget.consume_usage(usage1)
        budget.consume_usage(usage2)
        assert budget.remaining == 19550  # 20000 - 150 - 300
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
    """Test TokenBudget calibration functionality."""

    def test_calibration_disabled(self):
        """Test that calibration is skipped when disabled."""
        config = TokenBudgetConfig(calibration_enabled=False)
        budget = TokenBudget(config)
        usage = LLMUsage(total_tokens=500)
        budget.consume_usage(usage)
        assert budget.get_calibration_factor() == 1.0

    def test_calibration_needs_min_samples(self):
        """Test that calibration needs minimum samples."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)
        # Only 2 samples
        budget.consume_usage(LLMUsage(total_tokens=100))
        budget.consume_usage(LLMUsage(total_tokens=200))
        assert budget.get_calibration_factor() == 1.0  # Not enough samples

    def test_calibration_with_enough_samples(self):
        """Test calibration with enough samples."""
        config = TokenBudgetConfig(
            initial_budget=1000,  # Expected ~100 per call (1000/10)
            min_calibration_samples=3,
        )
        budget = TokenBudget(config)
        # Actual usage is ~200 per call
        budget.consume_usage(LLMUsage(total_tokens=200))
        budget.consume_usage(LLMUsage(total_tokens=200))
        budget.consume_usage(LLMUsage(total_tokens=200))
        # Calibration factor should be ~2.0 (200/100)
        factor = budget.get_calibration_factor()
        assert factor > 1.5  # Should indicate higher than expected usage

    def test_calibration_factor_lower_usage(self):
        """Test calibration when actual usage is lower than expected."""
        config = TokenBudgetConfig(
            initial_budget=1000,
            min_calibration_samples=3,
        )
        budget = TokenBudget(config)
        # Actual usage is ~50 per call (lower than expected 100)
        budget.consume_usage(LLMUsage(total_tokens=50))
        budget.consume_usage(LLMUsage(total_tokens=50))
        budget.consume_usage(LLMUsage(total_tokens=50))
        factor = budget.get_calibration_factor()
        assert factor < 1.0  # Should indicate lower than expected usage

    def test_reset_clears_calibration(self):
        """Test that reset clears calibration data."""
        budget = TokenBudget()
        budget.consume_usage(LLMUsage(total_tokens=100))
        budget.consume_usage(LLMUsage(total_tokens=200))
        budget.consume_usage(LLMUsage(total_tokens=300))
        budget.reset()
        assert len(budget.get_usage_history()) == 0
        assert budget.get_calibration_factor() == 1.0


class TestTokenBudgetStatus:
    """Test TokenBudget status reporting."""

    def test_get_status_basic(self):
        """Test basic status."""
        budget = TokenBudget()
        status = budget.get_status()
        assert status["initial"] == 20000  # Updated default
        assert status["remaining"] == 20000
        assert status["consumed"] == 0
        assert status["percentage_remaining"] == 100.0

    def test_get_status_after_consumption(self):
        """Test status after consumption."""
        budget = TokenBudget()
        budget.consume(5000)
        status = budget.get_status()
        assert status["remaining"] == 15000  # 20000 - 5000
        assert status["consumed"] == 5000
        assert status["percentage_remaining"] == 75.0

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
        assert budget.remaining == 20000  # Unchanged

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
        assert budget.remaining == 19850  # 20000 - 150
        # Cache tokens should be recorded in history
        history = budget.get_usage_history()
        assert history[0].cache_read_tokens == 50
        assert history[0].cache_write_tokens == 20
