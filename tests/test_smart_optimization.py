"""
Unit tests for v0.7.5 smart optimization features.

Tests for:
- TokenBudget: Token budget tracking
- QueryRouter: Query complexity routing
- ConfidenceParser: Confidence parsing from LLM responses
- SmartOptimizationConfig: Configuration validation
"""

import pytest

from nano_agent.agent.token_budget import TokenBudget, TokenBudgetConfig
from nano_agent.agent.router import QueryRouter, QueryComplexity, RoutingResult
from nano_agent.agent.confidence import ConfidenceParser, ConfidenceResult
from nano_agent.config.schema import SmartOptimizationConfig


# === TokenBudget Tests ===

class TestTokenBudget:
    """Tests for TokenBudget class."""

    def test_initial_state(self):
        """Test initial budget state."""
        budget = TokenBudget()
        assert budget.remaining == 50000  # Updated from 20000 to support longer conversations
        assert budget.initial_budget == 50000
        assert budget._total_consumed == 0

    def test_custom_initial_budget(self):
        """Test custom initial budget."""
        config = TokenBudgetConfig(initial_budget=5000)
        budget = TokenBudget(config)
        assert budget.remaining == 5000
        assert budget.initial_budget == 5000

    def test_consume_tokens(self):
        """Test token consumption."""
        budget = TokenBudget()
        budget.consume(500)
        assert budget.remaining == 49500  # 50000 - 500
        assert budget._total_consumed == 500

    def test_consume_exceeds_budget(self):
        """Test consumption that exceeds budget."""
        budget = TokenBudget()
        budget.consume(55000)  # More than initial (50000)
        assert budget.remaining == 0  # Clamped to 0
        assert budget._total_consumed == 55000  # Total consumed tracks actual consumption

    def test_should_warn(self):
        """Test warning threshold (backward compatible with new thresholds)."""
        config = TokenBudgetConfig(initial_budget=1000, warning_thresholds=[0.2])
        budget = TokenBudget(config)

        # Initially no warning
        assert not budget.should_warn()

        # Consume 80%
        budget.consume(800)
        assert budget.remaining == 200
        assert budget.should_warn()  # 20% remaining

    def test_should_summarize(self):
        """Test summarization trigger."""
        config = TokenBudgetConfig(initial_budget=1000, force_summarize=True)
        budget = TokenBudget(config)

        # Initially no summarize
        assert not budget.should_summarize()

        # Exhaust budget
        budget.consume(1000)
        assert budget.should_summarize()

    def test_should_summarize_disabled(self):
        """Test summarization disabled."""
        config = TokenBudgetConfig(initial_budget=1000, force_summarize=False)
        budget = TokenBudget(config)

        budget.consume(1000)
        assert not budget.should_summarize()

    def test_is_exhausted(self):
        """Test exhaustion check."""
        budget = TokenBudget()
        assert not budget.is_exhausted()

        budget.consume(50000)  # Exhaust full budget
        assert budget.is_exhausted()

    def test_reset(self):
        """Test budget reset."""
        budget = TokenBudget()
        budget.consume(35000)

        budget.reset()
        assert budget.remaining == 50000  # Reset to initial budget
        assert budget._total_consumed == 0

    def test_reset_with_new_budget(self):
        """Test reset with new budget."""
        budget = TokenBudget()
        budget.consume(15000)

        budget.reset(50000)
        assert budget.remaining == 50000
        assert budget.initial_budget == 50000

    def test_get_status(self):
        """Test status retrieval."""
        budget = TokenBudget()
        budget.consume(5000)

        status = budget.get_status()
        assert status["initial"] == 50000
        assert status["remaining"] == 45000
        assert status["consumed"] == 5000
        assert status["percentage_remaining"] == 90.0


# === QueryRouter Tests ===

