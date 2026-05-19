"""
Tests for IntentDetector for dynamic module activation.
"""

import pytest

from nano_agent.agent.intent_detector import IntentDetector, IntentKeywords


class TestIntentKeywords:
    """Test IntentKeywords dataclass."""

    def test_git_keywords_exist(self):
        """Test that git keywords are defined."""
        assert len(IntentKeywords.GIT_STATUS) > 0
        assert "commit" in IntentKeywords.GIT_STATUS
        assert "push" in IntentKeywords.GIT_STATUS
        assert "提交" in IntentKeywords.GIT_STATUS

    def test_environment_keywords_exist(self):
        """Test that environment keywords are defined."""
        assert len(IntentKeywords.ENVIRONMENT) > 0
        assert "env" in IntentKeywords.ENVIRONMENT
        assert "环境变量" in IntentKeywords.ENVIRONMENT
        assert ".env" in IntentKeywords.ENVIRONMENT


class TestIntentDetector:
    """Test IntentDetector functionality."""

    def test_detect_git_intent_with_commit(self):
        """Test detecting git intent with 'commit' keyword."""
        detector = IntentDetector()
        result = detector.detect("帮我提交这个修改")
        assert "git_status" in result

    def test_detect_git_intent_with_push(self):
        """Test detecting git intent with 'push' keyword."""
        detector = IntentDetector()
        result = detector.detect("push to remote")
        assert "git_status" in result

    def test_detect_git_intent_with_branch(self):
        """Test detecting git intent with 'branch' keyword."""
        detector = IntentDetector()
        result = detector.detect("切换分支到 main")
        assert "git_status" in result

    def test_detect_environment_intent_with_env(self):
        """Test detecting environment intent with 'env' keyword."""
        detector = IntentDetector()
        result = detector.detect("查看环境变量")
        assert "environment" in result

    def test_detect_environment_intent_with_dotenv(self):
        """Test detecting environment intent with '.env' keyword."""
        detector = IntentDetector()
        result = detector.detect("读取 .env 文件")
        assert "environment" in result

    def test_detect_multiple_intents(self):
        """Test detecting multiple intents."""
        detector = IntentDetector()
        result = detector.detect("提交代码并检查环境变量")
        assert "git_status" in result
        assert "environment" in result

    def test_detect_no_intent(self):
        """Test detecting no intent for unrelated input."""
        detector = IntentDetector()
        result = detector.detect("什么是装饰器？")
        assert len(result) == 0

    def test_detect_case_insensitive(self):
        """Test that detection is case insensitive."""
        detector = IntentDetector()
        result = detector.detect("COMMIT this change")
        assert "git_status" in result

    def test_should_activate_module_git(self):
        """Test should_activate_module for git."""
        detector = IntentDetector()
        assert detector.should_activate_module("git_status", "帮我提交")
        assert not detector.should_activate_module("git_status", "写个函数")

    def test_should_activate_module_environment(self):
        """Test should_activate_module for environment."""
        detector = IntentDetector()
        assert detector.should_activate_module("environment", "查看 env")
        assert not detector.should_activate_module("environment", "计算 1+1")

    def test_custom_keywords_override(self):
        """Test custom keywords override."""
        custom_keywords = {
            "git_status": ["自定义词"],
        }
        detector = IntentDetector(custom_keywords=custom_keywords)
        result = detector.detect("帮我提交")  # Original keyword should not work
        assert "git_status" not in result
        result = detector.detect("自定义词")
        assert "git_status" in result

    def test_add_keywords(self):
        """Test adding keywords."""
        detector = IntentDetector()
        detector.add_keywords("git_status", ["新关键词"])
        result = detector.detect("新关键词")
        assert "git_status" in result

    def test_remove_keywords(self):
        """Test removing keywords."""
        detector = IntentDetector()
        detector.remove_keywords("git_status", ["commit"])
        result = detector.detect("commit")
        assert "git_status" not in result

    def test_get_keywords(self):
        """Test getting keywords."""
        detector = IntentDetector()
        keywords = detector.get_keywords("git_status")
        assert "commit" in keywords
        assert "push" in keywords

    def test_get_keywords_unknown_intent(self):
        """Test getting keywords for unknown intent."""
        detector = IntentDetector()
        keywords = detector.get_keywords("unknown_intent")
        assert keywords == []


class TestIntentDetectorEdgeCases:
    """Test edge cases for IntentDetector."""

    def test_empty_input(self):
        """Test empty input."""
        detector = IntentDetector()
        result = detector.detect("")
        assert len(result) == 0

    def test_whitespace_only_input(self):
        """Test whitespace only input."""
        detector = IntentDetector()
        result = detector.detect("   ")
        assert len(result) == 0

    def test_partial_keyword_match(self):
        """Test partial keyword match (should not match)."""
        detector = IntentDetector()
        # 'env' is a keyword, but 'environmental' contains it
        result = detector.detect("environmental")
        assert "environment" in result  # 'env' is in 'environmental'

    def test_chinese_keywords(self):
        """Test Chinese keywords."""
        detector = IntentDetector()
        result = detector.detect("提交代码")
        assert "git_status" in result
        result = detector.detect("分支管理")
        assert "git_status" in result

    def test_mixed_language(self):
        """Test mixed language input."""
        detector = IntentDetector()
        result = detector.detect("git commit 提交")
        assert "git_status" in result