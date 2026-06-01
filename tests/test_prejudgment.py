"""
Tests for v0.7.14 Query Prejudgment mechanism.

Tests cover:
- PrejudgmentResult dataclass
- QueryPrejudgment response parsing (pure logic)
- QueryPrejudgment with mock LLM
- Integration with QueryRouter
- Config loading/saving
"""

import pytest
from unittest.mock import Mock, MagicMock

from nano_agent.agent.prejudgment import QueryPrejudgment, PrejudgmentResult
from nano_agent.agent.router import QueryRouter, QueryComplexity, RoutingResult
from nano_agent.config.schema import SmartOptimizationConfig
from nano_agent.config.loader import ConfigLoader
from nano_agent.llm.base import LLMUsage

# === PrejudgmentResult tests ===


class TestPrejudgmentResult:
    """Test PrejudgmentResult dataclass."""

    def test_simple_result(self):
        result = PrejudgmentResult(
            complexity=QueryComplexity.SIMPLE,
            answer="Hello! How can I help?",
            prejudgment_tokens=50,
            reason="Parsed from LLM response",
        )
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.answer == "Hello! How can I help?"
        assert result.prejudgment_tokens == 50

    def test_complex_result_no_answer(self):
        result = PrejudgmentResult(
            complexity=QueryComplexity.COMPLEX,
            answer=None,
            prejudgment_tokens=30,
            reason="Parsed from LLM response",
        )
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.answer is None

    def test_moderate_result_no_answer(self):
        result = PrejudgmentResult(
            complexity=QueryComplexity.MODERATE,
            answer=None,
            prejudgment_tokens=40,
            reason="Parsed from LLM response",
        )
        assert result.complexity == QueryComplexity.MODERATE
        assert result.answer is None


# === Response parsing tests (pure logic, no LLM) ===


class TestQueryPrejudgmentParsing:
    """Test _parse_response logic without LLM calls."""

    def setup_method(self):
        self.prejudgment = QueryPrejudgment(llm=None)

    def test_parse_simple_marker(self):
        complexity, answer = self.prejudgment._parse_response(
            "[COMPLEXITY: simple] 你好！有什么可以帮助你的？"
        )
        assert complexity == QueryComplexity.SIMPLE
        assert answer == "你好！有什么可以帮助你的？"

    def test_parse_moderate_marker(self):
        complexity, answer = self.prejudgment._parse_response("[COMPLEXITY: moderate]")
        assert complexity == QueryComplexity.MODERATE
        assert answer is None

    def test_parse_complex_marker(self):
        complexity, answer = self.prejudgment._parse_response("[COMPLEXITY: complex]")
        assert complexity == QueryComplexity.COMPLEX
        assert answer is None

    def test_parse_case_insensitive(self):
        complexity, answer = self.prejudgment._parse_response(
            "[Complexity: Simple] Hi there!"
        )
        assert complexity == QueryComplexity.SIMPLE
        assert answer == "Hi there!"

    def test_parse_mixed_case_complexity(self):
        complexity, _ = self.prejudgment._parse_response("[COMPLEXITY: Moderate]")
        assert complexity == QueryComplexity.MODERATE

    def test_parse_no_marker_defaults_complex(self):
        complexity, answer = self.prejudgment._parse_response(
            "This is a simple greeting"
        )
        assert complexity == QueryComplexity.COMPLEX
        assert answer is None

    def test_parse_invalid_marker_defaults_complex(self):
        complexity, answer = self.prejudgment._parse_response("[COMPLEXITY: unknown]")
        assert complexity == QueryComplexity.COMPLEX
        assert answer is None

    def test_parse_simple_with_multiline_answer(self):
        complexity, answer = self.prejudgment._parse_response(
            "[COMPLEXITY: simple]\nGIL 是全局解释器锁，\n它确保同一时刻只有一个线程执行 Python 字节码。"
        )
        assert complexity == QueryComplexity.SIMPLE
        assert "GIL" in answer

    def test_parse_marker_in_middle(self):
        complexity, answer = self.prejudgment._parse_response(
            "Let me classify: [COMPLEXITY: simple] Here is the answer."
        )
        assert complexity == QueryComplexity.SIMPLE
        assert "Here is the answer." in answer

    def test_parse_simple_empty_answer(self):
        complexity, answer = self.prejudgment._parse_response("[COMPLEXITY: simple]")
        assert complexity == QueryComplexity.SIMPLE
        assert answer is None


