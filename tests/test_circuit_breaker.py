"""
Circuit breaker unit tests.

Tests for the CircuitBreaker class that detects abnormal LLM behavior
and degrades execution from AUTO to SUPERVISED mode.
"""

import pytest
from unittest.mock import MagicMock

from nano_agent.agent.circuit_breaker import CircuitBreaker
from nano_agent.agent.types import ExecutionMode, AgentEvent
from nano_agent.config.schema import CircuitBreakerConfig
from nano_agent.agent.duplicate import DuplicateCheckResult
from nano_agent.agent.stall_detector import StallResult
from nano_agent.agent.events import EventEmitter


class TestCircuitBreakerConfig:
    """Circuit breaker configuration tests."""

    def test_default_config(self):
        config = CircuitBreakerConfig()
        assert config.enabled is True
        assert config.max_response_tokens == 8000
        assert config.duplicate_trigger_count == 3
        assert config.stall_trigger_count == 3
        assert config.auto_reset_on_user_confirm is True

    def test_custom_config(self):
        config = CircuitBreakerConfig(
            enabled=False,
            max_response_tokens=4000,
            duplicate_trigger_count=5,
            stall_trigger_count=4,
            auto_reset_on_user_confirm=False,
        )
        assert config.enabled is False
        assert config.max_response_tokens == 4000
        assert config.duplicate_trigger_count == 5
        assert config.stall_trigger_count == 4
        assert config.auto_reset_on_user_confirm is False

    def test_config_from_yaml(self):
        from nano_agent.config.loader import _from_dict

        config = _from_dict(
            CircuitBreakerConfig,
            {"enabled": True, "max_response_tokens": 6000},
        )
        assert config.enabled is True
        assert config.max_response_tokens == 6000
        assert config.duplicate_trigger_count == 3  # default preserved


