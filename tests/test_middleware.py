"""
Tests for tool execution middleware system.
"""

import pytest
import time
from unittest.mock import Mock, patch

from nano_agent.tools.middleware import (
    BaseMiddleware,
    MiddlewarePhase,
    MiddlewareContext,
    MiddlewareChain,
)
from nano_agent.tools.middlewares import (
    LoggingMiddleware,
    TracingMiddleware,
    ConfirmationMiddleware,
    CachingMiddleware,
)
from nano_agent.tools.base import BaseTool, ToolResult
from nano_agent.tools.registry import ToolRegistry
from nano_agent.agent.types import RiskLevel


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"
    risk_level = RiskLevel.MODERATE

    def __init__(self, output: str = "mock result", should_fail: bool = False):
        self._output = output
        self._should_fail = should_fail

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> ToolResult:
        if self._should_fail:
            raise ValueError("Mock error")
        return ToolResult(success=True, output=self._output)


class TestMiddlewareContext:
    """Tests for MiddlewareContext."""

    def test_create_context(self):
        """Test creating a context."""
        ctx = MiddlewareContext(tool_name="test_tool", arguments={"arg1": "value1"})
        assert ctx.tool_name == "test_tool"
        assert ctx.arguments == {"arg1": "value1"}
        assert ctx.result is None
        assert ctx.error is None
        assert ctx.state == {}

    def test_state_is_initialized(self):
        """Test that state is initialized to empty dict."""
        ctx = MiddlewareContext(tool_name="test", arguments={})
        assert ctx.state is not None
        assert isinstance(ctx.state, dict)


class TestMiddlewareChain:
    """Tests for MiddlewareChain."""

    def test_add_middleware(self):
        """Test adding middleware."""
        chain = MiddlewareChain()
        middleware = LoggingMiddleware()
        chain.add(middleware)
        assert len(chain) == 1

    def test_remove_middleware(self):
        """Test removing middleware."""
        chain = MiddlewareChain()
        middleware = LoggingMiddleware()
        chain.add(middleware)
        assert chain.remove(middleware) is True
        assert len(chain) == 0

    def test_remove_nonexistent(self):
        """Test removing nonexistent middleware."""
        chain = MiddlewareChain()
        middleware = LoggingMiddleware()
        assert chain.remove(middleware) is False

    def test_execute_without_middleware(self):
        """Test execution without middleware."""
        chain = MiddlewareChain()
        result = chain.execute(
            "test_tool",
            {"arg": "value"},
            lambda args: ToolResult(success=True, output="done"),
        )
        assert result.success is True
        assert result.output == "done"

    def test_execute_with_middleware(self):
        """Test execution with middleware."""
        chain = MiddlewareChain()

        call_log = []

        class TestMiddleware(BaseMiddleware):
            def before(self, ctx):
                call_log.append(("before", ctx.tool_name))
                return None

            def after(self, ctx):
                call_log.append(("after", ctx.tool_name))

        chain.add(TestMiddleware())
        chain.execute(
            "test_tool", {}, lambda args: ToolResult(success=True, output="done")
        )

        assert ("before", "test_tool") in call_log
        assert ("after", "test_tool") in call_log

    def test_middleware_priority_order(self):
        """Test that middleware runs in priority order."""
        chain = MiddlewareChain()

        order = []

        class LowPriority(BaseMiddleware):
            priority = 10

            def before(self, ctx):
                order.append("low_before")

        class HighPriority(BaseMiddleware):
            priority = 100

            def before(self, ctx):
                order.append("high_before")

        chain.add(LowPriority())
        chain.add(HighPriority())
        chain.execute("test", {}, lambda args: ToolResult(success=True, output="done"))

        # Higher priority should run first
        assert order == ["high_before", "low_before"]

    def test_middleware_short_circuit(self):
        """Test that middleware can short-circuit execution."""
        chain = MiddlewareChain()

        class ShortCircuitMiddleware(BaseMiddleware):
            def before(self, ctx):
                return ToolResult(success=False, output="", error="Blocked")

        chain.add(ShortCircuitMiddleware())

        executor_called = []

        def executor(args):
            executor_called.append(True)
            return ToolResult(success=True, output="done")

        result = chain.execute("test", {}, executor)

        assert result.success is False
        assert result.error == "Blocked"
        assert len(executor_called) == 0  # Executor should not be called

    def test_middleware_error_handling(self):
        """Test that middleware handles errors."""
        chain = MiddlewareChain()

        error_log = []

        class ErrorMiddleware(BaseMiddleware):
            def error(self, ctx):
                error_log.append(str(ctx.error))

        chain.add(ErrorMiddleware())

        def failing_executor(args):
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            chain.execute("test", {}, failing_executor)

        assert "Test error" in error_log


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    def test_logs_execution(self, capsys):
        """Test that logging middleware logs execution."""
        middleware = LoggingMiddleware(verbose=True)
        chain = MiddlewareChain()
        chain.add(middleware)

        chain.execute(
            "test_tool",
            {"arg": "value"},
            lambda args: ToolResult(success=True, output="done"),
        )

        captured = capsys.readouterr()
        assert "test_tool" in captured.out
        assert "arg" in captured.out

    def test_non_verbose_mode(self, capsys):
        """Test non-verbose mode."""
        middleware = LoggingMiddleware(verbose=False)
        chain = MiddlewareChain()
        chain.add(middleware)

        chain.execute(
            "test_tool",
            {"arg": "value"},
            lambda args: ToolResult(success=True, output="done"),
        )

        captured = capsys.readouterr()
        assert "test_tool" in captured.out
        assert "arg" not in captured.out