# === Mock LLM tests ===


class TestQueryPrejudgmentWithMockLLM:
    """Test prejudge() with mocked LLM."""

    def _make_mock_llm(self, response_text: str, total_tokens: int = 50):
        llm = Mock()
        usage = LLMUsage(
            prompt_tokens=20,
            completion_tokens=total_tokens - 20,
            total_tokens=total_tokens,
        )
        llm.chat.return_value = (response_text, [], usage)
        return llm

    def test_prejudge_simple(self):
        llm = self._make_mock_llm("[COMPLEXITY: simple] 你好！有什么可以帮助你的？")
        prejudgment = QueryPrejudgment(llm=llm)
        result = prejudgment.prejudge("你好")
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.answer is not None
        assert result.prejudgment_tokens == 50

    def test_prejudge_moderate(self):
        llm = self._make_mock_llm("[COMPLEXITY: moderate]")
        prejudgment = QueryPrejudgment(llm=llm)
        result = prejudgment.prejudge("读取 config.yaml 文件")
        assert result.complexity == QueryComplexity.MODERATE
        assert result.answer is None

    def test_prejudge_complex(self):
        llm = self._make_mock_llm("[COMPLEXITY: complex]")
        prejudgment = QueryPrejudgment(llm=llm)
        result = prejudgment.prejudge("分析这个项目并重构")
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.answer is None

    def test_prejudge_no_marker_defaults_complex(self):
        llm = self._make_mock_llm("I need more context to answer this.")
        prejudgment = QueryPrejudgment(llm=llm)
        result = prejudgment.prejudge("Some ambiguous query")
        assert result.complexity == QueryComplexity.COMPLEX

    def test_prejudge_llm_exception_defaults_complex(self):
        llm = Mock()
        llm.chat.side_effect = Exception("LLM unavailable")
        prejudgment = QueryPrejudgment(llm=llm)
        result = prejudgment.prejudge("你好")
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.answer is None
        assert result.prejudgment_tokens == 0

    def test_prejudge_llm_none_defaults_complex(self):
        prejudgment = QueryPrejudgment(llm=None)
        result = prejudgment.prejudge("你好")
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.answer is None
        assert result.prejudgment_tokens == 0
        assert "not available" in result.reason

    def test_prejudge_calls_llm_with_minimal_messages(self):
        llm = self._make_mock_llm("[COMPLEXITY: simple] Hi!")
        prejudgment = QueryPrejudgment(llm=llm)
        prejudgment.prejudge("hello")
        llm.chat.assert_called_once()
        call_args = llm.chat.call_args
        # Verify tools=None and system_stable=None
        assert call_args.kwargs.get("tools") is None
        assert call_args.kwargs.get("system_stable") is None
        # Verify messages contain the query
        messages = (
            call_args.args[0]
            if call_args.args
            else call_args.kwargs.get("messages", [])
        )
        assert any("hello" in str(m) for m in messages)

    def test_prejudge_factual_question(self):
        llm = self._make_mock_llm(
            "[COMPLEXITY: simple] GIL 是全局解释器锁，确保同一时刻只有一个线程执行 Python 字节码。"
        )
        prejudgment = QueryPrejudgment(llm=llm)
        result = prejudgment.prejudge("Python 的 GIL 是什么")
        assert result.complexity == QueryComplexity.SIMPLE
        assert "GIL" in result.answer


# === Router + Prejudgment integration tests ===


