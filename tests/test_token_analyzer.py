"""
Tests for TokenAnalyzer.
"""

import pytest

from nano_agent.monitoring.token_analyzer import (
    TokenCategory,
    TokenBreakdown,
    ToolTokenUsage,
    TokenAnalyzer,
)


class TestTokenCategory:
    """Tests for TokenCategory enum."""

    def test_category_values(self):
        """Test category enum values."""
        assert TokenCategory.SYSTEM.value == "system"
        assert TokenCategory.TOOLS.value == "tools"
        assert TokenCategory.HISTORY.value == "history"
        assert TokenCategory.RESPONSE.value == "response"
        assert TokenCategory.COMPRESSED.value == "compressed"


class TestTokenBreakdown:
    """Tests for TokenBreakdown dataclass."""

    def test_create_breakdown(self):
        """Test creating a breakdown."""
        breakdown = TokenBreakdown(
            category=TokenCategory.SYSTEM,
            tokens=100,
            percentage=50.0,
            details={"sub": 50},
        )
        assert breakdown.category == TokenCategory.SYSTEM
        assert breakdown.tokens == 100
        assert breakdown.percentage == 50.0
        assert breakdown.details == {"sub": 50}

    def test_default_details(self):
        """Test default empty details."""
        breakdown = TokenBreakdown(
            category=TokenCategory.TOOLS,
            tokens=50,
            percentage=25.0,
        )
        assert breakdown.details == {}


class TestToolTokenUsage:
    """Tests for ToolTokenUsage dataclass."""

    def test_create_usage(self):
        """Test creating tool usage."""
        usage = ToolTokenUsage(
            tool_name="file_read",
            input_tokens=10,
            output_tokens=100,
            call_count=2,
        )
        assert usage.tool_name == "file_read"
        assert usage.input_tokens == 10
        assert usage.output_tokens == 100
        assert usage.call_count == 2