class TestQueryRouter:
    """Tests for QueryRouter class."""

    def test_simple_greetings(self):
        """Test simple greeting classification."""
        router = QueryRouter()

        greetings = ["你好", "hello", "hi", "Hi!", "你好！"]
        for greeting in greetings:
            result = router.classify(greeting)
            assert result.complexity == QueryComplexity.SIMPLE
            assert result.suggested_max_tools == 0

    def test_simple_thanks(self):
        """Test simple thanks classification."""
        router = QueryRouter()

        thanks = ["谢谢", "thanks", "thank you", "感谢！"]
        for thank in thanks:
            result = router.classify(thank)
            assert result.complexity == QueryComplexity.SIMPLE

    def test_simple_identity(self):
        """Test simple identity questions."""
        router = QueryRouter()

        questions = ["你是谁", "who are you", "你的名字"]
        for q in questions:
            result = router.classify(q)
            assert result.complexity == QueryComplexity.SIMPLE

    def test_complex_multi_step(self):
        """Test complex multi-step queries."""
        router = QueryRouter()

        queries = [
            "分析这个项目的代码结构",
            "实现一个新的功能",
            "重构这个模块",
            "修复这个bug",
        ]
        for q in queries:
            result = router.classify(q)
            assert result.complexity == QueryComplexity.COMPLEX
            assert result.suggested_max_tools == -1

    def test_complex_with_keywords(self):
        """Test complex queries with keywords."""
        router = QueryRouter()

        queries = [
            "读取文件然后分析",
            "查找所有相关的代码",
            "批量处理这些文件",
        ]
        for q in queries:
            result = router.classify(q)
            assert result.complexity == QueryComplexity.COMPLEX

    def test_routing_disabled(self):
        """Test routing disabled."""
        router = QueryRouter(enabled=False)

        result = router.classify("你好")
        assert result.complexity == QueryComplexity.COMPLEX  # Defaults to complex
        assert result.suggested_max_tools == -1

    def test_simple_direct_disabled(self):
        """Test simple direct disabled."""
        router = QueryRouter(enabled=True, simple_direct=False)

        result = router.classify("你好")
        # Should not be classified as simple
        assert result.complexity != QueryComplexity.SIMPLE or result.suggested_max_tools != 0

    def test_is_simple_method(self):
        """Test is_simple convenience method."""
        router = QueryRouter()

        assert router.is_simple("你好")
        assert router.is_simple("hello")
        # "分析代码" matches complex pattern, so not simple
        result = router.classify("分析代码")
        assert result.complexity == QueryComplexity.COMPLEX

    def test_get_max_tools_method(self):
        """Test get_max_tools convenience method."""
        router = QueryRouter()

        assert router.get_max_tools("你好") == 0
        # "分析代码" is complex, so -1 (unlimited)
        result = router.classify("分析代码")
        assert result.suggested_max_tools == -1

    def test_custom_patterns(self):
        """Test custom patterns."""
        router = QueryRouter(
            custom_simple_patterns=[r"^test\s+simple$"]
        )

        result = router.classify("test simple")
        assert result.complexity == QueryComplexity.SIMPLE


# === ConfidenceParser Tests ===

class TestConfidenceParser:
    """Tests for ConfidenceParser class."""

    def test_parse_confidence_marker(self):
        """Test parsing confidence marker."""
        parser = ConfidenceParser()

        response = "The answer is 42. [CONFIDENCE: 0.95]"
        result = parser.parse(response)

        assert result.confidence == 0.95
        assert result.found_markers == True
        assert result.cleaned_response == "The answer is 42."

    def test_parse_can_answer_yes(self):
        """Test parsing can_answer yes."""
        parser = ConfidenceParser()

        response = "The answer is 42. [CAN_ANSWER: yes]"
        result = parser.parse(response)

        assert result.can_answer == True
        assert result.found_markers == True

    def test_parse_can_answer_no(self):
        """Test parsing can_answer no."""
        parser = ConfidenceParser()

        response = "I need more info. [CAN_ANSWER: no]"
        result = parser.parse(response)

        assert result.can_answer == False
        assert result.found_markers == True

    def test_parse_both_markers(self):
        """Test parsing both markers."""
        parser = ConfidenceParser()

        response = "The answer is 42. [CONFIDENCE: 0.85] [CAN_ANSWER: yes]"
        result = parser.parse(response)

        assert result.confidence == 0.85
        assert result.can_answer == True
        assert result.cleaned_response == "The answer is 42."

    def test_parse_no_markers(self):
        """Test parsing without markers."""
        parser = ConfidenceParser()

        response = "The answer is 42."
        result = parser.parse(response)

        assert result.confidence == 1.0  # Default
        assert result.can_answer == True  # Default
        assert result.found_markers == False
        assert result.cleaned_response == "The answer is 42."

    def test_parse_invalid_confidence(self):
        """Test parsing invalid confidence value."""
        parser = ConfidenceParser()

        response = "The answer. [CONFIDENCE: invalid]"
        result = parser.parse(response)

        assert result.confidence == 1.0  # Default on parse error

    def test_parse_confidence_clamping(self):
        """Test confidence value clamping."""
        parser = ConfidenceParser()

        # Too high
        result = parser.parse("[CONFIDENCE: 2.0]")
        assert result.confidence == 1.0

        # Too low
        result = parser.parse("[CONFIDENCE: -0.5]")
        assert result.confidence == 0.0

    def test_should_stop_early(self):
        """Test early stopping decision."""
        parser = ConfidenceParser(threshold=0.9)

        # High confidence, can answer -> stop
        should_stop, result = parser.should_stop_early(
            "Answer. [CONFIDENCE: 0.95] [CAN_ANSWER: yes]"
        )
        assert should_stop == True

        # High confidence, cannot answer -> no stop
        should_stop, result = parser.should_stop_early(
            "Answer. [CONFIDENCE: 0.95] [CAN_ANSWER: no]"
        )
        assert should_stop == False

        # Low confidence -> no stop
        should_stop, result = parser.should_stop_early(
            "Answer. [CONFIDENCE: 0.5] [CAN_ANSWER: yes]"
        )
        assert should_stop == False

    def test_custom_threshold(self):
        """Test custom threshold."""
        parser = ConfidenceParser(threshold=0.7)

        # 0.75 >= 0.7 threshold
        should_stop, _ = parser.should_stop_early(
            "Answer. [CONFIDENCE: 0.75] [CAN_ANSWER: yes]"
        )
        assert should_stop == True

    def test_case_insensitive(self):
        """Test case insensitive parsing."""
        parser = ConfidenceParser()

        result = parser.parse("[confidence: 0.9] [can_answer: YES]")
        assert result.confidence == 0.9
        assert result.can_answer == True

    def test_preserves_newlines(self):
        """Test that newlines are preserved in cleaned response.

        This is a regression test for the bug where all whitespace
        (including newlines) was collapsed to single spaces.
        """
        parser = ConfidenceParser()

        response = """## Header

### Subheader

**Bold text**:
- Item 1
- Item 2

[CONFIDENCE: 1.0] [CAN_ANSWER: yes]"""

        result = parser.parse(response)

        # Newlines should be preserved
        assert "\n" in result.cleaned_response
        assert "## Header" in result.cleaned_response
        assert "### Subheader" in result.cleaned_response
        assert "- Item 1" in result.cleaned_response
        assert "- Item 2" in result.cleaned_response

        # Confidence markers should be removed
        assert "[CONFIDENCE:" not in result.cleaned_response
        assert "[CAN_ANSWER:" not in result.cleaned_response


