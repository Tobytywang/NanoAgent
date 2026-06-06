"""Tests for LLM exponential backoff retry mechanism."""

import time
from unittest.mock import MagicMock, patch

import pytest

from nano_agent.config.schema import RetryConfig
from nano_agent.llm.base import BaseLLM, LLMUsage
from nano_agent.llm.messages import ToolCall
from nano_agent.llm.retry import calculate_delay, is_retryable_error, with_retry

pytestmark = pytest.mark.unit


# === TestIsRetryableError ===


class TestIsRetryableError:
    """Test retryable error classification."""

    def setup_method(self):
        self.config = RetryConfig()

    def test_http_error_429_retryable(self):
        """429 rate limit should be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 429
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is True

    def test_http_error_500_retryable(self):
        """500 server error should be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 500
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is True

    def test_http_error_502_retryable(self):
        """502 bad gateway should be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 502
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is True

    def test_http_error_503_retryable(self):
        """503 service unavailable should be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 503
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is True

    def test_http_error_400_not_retryable(self):
        """400 bad request should NOT be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 400
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is False

    def test_http_error_401_not_retryable(self):
        """401 unauthorized should NOT be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 401
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is False

    def test_http_error_403_not_retryable(self):
        """403 forbidden should NOT be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 403
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is False

    def test_http_error_404_not_retryable(self):
        """404 not found should NOT be retryable."""
        import requests

        response = MagicMock()
        response.status_code = 404
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, self.config) is False

    def test_connection_error_retryable(self):
        """ConnectionError should be retryable."""
        assert is_retryable_error(ConnectionError("refused"), self.config) is True

    def test_timeout_error_retryable(self):
        """TimeoutError should be retryable."""
        assert is_retryable_error(TimeoutError("timed out"), self.config) is True

    def test_value_error_not_retryable(self):
        """ValueError should NOT be retryable (logic error)."""
        assert is_retryable_error(ValueError("bad value"), self.config) is False

    def test_type_error_not_retryable(self):
        """TypeError should NOT be retryable (logic error)."""
        assert is_retryable_error(TypeError("bad type"), self.config) is False

    def test_key_error_not_retryable(self):
        """KeyError should NOT be retryable (logic error)."""
        assert is_retryable_error(KeyError("missing"), self.config) is False

    def test_custom_status_codes(self):
        """Custom retryable_status_codes should be respected."""
        config = RetryConfig(retryable_status_codes=[429, 503])
        import requests

        # 500 not in custom list
        response = MagicMock()
        response.status_code = 500
        exc = requests.exceptions.HTTPError(response=response)
        assert is_retryable_error(exc, config) is False

        # 503 in custom list
        response2 = MagicMock()
        response2.status_code = 503
        exc2 = requests.exceptions.HTTPError(response=response2)
        assert is_retryable_error(exc2, config) is True

    def test_requests_connection_error_retryable(self):
        """requests.exceptions.ConnectionError should be retryable."""
        import requests

        exc = requests.exceptions.ConnectionError("connection refused")
        assert is_retryable_error(exc, self.config) is True

    def test_requests_timeout_retryable(self):
        """requests.exceptions.Timeout should be retryable."""
        import requests

        exc = requests.exceptions.Timeout("request timed out")
        assert is_retryable_error(exc, self.config) is True


# === TestCalculateDelay ===


class TestCalculateDelay:
    """Test exponential backoff delay calculation."""

    def setup_method(self):
        self.config = RetryConfig(base_delay=1.0, max_delay=60.0, jitter=False)

    def test_attempt_0(self):
        """First retry: base * 2^0 = base."""
        assert calculate_delay(0, self.config) == 1.0

    def test_attempt_1(self):
        """Second retry: base * 2^1 = 2 * base."""
        assert calculate_delay(1, self.config) == 2.0

    def test_attempt_2(self):
        """Third retry: base * 2^2 = 4 * base."""
        assert calculate_delay(2, self.config) == 4.0

    def test_attempt_3(self):
        """Fourth retry: base * 2^3 = 8 * base."""
        assert calculate_delay(3, self.config) == 8.0

    def test_capped_at_max_delay(self):
        """Delay should not exceed max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=10.0, jitter=False)
        # attempt 10 would be 1 * 1024 = 1024, but capped at 10
        assert calculate_delay(10, config) == 10.0

    def test_jitter_adds_randomness(self):
        """With jitter, delay should vary between runs."""
        config = RetryConfig(base_delay=1.0, max_delay=60.0, jitter=True)
        delays = [calculate_delay(0, config) for _ in range(100)]
        # Without jitter, attempt 0 always = 1.0
        # With jitter, it should be in [1.0, 2.0) range
        assert min(delays) >= 1.0
        assert max(delays) < 2.0
        # Should have some variation
        assert len(set(delays)) > 1


