"""
Built-in middleware implementations.

Provides commonly used middlewares for logging, tracing, and confirmation.
"""

import time
from typing import Any

from ..middleware import BaseMiddleware, MiddlewareContext
from ..base import ToolResult
from ...agent.types import RiskLevel


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware for logging tool execution.

    Logs tool name, arguments, and execution time.
    Useful for debugging and monitoring.
    """

    priority = 100  # Run first to capture all executions

    def __init__(self, verbose: bool = True):
        """
        Initialize logging middleware.

        Args:
            verbose: If True, log arguments and results; if False, only log names
        """
        self._verbose = verbose

    def before(self, ctx: MiddlewareContext) -> ToolResult | None:
        """Log before execution."""
        if self._verbose:
            args_str = ", ".join(f"{k}={v}" for k, v in ctx.arguments.items())
            print(f"[Tool] {ctx.tool_name}({args_str})")
        else:
            print(f"[Tool] {ctx.tool_name}")
        return None

    def after(self, ctx: MiddlewareContext) -> None:
        """Log after execution."""
        elapsed = ctx.end_time - ctx.start_time
        status = "✓" if ctx.result.success else "✗"
        if self._verbose and ctx.result.output:
            output_preview = ctx.result.output[:100]
            if len(ctx.result.output) > 100:
                output_preview += "..."
            print(f"[Tool] {ctx.tool_name} {status} ({elapsed:.2f}s): {output_preview}")
        else:
            print(f"[Tool] {ctx.tool_name} {status} ({elapsed:.2f}s)")

    def error(self, ctx: MiddlewareContext) -> None:
        """Log error."""
        elapsed = ctx.end_time - ctx.start_time
        print(f"[Tool] {ctx.tool_name} ✗ ({elapsed:.2f}s): {ctx.error}")


class TracingMiddleware(BaseMiddleware):
    """
    Middleware for tracing tool execution history.

    Records all tool executions in a list, useful for debugging
    and analyzing agent behavior.
    """

    priority = 90  # Run after logging

    def __init__(self, max_traces: int = 100):
        """
        Initialize tracing middleware.

        Args:
            max_traces: Maximum number of traces to keep
        """
        self._max_traces = max_traces
        self._traces: list[dict[str, Any]] = []

    def before(self, ctx: MiddlewareContext) -> ToolResult | None:
        """Record trace start."""
        ctx.state["trace_index"] = len(self._traces)
        self._traces.append({
            "tool": ctx.tool_name,
            "arguments": ctx.arguments.copy(),
            "start_time": ctx.start_time,
            "status": "running"
        })
        return None

    def after(self, ctx: MiddlewareContext) -> None:
        """Record trace completion."""
        idx = ctx.state.get("trace_index", -1)
        if 0 <= idx < len(self._traces):
            self._traces[idx]["end_time"] = ctx.end_time
            self._traces[idx]["elapsed"] = ctx.end_time - ctx.start_time
            self._traces[idx]["status"] = "completed"
            self._traces[idx]["success"] = ctx.result.success
            self._traces[idx]["output"] = ctx.result.output[:200] if ctx.result.output else ""

        # Trim old traces
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces:]

    def error(self, ctx: MiddlewareContext) -> None:
        """Record trace error."""
        idx = ctx.state.get("trace_index", -1)
        if 0 <= idx < len(self._traces):
            self._traces[idx]["end_time"] = ctx.end_time
            self._traces[idx]["elapsed"] = ctx.end_time - ctx.start_time
            self._traces[idx]["status"] = "error"
            self._traces[idx]["error"] = str(ctx.error)

    def get_traces(self) -> list[dict[str, Any]]:
        """Get all recorded traces."""
        return self._traces.copy()

    def clear_traces(self) -> None:
        """Clear all traces."""
        self._traces.clear()


class ConfirmationMiddleware(BaseMiddleware):
    """
    Middleware for confirming dangerous tool executions.

    Requires user confirmation before executing tools with
    dangerous risk level.
    """

    priority = 50  # Run after logging/tracing

    def __init__(
        self,
        auto_confirm_safe: bool = True,
        confirm_callback: callable = None
    ):
        """
        Initialize confirmation middleware.

        Args:
            auto_confirm_safe: If True, auto-confirm SAFE level tools
            confirm_callback: Function to call for confirmation (returns bool)
                              If None, uses default console confirmation
        """
        self._auto_confirm_safe = auto_confirm_safe
        self._confirm_callback = confirm_callback
        self._skipped_tools: set[str] = set()  # Tools that were skipped

    def before(self, ctx: MiddlewareContext) -> ToolResult | None:
        """Check if confirmation is needed."""
        # Get tool from registry (passed via state by executor)
        tool = ctx.state.get("tool")
        if tool is None:
            return None

        risk_level = getattr(tool, "risk_level", RiskLevel.MODERATE)

        # Auto-confirm safe operations if configured
        if self._auto_confirm_safe and risk_level == RiskLevel.SAFE:
            return None

        # Skip confirmation for certain tools
        if ctx.tool_name in self._skipped_tools:
            return None

        # Get confirmation
        if self._confirm_callback:
            confirmed = self._confirm_callback(ctx.tool_name, ctx.arguments, risk_level)
        else:
            confirmed = self._default_confirm(ctx.tool_name, ctx.arguments, risk_level)

        if not confirmed:
            # User rejected, return error result
            self._skipped_tools.add(ctx.tool_name)
            return ToolResult(
                success=False,
                output="",
                error=f"Tool execution cancelled by user: {ctx.tool_name}"
            )

        return None

    def _default_confirm(self, tool_name: str, arguments: dict, risk_level: RiskLevel) -> bool:
        """Default console confirmation."""
        risk_icons = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.MODERATE: "🟡",
            RiskLevel.DANGEROUS: "🔴"
        }
        icon = risk_icons.get(risk_level, "⚪")

        print(f"\n{icon} Tool '{tool_name}' requires confirmation (risk: {risk_level.value})")
        print(f"   Arguments: {arguments}")

        try:
            response = input("   Proceed? [y/N]: ").strip().lower()
            return response in ("y", "yes", "ok")
        except (EOFError, KeyboardInterrupt):
            return False

    def skip_tool(self, tool_name: str) -> None:
        """Add a tool to the skip list (no confirmation needed)."""
        self._skipped_tools.add(tool_name)

    def require_tool(self, tool_name: str) -> None:
        """Remove a tool from the skip list."""
        self._skipped_tools.discard(tool_name)


class CachingMiddleware(BaseMiddleware):
    """
    Middleware for caching tool execution results.

    Caches results based on tool name and arguments hash.
    Useful for expensive operations that may be repeated.
    """

    priority = 200  # Run first to check cache before anything else

    def __init__(self, max_cache_size: int = 50, ttl_seconds: float = 300):
        """
        Initialize caching middleware.

        Args:
            max_cache_size: Maximum number of cached results
            ttl_seconds: Time-to-live for cached results
        """
        self._max_cache_size = max_cache_size
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, ToolResult]] = {}

    def _cache_key(self, tool_name: str, arguments: dict) -> str:
        """Generate cache key from tool name and arguments."""
        import hashlib
        args_hash = hashlib.md5(str(sorted(arguments.items())).encode()).hexdigest()
        return f"{tool_name}:{args_hash}"

    def before(self, ctx: MiddlewareContext) -> ToolResult | None:
        """Check cache for existing result."""
        key = self._cache_key(ctx.tool_name, ctx.arguments)
        cached = self._cache.get(key)

        if cached:
            cached_time, cached_result = cached
            elapsed = time.time() - cached_time

            if elapsed < self._ttl_seconds:
                # Cache hit
                ctx.state["cache_hit"] = True
                print(f"[Cache] Hit for {ctx.tool_name}")
                return cached_result

        # Cache miss, continue execution
        ctx.state["cache_key"] = key
        return None

    def after(self, ctx: MiddlewareContext) -> None:
        """Cache successful result."""
        if ctx.state.get("cache_hit"):
            return  # Don't re-cache

        if ctx.result.success:
            key = ctx.state.get("cache_key")
            if key:
                self._cache[key] = (time.time(), ctx.result)

                # Trim cache if too large
                if len(self._cache) > self._max_cache_size:
                    # Remove oldest entries
                    sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])
                    for old_key in sorted_keys[:len(self._cache) - self._max_cache_size]:
                        del self._cache[old_key]

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._max_cache_size
        }