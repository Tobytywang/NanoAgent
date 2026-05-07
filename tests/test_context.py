"""
Tests for v0.6.1 context management: token estimation and compression.
"""

import pytest
from unittest.mock import Mock, MagicMock

from nano_agent.agent import (
    ContextManager,
    NineSectionSummary,
    estimate_tokens,
    estimate_text_tokens,
)
from nano_agent.memory import ShortTermMemory
from nano_agent.config.schema import ContextConfig


class TestTokenEstimation:
    """Tests for token estimation utilities."""

    def test_estimate_english_text(self):
        """Test token estimation for English text."""
        # ~4 characters per token for English
        text = "Hello world, this is a test."
        tokens = estimate_text_tokens(text)
        # 29 chars / 4 ≈ 7 tokens
        assert 5 <= tokens <= 10

    def test_estimate_chinese_text(self):
        """Test token estimation for Chinese text."""
        # ~1.5 characters per token for Chinese
        text = "你好世界，这是一个测试。"
        tokens = estimate_text_tokens(text)
        # 11 chars / 1.5 ≈ 7 tokens
        assert 5 <= tokens <= 10

    def test_estimate_mixed_text(self):
        """Test token estimation for mixed Chinese/English text."""
        text = "Hello 你好 World 世界"
        tokens = estimate_text_tokens(text)
        # Should be between pure English and pure Chinese estimates
        assert tokens > 0

    def test_estimate_empty_text(self):
        """Test token estimation for empty text."""
        assert estimate_text_tokens("") == 0

    def test_estimate_messages(self):
        """Test token estimation for message list."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = estimate_tokens(messages)
        # Each message has ~4 tokens overhead
        assert tokens > 0

    def test_estimate_messages_with_empty_content(self):
        """Test token estimation for messages with empty content."""
        messages = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "Hello"},
        ]
        tokens = estimate_tokens(messages)
        # Should still count message overhead
        assert tokens >= 8  # 2 messages * 4 overhead


class TestNineSectionSummary:
    """Tests for NineSectionSummary dataclass."""

    def test_create_summary(self):
        """Test creating a nine-section summary."""
        summary = NineSectionSummary(
            user_request="Build a web app",
            technical_concepts="React, Node.js",
            files_and_code="app.js, index.html",
            errors_and_fixes="Fixed CORS issue",
            problem_solving="Added proxy server",
            user_messages="User wants dark mode",
            pending_tasks="Add authentication",
            current_work="Implementing login",
            next_steps="Test login flow"
        )
        assert summary.user_request == "Build a web app"
        assert summary.technical_concepts == "React, Node.js"

    def test_to_message(self):
        """Test converting summary to message format."""
        summary = NineSectionSummary(
            user_request="Test request",
            technical_concepts="",
            files_and_code="",
            errors_and_fixes="",
            problem_solving="",
            user_messages="",
            pending_tasks="",
            current_work="",
            next_steps=""
        )
        msg = summary.to_message()
        assert msg["role"] == "system"
        assert msg["name"] == "context_summary"
        assert "Test request" in msg["content"]
        assert "无" in msg["content"]  # Empty fields show as "无"


class TestContextManager:
    """Tests for ContextManager class."""

    def test_create_context_manager(self):
        """Test creating a context manager."""
        memory = ShortTermMemory()
        llm = Mock()
        config = ContextConfig()

        manager = ContextManager(memory, llm, config)
        assert manager.memory is memory
        assert manager.llm is llm
        assert manager.config is config

    def test_check_pressure_low(self):
        """Test pressure check when below threshold."""
        memory = ShortTermMemory()
        memory.add_user_message("Hello")

        llm = Mock()
        config = ContextConfig(pressure_threshold_low=0.70)

        manager = ContextManager(memory, llm, config)
        # With only 1 message, pressure should be very low
        result = manager.check_and_compress(max_context_tokens=100000)
        assert result is False  # No compression needed

    def test_check_pressure_high(self):
        """Test pressure check when above threshold."""
        memory = ShortTermMemory()

        # Add many messages to simulate high pressure
        for i in range(100):
            memory.add_user_message("This is a test message with some content. " * 10)
            memory.add_assistant_message("This is a response with some content. " * 10)

        llm = Mock()
        config = ContextConfig(
            pressure_threshold_low=0.70,
            pressure_threshold_mid=0.85,
            pressure_threshold_high=0.95
        )

        manager = ContextManager(memory, llm, config, verbose=True)
        # With many messages, should trigger compression
        result = manager.check_and_compress(max_context_tokens=1000)
        # Should have performed some cleanup
        assert len(memory.get_all()) < 200

    def test_light_cleanup(self):
        """Test light cleanup layer."""
        memory = ShortTermMemory()

        # Add messages
        memory.add_user_message("User message 1")
        memory.add_assistant_message("Assistant message 1")
        memory.add_user_message("User message 2")
        # Add tool results (temporary)
        memory.add_tool_result("tool_1", "Tool result 1")
        memory.add_tool_result("tool_2", "Tool result 2")

        llm = Mock()
        config = ContextConfig(temp_message_age=1)

        manager = ContextManager(memory, llm, config)
        result = manager._try_light_cleanup()

        # Should have cleaned up some messages
        assert isinstance(result, bool)

    def test_model_compress_circuit_breaker(self):
        """Test circuit breaker for model compression."""
        memory = ShortTermMemory()

        # Add enough messages to trigger compression (need >= 10)
        for i in range(15):
            memory.add_user_message(f"Test message {i}")

        llm = Mock()
        llm.chat = Mock(side_effect=Exception("LLM error"))

        config = ContextConfig(max_compress_failures=2)

        manager = ContextManager(memory, llm, config)

        # First failure
        manager._try_model_compress()
        assert manager.compress_failures == 1

        # Second failure
        manager._try_model_compress()
        assert manager.compress_failures == 2

        # Circuit breaker should prevent further attempts
        result = manager._try_model_compress()
        assert result is False
        assert manager.compress_failures == 2  # Should not increment

    def test_generate_summary(self):
        """Test summary generation."""
        memory = ShortTermMemory()

        # Add enough messages for summary generation (need >= 10)
        for i in range(12):
            memory.add_user_message(f"Build a web app - message {i}")
            memory.add_assistant_message(f"I'll help you build a web app - response {i}")

        llm = Mock()
        llm.chat = Mock(return_value=(
            """用户请求: Build a web app
