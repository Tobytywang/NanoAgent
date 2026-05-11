"""
Tests for v0.6.0 architecture: types, events, budget, and orchestrator.
"""

import pytest
from unittest.mock import Mock, MagicMock

from nano_agent.agent import (
    ExecutionResult,
    ThinkResult,
    ExecutionEvent,
    AgentEvent,
    EventEmitter,
    Budget,
    BudgetChecker,
    AgentOrchestrator,
    SessionStats,
    ReActAgent,
)
from nano_agent.memory import ShortTermMemory
from nano_agent.tools import ToolRegistry, ToolResult
from nano_agent.llm.messages import ToolCall
from nano_agent.llm.base import LLMUsage


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_create_execution_result(self):
        """Test creating an ExecutionResult."""
        result = ExecutionResult(
            response="Hello",
            success=True,
            iterations=1,
            tool_calls=[{"name": "test"}],
            tokens_used=100,
            session_id="abc123"
        )
        assert result.response == "Hello"
        assert result.success is True
        assert result.iterations == 1
        assert len(result.tool_calls) == 1
        assert result.tokens_used == 100
        assert result.session_id == "abc123"

    def test_execution_result_is_immutable(self):
        """Test that ExecutionResult is frozen (immutable)."""
        result = ExecutionResult(
            response="Hello",
            success=True,
            iterations=1,
            tool_calls=[],
            tokens_used=0,
            session_id=""
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            result.response = "Changed"


class TestThinkResult:
    """Tests for ThinkResult dataclass."""

    def test_create_think_result(self):
        """Test creating a ThinkResult."""
        result = ThinkResult(
            response_text="Thinking...",
            tool_calls=[],
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            is_final=True
        )
        assert result.response_text == "Thinking..."
        assert result.is_final is True
        assert result.usage.total_tokens == 15

    def test_think_result_with_tool_calls(self):
        """Test ThinkResult with tool calls."""
        tool_call = ToolCall(id="1", name="test", arguments={})
        result = ThinkResult(
            response_text="Let me check",
            tool_calls=[tool_call],
            usage=LLMUsage(),
            is_final=False
        )
        assert result.is_final is False
        assert len(result.tool_calls) == 1


class TestExecutionEvent:
    """Tests for ExecutionEvent dataclass."""

    def test_create_execution_event(self):
        """Test creating an ExecutionEvent."""
        event = ExecutionEvent(
            type="tool_call",
            data={"tool": "test", "arguments": {}}
        )
        assert event.type == "tool_call"
        assert event.data["tool"] == "test"


class TestAgentEvent:
    """Tests for AgentEvent enum."""

    def test_agent_event_values(self):
        """Test AgentEvent enum values."""
        assert AgentEvent.RUN_START.value == "run_start"
        assert AgentEvent.THINK_START.value == "think_start"
        assert AgentEvent.TOOL_CALL.value == "tool_call"
        assert AgentEvent.TOOL_RESULT.value == "tool_result"
        assert AgentEvent.RUN_END.value == "run_end"


class TestEventEmitter:
    """Tests for EventEmitter class."""

    def test_on_and_emit(self):
        """Test registering and emitting events."""
        emitter = EventEmitter()
        received = []

        def handler(event, data):
            received.append((event, data))

        emitter.on(AgentEvent.RUN_START, handler)
        emitter.emit(AgentEvent.RUN_START, {"input": "test"})

        assert len(received) == 1
        assert received[0][0] == AgentEvent.RUN_START
        assert received[0][1] == {"input": "test"}

    def test_multiple_handlers(self):
        """Test multiple handlers for same event."""
        emitter = EventEmitter()
        count = [0, 0]

        def handler1(event, data):
            count[0] += 1

        def handler2(event, data):
            count[1] += 1

        emitter.on(AgentEvent.RUN_START, handler1)
        emitter.on(AgentEvent.RUN_START, handler2)
        emitter.emit(AgentEvent.RUN_START, {})

        assert count == [1, 1]

    def test_off_removes_handler(self):
        """Test removing a handler."""
        emitter = EventEmitter()
        called = [False]

        def handler(event, data):
            called[0] = True

        emitter.on(AgentEvent.RUN_START, handler)
        emitter.off(AgentEvent.RUN_START, handler)
        emitter.emit(AgentEvent.RUN_START, {})

        assert called[0] is False

    def test_off_without_handler_removes_all(self):
        """Test removing all handlers for an event."""
        emitter = EventEmitter()
        count = [0]

        def handler(event, data):
            count[0] += 1

        emitter.on(AgentEvent.RUN_START, handler)
        emitter.on(AgentEvent.RUN_START, handler)
        emitter.off(AgentEvent.RUN_START)
        emitter.emit(AgentEvent.RUN_START, {})

        assert count[0] == 0

    def test_handler_exception_does_not_affect_others(self):
        """Test that exceptions in handlers don't affect other handlers."""
        emitter = EventEmitter()
        results = []

        def bad_handler(event, data):
            raise ValueError("Error!")

        def good_handler(event, data):
            results.append("ok")

        emitter.on(AgentEvent.RUN_START, bad_handler)
        emitter.on(AgentEvent.RUN_START, good_handler)
        emitter.emit(AgentEvent.RUN_START, {})

        assert results == ["ok"]

    def test_clear_removes_all_handlers(self):
        """Test clear removes all handlers."""
        emitter = EventEmitter()
        count = [0]

        def handler(event, data):
            count[0] += 1

        emitter.on(AgentEvent.RUN_START, handler)
        emitter.on(AgentEvent.TOOL_CALL, handler)
        emitter.clear()
        emitter.emit(AgentEvent.RUN_START, {})
        emitter.emit(AgentEvent.TOOL_CALL, {})

        assert count[0] == 0


class TestBudget:
    """Tests for Budget dataclass."""

    def test_default_budget(self):
        """Test default budget values."""
        budget = Budget()
        assert budget.max_iterations == 10
        assert budget.max_tokens == 100000
        assert budget.max_tool_calls == 50

    def test_custom_budget(self):
        """Test custom budget values."""
        budget = Budget(max_iterations=5, max_tokens=50000, max_tool_calls=20)
        assert budget.max_iterations == 5
        assert budget.max_tokens == 50000
        assert budget.max_tool_calls == 20


class TestBudgetChecker:
    """Tests for BudgetChecker class."""

    def test_can_continue_within_budget(self):
        """Test can_continue returns True when within budget."""
        budget = Budget(max_iterations=10, max_tokens=100, max_tool_calls=10)
        checker = BudgetChecker(budget)

        assert checker.can_continue(5, 50, 5) is True

    def test_can_continue_exceeds_iterations(self):
        """Test can_continue returns False when iterations exceeded."""
        budget = Budget(max_iterations=10)
        checker = BudgetChecker(budget)

        assert checker.can_continue(10, 0, 0) is False

    def test_can_continue_exceeds_tokens(self):
        """Test can_continue returns False when tokens exceeded."""
        budget = Budget(max_tokens=100)
        checker = BudgetChecker(budget)

        assert checker.can_continue(0, 100, 0) is False

    def test_can_continue_exceeds_tool_calls(self):
        """Test can_continue returns False when tool calls exceeded."""
        budget = Budget(max_tool_calls=10)
        checker = BudgetChecker(budget)

        assert checker.can_continue(0, 0, 10) is False

    def test_individual_checks(self):
        """Test individual check methods."""
        budget = Budget(max_iterations=5, max_tokens=100, max_tool_calls=10)
        checker = BudgetChecker(budget)

        assert checker.check_iterations(4) is True
        assert checker.check_iterations(5) is False
        assert checker.check_tokens(99) is True
        assert checker.check_tokens(100) is False
        assert checker.check_tool_calls(9) is True
        assert checker.check_tool_calls(10) is False


class TestSessionStats:
    """Tests for SessionStats dataclass."""

    def test_default_stats(self):
        """Test default session stats."""
        stats = SessionStats()
        assert stats.total_tokens == 0
        assert stats.total_tool_calls == 0
        assert stats.total_iterations == 0


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator class."""

    def test_create_orchestrator(self):
        """Test creating an orchestrator."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], LLMUsage()))

        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        orchestrator = AgentOrchestrator(agent)
        assert orchestrator.session_id != ""
        assert orchestrator.stats.total_tokens == 0

    def test_run_returns_execution_result(self):
        """Test that run returns ExecutionResult."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], LLMUsage()))

        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        orchestrator = AgentOrchestrator(agent)
        result = orchestrator.run("Hi")

        assert isinstance(result, ExecutionResult)
        assert result.response == "Hello"
        assert result.session_id == orchestrator.session_id

    def test_run_dry_mode(self):
        """Test dry-run mode."""
        llm = Mock()
        # First call returns tool call, second returns final answer
        tool_call = ToolCall(id="1", name="test", arguments={})
        llm.chat = Mock(
            side_effect=[
                ("Let me check", [tool_call], LLMUsage()),
                ("Done", [], LLMUsage())
            ]
        )

        memory = ShortTermMemory()
        registry = ToolRegistry()

        # Create a mock tool
        mock_tool = Mock()
        mock_tool.name = "test"
        mock_tool.description = "Test tool"
        mock_tool.parameters_schema = {}
        mock_tool.to_ollama_tool = Mock(return_value={})
        mock_tool.execute = Mock(return_value=ToolResult(success=True, output="executed"))
        registry.register(mock_tool)

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)
        orchestrator = AgentOrchestrator(agent)

        result = orchestrator.run_dry("Test")

        # In dry-run mode, tool should not be actually executed
        assert result.success is True
        assert result.response == "Done"

    def test_stats_accumulation(self):
        """Test that stats accumulate across runs."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)))

        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        orchestrator = AgentOrchestrator(agent)
        orchestrator.run("Hi")
        orchestrator.run("Hello")

        assert orchestrator.stats.total_tokens == 30  # 15 * 2

    def test_event_emission(self):
        """Test that events are emitted during run."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], LLMUsage()))

        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        orchestrator = AgentOrchestrator(agent)

        events = []
        orchestrator.events.on(AgentEvent.RUN_START, lambda e, d: events.append(e))
        orchestrator.events.on(AgentEvent.RUN_END, lambda e, d: events.append(e))

        orchestrator.run("Hi")

        assert AgentEvent.RUN_START in events
        assert AgentEvent.RUN_END in events

    def test_new_session(self):
        """Test starting a new session."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], LLMUsage()))

        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        orchestrator = AgentOrchestrator(agent)
        old_session_id = orchestrator.session_id
        orchestrator.run("Hi")

        new_session_id = orchestrator.new_session()

        assert new_session_id != old_session_id
        assert orchestrator.stats.total_tokens == 0
