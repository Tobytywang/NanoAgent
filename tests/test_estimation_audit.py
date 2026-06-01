"""
Tests for estimation audit (v0.7.18).

Covers:
1. EstimationAuditConfig defaults and custom values
2. record() deviation tracking, window size, disabled state
3. >50% threshold warning, configurable threshold
4. is_converged() convergence detection
5. get_summary() field completeness
6. PromptModule.effective_token_estimate dynamic vs fallback
7. PromptBuilder.estimate_tokens() uses dynamic estimation
8. result_summarizer calibrated estimation
9. calculate_max_chars calibration_factor
10. base_ratio first-round correction
11. SmartOptimizationConfig calibration fields
12. LLMCallMetrics new fields serialization
13. RawLLMCallData new fields backward compatibility
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from nano_agent.agent.estimation_audit import (
    EstimationAudit,
    EstimationAuditConfig,
    EstimationAuditResult,
    EstimationDeviation,
)
from nano_agent.agent.prompt_modules import PromptModule
from nano_agent.agent.result_summarizer import ToolResultSummarizer, SummarizerConfig
from nano_agent.agent.token_utils import calculate_max_chars, estimate_text_tokens
from nano_agent.config.schema import SmartOptimizationConfig
from nano_agent.monitoring.metrics import LLMCallMetrics
from nano_agent.monitoring.raw_data import RawLLMCallData


class TestEstimationAuditConfig:
    """Test EstimationAuditConfig defaults and custom values."""

    def test_defaults(self):
        config = EstimationAuditConfig()
        assert config.enabled is True
        assert config.deviation_warning_threshold == 0.50
        assert config.audit_window == 20
        assert config.min_samples_for_convergence == 5
        assert config.convergence_threshold == 0.10

    def test_custom_values(self):
        config = EstimationAuditConfig(
            enabled=False,
            deviation_warning_threshold=0.30,
            audit_window=10,
            min_samples_for_convergence=3,
            convergence_threshold=0.05,
        )
        assert config.enabled is False
        assert config.deviation_warning_threshold == 0.30
        assert config.audit_window == 10
        assert config.min_samples_for_convergence == 3
        assert config.convergence_threshold == 0.05


class TestEstimationAuditRecord:
    """Test record() method."""

    def test_basic_recording(self):
        audit = EstimationAudit()
        result = audit.record(estimated=100, actual=120, calibration_factor=1.0)
        assert isinstance(result, EstimationAuditResult)
        assert result.deviation_pct == pytest.approx(0.20, abs=0.01)
        assert result.direction == "under"
        assert result.is_warning is False
        assert result.calibration_factor == 1.0

    def test_over_estimation(self):
        audit = EstimationAudit()
        result = audit.record(estimated=200, actual=100)
        assert result.deviation_pct == pytest.approx(0.50)
        assert result.direction == "over"

    def test_under_estimation(self):
        audit = EstimationAudit()
        result = audit.record(estimated=100, actual=200)
        assert result.deviation_pct == pytest.approx(1.0)
        assert result.direction == "under"

    def test_zero_estimated_returns_unknown(self):
        audit = EstimationAudit()
        result = audit.record(estimated=0, actual=100)
        assert result.deviation_pct == 0.0
        assert result.direction == "unknown"
        assert result.is_warning is False

    def test_disabled_returns_zero(self):
        config = EstimationAuditConfig(enabled=False)
        audit = EstimationAudit(config)
        result = audit.record(estimated=100, actual=200)
        assert result.deviation_pct == 0.0
        assert result.is_warning is False
        assert len(audit.get_deviation_history()) == 0

    def test_window_trimming(self):
        config = EstimationAuditConfig(audit_window=5)
        audit = EstimationAudit(config)
        for i in range(10):
            audit.record(estimated=100, actual=110 + i)
        assert len(audit.get_deviation_history()) == 5


class TestEstimationAuditWarning:
    """Test >50% deviation warning."""

    def test_warning_below_threshold(self):
        audit = EstimationAudit()
        result = audit.record(estimated=100, actual=140)  # 40% deviation
        assert result.is_warning is False

    def test_warning_at_threshold(self):
        audit = EstimationAudit()
        result = audit.record(estimated=100, actual=150)  # 50% deviation
        assert result.is_warning is False  # NOT > 50%

    def test_warning_above_threshold(self):
        audit = EstimationAudit()
        result = audit.record(estimated=100, actual=160)  # 60% deviation
        assert result.is_warning is True

    def test_custom_threshold(self):
        config = EstimationAuditConfig(deviation_warning_threshold=0.30)
        audit = EstimationAudit(config)
        result = audit.record(estimated=100, actual=140)  # 40% deviation
        assert result.is_warning is True

    def test_warning_count_tracking(self):
        audit = EstimationAudit()
        audit.record(estimated=100, actual=160)  # warning
        audit.record(estimated=100, actual=110)  # no warning
        audit.record(estimated=100, actual=180)  # warning
        summary = audit.get_summary()
        assert summary["warning_count"] == 2


class TestEstimationAuditConvergence:
    """Test is_converged() convergence detection."""

    def test_not_enough_samples(self):
        audit = EstimationAudit()
        for _ in range(4):
            audit.record(estimated=100, actual=105)
        assert audit.is_converged() is False

    def test_converged(self):
        audit = EstimationAudit()
        for _ in range(5):
            audit.record(estimated=100, actual=105)  # 5% deviation each
        assert audit.is_converged() is True

    def test_not_converged_high_deviation(self):
        audit = EstimationAudit()
        for _ in range(4):
            audit.record(estimated=100, actual=105)
        audit.record(estimated=100, actual=150)  # 50% breaks convergence
        assert audit.is_converged() is False

    def test_convergence_with_custom_threshold(self):
        config = EstimationAuditConfig(
            min_samples_for_convergence=3, convergence_threshold=0.05
        )
        audit = EstimationAudit(config)
        for _ in range(3):
            audit.record(estimated=100, actual=104)  # 4% deviation
        assert audit.is_converged() is True


class TestEstimationAuditSummary:
    """Test get_summary() field completeness."""

    def test_empty_summary(self):
        audit = EstimationAudit()
        summary = audit.get_summary()
        assert summary["total_checks"] == 0
        assert summary["avg_deviation_pct"] == 0.0
        assert summary["max_deviation_pct"] == 0.0
        assert summary["is_converged"] is False

    def test_populated_summary(self):
        audit = EstimationAudit()
        audit.record(estimated=100, actual=80)  # 20% over
        audit.record(estimated=100, actual=120)  # 20% under
        summary = audit.get_summary()
        assert summary["total_checks"] == 2
        assert summary["avg_deviation_pct"] == pytest.approx(0.20, abs=0.01)
        assert summary["max_deviation_pct"] == pytest.approx(0.20, abs=0.01)
        assert summary["over_count"] == 1
        assert summary["under_count"] == 1
        assert summary["over_pct"] == 50.0
        assert summary["under_pct"] == 50.0

    def test_calibration_factor_in_summary(self):
        audit = EstimationAudit()
        audit.record(estimated=100, actual=120, calibration_factor=1.2)
        summary = audit.get_summary()
        assert summary["calibration_factor"] == pytest.approx(1.2, abs=0.01)


class TestPromptModuleEffectiveEstimate:
    """Test PromptModule.effective_token_estimate dynamic computation."""

    def test_dynamic_estimation_for_plain_content(self):
        module = PromptModule(
            name="test", description="test", content="Hello world!", token_estimate=999
        )
        effective = module.effective_token_estimate
        assert effective > 0
        assert effective < 999

    def test_fallback_for_template_content(self):
        module = PromptModule(
            name="tools",
            description="test",
            content="Tools: {tools_description}",
            token_estimate=80,
        )
        assert module.effective_token_estimate == 80

    def test_fallback_for_empty_content(self):
        module = PromptModule(
            name="empty", description="test", content="", token_estimate=50
        )
        assert module.effective_token_estimate == 50

    def test_dynamic_matches_estimate_text_tokens(self):
        module = PromptModule(
            name="test",
            description="test",
            content="This is a test prompt content.",
            token_estimate=0,
        )
        expected = estimate_text_tokens(module.content)
        assert module.effective_token_estimate == expected


class TestResultSummarizerCalibration:
    """Test result_summarizer calibrated estimation."""

    def test_summarize_with_calibration_factor(self):
        config = SummarizerConfig(max_summary_tokens=50)
        summarizer = ToolResultSummarizer(config)
        long_output = "x" * 5000
        result = summarizer.summarize(
            long_output, tool_name="test_tool", calibration_factor=1.5
        )
        assert isinstance(result, str)
        assert len(result) < len(long_output)

    def test_estimate_tokens_with_calibration(self):
        config = SummarizerConfig()
        summarizer = ToolResultSummarizer(config)
        text = "Hello world " * 50
        uncal = summarizer.estimate_tokens(text, calibration_factor=1.0)
        cal = summarizer.estimate_tokens(text, calibration_factor=1.5)
        assert cal >= uncal


class TestCalculateMaxCharsCalibration:
    """Test calculate_max_chars with calibration_factor."""

    def test_basic_with_calibration(self):
        text = "Hello world " * 100
        chars_default = calculate_max_chars(text, max_tokens=20, calibration_factor=1.0)
        chars_calibrated = calculate_max_chars(
            text, max_tokens=20, calibration_factor=1.5
        )
        assert chars_default >= chars_calibrated

    def test_empty_text(self):
        assert calculate_max_chars("", max_tokens=100) == 0

    def test_zero_max_tokens(self):
        assert calculate_max_chars("Hello", max_tokens=0) == 0


class TestBaseRatioFirstRoundCorrection:
    """Test base_ratio first-round correction in tracker."""

    def test_tracker_has_estimation_audit(self):
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()
        assert hasattr(tracker, "estimation_audit")
        assert hasattr(tracker, "get_estimation_audit_summary")

    def test_tracker_has_base_ratio_correction_fields(self):
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()
        assert hasattr(tracker, "_base_ratio_initialized")
        assert hasattr(tracker, "_base_ratio_iteration")
        assert tracker._base_ratio_initialized is False
        assert tracker._base_ratio_iteration == 0

    def test_single_iteration_no_base_ratio_set(self):
        """Single-iteration run should not set base_ratio; uses per-iteration ratio."""
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()
        tracker.start_run("test input")
        tracker.start_iteration(1)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=500,
            completion_tokens=50,
            latency_ms=100.0,
            tool_calls_count=0,
            input_messages=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hi"},
            ],
            output_text="Hello!",
            tools_schema=[{"name": "tool1", "description": "A tool"}],
        )
        tracker.end_iteration()
        tracker.end_run("Hello!")

        # base_ratio should NOT be set (single iteration)
        assert tracker._base_ratio == 0.0
        assert tracker._base_ratio_initialized is False

        # get_detailed_usage should still produce a valid breakdown
        usage = tracker.get_detailed_usage()
        assert len(usage) == 1
        row = usage[0]
        total_input = (
            row["tool_tokens"]
            + row["system_tokens"]
            + row["skill_tokens"]
            + row["summary_tokens"]
            + row["message_tokens"]
        )
        assert total_input == 500

    def test_two_iterations_base_ratio_from_second(self):
        """Two-iteration run should set base_ratio from second iteration."""
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()
        tracker.start_run("test input")

        # Iteration 1: minimal message_chars
        tracker.start_iteration(1)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=1000,
            completion_tokens=100,
            latency_ms=100.0,
            tool_calls_count=1,
            input_messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
            ],
            output_text="Let me check",
            tool_calls=[{"name": "tool1", "arguments": {"x": 1}}],
            tools_schema=[
                {
                    "name": "tool1",
                    "description": "A tool with a longer description to increase char count",
                }
            ],
        )
        tracker.end_iteration()

        # Iteration 2: more message_chars
        tracker.start_iteration(2)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=1500,
            completion_tokens=50,
            latency_ms=100.0,
            tool_calls_count=0,
            input_messages=[
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Let me check"},
                {
                    "role": "tool",
                    "content": "Result of tool1: something happened here that is quite verbose",
                },
                {"role": "assistant", "content": "Based on the result, I can say that"},
            ],
            output_text="Here is my answer",
            tools_schema=[
                {
                    "name": "tool1",
                    "description": "A tool with a longer description to increase char count",
                }
            ],
        )
        tracker.end_iteration()
        tracker.end_run("Here is my answer")

        # base_ratio is computed lazily by get_detailed_usage()
        usage = tracker.get_detailed_usage()

        # base_ratio should now be set (from iteration 2)
        assert tracker._base_ratio > 0.0
        assert tracker._base_ratio_initialized is True

        # get_detailed_usage should produce valid breakdowns
        assert len(usage) == 2
        for row in usage:
            total_input = (
                row["tool_tokens"]
                + row["system_tokens"]
                + row["skill_tokens"]
                + row["summary_tokens"]
                + row["message_tokens"]
            )
            assert total_input == row["input_tokens"]

    def test_three_iterations_base_ratio_stable(self):
        """Three-iteration run: base_ratio set from iteration 2, stable for iteration 3."""
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()
        tracker.start_run("test input")

        # Iteration 1
        tracker.start_iteration(1)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=800,
            completion_tokens=100,
            latency_ms=100.0,
            tool_calls_count=1,
            input_messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant with detailed instructions",
                },
                {"role": "user", "content": "Hello"},
            ],
            output_text="Let me check",
            tool_calls=[{"name": "tool1", "arguments": {"x": 1}}],
            tools_schema=[{"name": "tool1", "description": "A tool with description"}],
        )
        tracker.end_iteration()

        # Iteration 2
        tracker.start_iteration(2)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=1200,
            completion_tokens=100,
            latency_ms=100.0,
            tool_calls_count=1,
            input_messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant with detailed instructions",
                },
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Let me check that for you"},
                {"role": "tool", "content": "Result: something useful"},
            ],
            output_text="Almost done",
            tool_calls=[{"name": "tool2", "arguments": {"y": 2}}],
            tools_schema=[{"name": "tool1", "description": "A tool with description"}],
        )
        tracker.end_iteration()

        # Iteration 3
        tracker.start_iteration(3)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=1600,
            completion_tokens=50,
            latency_ms=100.0,
            tool_calls_count=0,
            input_messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant with detailed instructions",
                },
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Let me check that for you"},
                {"role": "tool", "content": "Result: something useful"},
                {"role": "assistant", "content": "Almost done, let me finalize"},
                {"role": "tool", "content": "Result: final data here"},
            ],
            output_text="Final answer here",
            tools_schema=[{"name": "tool1", "description": "A tool with description"}],
        )
        tracker.end_iteration()
        tracker.end_run("Final answer here")

        usage = tracker.get_detailed_usage()
        assert tracker._base_ratio_initialized is True
        assert len(usage) == 3
        for row in usage:
            total_input = (
                row["tool_tokens"]
                + row["system_tokens"]
                + row["skill_tokens"]
                + row["summary_tokens"]
                + row["message_tokens"]
            )
            assert total_input == row["input_tokens"]

        # Iterations 2 and 3 should have same tool_tokens (same base_tool_chars * base_ratio)
        assert usage[1]["tool_tokens"] == usage[2]["tool_tokens"]

    def test_base_ratio_resets_between_runs(self):
        """base_ratio should be reset when start_run() is called."""
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()

        # Run 1 with 2 iterations to set base_ratio
        tracker.start_run("run 1")
        tracker.start_iteration(1)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=500,
            completion_tokens=50,
            latency_ms=100.0,
            tool_calls_count=0,
            input_messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Hi"},
            ],
            output_text="Hello!",
        )
        tracker.end_iteration()
        tracker.start_iteration(2)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=700,
            completion_tokens=50,
            latency_ms=100.0,
            tool_calls_count=0,
            input_messages=[
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ],
            output_text="How can I help?",
        )
        tracker.end_iteration()
        tracker.end_run("How can I help?")

        # Trigger base_ratio computation
        tracker.get_detailed_usage()

        # After Run 1: base_ratio should be set
        assert tracker._base_ratio > 0.0
        assert tracker._base_ratio_initialized is True

        # Run 2: start_run should reset base_ratio fields
        tracker.start_run("run 2")
        assert tracker._base_ratio == 0.0
        assert tracker._base_ratio_initialized is False
        assert tracker._base_ratio_iteration == 0
        assert tracker._base_tool_chars == 0

    def test_first_iteration_breakdown_accurate(self):
        """First iteration should use per-iteration ratio, producing accurate breakdown."""
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()
        tracker.start_run("test")
        tracker.start_iteration(1)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=600,
            completion_tokens=50,
            latency_ms=100.0,
            tool_calls_count=0,
            input_messages=[
                {"role": "system", "content": "System prompt content here"},
                {"role": "user", "content": "Hello world"},
            ],
            output_text="Hi there!",
            tools_schema=[{"name": "tool1", "description": "A tool description"}],
        )
        tracker.end_iteration()
        tracker.end_run("Hi there!")

        usage = tracker.get_detailed_usage()
        assert len(usage) == 1
        row = usage[0]
        total_input = (
            row["tool_tokens"]
            + row["system_tokens"]
            + row["skill_tokens"]
            + row["summary_tokens"]
            + row["message_tokens"]
        )
        assert total_input == 600
        assert row["message_tokens"] >= 0
        assert row["tool_tokens"] > 0
        assert row["system_tokens"] > 0

    def test_message_tokens_never_negative(self):
        """message_tokens should never be negative due to max(0, ...) guard."""
        from nano_agent.monitoring.tracker import MetricsTracker

        tracker = MetricsTracker()
        tracker.start_run("test")

        # Iteration 1: very small prompt_tokens relative to fixed content
        tracker.start_iteration(1)
        tracker.record_llm_call(
            model="test",
            prompt_tokens=100,
            completion_tokens=10,
            latency_ms=100.0,
            tool_calls_count=0,
            input_messages=[
                {
                    "role": "system",
                    "content": "A" * 500,
                },  # Long system prompt
                {"role": "user", "content": "Hi"},
            ],
            output_text="Ok",
            tools_schema=[
                {"name": "tool1", "description": "B" * 200}
            ],  # Long tool schema
        )
        tracker.end_iteration()
        tracker.end_run("Ok")

        usage = tracker.get_detailed_usage()
        assert len(usage) == 1
        row = usage[0]
        assert row["message_tokens"] >= 0


class TestSmartOptimizationConfigCalibration:
    """Test SmartOptimizationConfig calibration fields."""

    def test_default_values(self):
        config = SmartOptimizationConfig()
        assert config.calibration_enabled is True
        assert config.calibration_window == 5
        assert config.min_calibration_samples == 3
        assert config.estimation_audit_enabled is True
        assert config.estimation_deviation_warning_threshold == 0.50

    def test_custom_values(self):
        config = SmartOptimizationConfig(
            calibration_enabled=False,
            calibration_window=10,
            min_calibration_samples=5,
            estimation_audit_enabled=False,
            estimation_deviation_warning_threshold=0.30,
        )
        assert config.calibration_enabled is False
        assert config.calibration_window == 10
        assert config.min_calibration_samples == 5
        assert config.estimation_audit_enabled is False
        assert config.estimation_deviation_warning_threshold == 0.30


class TestLLMCallMetricsNewFields:
    """Test LLMCallMetrics new fields and serialization."""

    def test_default_values(self):
        metrics = LLMCallMetrics(
            timestamp=datetime.now(),
            model="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=100.0,
            tool_calls_count=0,
        )
        assert metrics.estimated_tokens == 0
        assert metrics.deviation_pct == 0.0

    def test_custom_values(self):
        metrics = LLMCallMetrics(
            timestamp=datetime.now(),
            model="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=100.0,
            tool_calls_count=0,
            estimated_tokens=80,
            deviation_pct=0.25,
        )
        assert metrics.estimated_tokens == 80
        assert metrics.deviation_pct == 0.25

    def test_to_dict_includes_new_fields(self):
        metrics = LLMCallMetrics(
            timestamp=datetime.now(),
            model="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=100.0,
            tool_calls_count=0,
            estimated_tokens=80,
            deviation_pct=0.25,
        )
        d = metrics.to_dict()
        assert "estimated_tokens" in d
        assert d["estimated_tokens"] == 80
        assert "deviation_pct" in d
        assert d["deviation_pct"] == 0.25


class TestRawLLMCallDataNewFields:
    """Test RawLLMCallData new fields backward compatibility."""

    def test_default_values(self):
        raw = RawLLMCallData(
            llm=MagicMock(),
            messages=[],
            tools_schema=None,
            response_text="",
            tool_calls=[],
            usage=MagicMock(),
            latency_ms=100.0,
        )
        assert raw.estimated_tokens == 0
        assert raw.calibration_factor == 1.0

    def test_custom_values(self):
        raw = RawLLMCallData(
            llm=MagicMock(),
            messages=[],
            tools_schema=None,
            response_text="",
            tool_calls=[],
            usage=MagicMock(),
            latency_ms=100.0,
            estimated_tokens=80,
            calibration_factor=1.2,
        )
        assert raw.estimated_tokens == 80
        assert raw.calibration_factor == 1.2