技术概念: React, Node.js
文件与代码: app.js
错误与修复: 无
问题解决: 无
用户补充: 无
待处理任务: Add authentication
当前工作: Setting up project
下一步: Create components""",
            [],
            Mock(total_tokens=100)
        ))

        config = ContextConfig()
        manager = ContextManager(memory, llm, config)

        summary = manager._generate_summary()
        assert summary is not None
        assert "web app" in summary.user_request.lower()
        assert "React" in summary.technical_concepts

    def test_parse_summary(self):
        """Test parsing LLM output into summary."""
        llm_output = """用户请求: Build a REST API
技术概念: FastAPI, PostgreSQL
文件与代码: main.py, models.py
错误与修复: Fixed database connection
问题解决: Added connection pooling
用户补充: Need rate limiting
待处理任务: Add tests
当前工作: Implementing endpoints
下一步: Write unit tests"""

        memory = ShortTermMemory()
        config = ContextConfig()
        manager = ContextManager(memory, Mock(), config)

        summary = manager._parse_summary(llm_output)

        assert "REST API" in summary.user_request
        assert "FastAPI" in summary.technical_concepts
        assert "main.py" in summary.files_and_code
        assert "database connection" in summary.errors_and_fixes

    def test_replace_with_summary(self):
        """Test replacing messages with summary."""
        memory = ShortTermMemory()

        # Add many messages
        for i in range(20):
            memory.add_user_message(f"Message {i}")
            memory.add_assistant_message(f"Response {i}")

        initial_count = len(memory.get_all())

        llm = Mock()
        config = ContextConfig()

        manager = ContextManager(memory, llm, config)

        summary = NineSectionSummary(
            user_request="Test",
            technical_concepts="",
            files_and_code="",
            errors_and_fixes="",
            problem_solving="",
            user_messages="",
            pending_tasks="",
            current_work="",
            next_steps=""
        )

        manager._replace_with_summary(summary)

        # Should have fewer messages after replacement
        final_count = len(memory.get_all())
        assert final_count < initial_count

        # Should have summary message
        messages = memory.get_all()
        summary_msgs = [m for m in messages if m.get("name") == "context_summary"]
        assert len(summary_msgs) == 1


class TestContextConfig:
    """Tests for ContextConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ContextConfig()
        assert config.pressure_threshold_low == 0.70
        assert config.pressure_threshold_mid == 0.85
        assert config.pressure_threshold_high == 0.95
        assert config.max_context_tokens is None
        assert config.max_compress_failures == 3
        assert config.summary_max_tokens == 4000
        assert config.temp_message_age == 5

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ContextConfig(
            pressure_threshold_low=0.5,
            pressure_threshold_mid=0.75,
            pressure_threshold_high=0.9,
            max_context_tokens=64000,
            max_compress_failures=5
        )
        assert config.pressure_threshold_low == 0.5
        assert config.max_context_tokens == 64000
        assert config.max_compress_failures == 5
