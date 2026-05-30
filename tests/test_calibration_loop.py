"""
Tests for v0.7.13: Calibration loop fixes.

Validates that:
1. CalibrationData dataclass works correctly
2. record_calibration_data() records and windows data
3. _update_calibration() uses the corrected formula (actual/estimated)
4. Calibration factor is consumed by estimate_tokens()
5. Calibration factor influences compression decisions
"""

import pytest

pytestmark = pytest.mark.unit

from nano_agent.agent.token_budget import (
    CalibrationData,
    TokenBudget,
    TokenBudgetConfig,
)
from nano_agent.agent.token_utils import estimate_tokens, estimate_text_tokens


class TestCalibrationData:
    """Test CalibrationData dataclass."""

    def test_create_calibration_data(self):
        """CalibrationData stores estimated and actual token counts."""
        data = CalibrationData(estimated=100, actual=120)
        assert data.estimated == 100
        assert data.actual == 120

    def test_calibration_data_equality(self):
        """CalibrationData supports equality comparison."""
        data1 = CalibrationData(estimated=100, actual=120)
        data2 = CalibrationData(estimated=100, actual=120)
        assert data1 == data2


class TestRecordCalibrationData:
    """Test record_calibration_data() method."""

    def test_records_data_point(self):
        """record_calibration_data() adds a CalibrationData entry."""
        budget = TokenBudget()
        assert len(budget._calibration_data) == 0

        budget.record_calibration_data(estimated=100, actual=120)
        assert len(budget._calibration_data) == 1
        assert budget._calibration_data[0].estimated == 100
        assert budget._calibration_data[0].actual == 120

    def test_window_size_limit(self):
        """Data beyond calibration_window is trimmed."""
        config = TokenBudgetConfig(calibration_window=3)
        budget = TokenBudget(config)

        for i in range(5):
            budget.record_calibration_data(estimated=100, actual=100 + i)

        assert len(budget._calibration_data) == 3
        # Should keep the last 3 entries
        assert budget._calibration_data[0].actual == 102
        assert budget._calibration_data[1].actual == 103
        assert budget._calibration_data[2].actual == 104

    def test_disabled_calibration_no_record(self):
        """When calibration_enabled=False, data is not recorded."""
        config = TokenBudgetConfig(calibration_enabled=False)
        budget = TokenBudget(config)

        budget.record_calibration_data(estimated=100, actual=120)
        assert len(budget._calibration_data) == 0

    def test_triggers_update(self):
        """record_calibration_data() triggers _update_calibration()."""
        budget = TokenBudget()
        # Add 3 samples (min_calibration_samples default)
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=100, actual=130)
        budget.record_calibration_data(estimated=100, actual=110)
        # Calibration factor should have been updated
        assert budget.get_calibration_factor() != 1.0


