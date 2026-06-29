"""
Tests for tool resource limiter (v0.8.10) — timeout and rate limiting.
"""

import time
import pytest

from nano_agent.tools.resource_limiter import (
    ToolTimeoutWrapper,
    ToolRateLimiter,
    RateLimitResult,
    RateLimitType,
    _MiniTokenBucket,
)
from nano_agent.tools.base import ToolResult, BaseTool
from nano_agent.config.schema import ToolResourceLimiterConfig

pytestmark = pytest.mark.unit


# === MiniTokenBucket Tests ===


class TestMiniTokenBucket:
    def test_initial_tokens_equal_max(self):
        bucket = _MiniTokenBucket(30)
        assert bucket.remaining() == 30

    def test_try_acquire_success(self):
        bucket = _MiniTokenBucket(30)
        assert bucket.try_acquire() is True

    def test_try_acquire_decrements(self):
        bucket = _MiniTokenBucket(3)
        assert bucket.try_acquire() is True
        assert bucket.try_acquire() is True
        assert bucket.try_acquire() is True
        assert bucket.try_acquire() is False

    def test_refill_over_time(self):
        bucket = _MiniTokenBucket(60)  # 1 token/sec
        # Drain all tokens
        for _ in range(60):
            bucket.try_acquire()
        assert bucket.remaining() == 0

        # Wait for refill
        time.sleep(1.1)
        assert bucket.try_acquire() is True

    def test_wait_time_zero_when_tokens_available(self):
        bucket = _MiniTokenBucket(30)
        assert bucket.wait_time() == 0.0

    def test_wait_time_positive_when_empty(self):
        bucket = _MiniTokenBucket(60)  # 1 token/sec
        for _ in range(60):
            bucket.try_acquire()
        wait = bucket.wait_time()
        assert wait > 0

    def test_reset_restores_full_capacity(self):
        bucket = _MiniTokenBucket(10)
        for _ in range(10):
            bucket.try_acquire()
        assert bucket.remaining() == 0
        bucket.reset()
        assert bucket.remaining() == 10

    def test_tokens_capped_at_max(self):
        bucket = _MiniTokenBucket(5)
        time.sleep(0.1)  # Trigger refill
        bucket._refill()
        assert bucket.remaining() <= 5

    def test_release_returns_token(self):
        bucket = _MiniTokenBucket(3)
        for _ in range(3):
            bucket.try_acquire()
        assert bucket.remaining() == 0
        bucket.release()
        assert bucket.remaining() == 1

    def test_release_capped_at_max(self):
        bucket = _MiniTokenBucket(3)
        bucket.release()  # Already full
        assert bucket.remaining() == 3


# === ToolTimeoutWrapper Tests ===


class TestToolTimeoutWrapper:
    def test_get_timeout_default(self):
        wrapper = ToolTimeoutWrapper(default_timeout=60)
        assert wrapper.get_timeout("file_read") == 60

    def test_get_timeout_override(self):
        wrapper = ToolTimeoutWrapper(
            default_timeout=60, timeout_overrides={"shell_execute": 30}
        )
        assert wrapper.get_timeout("shell_execute") == 30
        assert wrapper.get_timeout("file_read") == 60

    def test_get_timeout_zero_means_no_timeout(self):
        wrapper = ToolTimeoutWrapper(default_timeout=0)
        assert wrapper.get_timeout("any_tool") == 0

    def test_execute_with_timeout_fast_function(self):
        wrapper = ToolTimeoutWrapper(default_timeout=5)

        def fast_executor():
            return ToolResult(success=True, output="done")

        result = wrapper.execute_with_timeout("file_read", fast_executor)
        assert result.success is True
        assert result.output == "done"

    def test_execute_with_timeout_no_timeout_when_zero(self):
        wrapper = ToolTimeoutWrapper(default_timeout=0)

        def executor():
            return ToolResult(success=True, output="ok")

        result = wrapper.execute_with_timeout("any", executor)
        assert result.success is True

    def test_should_wrap_tool_without_builtin_timeout(self):
        wrapper = ToolTimeoutWrapper(default_timeout=60)

        class NoTimeoutTool(BaseTool):
            name = "test"
            description = "test"

            @property
            def parameters_schema(self):
                return {}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        tool = NoTimeoutTool()
        assert wrapper.should_wrap(tool) is True

    def test_should_skip_tool_with_builtin_timeout(self):
        wrapper = ToolTimeoutWrapper(default_timeout=60)

        class BuiltinTimeoutTool(BaseTool):
            name = "test"
            description = "test"
            has_builtin_timeout = True

            @property
            def parameters_schema(self):
                return {}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        tool = BuiltinTimeoutTool()
        assert wrapper.should_wrap(tool) is False

    def test_execute_with_timeout_handles_exception(self):
        wrapper = ToolTimeoutWrapper(default_timeout=5)

        def failing_executor():
            raise ValueError("test error")

        result = wrapper.execute_with_timeout("file_read", failing_executor)
        assert result.success is False
        assert "test error" in result.error


# === ToolRateLimiter Tests ===


