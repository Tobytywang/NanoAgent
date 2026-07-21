"""
Tool resource limiter — timeout and rate limiting for tool execution.

Provides two protection layers:
1. ToolTimeoutWrapper: Framework-level timeout for tools without built-in timeout
2. ToolRateLimiter: Per-tool and global call frequency limits using token buckets
"""

import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .base import ToolResult


class RateLimitType(str, Enum):
    GLOBAL = "global"
    PER_TOOL = "per_tool"


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    tool_name: str
    limit_type: RateLimitType | None = None
    calls_remaining: int = 0
    wait_time: float = 0.0


class _MiniTokenBucket:
    """Lightweight token bucket for rate limiting.

    Not thread-safe — designed for synchronous single-threaded agent execution.
    """

    def __init__(self, calls_per_minute: int):
        self._max_tokens = float(calls_per_minute)
        self._tokens = self._max_tokens
        self._refill_rate = calls_per_minute / 60.0
        self._last_refill = time.monotonic()

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking."""
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def release(self) -> None:
        """Return a previously acquired token."""
        self._tokens = min(self._max_tokens, self._tokens + 1.0)

    def wait_time(self) -> float:
        """Estimated seconds until next token available."""
        self._refill()
        if self._tokens >= 1.0:
            return 0.0
        return (1.0 - self._tokens) / self._refill_rate

    def remaining(self) -> int:
        """Current token count (floor)."""
        self._refill()
        return int(self._tokens)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def reset(self) -> None:
        self._tokens = self._max_tokens
        self._last_refill = time.monotonic()


class ToolTimeoutWrapper:
    """Framework-level timeout wrapper for tool execution.

    Uses signal.setitimer on Unix/macOS, ThreadPoolExecutor as fallback.
    Tools with built-in timeout (has_builtin_timeout=True) are skipped.
    """

    def __init__(self, default_timeout: int, timeout_overrides: dict | None = None):
        self.default_timeout = default_timeout
        self.timeout_overrides = timeout_overrides or {}
        self._thread_pool: ThreadPoolExecutor | None = None

    def get_timeout(self, tool_name: str) -> int | None:
        """Get timeout for a tool."""
        if tool_name in self.timeout_overrides:
            return self.timeout_overrides[tool_name]
        return self.default_timeout

    def execute_with_timeout(
        self, tool_name: str, executor: Callable[[], ToolResult]
    ) -> ToolResult:
        """Execute a tool call with timeout protection."""
        timeout = self.get_timeout(tool_name)
        if timeout is None or timeout <= 0:
            return executor()

        if (
            hasattr(signal, "SIGALRM")
            and threading.current_thread() is threading.main_thread()
        ):
            return self._execute_with_signal(timeout, executor)
        return self._execute_with_threadpool(timeout, executor)

    def _execute_with_signal(
        self, timeout: float, executor: Callable[[], ToolResult]
    ) -> ToolResult:
        """Unix/macOS: use signal.setitimer for sub-second precision."""
        result_holder = [None]
        timed_out = [False]

        def _timeout_handler(signum, frame):
            timed_out[0] = True

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            result_holder[0] = executor()
        except Exception as e:
            if timed_out[0]:
                return ToolResult(
                    success=False, output="", error=f"工具执行超时 ({timeout}秒)"
                )
            return ToolResult(success=False, output="", error=str(e))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)

        if timed_out[0]:
            return ToolResult(
                success=False, output="", error=f"工具执行超时 ({timeout}秒)"
            )
        return result_holder[0]

    def _execute_with_threadpool(
        self, timeout: float, executor: Callable[[], ToolResult]
    ) -> ToolResult:
        """Fallback: use ThreadPoolExecutor with future.result(timeout=)."""
        if self._thread_pool is None:
            self._thread_pool = ThreadPoolExecutor(max_workers=1)

        future = self._thread_pool.submit(executor)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            return ToolResult(
                success=False, output="", error=f"工具执行超时 ({timeout}秒)"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def should_wrap(self, tool) -> bool:
        """Check if a tool should be wrapped with timeout.

        Tools with has_builtin_timeout=True manage their own timeout.
        """
        return not getattr(tool, "has_builtin_timeout", False)

    def close(self) -> None:
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=False)
            self._thread_pool = None


class ToolRateLimiter:
    """Per-tool and global call frequency limiter using token buckets.

    Unlike the LLM RateLimiter (which blocks until a token is available),
    this limiter returns immediately when rate-limited.
    """

    def __init__(
        self,
        per_tool_calls_per_minute: int = 30,
        global_calls_per_minute: int = 60,
    ):
        self._per_tool_limit = per_tool_calls_per_minute
        self._global_bucket = _MiniTokenBucket(global_calls_per_minute)
        self._per_tool_buckets: dict[str, _MiniTokenBucket] = {}

    def check(self, tool_name: str) -> RateLimitResult:
        """Check if a tool call is allowed."""
        if not self._global_bucket.try_acquire():
            return RateLimitResult(
                allowed=False,
                tool_name=tool_name,
                limit_type=RateLimitType.GLOBAL,
                wait_time=self._global_bucket.wait_time(),
            )

        bucket = self._get_tool_bucket(tool_name)
        if not bucket.try_acquire():
            self._global_bucket.release()
            return RateLimitResult(
                allowed=False,
                tool_name=tool_name,
                limit_type=RateLimitType.PER_TOOL,
                calls_remaining=0,
                wait_time=bucket.wait_time(),
            )

        return RateLimitResult(
            allowed=True,
            tool_name=tool_name,
            calls_remaining=bucket.remaining(),
        )

    def _get_tool_bucket(self, tool_name: str) -> _MiniTokenBucket:
        if tool_name not in self._per_tool_buckets:
            self._per_tool_buckets[tool_name] = _MiniTokenBucket(self._per_tool_limit)
        return self._per_tool_buckets[tool_name]

    def reset(self) -> None:
        self._global_bucket.reset()
        for bucket in self._per_tool_buckets.values():
            bucket.reset()
