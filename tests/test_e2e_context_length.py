"""
E2E tests for v0.7.11: Model Context Window Accuracy.

Validates the full pipeline from config → LLM injection → context length
resolution → ContextManager compression decisions. Uses FakeLLM and
FakeMemory — no real Ollama/OpenAI service required.
"""

import pytest

from nano_agent.config.schema import (
    Config,
    LLMConfig,
    ContextConfig,
    CONSERVATIVE_CONTEXT_FALLBACK,
    MODEL_CONTEXT_LENGTHS,
)
from nano_agent.agent.context import ContextManager
from nano_agent.llm.base import BaseLLM, LLMUsage

# ============================================================
# Test doubles
# ============================================================


class FakeLLM(BaseLLM):
    """Fake LLM that returns preset responses and records calls."""

    def __init__(
        self,
        model: str = "fake-model",
        base_url: str = "http://localhost:0",
        response: str = "done",
        context_length: int | None = None,
    ):
        self.model = model
        self.base_url = base_url
        self._response = response
        self._context_length = context_length
        self.chat_calls = []

    def chat(self, messages, tools=None, system_stable=None, **kwargs):
        self.chat_calls.append(messages)
        return self._response, [], LLMUsage()

    def query_context_length(self) -> int | None:
        return self._context_length


class FakeMemory:
    """Fake memory with controllable message list."""

    def __init__(self, messages=None):
        self._messages = list(messages or [])
        self._stable_system_prompt = None
        self._system_prompt = None

    def get_all(self):
        return list(self._messages)

    def clear(self):
        self._messages.clear()

    def add(self, msg):
        self._messages.append(msg)

    def set_stable_system_prompt(self, prompt: str):
        self._stable_system_prompt = prompt

    def set_system_prompt(self, prompt: str):
        self._system_prompt = prompt


def make_heavy_messages(rounds: int = 50):
    """Generate mixed messages that consume significant tokens.

    Each round adds 3 messages (user + assistant + tool) with long content.
    50 rounds ≈ 8400 tokens (exceeds 8192 window at >95%).
    """
    msgs = []
    for i in range(rounds):
        msgs.append(
            {
                "role": "user",
                "content": "This is a substantial conversation message that contains enough text to consume significant context window space. "
                * 20,
            }
        )
        msgs.append(
            {
                "role": "assistant",
                "content": "I have processed your request and here is my analysis of the situation with detailed findings and recommendations. "
                * 20,
            }
        )
        msgs.append(
            {
                "role": "tool",
                "content": "Tool execution result: the operation completed successfully with the following output data and status information. "
                * 20,
                "tool_call_id": f"call_{i}",
            }
        )
    return msgs


# ============================================================
# E2E-1: Config → LLM → set_llm_client → get_context_length
# ============================================================


class TestE2EConfigToContextLength:
    """Full pipeline: config + LLM injection → correct context length."""

    def test_api_query_used_after_injection(self):
        config = LLMConfig(model="custom-model")

        # Before injection: unknown model → conservative fallback
        assert config.get_context_length() == CONSERVATIVE_CONTEXT_FALLBACK

        # Inject LLM that reports 65536
        fake_llm = FakeLLM(context_length=65536)
        config.set_llm_client(fake_llm)

        # After injection: API query result is used
        assert config.get_context_length() == 65536

    def test_user_override_beats_api_query(self):
        config = LLMConfig(model="custom-model", context_length=32768)
        fake_llm = FakeLLM(context_length=65536)
        config.set_llm_client(fake_llm)

        # Override wins over API query
        assert config.get_context_length() == 32768

    def test_api_returns_none_falls_through_to_lookup(self):
        config = LLMConfig(model="gpt-4o")

        # FakeLLM returns None (API unavailable)
        fake_llm = FakeLLM(context_length=None)
        config.set_llm_client(fake_llm)

        # Falls through to lookup table
        assert config.get_context_length() == 128000

    def test_api_returns_none_unknown_model_falls_to_conservative(self):
        config = LLMConfig(model="unknown-future-model")

        fake_llm = FakeLLM(context_length=None)
        config.set_llm_client(fake_llm)

        # Falls through lookup → conservative fallback
        assert config.get_context_length() == CONSERVATIVE_CONTEXT_FALLBACK

    def test_llama31_not_mistaken_for_llama3_after_injection(self):
        """Even with API returning None, llama3.1 must use its own entry."""
        config = LLMConfig(model="llama3.1")
        fake_llm = FakeLLM(context_length=None)
        config.set_llm_client(fake_llm)

        # Must be 131072 (llama3.1), NOT 8192 (llama3)
        assert config.get_context_length() == 131072


# ============================================================
# E2E-2: ContextManager uses llm_config, not hardcoded 128000
# ============================================================


