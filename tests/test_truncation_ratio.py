"""
Tests for v0.7.13: Truncation ratio fixes.

Validates that calculate_max_chars() correctly handles Chinese/English
mixed text, and that truncation logic in react.py, compressor.py, and
result_summarizer.py uses the new function instead of * 4.
"""

import pytest

pytestmark = pytest.mark.unit

from nano_agent.agent.token_utils import (
    estimate_text_tokens,
    calculate_max_chars,
)


class TestCalculateMaxChars:
    """Test calculate_max_chars() for Chinese/English mixed text truncation."""

    def test_pure_english_text(self):
        """English text: 1 token ≈ 4 chars, so max_chars ≈ max_tokens * 4."""
        text = "Hello world this is a test of English text truncation"
        max_tokens = 10
        max_chars = calculate_max_chars(text, max_tokens)
        # English ~4 chars/token, 10 tokens ≈ 40 chars
        assert max_chars > 0
        assert estimate_text_tokens(text[:max_chars]) <= max_tokens

    def test_pure_chinese_text(self):
        """Chinese text: 1 token ≈ 1.5 chars, so max_chars ≈ max_tokens * 1.5."""
        text = "这是一个中文文本的测试用例用于验证截断比率是否正确"
        max_tokens = 20
        max_chars = calculate_max_chars(text, max_tokens)
        assert max_chars > 0
        assert estimate_text_tokens(text[:max_chars]) <= max_tokens
        # Verify Chinese gets more chars than the old * 4 formula would
        # Old formula: max_tokens * 4 = 80 chars, but 20 tokens ≈ 30 Chinese chars
        # New formula should allow ~30 chars for 20 tokens of pure Chinese
        old_max = max_tokens * 4
        # Chinese text should get LESS chars (more tokens per char)
        # Actually: Chinese 1.5 chars/token means 20 tokens ≈ 30 chars
        # Old *4 would give 80 chars but 80 Chinese chars ≈ 53 tokens (way over budget)
        # So new formula correctly limits to fewer chars for Chinese

    def test_mixed_chinese_english(self):
        """Mixed text should correctly balance both ratios."""
        text = "这是中文Hello World混合文本testing截断逻辑"
        max_tokens = 20
        max_chars = calculate_max_chars(text, max_tokens)
        assert max_chars > 0
        assert estimate_text_tokens(text[:max_chars]) <= max_tokens

    def test_short_text_no_truncation_needed(self):
        """If text already fits within budget, return full length."""
        text = "Short text"
        max_tokens = 100
        max_chars = calculate_max_chars(text, max_tokens)
        assert max_chars == len(text)

    def test_empty_text(self):
        """Empty text returns 0."""
        assert calculate_max_chars("", 100) == 0

    def test_zero_budget(self):
        """Zero token budget returns 0 chars."""
        text = "Some text here"
        assert calculate_max_chars(text, 0) == 0

    def test_negative_budget(self):
        """Negative token budget returns 0 chars."""
        text = "Some text here"
        assert calculate_max_chars(text, -1) == 0

    def test_binary_search_convergence(self):
        """Binary search finds a point where tokens <= max_tokens."""
        # Long text with mixed content
        text = "这是一段很长的中文和English混合文本，" * 50
        max_tokens = 50
        max_chars = calculate_max_chars(text, max_tokens)
        assert max_chars > 0
        assert max_chars < len(text)
        # The truncated text should fit within the budget
        assert estimate_text_tokens(text[:max_chars]) <= max_tokens

    def test_single_token_budget(self):
        """Very small budget (1 token) should still find a valid char count."""
        text = "Hello world"
        max_chars = calculate_max_chars(text, 1)
        assert max_chars >= 0
        assert estimate_text_tokens(text[:max_chars]) <= 1

    def test_exact_fit(self):
        """Text that exactly fits the budget should return full length."""
        # Create text that is exactly within budget
        text = "a" * 40  # 40 English chars ≈ 10 tokens
        max_tokens = 10
        max_chars = calculate_max_chars(text, max_tokens)
        assert max_chars == len(text)