# === SmartOptimizationConfig Tests ===

class TestSmartOptimizationConfig:
    """Tests for SmartOptimizationConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SmartOptimizationConfig()

        # Confidence
        assert config.confidence_enabled == True
        assert config.confidence_threshold == 0.9

        # Budget (v0.7.8 updated)
        assert config.budget_enabled == True
        assert config.initial_budget == 50000  # Increased from 20000 to support longer conversations
        assert config.budget_warning_thresholds == [0.5, 0.3, 0.2, 0.1]  # Multi-level thresholds
        assert config.budget_warning_mode == "console"
        assert config.budget_warning_interval == 1
        assert config.budget_force_summarize == True
        assert config.budget_llm_summary_enabled == True  # LLM summary enabled by default

        # Routing
        assert config.routing_enabled == True
        assert config.routing_simple_direct == True
        assert config.routing_moderate_single_tool == True

        # Tool processor
        assert config.tool_processor_enabled == True
        assert config.tool_processor_max_output_tokens == 300

    def test_all_disabled(self):
        """Test configuration with all features disabled."""
        config = SmartOptimizationConfig(
            confidence_enabled=False,
            budget_enabled=False,
            routing_enabled=False,
            tool_processor_enabled=False,
        )

        assert config.confidence_enabled == False
        assert config.budget_enabled == False
        assert config.routing_enabled == False
        assert config.tool_processor_enabled == False

    def test_custom_threshold(self):
        """Test custom confidence threshold."""
        config = SmartOptimizationConfig(confidence_threshold=0.8)
        assert config.confidence_threshold == 0.8

    def test_custom_budget(self):
        """Test custom budget values."""
        config = SmartOptimizationConfig(
            initial_budget=5000,
            budget_warning_thresholds=[0.4, 0.2],
            budget_warning_mode="silent",
        )
        assert config.initial_budget == 5000
        assert config.budget_warning_thresholds == [0.4, 0.2]
        assert config.budget_warning_mode == "silent"


# === Integration Tests ===

class TestSmartOptimizationIntegration:
    """Integration tests for smart optimization."""

    def test_budget_and_router_work_together(self):
        """Test budget and router integration."""
        budget = TokenBudget(TokenBudgetConfig(initial_budget=1000))
        router = QueryRouter()

        # Simple query -> no budget consumption
        result = router.classify("你好")
        if result.complexity == QueryComplexity.SIMPLE:
            # Should not consume budget
            assert budget.remaining == 1000

    def test_confidence_parser_with_threshold(self):
        """Test confidence parser respects threshold."""
        parser = ConfidenceParser(threshold=0.85)

        # Below threshold
        should_stop, _ = parser.should_stop_early(
            "[CONFIDENCE: 0.80] [CAN_ANSWER: yes]"
        )
        assert should_stop == False

        # Above threshold
        should_stop, _ = parser.should_stop_early(
            "[CONFIDENCE: 0.90] [CAN_ANSWER: yes]"
        )
        assert should_stop == True