# === TestWithRetry ===


class TestWithRetry:
    """Test the with_retry wrapper function."""

    def setup_method(self):
        self.config = RetryConfig(
            enabled=True, max_retries=3, base_delay=0.01, max_delay=0.1, jitter=False
        )

    def test_succeeds_on_first_call(self):
        """Function succeeds immediately — no retry needed."""

        def func():
            return ("hello", [], LLMUsage())

        result = with_retry(func, self.config)
        assert result == ("hello", [], LLMUsage())

    def test_succeeds_after_retry(self):
        """Function fails once then succeeds — should return result after retry."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("refused")
            return ("success", [], LLMUsage())

        result = with_retry(func, self.config)
        assert result == ("success", [], LLMUsage())
        assert call_count == 2

    def test_non_retryable_error_raises_immediately(self):
        """Non-retryable error should raise immediately without retry."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad value")

        with pytest.raises(ValueError, match="bad value"):
            with_retry(func, self.config)
        assert call_count == 1

    def test_exhausts_retries_then_raises(self):
        """All retries exhausted — should raise the last exception."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError(f"refused #{call_count}")

        with pytest.raises(ConnectionError, match="refused #4"):
            with_retry(func, self.config)
        # 1 initial + 3 retries = 4 total calls
        assert call_count == 4

    def test_on_retry_callback_called(self):
        """on_retry callback should be invoked with event data before each retry."""
        retry_events = []
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("refused")
            return ("ok", [], LLMUsage())

        with_retry(func, self.config, on_retry=retry_events.append)
        assert len(retry_events) == 2
        assert retry_events[0]["attempt"] == 1
        assert retry_events[0]["max_retries"] == 3
        assert retry_events[0]["delay"] >= 0
        assert isinstance(retry_events[0]["error"], ConnectionError)
        assert retry_events[1]["attempt"] == 2

    def test_delay_increases_exponentially(self):
        """Verify that sleep delays increase exponentially."""
        sleep_times = []

        def fake_sleep(seconds):
            sleep_times.append(seconds)

        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("refused")
            return ("ok", [], LLMUsage())

        with patch("time.sleep", fake_sleep):
            with_retry(func, self.config)

        # base=0.01, attempt 0: 0.01, attempt 1: 0.02, attempt 2: 0.04
        assert len(sleep_times) == 3
        assert sleep_times[0] == pytest.approx(0.01)
        assert sleep_times[1] == pytest.approx(0.02)
        assert sleep_times[2] == pytest.approx(0.04)

    def test_zero_max_retries_no_retry(self):
        """max_retries=0 should not retry at all."""
        config = RetryConfig(max_retries=0, base_delay=0.01, jitter=False)
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("refused")

        with pytest.raises(ConnectionError):
            with_retry(func, config)
        assert call_count == 1

    def test_http_429_retried_then_succeeds(self):
        """429 rate limit should be retried and eventually succeed."""
        import requests

        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                response = MagicMock()
                response.status_code = 429
                raise requests.exceptions.HTTPError(response=response)
            return ("ok", [], LLMUsage())

        with patch("time.sleep"):
            result = with_retry(func, self.config)
        assert result == ("ok", [], LLMUsage())
        assert call_count == 2


# === TestBaseLLMChatRetry ===


class TestBaseLLMChatRetry:
    """Test that BaseLLM.chat() correctly wraps _chat_impl with retry."""

    def _create_mock_llm(self):
        """Create a minimal concrete subclass of BaseLLM for testing."""

        class MockLLM(BaseLLM):
            def __init__(self):
                self.call_count = 0

            def _chat_impl(self, messages, tools=None, system_stable=None, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    raise ConnectionError("refused")
                return ("hello", [], LLMUsage())

        return MockLLM()

    def test_chat_retries_on_transient_error(self):
        """chat() should retry and succeed on transient error."""
        llm = self._create_mock_llm()
        llm._retry_config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        with patch("time.sleep"):
            text, tool_calls, usage = llm.chat([{"role": "user", "content": "hi"}])
        assert text == "hello"
        assert llm.call_count == 2

    def test_chat_no_retry_when_disabled(self):
        """chat() should not retry when retry is disabled."""
        llm = self._create_mock_llm()
        llm._retry_config = RetryConfig(enabled=False)
        with pytest.raises(ConnectionError):
            llm.chat([{"role": "user", "content": "hi"}])
        assert llm.call_count == 1

    def test_chat_no_retry_when_no_config(self):
        """chat() should not retry when _retry_config is None."""
        llm = self._create_mock_llm()
        # _retry_config is None by default
        with pytest.raises(ConnectionError):
            llm.chat([{"role": "user", "content": "hi"}])
        assert llm.call_count == 1

    def test_on_retry_callback_invoked(self):
        """chat() should invoke _on_retry_callback on retry."""
        llm = self._create_mock_llm()
        llm._retry_config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        retry_events = []
        llm._on_retry_callback = retry_events.append
        with patch("time.sleep"):
            llm.chat([{"role": "user", "content": "hi"}])
        assert len(retry_events) == 1
        assert retry_events[0]["attempt"] == 1

    def test_chat_non_retryable_error_not_retried(self):
        """chat() should not retry on non-retryable errors."""

        class FailLLM(BaseLLM):
            def __init__(self):
                self.call_count = 0

            def _chat_impl(self, messages, tools=None, system_stable=None, **kwargs):
                self.call_count += 1
                raise ValueError("bad input")

        llm = FailLLM()
        llm._retry_config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        with pytest.raises(ValueError, match="bad input"):
            llm.chat([{"role": "user", "content": "hi"}])
        assert llm.call_count == 1


# === TestRetryConfig ===


class TestRetryConfig:
    """Test RetryConfig defaults and integration."""

    def test_defaults(self):
        """Default values should be sensible."""
        config = RetryConfig()
        assert config.enabled is True
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True
        assert 429 in config.retryable_status_codes
        assert 500 in config.retryable_status_codes

    def test_config_in_top_level(self):
        """RetryConfig should be accessible from Config."""
        from nano_agent.config.schema import Config

        config = Config()
        assert hasattr(config, "retry")
        assert isinstance(config.retry, RetryConfig)
        assert config.retry.enabled is True

    def test_config_from_dict(self):
        """RetryConfig should be parsed from dict by the generic loader."""
        from nano_agent.config.loader import _from_dict
        from nano_agent.config.schema import Config

        data = {"retry": {"enabled": False, "max_retries": 5}}
        config = _from_dict(Config, data)
        assert config.retry.enabled is False
        assert config.retry.max_retries == 5
        # Other fields should use defaults
        assert config.retry.base_delay == 1.0

    def test_config_save_and_load(self, tmp_path):
        """RetryConfig should round-trip through YAML save/load."""
        from nano_agent.config.loader import ConfigLoader
        from nano_agent.config.schema import Config

        config = Config()
        config.retry.max_retries = 5
        config.retry.base_delay = 2.0

        config_path = tmp_path / "test_config.yaml"
        ConfigLoader.save(config, config_path)

        loaded = ConfigLoader.load(config_path)
        assert loaded.retry.max_retries == 5
        assert loaded.retry.base_delay == 2.0