class TestCircuitBreakerCheckLLMResponse:
    """Test check_llm_response method."""

    def test_normal_response_no_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        assert cb.mode == ExecutionMode.AUTO
        triggered = cb.check_llm_response(5000)
        assert triggered is False
        assert cb.mode == ExecutionMode.AUTO

    def test_oversized_response_triggers(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        triggered = cb.check_llm_response(9000)
        assert triggered is True
        assert cb.mode == ExecutionMode.SUPERVISED
        assert cb.trigger_reason is not None
        assert "9000" in cb.trigger_reason

    def test_exact_threshold_no_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        triggered = cb.check_llm_response(8000)
        assert triggered is False
        assert cb.mode == ExecutionMode.AUTO

    def test_disabled_never_triggers(self):
        cb = CircuitBreaker(CircuitBreakerConfig(enabled=False))
        triggered = cb.check_llm_response(20000)
        assert triggered is False
        assert cb.mode == ExecutionMode.AUTO

    def test_custom_threshold(self):
        cb = CircuitBreaker(CircuitBreakerConfig(max_response_tokens=4000))
        triggered = cb.check_llm_response(5000)
        assert triggered is True
        assert cb.mode == ExecutionMode.SUPERVISED

    def test_already_suppressed_no_repeat_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        cb.check_llm_response(9000)
        assert cb.mode == ExecutionMode.SUPERVISED
        triggered = cb.check_llm_response(10000)
        assert triggered is True  # Still returns True (condition met)
        # But reason stays from first trigger
        assert "9000" in cb.trigger_reason


class TestCircuitBreakerCheckDuplicate:
    """Test check_duplicate method."""

    def test_no_duplicate_no_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = DuplicateCheckResult(
            is_duplicate=False, should_skip=False, count=1, key="test:abc"
        )
        triggered = cb.check_duplicate(result)
        assert triggered is False
        assert cb.mode == ExecutionMode.AUTO

    def test_duplicate_below_threshold_no_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = DuplicateCheckResult(
            is_duplicate=True, should_skip=False, count=2, key="test:abc"
        )
        triggered = cb.check_duplicate(result)
        assert triggered is False

    def test_duplicate_at_threshold_triggers(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = DuplicateCheckResult(
            is_duplicate=True, should_skip=True, count=3, key="test:abc"
        )
        triggered = cb.check_duplicate(result)
        assert triggered is True
        assert cb.mode == ExecutionMode.SUPERVISED

    def test_duplicate_above_threshold_triggers(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = DuplicateCheckResult(
            is_duplicate=True, should_skip=True, count=5, key="test:abc"
        )
        triggered = cb.check_duplicate(result)
        assert triggered is True

    def test_custom_duplicate_threshold(self):
        cb = CircuitBreaker(CircuitBreakerConfig(duplicate_trigger_count=5))
        result = DuplicateCheckResult(
            is_duplicate=True, should_skip=False, count=4, key="test:abc"
        )
        triggered = cb.check_duplicate(result)
        assert triggered is False

        result5 = DuplicateCheckResult(
            is_duplicate=True, should_skip=True, count=5, key="test:abc"
        )
        triggered = cb.check_duplicate(result5)
        assert triggered is True


class TestCircuitBreakerCheckStall:
    """Test check_stall method."""

    def test_no_stall_no_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = StallResult(is_stalled=False, stalled_iterations=0)
        triggered = cb.check_stall(result)
        assert triggered is False
        assert cb.mode == ExecutionMode.AUTO

    def test_stall_below_threshold_no_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = StallResult(is_stalled=True, stalled_iterations=2)
        triggered = cb.check_stall(result)
        assert triggered is False

    def test_stall_at_threshold_triggers(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = StallResult(is_stalled=True, stalled_iterations=3, hint="test hint")
        triggered = cb.check_stall(result)
        assert triggered is True
        assert cb.mode == ExecutionMode.SUPERVISED

    def test_stall_above_threshold_triggers(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        result = StallResult(is_stalled=True, stalled_iterations=5)
        triggered = cb.check_stall(result)
        assert triggered is True

    def test_custom_stall_threshold(self):
        cb = CircuitBreaker(CircuitBreakerConfig(stall_trigger_count=5))
        result = StallResult(is_stalled=True, stalled_iterations=4)
        triggered = cb.check_stall(result)
        assert triggered is False


class TestCircuitBreakerReset:
    """Test reset method."""

    def test_reset_after_trigger(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        cb.check_llm_response(9000)
        assert cb.mode == ExecutionMode.SUPERVISED

        cb.reset()
        assert cb.mode == ExecutionMode.AUTO
        assert cb.trigger_reason is None

    def test_reset_when_already_auto(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        cb.reset()
        assert cb.mode == ExecutionMode.AUTO
        assert cb.trigger_reason is None

    def test_trigger_after_reset(self):
        cb = CircuitBreaker(CircuitBreakerConfig())
        cb.check_llm_response(9000)
        cb.reset()
        # Can trigger again after reset
        triggered = cb.check_llm_response(9000)
        assert triggered is True
        assert cb.mode == ExecutionMode.SUPERVISED


class TestCircuitBreakerEvents:
    """Test event emission."""

    def test_event_emitted_on_trigger(self):
        events = EventEmitter()
        cb = CircuitBreaker(CircuitBreakerConfig(), event_emitter=events)

        received_events = []
        events.on(
            AgentEvent.CIRCUIT_BREAKER,
            lambda event, data: received_events.append(data),
        )

        cb.check_llm_response(9000)
        assert len(received_events) == 1
        assert received_events[0]["mode"] == "supervised"
        assert "9000" in received_events[0]["reason"]

    def test_no_event_on_second_trigger(self):
        events = EventEmitter()
        cb = CircuitBreaker(CircuitBreakerConfig(), event_emitter=events)

        received_events = []
        events.on(
            AgentEvent.CIRCUIT_BREAKER,
            lambda event, data: received_events.append(data),
        )

        cb.check_llm_response(9000)
        cb.check_llm_response(10000)  # Already in SUPERVISED
        assert len(received_events) == 1  # Only one event

    def test_no_event_when_disabled(self):
        events = EventEmitter()
        cb = CircuitBreaker(CircuitBreakerConfig(enabled=False), event_emitter=events)

        received_events = []
        events.on(
            AgentEvent.CIRCUIT_BREAKER,
            lambda event, data: received_events.append(data),
        )

        cb.check_llm_response(9000)
        assert len(received_events) == 0


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with config chain."""

    def test_circuit_breaker_config_in_smart_optimization(self):
        from nano_agent.config.schema import SmartOptimizationConfig

        config = SmartOptimizationConfig()
        assert hasattr(config, "circuit_breaker")
        assert config.circuit_breaker.enabled is True

    def test_circuit_breaker_config_in_full_config(self):
        from nano_agent.config.schema import Config

        config = Config()
        assert hasattr(config.smart_optimization, "circuit_breaker")
        cb = config.smart_optimization.circuit_breaker
        assert cb.max_response_tokens == 8000

    def test_circuit_breaker_config_from_yaml(self):
        from nano_agent.config.loader import _from_dict
        from nano_agent.config.schema import Config

        data = {
            "smart_optimization": {
                "circuit_breaker": {
                    "enabled": True,
                    "max_response_tokens": 6000,
                }
            }
        }
        config = _from_dict(Config, data)
        assert config.smart_optimization.circuit_breaker.max_response_tokens == 6000

    def test_execution_mode_enum(self):
        assert ExecutionMode.AUTO.value == "auto"
        assert ExecutionMode.SUPERVISED.value == "supervised"

    def test_circuit_breaker_event_enum(self):
        assert AgentEvent.CIRCUIT_BREAKER.value == "circuit_breaker"
