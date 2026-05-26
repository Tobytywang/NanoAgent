"""
Tests for Budget Wrap-Up feature.
"""

import pytest

from nano_agent.agent.token_budget import TokenBudget, TokenBudgetConfig


class TestTokenBudgetConfigWrapup:
    """Test wrap-up config fields."""

    def test_default_wrapup_disabled(self):
        config = TokenBudgetConfig()
        assert not config.wrapup_enabled
        assert config.wrapup_threshold == 0.1
        assert config.wrapup_free_round is True
        assert config.wrapup_max_tokens == 2000

    def test_custom_wrapup_config(self):
        config = TokenBudgetConfig(
            wrapup_enabled=True,
            wrapup_threshold=0.2,
            wrapup_free_round=False,
            wrapup_max_tokens=3000,
        )
        assert config.wrapup_enabled
        assert config.wrapup_threshold == 0.2
        assert not config.wrapup_free_round
        assert config.wrapup_max_tokens == 3000


class TestTokenBudgetShouldWrapup:
    """Test should_wrapup() method."""

    def test_disabled_returns_false(self):
        config = TokenBudgetConfig(wrapup_enabled=False)
        budget = TokenBudget(config)
        # Even with budget at 0, wrapup won't trigger
        budget.consume(50000)
        assert not budget.should_wrapup()

    def test_enabled_above_threshold_returns_false(self):
        config = TokenBudgetConfig(initial_budget=10000, wrapup_enabled=True, wrapup_threshold=0.1)
        budget = TokenBudget(config)
        # Remaining: 9000/10000 = 0.9 > 0.1
        budget.consume(1000)
        assert not budget.should_wrapup()

    def test_enabled_at_threshold_returns_true(self):
        config = TokenBudgetConfig(initial_budget=10000, wrapup_enabled=True, wrapup_threshold=0.1)
        budget = TokenBudget(config)
        # Remaining: 1000/10000 = 0.1 <= 0.1
        budget.consume(9000)
        assert budget.should_wrapup()

    def test_enabled_below_threshold_returns_true(self):
        config = TokenBudgetConfig(initial_budget=10000, wrapup_enabled=True, wrapup_threshold=0.1)
        budget = TokenBudget(config)
        # Remaining: 500/10000 = 0.05 < 0.1
        budget.consume(9500)
        assert budget.should_wrapup()

    def test_exhausted_budget_with_wrapup_enabled(self):
        config = TokenBudgetConfig(initial_budget=10000, wrapup_enabled=True, wrapup_threshold=0.1)
        budget = TokenBudget(config)
        budget.consume(10000)
        # Remaining: 0/10000 = 0 <= 0.1
        assert budget.should_wrapup()
        # But also should_summarize (budget truly exhausted)
        assert budget.should_summarize()

    def test_zero_initial_budget_returns_false(self):
        config = TokenBudgetConfig(initial_budget=0, wrapup_enabled=True)
        budget = TokenBudget(config)
        assert not budget.should_wrapup()

    def test_higher_threshold_triggers_earlier(self):
        config = TokenBudgetConfig(initial_budget=10000, wrapup_enabled=True, wrapup_threshold=0.3)
        budget = TokenBudget(config)
        # Remaining: 7000/10000 = 0.7 > 0.3 → False
        budget.consume(3000)
        assert not budget.should_wrapup()
        # Remaining: 3000/10000 = 0.3 <= 0.3 → True
        budget.consume(4000)
        assert budget.should_wrapup()


class TestSmartOptimizationConfigWrapup:
    """Test that wrap-up config fields are properly stored in SmartOptimizationConfig."""

    def test_default_values(self):
        from nano_agent.config.schema import SmartOptimizationConfig
        config = SmartOptimizationConfig()
        assert not config.budget_wrapup_enabled
        assert config.budget_wrapup_threshold == 0.1
        assert config.budget_wrapup_free_round is True
        assert config.budget_wrapup_max_tokens == 2000

    def test_custom_values(self):
        from nano_agent.config.schema import SmartOptimizationConfig
        config = SmartOptimizationConfig(
            budget_wrapup_enabled=True,
            budget_wrapup_threshold=0.2,
            budget_wrapup_free_round=False,
            budget_wrapup_max_tokens=4000,
        )
        assert config.budget_wrapup_enabled
        assert config.budget_wrapup_threshold == 0.2
        assert not config.budget_wrapup_free_round
        assert config.budget_wrapup_max_tokens == 4000


class TestConfigLoaderWrapup:
    """Test that loader properly parses wrap-up config."""

    def test_loader_parses_wrapup_fields(self):
        from nano_agent.config.loader import ConfigLoader
        data = {
            "smart_optimization": {
                "budget_wrapup_enabled": True,
                "budget_wrapup_threshold": 0.2,
                "budget_wrapup_free_round": False,
                "budget_wrapup_max_tokens": 4000,
            }
        }
        config = ConfigLoader._parse_config(data)
        assert config.smart_optimization.budget_wrapup_enabled
        assert config.smart_optimization.budget_wrapup_threshold == 0.2
        assert not config.smart_optimization.budget_wrapup_free_round
        assert config.smart_optimization.budget_wrapup_max_tokens == 4000

    def test_loader_defaults_when_absent(self):
        from nano_agent.config.loader import ConfigLoader
        config = ConfigLoader._parse_config({})
        assert not config.smart_optimization.budget_wrapup_enabled
        assert config.smart_optimization.budget_wrapup_threshold == 0.1
        assert config.smart_optimization.budget_wrapup_free_round is True
        assert config.smart_optimization.budget_wrapup_max_tokens == 2000