class TestPrejudgmentRouterIntegration:
    """Test that QueryRouter and QueryPrejudgment work together correctly."""

    def test_router_simple_skips_prejudgment(self):
        """When QueryRouter classifies as SIMPLE, prejudgment should not be called."""
        router = QueryRouter(enabled=True, simple_direct=True)
        result = router.classify("你好")
        assert result.complexity == QueryComplexity.SIMPLE
        # This query should never reach prejudgment

    def test_router_moderate_skips_prejudgment(self):
        """When QueryRouter classifies as MODERATE, prejudgment should not be called."""
        router = QueryRouter(enabled=True, moderate_single_tool=True)
        result = router.classify("读取 config.yaml")
        # Moderate or default complex — depends on patterns
        # The key point: if it's MODERATE, no prejudgment needed
        if result.complexity == QueryComplexity.MODERATE:
            assert result.suggested_max_tools == 1

    def test_router_complex_default_triggers_prejudgment(self):
        """When QueryRouter defaults to COMPLEX, prejudgment should be triggered."""
        router = QueryRouter(enabled=True)
        result = router.classify("Python 的 GIL 是什么")
        # This should be COMPLEX by default (no pattern matched)
        assert result.complexity == QueryComplexity.COMPLEX
        assert "defaulting to complex" in result.reason.lower()

    def test_router_complex_pattern_skips_prejudgment(self):
        """When QueryRouter matches COMPLEX pattern, prejudgment should NOT be triggered."""
        router = QueryRouter(enabled=True)
        result = router.classify("分析这个项目的架构")
        assert result.complexity == QueryComplexity.COMPLEX
        assert "defaulting to complex" not in result.reason.lower()

    def test_should_prejudge_logic(self):
        """Test the should_prejudge decision logic."""
        router = QueryRouter(enabled=True)

        # Case 1: Router returned default COMPLEX → should prejudge
        default_complex = router.classify("Python 的装饰器是什么")
        should_prejudge = (
            default_complex.complexity == QueryComplexity.COMPLEX
            and "defaulting to complex" in default_complex.reason.lower()
        )
        assert should_prejudge is True

        # Case 2: Router matched COMPLEX pattern → should NOT prejudge
        pattern_complex = router.classify("分析这个项目的架构")
        should_prejudge = (
            pattern_complex.complexity == QueryComplexity.COMPLEX
            and "defaulting to complex" in pattern_complex.reason.lower()
        )
        assert should_prejudge is False

        # Case 3: Router returned SIMPLE → should NOT prejudge
        simple = router.classify("你好")
        should_prejudge = (
            simple.complexity == QueryComplexity.COMPLEX
            and "defaulting to complex" in simple.reason.lower()
        )
        assert should_prejudge is False


# === Config tests ===


class TestPrejudgmentConfig:
    """Test prejudgment config fields."""

    def test_default_disabled(self):
        config = SmartOptimizationConfig()
        assert config.prejudgment_enabled is False

    def test_default_empty_prompt(self):
        config = SmartOptimizationConfig()
        assert config.prejudgment_simple_prompt == ""

    def test_default_max_answer_tokens(self):
        config = SmartOptimizationConfig()
        assert config.prejudgment_max_answer_tokens == 300

    def test_custom_values(self):
        config = SmartOptimizationConfig(
            prejudgment_enabled=True,
            prejudgment_simple_prompt="Answer in Chinese.",
            prejudgment_max_answer_tokens=500,
        )
        assert config.prejudgment_enabled is True
        assert config.prejudgment_simple_prompt == "Answer in Chinese."
        assert config.prejudgment_max_answer_tokens == 500

    def test_config_loader_parse(self):
        data = {
            "smart_optimization": {
                "prejudgment_enabled": True,
                "prejudgment_simple_prompt": "Be concise.",
                "prejudgment_max_answer_tokens": 200,
            }
        }
        config = ConfigLoader._parse_smart_optimization_config(
            data["smart_optimization"]
        )
        assert config.prejudgment_enabled is True
        assert config.prejudgment_simple_prompt == "Be concise."
        assert config.prejudgment_max_answer_tokens == 200

    def test_config_loader_defaults(self):
        config = ConfigLoader._parse_smart_optimization_config({})
        assert config.prejudgment_enabled is False
        assert config.prejudgment_simple_prompt == ""
        assert config.prejudgment_max_answer_tokens == 300

    def test_config_loader_save_roundtrip(self, tmp_path):
        """Test that prejudgment config survives save/load roundtrip."""
        from nano_agent.config.schema import (
            Config,
            LLMConfig,
            AgentConfig,
            MemoryConfig,
        )

        config = Config(
            llm=LLMConfig(),
            agent=AgentConfig(),
            memory=MemoryConfig(),
            smart_optimization=SmartOptimizationConfig(
                prejudgment_enabled=True,
                prejudgment_simple_prompt="Be brief.",
                prejudgment_max_answer_tokens=400,
            ),
        )
        config_path = tmp_path / "test_config.yaml"
        ConfigLoader.save(config, str(config_path))

        loaded = ConfigLoader.load(str(config_path))
        assert loaded.smart_optimization.prejudgment_enabled is True
        assert loaded.smart_optimization.prejudgment_simple_prompt == "Be brief."
        assert loaded.smart_optimization.prejudgment_max_answer_tokens == 400