class TestEstimateTokensWithCalibration:
    """Test that estimate_text_tokens accepts calibration_factor."""

    def test_default_calibration_is_1(self):
        """Without calibration, estimate_text_tokens works as before."""
        text = "Hello world"
        result = estimate_text_tokens(text)
        result_with_factor = estimate_text_tokens(text, calibration_factor=1.0)
        assert result == result_with_factor

    def test_calibration_factor_1_5(self):
        """Calibration factor 1.5 increases estimated tokens by ~50%."""
        text = "Hello world"
        calibrated = estimate_text_tokens(text, calibration_factor=1.5)
        base = estimate_text_tokens(text)
        # Allow for rounding due to int() applied before and after factor
        assert calibrated >= base  # Should be higher
        assert abs(calibrated - base * 1.5) < 2  # Close to 1.5x

    def test_calibration_factor_0_8(self):
        """Calibration factor 0.8 reduces estimated tokens by ~20%."""
        text = "Hello world"
        calibrated = estimate_text_tokens(text, calibration_factor=0.8)
        base = estimate_text_tokens(text)
        assert calibrated <= base  # Should be lower
        assert abs(calibrated - base * 0.8) < 2

    def test_estimate_tokens_messages_with_calibration(self):
        """estimate_tokens() for message list also supports calibration."""
        from nano_agent.agent.token_utils import estimate_tokens

        messages = [{"role": "user", "content": "Hello"}]
        base = estimate_tokens(messages)
        calibrated = estimate_tokens(messages, calibration_factor=1.3)
        # Should be higher with calibration
        assert calibrated >= base


class TestResultSummarizerEstimateTokens:
    """Test that result_summarizer.estimate_tokens() uses token_utils."""

    def test_unified_estimation_supports_chinese(self):
        """The unified estimate_text_tokens supports Chinese, unlike len//4."""
        from nano_agent.agent.result_summarizer import ToolResultSummarizer

        summarizer = ToolResultSummarizer()
        chinese_text = "这是中文测试"
        # Old method: len("这是中文测试") // 4 = 6 // 4 = 1
        # New method: estimates Chinese chars properly (~4 tokens)
        result = summarizer.estimate_tokens(chinese_text)
        assert result > 1  # Should be more accurate than len//4

    def test_unified_estimation_consistent_with_token_utils(self):
        """Result summarizer estimate matches token_utils.estimate_text_tokens."""
        from nano_agent.agent.result_summarizer import ToolResultSummarizer

        summarizer = ToolResultSummarizer()
        text = "Hello 这是混合 text"
        result = summarizer.estimate_tokens(text)
        expected = estimate_text_tokens(text)
        assert result == expected


class TestMaxSummaryTokensActivation:
    """Test that max_summary_tokens is now enforced in summarize()."""

    def test_summary_truncated_when_over_budget(self):
        """When summary exceeds max_summary_tokens, it gets truncated."""
        from nano_agent.agent.result_summarizer import SummarizerConfig, ToolResultSummarizer

        config = SummarizerConfig(max_summary_tokens=10)
        summarizer = ToolResultSummarizer(config)
        # Long text that will exceed 10 tokens after summarization
        long_text = "Line 1\nLine 2\nLine 3\nLine 4\n" * 20
        result = summarizer.summarize(long_text, "shell_execute")
        assert estimate_text_tokens(result) <= 10 or "摘要已截断" in result

    def test_summary_not_truncated_when_under_budget(self):
        """Short summaries that fit within max_summary_tokens are kept intact."""
        from nano_agent.agent.result_summarizer import SummarizerConfig, ToolResultSummarizer

        config = SummarizerConfig(max_summary_tokens=500)
        summarizer = ToolResultSummarizer(config)
        short_text = "Short output"
        result = summarizer.summarize(short_text, "shell_execute")
        assert "摘要已截断" not in result

    def test_zero_max_summary_tokens_no_truncation(self):
        """When max_summary_tokens=0, no truncation is applied."""
        from nano_agent.agent.result_summarizer import SummarizerConfig, ToolResultSummarizer

        config = SummarizerConfig(max_summary_tokens=0)
        summarizer = ToolResultSummarizer(config)
        text = "Some text here"
        result = summarizer.summarize(text, "shell_execute")
        assert "摘要已截断" not in result


class TestCompressorTruncation:
    """Test that compressor._create_summary() uses calculate_max_chars."""

    def test_chinese_summary_truncation(self):
        """Chinese summary content truncated using calculate_max_chars."""
        from nano_agent.agent.compressor import CompressorConfig, MessageCompressor

        config = CompressorConfig(summary_max_tokens=20)
        compressor = MessageCompressor(config)

        # Create old messages with Chinese content
        old_messages = [
            {"role": "user", "content": "这是第一个用户的请求关于某个问题"},
            {"role": "assistant", "content": "这是助手的回复内容包含了详细的分析和解决方案"},
            {"role": "tool", "content": "这是工具的执行结果", "name": "file_read"},
        ] * 10  # Make it long enough

        summary = compressor._create_summary(old_messages)
        # The summary should fit within the token budget
        assert estimate_text_tokens(summary["content"]) <= config.summary_max_tokens + 10  # Allow small overhead for "..." suffix