class TestTokenAnalyzer:
    """Tests for TokenAnalyzer class."""

    def test_init(self):
        """Test analyzer initialization."""
        analyzer = TokenAnalyzer()
        assert analyzer._category_totals[TokenCategory.SYSTEM] == 0
        assert analyzer._category_totals[TokenCategory.TOOLS] == 0
        assert len(analyzer._tool_token_usage) == 0

    def test_analyze_llm_call_basic(self):
        """Test basic LLM call analysis."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
        )

        # Should have system and history tokens
        assert analyzer._category_totals[TokenCategory.SYSTEM] > 0
        assert analyzer._category_totals[TokenCategory.HISTORY] > 0
        assert analyzer._category_totals[TokenCategory.RESPONSE] == 50

    def test_analyze_llm_call_with_tools(self):
        """Test LLM call analysis with tool output."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=200,
            completion_tokens=100,
            input_messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "tool", "name": "file_read", "content": "File content here"},
            ],
            tool_calls=[{"name": "shell_exec", "arguments": {"cmd": "ls"}}],
        )

        # Should have tool tokens
        assert analyzer._category_totals[TokenCategory.TOOLS] > 0
        # Tool should be recorded
        assert "file_read" in analyzer._tool_token_usage
        assert "shell_exec" in analyzer._tool_token_usage

    def test_get_breakdown_empty(self):
        """Test breakdown with no data."""
        analyzer = TokenAnalyzer()
        breakdown = analyzer.get_breakdown()
        assert breakdown == []

    def test_get_breakdown_with_data(self):
        """Test breakdown with data."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Hello"},
            ],
        )

        breakdown = analyzer.get_breakdown()
        assert len(breakdown) > 0

        # Check breakdown structure
        for b in breakdown:
            assert isinstance(b, TokenBreakdown)
            assert b.tokens > 0
            assert b.percentage >= 0

    def test_get_breakdown_sorted(self):
        """Test breakdown is sorted by tokens."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[
                {"role": "system", "content": "System prompt here"},
                {"role": "user", "content": "Hi"},
            ],
        )

        breakdown = analyzer.get_breakdown()
        tokens = [b.tokens for b in breakdown if b.category != TokenCategory.COMPRESSED]

        # Should be sorted descending
        assert tokens == sorted(tokens, reverse=True)

    def test_get_tool_ranking_empty(self):
        """Test tool ranking with no data."""
        analyzer = TokenAnalyzer()
        ranking = analyzer.get_tool_ranking()
        assert ranking == []

    def test_get_tool_ranking_with_data(self):
        """Test tool ranking with data."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=200,
            completion_tokens=100,
            input_messages=[
                {"role": "tool", "name": "file_read", "content": "Content 1"},
                {"role": "tool", "name": "file_read", "content": "Content 2"},
                {"role": "tool", "name": "shell_exec", "content": "Output"},
            ],
            tool_calls=[
                {"name": "file_read", "arguments": {"path": "a.py"}},
                {"name": "file_read", "arguments": {"path": "b.py"}},
            ],
        )

        ranking = analyzer.get_tool_ranking()
        assert len(ranking) > 0

        # Should be sorted by total tokens
        for i in range(len(ranking) - 1):
            total1 = ranking[i].input_tokens + ranking[i].output_tokens
            total2 = ranking[i + 1].input_tokens + ranking[i + 1].output_tokens
            assert total1 >= total2

    def test_get_tool_ranking_limit(self):
        """Test tool ranking limit."""
        analyzer = TokenAnalyzer()

        # Add many tools
        for i in range(15):
            analyzer.analyze_llm_call(
                prompt_tokens=100,
                completion_tokens=50,
                input_messages=[
                    {"role": "tool", "name": f"tool_{i}", "content": f"Output {i}"},
                ],
            )

        ranking = analyzer.get_tool_ranking(limit=5)
        assert len(ranking) == 5

    def test_get_iteration_breakdowns(self):
        """Test iteration breakdowns."""
        analyzer = TokenAnalyzer()

        # First iteration
        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[{"role": "system", "content": "Sys"}],
        )

        # Second iteration
        analyzer.analyze_llm_call(
            prompt_tokens=150,
            completion_tokens=75,
            input_messages=[{"role": "system", "content": "Sys"}],
        )

        breakdowns = analyzer.get_iteration_breakdowns()
        assert len(breakdowns) == 2
        assert breakdowns[0]["total"] == 150  # 100 + 50
        assert breakdowns[1]["total"] == 225  # 150 + 75

    def test_record_compression_savings(self):
        """Test recording compression savings."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[{"role": "system", "content": "Sys"}],
        )

        analyzer.record_compression_savings(500)

        assert analyzer._category_totals[TokenCategory.COMPRESSED] == 500

    def test_get_summary(self):
        """Test getting summary."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "tool", "name": "file_read", "content": "Content"},
            ],
        )

        summary = analyzer.get_summary()

        assert "categories" in summary
        assert "top_tools" in summary
        assert "iteration_count" in summary
        assert "total_tokens" in summary
        assert summary["iteration_count"] == 1

    def test_reset(self):
        """Test resetting analyzer."""
        analyzer = TokenAnalyzer()

        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[{"role": "system", "content": "Sys"}],
        )

        analyzer.reset()

        assert analyzer._category_totals[TokenCategory.SYSTEM] == 0
        assert len(analyzer._tool_token_usage) == 0
        assert len(analyzer._iteration_breakdowns) == 0

    def test_estimate_message_chars_string(self):
        """Test estimating chars for string content."""
        analyzer = TokenAnalyzer()

        # English text
        msg = {"role": "user", "content": "Hello world"}
        chars = analyzer._estimate_message_chars(msg)
        assert chars == 11  # "Hello world" has 11 characters

    def test_estimate_message_chars_list(self):
        """Test estimating chars for list content."""
        analyzer = TokenAnalyzer()

        msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ],
        }
        chars = analyzer._estimate_message_chars(msg)
        assert chars == 10  # "Hello" + "World" = 10 characters

    def test_multiple_iterations_accumulate(self):
        """Test that multiple iterations accumulate correctly."""
        analyzer = TokenAnalyzer()

        # First iteration
        analyzer.analyze_llm_call(
            prompt_tokens=100,
            completion_tokens=50,
            input_messages=[{"role": "system", "content": "Sys"}],
        )

        # Second iteration
        analyzer.analyze_llm_call(
            prompt_tokens=150,
            completion_tokens=75,
            input_messages=[{"role": "system", "content": "Sys"}],
        )

        # Should accumulate
        assert analyzer._category_totals[TokenCategory.RESPONSE] == 125  # 50 + 75
        assert len(analyzer._iteration_breakdowns) == 2