class TestTracingMiddleware:
    """Tests for TracingMiddleware."""

    def test_records_traces(self):
        """Test that tracing middleware records traces."""
        middleware = TracingMiddleware()
        chain = MiddlewareChain()
        chain.add(middleware)

        chain.execute("tool1", {}, lambda args: ToolResult(success=True, output="done"))
        chain.execute("tool2", {}, lambda args: ToolResult(success=True, output="done"))

        traces = middleware.get_traces()
        assert len(traces) == 2
        assert traces[0]["tool"] == "tool1"
        assert traces[1]["tool"] == "tool2"
        assert traces[0]["status"] == "completed"

    def test_max_traces_limit(self):
        """Test that trace limit is enforced."""
        middleware = TracingMiddleware(max_traces=3)
        chain = MiddlewareChain()
        chain.add(middleware)

        for i in range(5):
            chain.execute(
                f"tool{i}", {}, lambda args: ToolResult(success=True, output="done")
            )

        traces = middleware.get_traces()
        assert len(traces) == 3

    def test_clear_traces(self):
        """Test clearing traces."""
        middleware = TracingMiddleware()
        chain = MiddlewareChain()
        chain.add(middleware)

        chain.execute("tool1", {}, lambda args: ToolResult(success=True, output="done"))
        assert len(middleware.get_traces()) == 1

        middleware.clear_traces()
        assert len(middleware.get_traces()) == 0


class TestConfirmationMiddleware:
    """Tests for ConfirmationMiddleware."""

    def test_auto_confirm_safe(self):
        """Test that safe tools are auto-confirmed."""
        middleware = ConfirmationMiddleware(auto_confirm_safe=True)

        ctx = MiddlewareContext(tool_name="safe_tool", arguments={})
        ctx.state["tool"] = MockTool()
        ctx.state["tool"].risk_level = RiskLevel.SAFE

        result = middleware.before(ctx)
        assert result is None  # None means proceed

    def test_custom_confirm_callback(self):
        """Test custom confirmation callback."""
        confirm_calls = []

        def callback(tool_name, args, risk_level):
            confirm_calls.append((tool_name, risk_level))
            return True

        middleware = ConfirmationMiddleware(confirm_callback=callback)

        ctx = MiddlewareContext(tool_name="test_tool", arguments={})
        ctx.state["tool"] = MockTool()

        result = middleware.before(ctx)
        assert result is None
        assert len(confirm_calls) == 1

    def test_user_rejects(self):
        """Test that rejection returns error result."""
        middleware = ConfirmationMiddleware(confirm_callback=lambda *args: False)

        ctx = MiddlewareContext(tool_name="test_tool", arguments={})
        ctx.state["tool"] = MockTool()

        result = middleware.before(ctx)
        assert result is not None
        assert result.success is False
        assert "cancelled" in result.error.lower()


