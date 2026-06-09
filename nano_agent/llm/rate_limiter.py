"""
Token bucket rate limiter for LLM API calls.

Provides proactive throttling to prevent hitting API rate limits,
complementing the reactive retry mechanism (v0.8.0).
"""

import time
from typing import Callable

from ..config.schema import RateLimiterConfig


class TokenBucketRateLimiter:
    """Token bucket rate limiter.

    Allows short bursts up to `burst` requests, while maintaining
    a long-term average of `requests_per_minute` requests.

    Thread safety: NOT thread-safe. Designed for synchronous
    single-threaded agent execution (same assumption as retry.py).
    """

    def __init__(self, config: RateLimiterConfig):
        self.config = config
        self._tokens = float(config.burst)
        self._max_tokens = float(config.burst)
        self._refill_rate = config.requests_per_minute / 60.0
        self._last_refill = time.monotonic()

    def acquire(self) -> float:
        """Acquire a token, blocking if necessary.

        Returns:
            Wait time in seconds (0 if no wait needed).
        """
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return 0.0

        wait = (1.0 - self._tokens) / self._refill_rate
        time.sleep(wait)
        self._refill()
        self._tokens -= 1.0
        return wait

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def reset(self) -> None:
        """Reset bucket to full capacity."""
        self._tokens = self._max_tokens
        self._last_refill = time.monotonic()


def with_rate_limit(
    func: Callable,
    limiter: TokenBucketRateLimiter,
    on_wait: Callable[[dict], None] | None = None,
):
    """Execute func with rate limiting.

    Args:
        func: The function to call.
        limiter: Token bucket rate limiter instance.
        on_wait: Optional callback invoked when rate limited with event data:
                 {"wait_time": float, "rpm": int, "burst": int}

    Returns:
        The return value of func().
    """
    wait_time = limiter.acquire()
    if wait_time > 0 and on_wait is not None:
        on_wait(
            {
                "wait_time": wait_time,
                "rpm": limiter.config.requests_per_minute,
                "burst": limiter.config.burst,
            }
        )
    return func()