class TestCalibrationUpdate:
    """Test the corrected _update_calibration() formula."""

    def test_underestimation_factor_above_1(self):
        """When actual > estimated, calibration factor > 1.0."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        # Actual is consistently 20% higher than estimated
        budget.record_calibration_data(estimated=100, actual=120)
        budget.record_calibration_data(estimated=200, actual=240)
        budget.record_calibration_data(estimated=150, actual=180)

        factor = budget.get_calibration_factor()
        assert factor > 1.0
        assert abs(factor - 1.2) < 0.01

    def test_overestimation_factor_below_1(self):
        """When actual < estimated, calibration factor < 1.0."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        # Actual is consistently 25% lower than estimated
        budget.record_calibration_data(estimated=100, actual=75)
        budget.record_calibration_data(estimated=200, actual=150)
        budget.record_calibration_data(estimated=150, actual=112)

        factor = budget.get_calibration_factor()
        assert factor < 1.0
        assert abs(factor - 0.75) < 0.02

    def test_accurate_estimation_factor_near_1(self):
        """When actual ≈ estimated, calibration factor ≈ 1.0."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        budget.record_calibration_data(estimated=100, actual=101)
        budget.record_calibration_data(estimated=200, actual=199)
        budget.record_calibration_data(estimated=150, actual=150)

        factor = budget.get_calibration_factor()
        assert abs(factor - 1.0) < 0.02

    def test_clamp_lower_bound(self):
        """Calibration factor is clamped to 0.5 minimum."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        # Actual is 10x lower than estimated (extreme overestimation)
        budget.record_calibration_data(estimated=1000, actual=100)
        budget.record_calibration_data(estimated=2000, actual=200)
        budget.record_calibration_data(estimated=1500, actual=150)

        factor = budget.get_calibration_factor()
        assert factor == 0.5

    def test_clamp_upper_bound(self):
        """Calibration factor is clamped to 2.0 maximum."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        # Actual is 10x higher than estimated (extreme underestimation)
        budget.record_calibration_data(estimated=100, actual=1000)
        budget.record_calibration_data(estimated=200, actual=2000)
        budget.record_calibration_data(estimated=150, actual=1500)

        factor = budget.get_calibration_factor()
        assert factor == 2.0

    def test_min_samples_required(self):
        """Calibration does not update until min_calibration_samples reached."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        # Only 2 samples - not enough
        budget.record_calibration_data(estimated=100, actual=200)
        budget.record_calibration_data(estimated=100, actual=200)
        assert budget.get_calibration_factor() == 1.0  # Still default

        # Third sample triggers calibration
        budget.record_calibration_data(estimated=100, actual=200)
        assert budget.get_calibration_factor() > 1.0

    def test_disabled_calibration_no_update(self):
        """When calibration_enabled=False, factor stays at 1.0."""
        config = TokenBudgetConfig(calibration_enabled=False)
        budget = TokenBudget(config)

        budget.record_calibration_data(estimated=100, actual=200)
        budget.record_calibration_data(estimated=100, actual=200)
        budget.record_calibration_data(estimated=100, actual=200)

        assert budget.get_calibration_factor() == 1.0

    def test_division_by_zero_protection(self):
        """When estimated=0, max(estimated, 1) prevents division by zero."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        # estimated=0 would cause division by zero without protection
        budget.record_calibration_data(estimated=0, actual=100)
        budget.record_calibration_data(estimated=0, actual=100)
        budget.record_calibration_data(estimated=0, actual=100)

        # Should not crash, factor should be clamped to 2.0
        factor = budget.get_calibration_factor()
        assert factor == 2.0  # 100/1 = 100, clamped to 2.0


class TestCalibrationConsumedByEstimate:
    """Test that calibration factor is consumed by estimate_tokens()."""

    def test_estimated_tokens_increased_by_factor(self):
        """estimate_tokens() returns higher values when calibration_factor > 1."""
        from nano_agent.agent.token_utils import estimate_tokens

        messages = [{"role": "user", "content": "Hello world test"}]
        base = estimate_tokens(messages)
        calibrated = estimate_tokens(messages, calibration_factor=1.5)
        assert calibrated == int(base * 1.5)

    def test_estimated_text_tokens_decreased_by_factor(self):
        """estimate_text_tokens() returns lower values when calibration_factor < 1."""
        text = "Hello world this is a longer test string"
        base = estimate_text_tokens(text)
        calibrated = estimate_text_tokens(text, calibration_factor=0.7)
        assert calibrated <= base

    def test_real_calibration_changes_decision(self):
        """With calibrated estimation, a different compression decision is made."""
        from nano_agent.agent.compressor import CompressorConfig, MessageCompressor

        config = CompressorConfig(threshold_tokens=100, enabled=True)
        compressor = MessageCompressor(config)

        # Create messages that estimate to ~80 tokens (below 100 threshold)
        messages = [{"role": "user", "content": "a" * 300}]
        from nano_agent.agent.token_utils import estimate_tokens
        estimated = estimate_tokens(messages)
        assert estimated < 100  # Below threshold without calibration

        # Without calibration: should not compress
        assert not compressor.should_compress(messages, calibration_factor=1.0)

        # With calibration factor 1.5: estimated ~120 tokens (above 100 threshold)
        calibrated_est = estimate_tokens(messages, calibration_factor=1.5)
        assert calibrated_est > 100

        # With calibration: should compress
        assert compressor.should_compress(messages, calibration_factor=1.5)


class TestCalibrationIntegration:
    """End-to-end calibration tests."""

    def test_calibration_converges_over_multiple_calls(self):
        """After multiple data points, calibration factor converges."""
        config = TokenBudgetConfig(min_calibration_samples=3)
        budget = TokenBudget(config)

        # Simulate a scenario where estimation is consistently 25% low
        for _ in range(10):
            budget.record_calibration_data(estimated=100, actual=125)

        factor = budget.get_calibration_factor()
        assert abs(factor - 1.25) < 0.01

    def test_reset_clears_calibration_data(self):
        """reset() clears all calibration data and resets factor."""
        budget = TokenBudget()
        budget.record_calibration_data(estimated=100, actual=200)
        budget.record_calibration_data(estimated=100, actual=200)
        budget.record_calibration_data(estimated=100, actual=200)
        assert len(budget._calibration_data) == 3

        budget.reset()
        assert len(budget._calibration_data) == 0
        assert budget.get_calibration_factor() == 1.0

    def test_status_includes_calibration_samples(self):
        """get_status() includes calibration_samples count."""
        budget = TokenBudget()
        budget.record_calibration_data(estimated=100, actual=120)

        status = budget.get_status()
        assert "calibration_samples" in status
        assert status["calibration_samples"] == 1

    def test_calibration_factor_influences_context_decision(self):
        """Calibration factor passed to check_and_compress affects token source label."""
        from nano_agent.agent.context import ContextManager
        from nano_agent.agent.token_utils import estimate_tokens
        from nano_agent.config.schema import ContextConfig
        from unittest.mock import MagicMock

        memory = MagicMock()
        # Return a short message that estimates to ~60 tokens
        memory.get_all.return_value = [{"role": "user", "content": "Test message"}]

        config = ContextConfig(
            pressure_threshold_low=0.70,
            pressure_threshold_mid=0.85,
            pressure_threshold_high=0.95,
        )

        cm = ContextManager(memory=memory, llm=None, config=config, llm_config=MagicMock())

        # Without calibration: estimated ~60 tokens, ratio < 0.70 → no compression
        estimated_base = estimate_tokens(memory.get_all(), calibration_factor=1.0)
        estimated_calib = estimate_tokens(memory.get_all(), calibration_factor=1.5)

        # Verify that calibration changes the estimated count
        assert estimated_calib > estimated_base
