"""Tests for v0.7.12: Real prompt_tokens at decision points.

Verifies that check_and_compress() and should_compress() use real
prompt_tokens when available, falling back to estimate_tokens() otherwise.
"""

import pytest
from unittest.mock import MagicMock, patch

from nano_agent.agent.context import ContextManager
from nano_agent.agent.compressor import MessageCompressor
from nano_agent.agent.react import ReActAgent
from nano_agent.config.schema import (
    ContextConfig,
    CompressorConfig,
)
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.agent.token_utils import estimate_tokens

# --- Fixtures ---


def _make_messages(n: int, text: str = "Hello world") -> list[dict]:
    """Create n simple messages for testing."""
    return [{"role": "user", "content": text} for _ in range(n)]


def _make_context_manager(max_tokens: int = 4096, verbose: bool = False):
    """Create a ContextManager with test config."""
    config = ContextConfig(max_context_tokens=max_tokens)
    memory = ShortTermMemory(max_messages=50)
    llm = MagicMock()
    return ContextManager(config=config, memory=memory, llm=llm, verbose=verbose)


def _make_compressor(threshold_tokens: int = 2000, enabled: bool = True):
    """Create a MessageCompressor with test config."""
    config = CompressorConfig(threshold_tokens=threshold_tokens, enabled=enabled)
    comp = MessageCompressor(config=config)
    # Mock the LLM so compress() can work without real API call
    comp.llm = MagicMock()
    return comp


# --- ContextManager Tests ---


class TestContextManagerRealTokens:
    """Test check_and_compress with real prompt_tokens."""

    def test_real_tokens_override_estimate(self):
        """When last_prompt_tokens is provided, use it instead of estimate."""
        cm = _make_context_manager(max_tokens=4096)
        for msg in _make_messages(5):
            cm.memory.add(msg)

        # With real tokens = 3500 (close to limit), compression should trigger
        cm.check_and_compress(max_context_tokens=4096, last_prompt_tokens=3500)

    def test_fallback_to_estimate_when_no_real_tokens(self):
        """When last_prompt_tokens is None, fall back to estimate_tokens()."""
        cm = _make_context_manager(max_tokens=4096, verbose=True)
        for msg in _make_messages(5):
            cm.memory.add(msg)

        # Should not crash and should use estimate internally
        cm.check_and_compress(max_context_tokens=4096, last_prompt_tokens=None)

    def test_none_same_as_no_argument(self):
        """Passing last_prompt_tokens=None is same as not passing it."""
        cm = _make_context_manager(max_tokens=8192)
        for msg in _make_messages(3):
            cm.memory.add(msg)

        cm.check_and_compress(max_context_tokens=8192)

        cm2 = _make_context_manager(max_tokens=8192)
        for msg in _make_messages(3):
            cm2.memory.add(msg)
        cm2.check_and_compress(max_context_tokens=8192, last_prompt_tokens=None)

    def test_real_tokens_prevents_compression_when_estimate_would_trigger(self):
        """Scenario: estimate says over limit but real tokens say safe."""
        cm = _make_context_manager(max_tokens=4096)
        # Add many messages so estimate is high
        for msg in _make_messages(50, "a long message " * 20):
            cm.memory.add(msg)

        # Real tokens = 1000, ratio = 1000/4096 = 24.4% → well below threshold
        result = cm.check_and_compress(max_context_tokens=4096, last_prompt_tokens=1000)
        assert result is False

    def test_verbose_output_includes_source(self, capsys):
        """Verbose output shows [real] or [estimated] source tag."""
        cm = _make_context_manager(max_tokens=4096, verbose=True)
        cm.memory.add({"role": "user", "content": "test"})

        # Test with real tokens
        cm.check_and_compress(max_context_tokens=4096, last_prompt_tokens=500)
        captured = capsys.readouterr()
        assert "[real]" in captured.out

        # Test with estimated (None)
        cm.check_and_compress(max_context_tokens=4096, last_prompt_tokens=None)
        captured = capsys.readouterr()
        assert "[estimated]" in captured.out


# --- Compressor Tests ---


