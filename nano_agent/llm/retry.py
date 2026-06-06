"""
Exponential backoff retry for LLM API calls.

Provides automatic retry on transient errors (429 rate limit, 500 server
errors, network failures) with configurable backoff strategy.
"""

import random
import time
from typing import Callable

from ..config.schema import RetryConfig


def is_retryable_error(exc: Exception, config: RetryConfig) -> bool:
    """Check if an exception should be retried.

    Retryable: 429/500-class HTTP errors, network failures.
    Not retryable: 4xx client errors (400/401/403/404), logic errors (ValueError).
    """
    # Check for requests.exceptions.HTTPError
    exc_class_name = type(exc).__name__
    exc_module = type(exc).__module__ or ""

    # requests.exceptions.HTTPError — check status code
    if exc_class_name == "HTTPError" and "requests" in exc_module:
        response = getattr(exc, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if status_code is not None:
                return status_code in config.retryable_status_codes
        return True  # HTTPError without response — assume retryable

    # anthropic SDK exceptions
    if "anthropic" in exc_module:
        # RateLimitError — always retryable
        if exc_class_name == "RateLimitError":
            return True
        # APIStatusError — check status code
        if exc_class_name == "APIStatusError":
            status_code = getattr(exc, "status_code", None)
            if status_code is not None:
                return status_code in config.retryable_status_codes
            return True
        # APIConnectionError, APITimeoutError — always retryable
        if exc_class_name in ("APIConnectionError", "APITimeoutError"):
            return True

    # Network-level errors — always retryable
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    # requests.exceptions.ConnectionError / Timeout
    if exc_class_name in ("ConnectionError", "Timeout") and "requests" in exc_module:
        return True

    return False


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for the given retry attempt.

    Uses exponential backoff: base * 2^attempt, capped at max_delay.
    Optionally adds random jitter to prevent thundering herd.
    """
    delay = config.base_delay * (2**attempt)
    if config.jitter:
        delay += random.uniform(0, config.base_delay)
    return min(delay, config.max_delay)


def with_retry(
    func: Callable,
    config: RetryConfig,
    on_retry: Callable[[dict], None] | None = None,
):
    """Execute func with automatic retry on transient errors.

    Args:
        func: The function to call (should be a lambda wrapping the actual call).
        config: Retry configuration.
        on_retry: Optional callback invoked before each retry with event data:
                  {"attempt": int, "max_retries": int, "delay": float, "error": Exception}

    Returns:
        The return value of func() on success.

    Raises:
        The last exception if all retries are exhausted, or the original
        exception if it's not retryable.
    """
    last_exc = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc

            # Don't retry if not retryable
            if not is_retryable_error(exc, config):
                raise

            # Don't retry if we've exhausted attempts
            if attempt >= config.max_retries:
                raise

            # Calculate delay and wait
            delay = calculate_delay(attempt, config)

            if on_retry is not None:
                on_retry(
                    {
                        "attempt": attempt + 1,
                        "max_retries": config.max_retries,
                        "delay": delay,
                        "error": exc,
                    }
                )

            time.sleep(delay)

    # Should not reach here, but just in case
    raise last_exc  # type: ignore[misc]