class TestE2EContextManagerCompression:
    """Same message load, different window sizes → different behavior."""

    def _make_cm(self, llm_config, messages):
        fake_llm = FakeLLM(response="summary text")
        return ContextManager(
            memory=FakeMemory(messages),
            llm=fake_llm,
            config=ContextConfig(),
            llm_config=llm_config,
        )

    def test_small_window_triggers_compression(self):
        """Heavy messages with 8192 window should trigger compression.

        50 rounds ≈ 8400 tokens > 8192 * 95% → model compression.
        """
        llm_config = LLMConfig(model="llama3")  # 8192
        messages = make_heavy_messages(rounds=50)
        cm = self._make_cm(llm_config, messages)

        result = cm.check_and_compress()
        assert result is True, "Should compress with small window (8192)"

    def test_large_window_no_compression(self):
        """Same messages with 128000 window should NOT compress.

        8400 tokens / 128000 = 6.5%, well below 70% threshold.
        """
        llm_config = LLMConfig(model="gpt-4o")  # 128000
        messages = make_heavy_messages(rounds=50)
        cm = self._make_cm(llm_config, messages)

        result = cm.check_and_compress()
        assert result is False, "Should NOT compress with large window (128000)"

    def test_config_override_affects_compression(self):
        """User override (context_length=4096) makes compression trigger earlier."""
        llm_config = LLMConfig(model="gpt-4o", context_length=4096)
        messages = make_heavy_messages(rounds=50)
        cm = self._make_cm(llm_config, messages)

        result = cm.check_and_compress()
        # With only 4096 window, 8400 tokens is >95% → compress
        assert result is True, "Should compress with user-override small window (4096)"

    def test_no_llm_config_uses_conservative_fallback(self):
        """Without llm_config, ContextManager should use conservative fallback (8192)."""
        messages = make_heavy_messages(rounds=50)
        fake_llm = FakeLLM(response="summary")
        cm = ContextManager(
            memory=FakeMemory(messages),
            llm=fake_llm,
            config=ContextConfig(),
            llm_config=None,
        )

        result = cm.check_and_compress()
        # 8400 tokens with 8192 window → should compress
        assert result is True, "Should compress with conservative fallback (8192)"


# ============================================================
# E2E-3: AgentBuilder full pipeline — llm_config reaches agent
# ============================================================


class TestE2EAgentBuilderPipeline:
    """Verify llm_config flows from Config through AgentBuilder to Agent."""

    def test_agent_gets_llm_config(self):
        from nano_agent.core.builder import AgentBuilder

        config = Config()
        config.llm.model = "llama3"

        builder = AgentBuilder(config)
        builder.with_llm_instance(FakeLLM(model="llama3"))
        builder.with_memory_instance(FakeMemory())

        orchestrator = builder.build()
        assert orchestrator.agent.context_manager is not None
        assert orchestrator.agent.context_manager._llm_config is config.llm

    def test_agent_context_manager_uses_correct_window(self):
        from nano_agent.core.builder import AgentBuilder

        config = Config()
        config.llm.model = "llama3"

        builder = AgentBuilder(config)
        builder.with_llm_instance(FakeLLM(model="llama3"))
        builder.with_memory_instance(FakeMemory())

        orchestrator = builder.build()
        assert (
            orchestrator.agent.context_manager._llm_config.get_context_length() == 8192
        )

    def test_agent_context_manager_with_override(self):
        from nano_agent.core.builder import AgentBuilder

        config = Config()
        config.llm.model = "llama3"
        config.llm.context_length = 32768

        builder = AgentBuilder(config)
        builder.with_llm_instance(FakeLLM(model="llama3"))
        builder.with_memory_instance(FakeMemory())

        orchestrator = builder.build()
        assert (
            orchestrator.agent.context_manager._llm_config.get_context_length() == 32768
        )

    def test_set_llm_client_injected_by_builder(self):
        """After builder.build(), config.llm should have the LLM client set."""
        from nano_agent.core.builder import AgentBuilder

        config = Config()
        config.llm.model = "llama3"
        fake_llm = FakeLLM(model="llama3", context_length=65536)

        builder = AgentBuilder(config)
        builder.with_llm_instance(fake_llm)
        builder.with_memory_instance(FakeMemory())

        # Before build: no client
        assert config.llm._llm_client is None

        agent = builder.build()

        # After build: client should be injected by builder
        assert config.llm._llm_client is fake_llm
        # And get_context_length should use API query
        assert config.llm.get_context_length() == 65536


# ============================================================
# E2E-4: Conservative fallback — unknown model never gets 128000
# ============================================================


class TestE2EConservativeFallback:
    """Unknown models must get 8192, not 128000."""

    def test_unknown_model_default(self):
        config = LLMConfig(model="future-model-v99")
        assert config.get_context_length() == 8192

    def test_unknown_model_api_returns_none(self):
        config = LLMConfig(model="future-model-v99")
        fake_llm = FakeLLM(context_length=None)
        config.set_llm_client(fake_llm)
        assert config.get_context_length() == 8192

    def test_unknown_model_api_returns_value(self):
        config = LLMConfig(model="future-model-v99")
        fake_llm = FakeLLM(context_length=100000)
        config.set_llm_client(fake_llm)
        assert config.get_context_length() == 100000

    def test_no_regression_on_known_models(self):
        """All models in the lookup table must return their correct value."""
        for model, expected in MODEL_CONTEXT_LENGTHS.items():
            config = LLMConfig(model=model)
            actual = config.get_context_length()
            assert actual == expected, f"{model}: expected {expected}, got {actual}"

    def test_partial_match_does_not_underestimate(self):
        """llama3.1 (131072) must not match llama3 (8192)."""
        config = LLMConfig(model="llama3.1")
        assert config.get_context_length() == 131072

    def test_conservative_fallback_is_safe(self):
        """8192 is safe: it may trigger early compression but never overflow."""
        config = LLMConfig(model="unknown")
        length = config.get_context_length()
        assert length <= 8192, f"Fallback {length} is too large — risk of overflow"
