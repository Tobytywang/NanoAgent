"""
Tests for utility functions.

Tests string utilities and pattern extraction functions.
"""

import pytest

pytestmark = pytest.mark.unit

from nano_agent.utils.strings import safe_str
from nano_agent.utils.patterns import (
    USER_NAME_PATTERNS,
    AGENT_NAME_PATTERNS,
    extract_name_from_patterns,
)


class TestSafeStr:
    """Tests for safe_str utility function."""

    def test_safe_str_normal_ascii(self):
        """Test safe_str with normal ASCII text."""
        text = "Hello World"
        result = safe_str(text)

        assert result == text

    def test_safe_str_normal_unicode(self):
        """Test safe_str with normal Unicode text."""
        text = "你好世界"
        result = safe_str(text)

        assert result == text

    def test_safe_str_chinese(self):
        """Test safe_str with Chinese characters."""
        text = "用户的名字是奥特曼"
        result = safe_str(text)

        assert result == text

    def test_safe_str_empty_string(self):
        """Test safe_str with empty string."""
        result = safe_str("")

        assert result == ""

    def test_safe_str_none(self):
        """Test safe_str with None input."""
        result = safe_str(None)

        assert result is None

    def test_safe_str_preserves_valid_content(self):
        """Test safe_str preserves valid content."""
        text = "Valid text with Chinese 你好 and English"
        result = safe_str(text)

        assert result == text

    def test_safe_str_handles_mixed_content(self):
        """Test safe_str handles mixed valid content."""
        text = "Mixed: ABC 你好 123"
        result = safe_str(text)

        assert result == text


class TestPatterns:
    """Tests for pattern constants."""

    def test_user_name_patterns_not_empty(self):
        """Test USER_NAME_PATTERNS is not empty."""
        assert len(USER_NAME_PATTERNS) > 0

    def test_agent_name_patterns_not_empty(self):
        """Test AGENT_NAME_PATTERNS is not empty."""
        assert len(AGENT_NAME_PATTERNS) > 0

    def test_patterns_are_valid_regex(self):
        """Test all patterns are valid regular expressions."""
        import re

        for pattern in USER_NAME_PATTERNS:
            re.compile(pattern)  # Should not raise

        for pattern in AGENT_NAME_PATTERNS:
            re.compile(pattern)  # Should not raise


class TestExtractNameFromPatterns:
    """Tests for extract_name_from_patterns function."""

    def test_extract_user_name_is(self):
        """Test extracting '用户名是...'."""
        content = "用户名是张三"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "张三"

    def test_extract_user_name_called(self):
        """Test extracting '用户叫...'."""
        content = "用户叫李四"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "李四"

    def test_extract_user_name_explicit(self):
        """Test extracting '用户的名字是...'."""
        content = "用户的名字是天宇"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "天宇"

    def test_extract_agent_name_is(self):
        """Test extracting 'Agent名是...'."""
        content = "Agent名是Nano"
        result = extract_name_from_patterns(content, AGENT_NAME_PATTERNS)

        assert result == "Nano"

    def test_extract_agent_my_name(self):
        """Test extracting '我的名字是...'."""
        content = "我的名字是奥特曼"
        result = extract_name_from_patterns(content, AGENT_NAME_PATTERNS)

        assert result == "奥特曼"

    def test_extract_agent_i_am_called(self):
        """Test extracting '我叫...'."""
        content = "我叫Nomi"
        result = extract_name_from_patterns(content, AGENT_NAME_PATTERNS)

        assert result == "Nomi"

    def test_extract_agent_your_name(self):
        """Test extracting '你的名字是...'."""
        content = "你的名字是助手"
        result = extract_name_from_patterns(content, AGENT_NAME_PATTERNS)

        assert result == "助手"

    def test_extract_no_match(self):
        """Test returns None when no pattern matches."""
        content = "今天天气很好"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result is None

    def test_extract_first_match_wins(self):
        """Test first matching pattern is used."""
        content = "用户名是张三，用户叫李四"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "张三"

    def test_extract_strips_whitespace(self):
        """Test extracted name has whitespace stripped."""
        content = "用户名是  张三  "
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "张三"

    def test_extract_stops_at_punctuation(self):
        """Test extraction stops at punctuation."""
        content = "用户名是张三，用户王五给我起的名字"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "张三"
        assert "，" not in result

    def test_extract_stops_at_chinese_punctuation(self):
        """Test extraction stops at Chinese punctuation."""
        content = "用户名是张三。这是另一句话"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "张三"
        assert "。" not in result

    def test_extract_stops_at_english_punctuation(self):
        """Test extraction stops at English punctuation."""
        content = "用户名是张三, another part"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "张三"
        assert "," not in result

    def test_extract_with_exclamation(self):
        """Test extraction stops at exclamation."""
        content = "用户名是张三！"
        result = extract_name_from_patterns(content, USER_NAME_PATTERNS)

        assert result == "张三"
        assert "！" not in result

    def test_extract_empty_patterns(self):
        """Test returns None with empty patterns list."""
        content = "用户名是张三"
        result = extract_name_from_patterns(content, [])

        assert result is None

    def test_extract_empty_content(self):
        """Test returns None with empty content."""
        result = extract_name_from_patterns("", USER_NAME_PATTERNS)

        assert result is None