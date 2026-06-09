"""Tests for LLM API rate limiter (v0.8.1)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from nano_agent.config.schema import Config, RateLimiterConfig, RetryConfig
from nano_agent.llm.base import BaseLLM, LLMUsage
from nano_agent.llm.messages import ToolCall
from nano_agent.llm.rate_limiter import TokenBucketRateLimiter, with_rate_limit

pytestmark = pytest.mark.unit


# === TestTokenBucketRateLimiter ===


class TestTokenBucketRateLimiter:
    """Test token bucket rate limiter core logic."""

    def test_bucket_starts_full(self):
        """New limiter should start with burst tokens."""
        config = RateLimiterConfig(burst=10)
        limiter = TokenBucketRateLimiter(config)
        assert limiter._tokens == 10.0

    def test_acquire_decrements_tokens(self):
        """Each acquire should reduce tokens by 1."""
        config = RateLimiterConfig(burst=5, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            limiter.acquire()
            assert limiter._tokens == 4.0

    def test_refill_over_time(self):
        """Tokens should refill at the configured rate over time."""
        config = RateLimiterConfig(burst=100, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        # Drain to 0
        limiter._tokens = 0.0
        limiter._last_refill = 0.0
        # Simulate 30 seconds passing — should refill 30 tokens (60 rpm / 60 = 1/sec)
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=30.0):
            limiter._refill()
            assert limiter._tokens == 30.0  # 0 + 30s * 1.0/sec

    def test_acquire_waits_when_empty(self):
        """When tokens are 0, acquire should block and return wait time > 0."""
        config = RateLimiterConfig(burst=1, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        # Drain the bucket
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            limiter.acquire()
        # Now empty — next acquire should wait
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            limiter._tokens = 0.0
            with patch("nano_agent.llm.rate_limiter.time.sleep") as mock_sleep:
                wait_time = limiter.acquire()
                assert wait_time > 0
                mock_sleep.assert_called_once_with(wait_time)

    def test_burst_allows_burst(self):
        """Should be able to acquire `burst` requests immediately."""
        config = RateLimiterConfig(burst=5, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            for _ in range(5):
                wait = limiter.acquire()
                assert wait == 0.0

    def test_refill_capped_at_max(self):
        """Tokens should never exceed max_tokens (burst)."""
        config = RateLimiterConfig(burst=5, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        limiter._last_refill = 0.0
        # Simulate a very long time passing — tokens should cap at burst
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=9999.0):
            limiter._refill()
            assert limiter._tokens == 5.0

    def test_reset_restores_full_bucket(self):
        """reset() should restore tokens to max."""
        config = RateLimiterConfig(burst=10, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        # Drain some tokens
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            limiter.acquire()
            limiter.acquire()
            assert limiter._tokens == 8.0
        # Reset
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=1.0):
            limiter.reset()
            assert limiter._tokens == 10.0


# === TestWithRateLimit ===


class TestWithRateLimit:
    """Test with_rate_limit wrapper function."""

    def test_no_wait_when_tokens_available(self):
        """Function should be called immediately when tokens available."""
        config = RateLimiterConfig(burst=10, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        func = MagicMock(return_value="result")
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            result = with_rate_limit(func, limiter)
        assert result == "result"
        func.assert_called_once()

    def test_callback_called_when_waiting(self):
        """on_wait callback should be called when rate limited."""
        config = RateLimiterConfig(burst=1, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        on_wait = MagicMock()
        # Drain the bucket first
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            limiter.acquire()
        # Next call should trigger callback
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            limiter._tokens = 0.0
            with patch("nano_agent.llm.rate_limiter.time.sleep"):
                with_rate_limit(lambda: "ok", limiter, on_wait=on_wait)
        on_wait.assert_called_once()
        call_data = on_wait.call_args[0][0]
        assert "wait_time" in call_data
        assert "rpm" in call_data
        assert "burst" in call_data
        assert call_data["rpm"] == 60
        assert call_data["burst"] == 1

    def test_callback_not_called_when_no_wait(self):
        """on_wait callback should NOT be called when no waiting needed."""
        config = RateLimiterConfig(burst=10, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        on_wait = MagicMock()
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            with_rate_limit(lambda: "ok", limiter, on_wait=on_wait)
        on_wait.assert_not_called()

    def test_function_return_value_passed_through(self):
        """Return value of wrapped function should be returned unchanged."""
        config = RateLimiterConfig(burst=10, requests_per_minute=60)
        limiter = TokenBucketRateLimiter(config)
        expected = ("text", [MagicMock()], MagicMock())
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            limiter._last_refill = 0
            result = with_rate_limit(lambda: expected, limiter)
        assert result == expected


# === TestRateLimiterConfig ===


class TestRateLimiterConfig:
    """Test RateLimiterConfig defaults and integration."""

    def test_defaults(self):
        """Default config should have sensible values."""
        config = RateLimiterConfig()
        assert config.enabled is True
        assert config.requests_per_minute == 60
        assert config.burst == 10

    def test_config_in_top_level(self):
        """Config.rate_limiter should exist and be RateLimiterConfig."""
        config = Config()
        assert isinstance(config.rate_limiter, RateLimiterConfig)
        assert config.rate_limiter.enabled is True

    def test_config_from_dict(self):
        """RateLimiterConfig should be parsed from dict by loader."""
        from nano_agent.config.loader import _from_dict

        data = {"rate_limiter": {"enabled": False, "requests_per_minute": 30}}
        config = _from_dict(Config, data)
        assert config.rate_limiter.enabled is False
        assert config.rate_limiter.requests_per_minute == 30
        assert config.rate_limiter.burst == 10  # default preserved

    def test_config_save_and_load(self, tmp_path):
        """Config should round-trip through YAML."""
        from nano_agent.config.loader import ConfigLoader

        config = Config()
        config.rate_limiter.requests_per_minute = 120
        config.rate_limiter.burst = 20

        path = tmp_path / "test_config.yaml"
        ConfigLoader.save(config, path)
        loaded = ConfigLoader.load(path)

        assert loaded.rate_limiter.requests_per_minute == 120
        assert loaded.rate_limiter.burst == 20


# === TestBaseLLMChatRateLimiter ===


class TestBaseLLMChatRateLimiter:
    """Test rate limiter integration with BaseLLM.chat()."""

    def _make_llm(self):
        """Create a concrete BaseLLM subclass for testing."""

        class TestLLM(BaseLLM):
            supports_explicit_caching = False

            def __init__(self):
                self.model = "test"
                self.base_url = "http://test"

            def _chat_impl(self, messages, tools=None, system_stable=None, **kwargs):
                return "response", [], LLMUsage()

        return TestLLM()

    def test_chat_with_rate_limit_enabled(self):
        """chat() should wrap with rate limiter when enabled."""
        llm = self._make_llm()
        llm._rate_limiter_config = RateLimiterConfig(enabled=True, burst=10)
        llm._rate_limiter = TokenBucketRateLimiter(llm._rate_limiter_config)
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            result = llm.chat([{"role": "user", "content": "hi"}])
        assert result[0] == "response"

    def test_chat_without_rate_limit_when_disabled(self):
        """chat() should skip rate limiter when disabled."""
        llm = self._make_llm()
        llm._rate_limiter_config = RateLimiterConfig(enabled=False)
        result = llm.chat([{"role": "user", "content": "hi"}])
        assert result[0] == "response"

    def test_chat_without_rate_limit_when_no_config(self):
        """chat() should skip rate limiter when _rate_limiter_config is None."""
        llm = self._make_llm()
        assert llm._rate_limiter_config is None
        result = llm.chat([{"role": "user", "content": "hi"}])
        assert result[0] == "response"

    def test_rate_limit_and_retry_together(self):
        """Rate limiter should wrap retry — both active simultaneously."""
        llm = self._make_llm()
        llm._rate_limiter_config = RateLimiterConfig(enabled=True, burst=10)
        llm._rate_limiter = TokenBucketRateLimiter(llm._rate_limiter_config)
        llm._rate_limiter._last_refill = 0.0
        llm._retry_config = RetryConfig(enabled=True, max_retries=2)
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            result = llm.chat([{"role": "user", "content": "hi"}])
        assert result[0] == "response"

    def test_on_rate_limit_callback_invoked(self):
        """_on_rate_limit_callback should be called when rate limited."""
        llm = self._make_llm()
        config = RateLimiterConfig(enabled=True, burst=1, requests_per_minute=60)
        llm._rate_limiter_config = config
        llm._rate_limiter = TokenBucketRateLimiter(config)
        callback = MagicMock()
        llm._on_rate_limit_callback = callback
        # Drain the bucket
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            llm.chat([{"role": "user", "content": "first"}])
        callback.assert_not_called()  # First call has tokens
        # Second call should trigger callback
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            llm._rate_limiter._tokens = 0.0
            with patch("nano_agent.llm.rate_limiter.time.sleep"):
                llm.chat([{"role": "user", "content": "second"}])
        callback.assert_called_once()


# === TestRateLimiterConfigValidation ===


class TestRateLimiterConfigValidation:
    """Test RateLimiterConfig input validation."""

    def test_reject_zero_rpm(self):
        """requests_per_minute=0 should raise ValueError."""
        with pytest.raises(ValueError, match="requests_per_minute must be > 0"):
            RateLimiterConfig(requests_per_minute=0)

    def test_reject_negative_rpm(self):
        """Negative requests_per_minute should raise ValueError."""
        with pytest.raises(ValueError, match="requests_per_minute must be > 0"):
            RateLimiterConfig(requests_per_minute=-1)

    def test_reject_zero_burst(self):
        """burst=0 should raise ValueError."""
        with pytest.raises(ValueError, match="burst must be > 0"):
            RateLimiterConfig(burst=0)

    def test_reject_negative_burst(self):
        """Negative burst should raise ValueError."""
        with pytest.raises(ValueError, match="burst must be > 0"):
            RateLimiterConfig(burst=-5)

    def test_valid_config_passes(self):
        """Valid config should not raise."""
        config = RateLimiterConfig(requests_per_minute=60, burst=10)
        assert config.requests_per_minute == 60
        assert config.burst == 10


# === TestBuilderRateLimiterInjection ===


class TestBuilderRateLimiterInjection:
    """Test AgentBuilder correctly injects rate limiter components."""

    def _make_config(self):
        from nano_agent.config.schema import Config

        config = Config()
        config.agent.verbose = False
        return config

    def _make_llm(self):
        from nano_agent.llm.base import BaseLLM, LLMUsage

        class TestLLM(BaseLLM):
            supports_explicit_caching = False

            def __init__(self):
                self.model = "test"
                self.base_url = "http://test"

            def _chat_impl(self, messages, tools=None, system_stable=None, **kwargs):
                return "response", [], LLMUsage()

        return TestLLM()

    def test_builder_injects_rate_limiter_config(self):
        """Builder should inject rate_limiter_config into LLM."""
        from nano_agent.core.builder import AgentBuilder
        from nano_agent.memory import ShortTermMemory

        config = self._make_config()
        llm = self._make_llm()
        builder = AgentBuilder(config)
        builder.with_llm_instance(llm)
        builder.with_memory_instance(ShortTermMemory())
        builder.build()

        assert llm._rate_limiter_config is config.rate_limiter
        assert isinstance(llm._rate_limiter, TokenBucketRateLimiter)

    def test_builder_wires_rate_limit_callback(self):
        """Builder should wire _on_rate_limit_callback when enabled."""
        from nano_agent.core.builder import AgentBuilder
        from nano_agent.memory import ShortTermMemory

        config = self._make_config()
        config.rate_limiter.enabled = True
        llm = self._make_llm()
        builder = AgentBuilder(config)
        builder.with_llm_instance(llm)
        builder.with_memory_instance(ShortTermMemory())
        orchestrator = builder.build()

        assert llm._on_rate_limit_callback is not None

    def test_builder_no_callback_when_disabled(self):
        """Builder should not wire callback when rate_limiter disabled."""
        from nano_agent.core.builder import AgentBuilder
        from nano_agent.memory import ShortTermMemory

        config = self._make_config()
        config.rate_limiter.enabled = False
        llm = self._make_llm()
        builder = AgentBuilder(config)
        builder.with_llm_instance(llm)
        builder.with_memory_instance(ShortTermMemory())
        builder.build()

        assert llm._on_rate_limit_callback is None

    def test_rate_limited_event_emitted(self):
        """AgentEvent.LLM_RATE_LIMITED should be emitted when rate limited."""
        from nano_agent.agent.types import AgentEvent
        from nano_agent.core.builder import AgentBuilder
        from nano_agent.memory import ShortTermMemory

        config = self._make_config()
        config.rate_limiter.enabled = True
        config.rate_limiter.burst = 1
        config.rate_limiter.requests_per_minute = 60
        llm = self._make_llm()
        builder = AgentBuilder(config)
        builder.with_llm_instance(llm)
        builder.with_memory_instance(ShortTermMemory())
        orchestrator = builder.build()

        emitted_events = []
        orchestrator.agent.events.on(
            AgentEvent.LLM_RATE_LIMITED,
            lambda event, data: emitted_events.append(data),
        )

        # First call uses the burst token, no event
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            llm.chat([{"role": "user", "content": "first"}])
        assert len(emitted_events) == 0

        # Second call triggers rate limit event
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            llm._rate_limiter._tokens = 0.0
            with patch("nano_agent.llm.rate_limiter.time.sleep"):
                llm.chat([{"role": "user", "content": "second"}])
        assert len(emitted_events) == 1
        assert "wait_time" in emitted_events[0]
        assert "rpm" in emitted_events[0]

    def test_rate_limit_and_retry_both_active(self):
        """Rate limiter wraps retry — both layers active in builder-built agent."""
        from nano_agent.core.builder import AgentBuilder
        from nano_agent.memory import ShortTermMemory

        config = self._make_config()
        config.rate_limiter.enabled = True
        config.rate_limiter.burst = 10
        config.retry.enabled = True
        config.retry.max_retries = 2
        llm = self._make_llm()
        builder = AgentBuilder(config)
        builder.with_llm_instance(llm)
        builder.with_memory_instance(ShortTermMemory())
        orchestrator = builder.build()

        # Both should be configured
        assert llm._rate_limiter_config is not None
        assert llm._retry_config is not None

        # chat() should work through both layers
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            result = llm.chat([{"role": "user", "content": "hi"}])
        assert result[0] == "response"


# === TestApplyRateLimit ===


class TestApplyRateLimit:
    """Test _apply_rate_limit helper method."""

    def _make_llm(self):
        from nano_agent.llm.base import BaseLLM, LLMUsage

        class TestLLM(BaseLLM):
            supports_explicit_caching = False

            def __init__(self):
                self.model = "test"
                self.base_url = "http://test"

            def _chat_impl(self, messages, tools=None, system_stable=None, **kwargs):
                return "response", [], LLMUsage()

        return TestLLM()

    def test_noop_when_disabled(self):
        """_apply_rate_limit() should do nothing when disabled."""
        llm = self._make_llm()
        llm._rate_limiter_config = RateLimiterConfig(enabled=False)
        llm._rate_limiter = TokenBucketRateLimiter(llm._rate_limiter_config)
        llm._apply_rate_limit()  # Should not raise or block

    def test_noop_when_no_config(self):
        """_apply_rate_limit() should do nothing when config is None."""
        llm = self._make_llm()
        llm._apply_rate_limit()  # Should not raise or block

    def test_acquires_token_when_enabled(self):
        """_apply_rate_limit() should acquire a token when enabled."""
        llm = self._make_llm()
        config = RateLimiterConfig(enabled=True, burst=5, requests_per_minute=60)
        llm._rate_limiter_config = config
        llm._rate_limiter = TokenBucketRateLimiter(config)
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            llm._apply_rate_limit()
        assert llm._rate_limiter._tokens == 4.0  # 5 - 1

    def test_callback_invoked_when_waiting(self):
        """_apply_rate_limit() should invoke callback when rate limited."""
        llm = self._make_llm()
        config = RateLimiterConfig(enabled=True, burst=1, requests_per_minute=60)
        llm._rate_limiter_config = config
        llm._rate_limiter = TokenBucketRateLimiter(config)
        callback = MagicMock()
        llm._on_rate_limit_callback = callback
        # Drain bucket
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            llm._apply_rate_limit()
        callback.assert_not_called()
        # Second call triggers callback
        with patch("nano_agent.llm.rate_limiter.time.monotonic", return_value=0):
            llm._rate_limiter._last_refill = 0
            llm._rate_limiter._tokens = 0.0
            with patch("nano_agent.llm.rate_limiter.time.sleep"):
                llm._apply_rate_limit()
        callback.assert_called_once()