class TestToolRateLimiter:
    def test_first_call_allowed(self):
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=30, global_calls_per_minute=60
        )
        result = limiter.check("file_read")
        assert result.allowed is True
        assert result.tool_name == "file_read"

    def test_per_tool_rate_limit(self):
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=3, global_calls_per_minute=100
        )
        # First 3 calls should succeed
        for _ in range(3):
            result = limiter.check("file_read")
            assert result.allowed is True
        # 4th call should be rate limited
        result = limiter.check("file_read")
        assert result.allowed is False
        assert result.limit_type == RateLimitType.PER_TOOL

    def test_global_rate_limit(self):
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=100, global_calls_per_minute=3
        )
        # First 3 calls across different tools should succeed
        assert limiter.check("file_read").allowed is True
        assert limiter.check("file_write").allowed is True
        assert limiter.check("shell_execute").allowed is True
        # 4th call should hit global limit
        result = limiter.check("memorize")
        assert result.allowed is False
        assert result.limit_type == RateLimitType.GLOBAL

    def test_different_tools_have_separate_buckets(self):
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=2, global_calls_per_minute=100
        )
        # Use up file_read quota
        assert limiter.check("file_read").allowed is True
        assert limiter.check("file_read").allowed is True
        assert limiter.check("file_read").allowed is False
        # file_write should still work
        assert limiter.check("file_write").allowed is True

    def test_rate_limit_result_has_wait_time(self):
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=3, global_calls_per_minute=100
        )
        for _ in range(3):
            limiter.check("file_read")
        result = limiter.check("file_read")
        assert result.allowed is False
        assert result.wait_time > 0

    def test_rate_limit_result_has_calls_remaining(self):
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=5, global_calls_per_minute=100
        )
        result = limiter.check("file_read")
        assert result.allowed is True
        assert result.calls_remaining >= 3  # Used 1, should have ~4 left

    def test_reset_clears_all_limits(self):
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=2, global_calls_per_minute=2
        )
        limiter.check("file_read")
        limiter.check("file_read")
        assert limiter.check("file_read").allowed is False
        limiter.reset()
        assert limiter.check("file_read").allowed is True

    def test_global_token_returned_on_per_tool_rejection(self):
        """When per-tool limit hits, global token should be returned."""
        limiter = ToolRateLimiter(
            per_tool_calls_per_minute=1, global_calls_per_minute=3
        )
        # Use file_read's per-tool quota
        limiter.check("file_read")
        # file_read is now per-tool limited; global token should be returned
        limiter.check("file_read")
        # Other tools should still be able to use global quota
        assert limiter.check("file_write").allowed is True


# === ToolResourceLimiterConfig Tests ===


class TestToolResourceLimiterConfig:
    def test_defaults(self):
        config = ToolResourceLimiterConfig()
        assert config.enabled is True
        assert config.timeout_enabled is True
        assert config.default_timeout == 60
        assert config.rate_limit_enabled is True
        assert config.per_tool_calls_per_minute == 30
        assert config.global_calls_per_minute == 60

    def test_custom_values(self):
        config = ToolResourceLimiterConfig(
            enabled=False,
            default_timeout=120,
            per_tool_calls_per_minute=10,
        )
        assert config.enabled is False
        assert config.default_timeout == 120
        assert config.per_tool_calls_per_minute == 10

    def test_validation_negative_timeout(self):
        with pytest.raises(ValueError, match="default_timeout"):
            ToolResourceLimiterConfig(default_timeout=-1)

    def test_validation_negative_per_tool(self):
        with pytest.raises(ValueError, match="per_tool_calls_per_minute"):
            ToolResourceLimiterConfig(per_tool_calls_per_minute=0)

    def test_validation_negative_global(self):
        with pytest.raises(ValueError, match="global_calls_per_minute"):
            ToolResourceLimiterConfig(global_calls_per_minute=-5)

    def test_timeout_overrides_default_empty(self):
        config = ToolResourceLimiterConfig()
        assert config.timeout_overrides == {}

    def test_timeout_overrides_custom(self):
        config = ToolResourceLimiterConfig(
            timeout_overrides={"file_read": 30, "shell_execute": 120}
        )
        assert config.timeout_overrides["file_read"] == 30


# === Integration: Subsystems + Config ===