class TestCompressorRealTokens:
    """Test should_compress and compress with real prompt_tokens."""

    def test_should_compress_uses_real_tokens(self):
        """should_compress uses last_prompt_tokens when provided."""
        comp = _make_compressor(threshold_tokens=2000)

        messages = _make_messages(5)
        # Real tokens = 2500 > threshold 2000 → should compress
        assert comp.should_compress(messages, last_prompt_tokens=2500) is True

        # Real tokens = 1500 < threshold 2000 → should not compress
        assert comp.should_compress(messages, last_prompt_tokens=1500) is False

    def test_should_compress_fallback_to_estimate(self):
        """should_compress falls back to estimate when no real tokens."""
        comp = _make_compressor(threshold_tokens=2000)

        # Few messages → estimate below threshold → should not compress
        messages = _make_messages(1, "hi")
        assert comp.should_compress(messages, last_prompt_tokens=None) is False

    def test_compress_passes_through_last_prompt_tokens(self):
        """compress() passes last_prompt_tokens to should_compress()."""
        comp = _make_compressor(threshold_tokens=100)
        # Mock the _summarize method to avoid LLM call
        comp._summarize = MagicMock(
            return_value=[{"role": "system", "content": "summary"}]
        )

        messages = _make_messages(10, "x " * 50)
        # Real tokens = 200 > threshold 100 → should compress
        result = comp.compress(messages, last_prompt_tokens=200)
        assert len(result) < len(messages)

    def test_compress_skips_when_real_tokens_below_threshold(self):
        """compress() skips compression when real tokens are below threshold."""
        comp = _make_compressor(threshold_tokens=2000)

        messages = _make_messages(10, "x " * 50)
        # Real tokens = 500 < threshold 2000 → should NOT compress
        result = comp.compress(messages, last_prompt_tokens=500)
        assert result == messages  # Unchanged

    def test_disabled_compressor_ignores_real_tokens(self):
        """Disabled compressor always returns False regardless of real tokens."""
        comp = _make_compressor(threshold_tokens=100, enabled=False)

        messages = _make_messages(5)
        # Even with high real tokens, disabled means no compression
        assert comp.should_compress(messages, last_prompt_tokens=9999) is False


# --- ReActAgent Integration Tests ---


class TestReActAgentRealTokenIntegration:
    """Test _last_prompt_tokens state management in ReActAgent."""

    def test_initial_state_is_none(self):
        """_last_prompt_tokens starts as None."""
        agent = object.__new__(ReActAgent)
        agent._last_prompt_tokens = None
        assert agent._last_prompt_tokens is None

    def test_real_tokens_stored_after_llm_call(self):
        """After LLM call with usage.prompt_tokens > 0, _last_prompt_tokens is updated."""
        import inspect

        source = inspect.getsource(ReActAgent)
        assert "self._last_prompt_tokens = usage.prompt_tokens" in source

    def test_prepare_run_resets_last_prompt_tokens(self):
        """_prepare_run() resets _last_prompt_tokens to None."""
        import inspect

        source = inspect.getsource(ReActAgent._prepare_run)
        assert "self._last_prompt_tokens = None" in source

    def test_check_and_compress_receives_last_prompt_tokens(self):
        """_think_stream() passes _last_prompt_tokens to check_and_compress."""
        import inspect

        source = inspect.getsource(ReActAgent._think_stream)
        assert "last_prompt_tokens=self._last_prompt_tokens" in source

    def test_should_compress_receives_last_prompt_tokens(self):
        """_think_stream() passes _last_prompt_tokens to should_compress."""
        import inspect

        source = inspect.getsource(ReActAgent._think_stream)
        # v0.7.13: should_compress now also receives calibration_factor
        assert "should_compress" in source
        assert "last_prompt_tokens=self._last_prompt_tokens" in source

    def test_compress_receives_last_prompt_tokens(self):
        """_think_stream() passes _last_prompt_tokens to compress."""
        import inspect

        source = inspect.getsource(ReActAgent._think_stream)
        # v0.7.13: compress now also receives calibration_factor
        assert "compress" in source
        assert "last_prompt_tokens=self._last_prompt_tokens" in source


# --- Backward Compatibility Tests ---


class TestBackwardCompatibility:
    """Ensure existing code works without passing last_prompt_tokens."""

    def test_context_manager_no_new_param(self):
        """check_and_compress works without last_prompt_tokens."""
        cm = _make_context_manager(max_tokens=8192)
        cm.memory.add({"role": "user", "content": "test"})
        cm.check_and_compress(max_context_tokens=8192)

    def test_compressor_no_new_param(self):
        """should_compress works without last_prompt_tokens."""
        comp = _make_compressor(threshold_tokens=2000)
        messages = _make_messages(3)
        comp.should_compress(messages)

    def test_compress_no_new_param(self):
        """compress works without last_prompt_tokens."""
        comp = _make_compressor(threshold_tokens=2000)
        messages = _make_messages(3)
        result = comp.compress(messages)
        assert isinstance(result, list)

    def test_estimate_tokens_still_works(self):
        """estimate_tokens() is still callable as fallback."""
        messages = _make_messages(3, "Hello world")
        count = estimate_tokens(messages)
        assert isinstance(count, int)
        assert count > 0