class TestCachingMiddleware:
    """Tests for CachingMiddleware."""

    def test_caches_result(self):
        """Test that results are cached."""
        middleware = CachingMiddleware()
        chain = MiddlewareChain()
        chain.add(middleware)

        call_count = [0]

        def counting_executor(args):
            call_count[0] += 1
            return ToolResult(success=True, output=f"call_{call_count[0]}")

        # First call
        result1 = chain.execute("test", {"arg": "value"}, counting_executor)
        assert result1.output == "call_1"

        # Second call with same args should be cached
        result2 = chain.execute("test", {"arg": "value"}, counting_executor)
        assert result2.output == "call_1"  # Same as first call
        assert call_count[0] == 1  # Executor only called once

    def test_different_args_not_cached(self):
        """Test that different arguments are not cached."""
        middleware = CachingMiddleware()
        chain = MiddlewareChain()
        chain.add(middleware)

        call_count = [0]

        def counting_executor(args):
            call_count[0] += 1
            return ToolResult(success=True, output=f"call_{call_count[0]}")

        chain.execute("test", {"arg": "value1"}, counting_executor)
        chain.execute("test", {"arg": "value2"}, counting_executor)

        assert call_count[0] == 2  # Both calls executed

    def test_cache_expiry(self):
        """Test that cache expires after TTL."""
        middleware = CachingMiddleware(ttl_seconds=0.1)
        chain = MiddlewareChain()
        chain.add(middleware)

        call_count = [0]

        def counting_executor(args):
            call_count[0] += 1
            return ToolResult(success=True, output=f"call_{call_count[0]}")

        # First call
        chain.execute("test", {}, counting_executor)
        assert call_count[0] == 1

        # Wait for TTL to expire
        time.sleep(0.15)

        # Should execute again
        chain.execute("test", {}, counting_executor)
        assert call_count[0] == 2


class TestToolRegistryWithMiddleware:
    """Tests for ToolRegistry with middleware integration."""

    def test_execute_with_middleware(self):
        """Test that registry.execute uses middleware."""
        registry = ToolRegistry()
        registry.register(MockTool(output="test result"))

        trace_middleware = TracingMiddleware()
        registry.add_middleware(trace_middleware)

        result = registry.execute("mock_tool")

        assert result.success is True
        assert result.output == "test result"
        assert len(trace_middleware.get_traces()) == 1

    def test_execute_tool_bypasses_middleware(self):
        """Test that execute_tool bypasses middleware."""
        registry = ToolRegistry()
        registry.register(MockTool())

        trace_middleware = TracingMiddleware()
        registry.add_middleware(trace_middleware)

        result = registry.execute_tool("mock_tool", {})

        assert result.success is True
        assert len(trace_middleware.get_traces()) == 0  # No traces recorded

    def test_add_remove_middleware(self):
        """Test adding and removing middleware."""
        registry = ToolRegistry()
        middleware = LoggingMiddleware()

        registry.add_middleware(middleware)
        assert registry.remove_middleware(middleware) is True
        assert registry.remove_middleware(middleware) is False

    def test_unknown_tool_error(self):
        """Test error for unknown tool."""
        registry = ToolRegistry()

        result = registry.execute("unknown_tool")
        assert result.success is False
        assert "Unknown tool" in result.error
