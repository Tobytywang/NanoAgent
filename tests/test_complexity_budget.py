"""
Tests for complexity budget profile (v0.7.16).

Verifies that token budget is adjusted based on query complexity,
so simple tasks don't waste full budget.
"""

import pytest

from nano_agent.agent.router import QueryRouter, QueryComplexity, RoutingResult
from nano_agent.agent.token_budget import TokenBudget, TokenBudgetConfig


pytestmark = pytest.mark.unit


class TestRoutingResultBudgetRatio:
    """Test RoutingResult.suggested_budget_ratio field."""

    def test_default_budget_ratio_is_1(self):
        result = RoutingResult(
            complexity=QueryComplexity.COMPLEX,
            reason="test",
            suggested_max_tools=-1,
        )
        assert result.suggested_budget_ratio == 1.0

    def test_custom_budget_ratio(self):
        result = RoutingResult(
            complexity=QueryComplexity.SIMPLE,
            reason="test",
            suggested_max_tools=0,
            suggested_budget_ratio=0.15,
        )
        assert result.suggested_budget_ratio == 0.15


class TestQueryRouterBudgetRatio:
    """Test QueryRouter returns correct budget ratios."""

    def test_simple_query_gets_small_budget(self):
        router = QueryRouter(enabled=True, simple_direct=True)
        result = router.classify("你好")
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.suggested_budget_ratio == 0.15

    def test_moderate_query_gets_medium_budget(self):
        router = QueryRouter(enabled=True, moderate_single_tool=True)
        result = router.classify("读取 config.yaml")
        assert result.complexity == QueryComplexity.MODERATE
        assert result.suggested_budget_ratio == 0.5

    def test_complex_query_gets_full_budget(self):
        router = QueryRouter(enabled=True)
        result = router.classify("分析这个代码的性能问题")
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.suggested_budget_ratio == 1.0

    def test_disabled_routing_returns_full_budget(self):
        router = QueryRouter(enabled=False)
        result = router.classify("你好")
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.suggested_budget_ratio == 1.0

    def test_default_complex_returns_full_budget(self):
        router = QueryRouter(enabled=True)
        result = router.classify("some random query")
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.suggested_budget_ratio == 1.0

    def test_custom_budget_ratios(self):
        router = QueryRouter(
            enabled=True,
            simple_direct=True,
            simple_budget_ratio=0.1,
            moderate_budget_ratio=0.3,
            complex_budget_ratio=0.8,
        )
        simple = router.classify("你好")
        assert simple.suggested_budget_ratio == 0.1

        moderate = router.classify("读取 file.py")
        assert moderate.suggested_budget_ratio == 0.3

        complex_q = router.classify("分析代码")
        assert complex_q.suggested_budget_ratio == 0.8


class TestTokenBudgetSetBudgetRatio:
    """Test TokenBudget.set_budget_ratio() method."""

    def test_set_ratio_adjusts_initial_budget(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=100000))
        budget.set_budget_ratio(0.15, 100000)
        assert budget.initial_budget == 15000
        assert budget.remaining == 15000

    def test_set_ratio_resets_consumed(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=100000))
        budget.consume(50000)
        assert budget._total_consumed == 50000

        budget.set_budget_ratio(0.5, 100000)
        assert budget._total_consumed == 0
        assert budget.remaining == 50000

    def test_set_ratio_resets_warning_state(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=100000))
        budget._last_warning_level = 2
        budget._warnings_issued = 5

        budget.set_budget_ratio(0.15, 100000)
        assert budget._last_warning_level == -1
        assert budget._warnings_issued == 0

    def test_set_ratio_clamps_minimum(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=100000))
        budget.set_budget_ratio(0.01, 100000)
        # Should be clamped to at least 5% of base
        assert budget.initial_budget == int(100000 * 0.05)
        assert budget.remaining == int(100000 * 0.05)

    def test_set_ratio_full_budget(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=100000))
        budget.set_budget_ratio(1.0, 100000)
        assert budget.initial_budget == 100000
        assert budget.remaining == 100000

    def test_set_ratio_moderate_budget(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=50000))
        budget.set_budget_ratio(0.5, 50000)
        assert budget.initial_budget == 25000
        assert budget.remaining == 25000

    def test_budget_ratio_affects_warning_thresholds(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=100000))
        budget.set_budget_ratio(0.15, 100000)
        # 50% warning threshold should now be at 7500 (50% of 15000)
        ratio = budget.remaining / budget.initial_budget
        assert ratio == 1.0  # Fresh budget, full ratio

    def test_budget_ratio_with_different_base(self):
        budget = TokenBudget(TokenBudgetConfig(initial_budget=20000))
        # Use a different base budget than the config default
        budget.set_budget_ratio(0.5, 120000)
        assert budget.initial_budget == 60000
        assert budget.remaining == 60000