class TestSubsystemsIntegration:
    def test_subsystems_creates_timeout_wrapper(self):
        from nano_agent.agent.subsystems import AgentSubsystems
        from nano_agent.config.schema import (
            SmartOptimizationConfig,
            OutputStyleConfig,
            CacheConfig,
            CompressorConfig,
            SemanticCompressorConfig,
            ToolMergeConfig,
            ConfirmationConfig,
            ToolOffloadConfig,
            AggressiveOutputConfig,
            StandardizedOutputConfig,
            PromptConfig,
        )

        config = ToolResourceLimiterConfig(
            timeout_enabled=True, rate_limit_enabled=False
        )
        subs = AgentSubsystems.from_configs(
            smart_optimization=SmartOptimizationConfig(),
            output_style=OutputStyleConfig(),
            cache=CacheConfig(),
            compressor=CompressorConfig(),
            semantic_compressor=SemanticCompressorConfig(),
            tool_merge=ToolMergeConfig(),
            confirmation=ConfirmationConfig(),
            offload=ToolOffloadConfig(),
            aggressive_output=AggressiveOutputConfig(),
            standardized_output=StandardizedOutputConfig(),
            prompt=PromptConfig(),
            tool_resource_limiter=config,
        )
        assert subs.timeout_wrapper is not None
        assert subs.rate_limiter is None

    def test_subsystems_creates_rate_limiter(self):
        from nano_agent.agent.subsystems import AgentSubsystems
        from nano_agent.config.schema import (
            SmartOptimizationConfig,
            OutputStyleConfig,
            CacheConfig,
            CompressorConfig,
            SemanticCompressorConfig,
            ToolMergeConfig,
            ConfirmationConfig,
            ToolOffloadConfig,
            AggressiveOutputConfig,
            StandardizedOutputConfig,
            PromptConfig,
        )

        config = ToolResourceLimiterConfig(
            timeout_enabled=False, rate_limit_enabled=True
        )
        subs = AgentSubsystems.from_configs(
            smart_optimization=SmartOptimizationConfig(),
            output_style=OutputStyleConfig(),
            cache=CacheConfig(),
            compressor=CompressorConfig(),
            semantic_compressor=SemanticCompressorConfig(),
            tool_merge=ToolMergeConfig(),
            confirmation=ConfirmationConfig(),
            offload=ToolOffloadConfig(),
            aggressive_output=AggressiveOutputConfig(),
            standardized_output=StandardizedOutputConfig(),
            prompt=PromptConfig(),
            tool_resource_limiter=config,
        )
        assert subs.timeout_wrapper is None
        assert subs.rate_limiter is not None

    def test_subsystems_creates_both(self):
        from nano_agent.agent.subsystems import AgentSubsystems
        from nano_agent.config.schema import (
            SmartOptimizationConfig,
            OutputStyleConfig,
            CacheConfig,
            CompressorConfig,
            SemanticCompressorConfig,
            ToolMergeConfig,
            ConfirmationConfig,
            ToolOffloadConfig,
            AggressiveOutputConfig,
            StandardizedOutputConfig,
            PromptConfig,
        )

        config = ToolResourceLimiterConfig()
        subs = AgentSubsystems.from_configs(
            smart_optimization=SmartOptimizationConfig(),
            output_style=OutputStyleConfig(),
            cache=CacheConfig(),
            compressor=CompressorConfig(),
            semantic_compressor=SemanticCompressorConfig(),
            tool_merge=ToolMergeConfig(),
            confirmation=ConfirmationConfig(),
            offload=ToolOffloadConfig(),
            aggressive_output=AggressiveOutputConfig(),
            standardized_output=StandardizedOutputConfig(),
            prompt=PromptConfig(),
            tool_resource_limiter=config,
        )
        assert subs.timeout_wrapper is not None
        assert subs.rate_limiter is not None

    def test_subsystems_disabled_creates_neither(self):
        from nano_agent.agent.subsystems import AgentSubsystems
        from nano_agent.config.schema import (
            SmartOptimizationConfig,
            OutputStyleConfig,
            CacheConfig,
            CompressorConfig,
            SemanticCompressorConfig,
            ToolMergeConfig,
            ConfirmationConfig,
            ToolOffloadConfig,
            AggressiveOutputConfig,
            StandardizedOutputConfig,
            PromptConfig,
        )

        config = ToolResourceLimiterConfig(enabled=False)
        subs = AgentSubsystems.from_configs(
            smart_optimization=SmartOptimizationConfig(),
            output_style=OutputStyleConfig(),
            cache=CacheConfig(),
            compressor=CompressorConfig(),
            semantic_compressor=SemanticCompressorConfig(),
            tool_merge=ToolMergeConfig(),
            confirmation=ConfirmationConfig(),
            offload=ToolOffloadConfig(),
            aggressive_output=AggressiveOutputConfig(),
            standardized_output=StandardizedOutputConfig(),
            prompt=PromptConfig(),
            tool_resource_limiter=config,
        )
        assert subs.timeout_wrapper is None
        assert subs.rate_limiter is None

    def test_subsystems_none_config_creates_neither(self):
        from nano_agent.agent.subsystems import AgentSubsystems

        subs = AgentSubsystems.from_defaults()
        assert subs.timeout_wrapper is None
        assert subs.rate_limiter is None


# === BaseTool.has_builtin_timeout ===


class TestBaseToolBuiltinTimeout:
    def test_default_is_false(self):
        class TestTool(BaseTool):
            name = "test"
            description = "test"

            @property
            def parameters_schema(self):
                return {}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        tool = TestTool()
        assert tool.has_builtin_timeout is False

    def test_can_set_to_true(self):
        class FastTool(BaseTool):
            name = "fast"
            description = "fast"
            has_builtin_timeout = True

            @property
            def parameters_schema(self):
                return {}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="")

        tool = FastTool()
        assert tool.has_builtin_timeout is True
