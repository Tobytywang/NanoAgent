"""
Tests for v0.9.0 streaming execution.

Covers ExecutionEvent types, _think_stream(), run_stream(),
and orchestrator.run_stream().
"""

import pytest
from unittest.mock import Mock, MagicMock

from nano_agent.agent.react import ReActAgent
from nano_agent.agent.types import (
    ExecutionEvent,
    ExecutionEventType,
    ExecutionHandle,
    ThinkResult,
    TerminationReason,
)
from nano_agent.agent.orchestrator import AgentOrchestrator
from nano_agent.llm.base import LLMUsage
from nano_agent.llm.messages import ToolCall
from nano_agent.tools import ToolRegistry
from nano_agent.tools.base import ToolResult, BaseTool
from nano_agent.memory.short_term import ShortTermMemory


class MockTool(BaseTool):
    """Mock tool that echoes input — differs from conftest _create_mock_tool which uses fixed output."""

    name = "mock_tool"
    description = "A mock tool for testing"

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        }

    def execute(self, input: str = "") -> ToolResult:
        return ToolResult(success=True, output=f"Processed: {input}")


# --- Type Tests ---


class TestExecutionEventType:
    """Test ExecutionEventType enum values."""

    def test_all_event_types_defined(self):
        expected = {
            "RUN_START",
            "THINK_START",
            "THINK_TEXT",
            "THINK_END",
            "TOOL_CALL",
            "TOOL_RESULT",
            "GUARD_SHORT_CIRCUIT",
            "RUN_END",
            "CANCELLED",
        }
        actual = {e.name for e in ExecutionEventType}
        assert actual == expected

    def test_event_type_values(self):
        assert ExecutionEventType.RUN_START.value == "run_start"
        assert ExecutionEventType.THINK_TEXT.value == "think_text"
        assert ExecutionEventType.CANCELLED.value == "cancelled"


class TestExecutionEvent:
    """Test ExecutionEvent typed fields."""

    def test_default_fields_are_none(self):
        event = ExecutionEvent(type="test", data={})
        assert event.text_chunk is None
        assert event.think_result is None
        assert event.tool_call is None
        assert event.tool_result is None
        assert event.result is None
        assert event.guard_name is None

    def test_typed_fields_populated(self):
        think = ThinkResult(
            response_text="hi", tool_calls=[], usage=LLMUsage(), is_final=True
        )
        event = ExecutionEvent(
            type=ExecutionEventType.THINK_END,
            data={},
            think_result=think,
            text_chunk="hi",
        )
        assert event.think_result is think
        assert event.text_chunk == "hi"


class TestExecutionHandle:
    """Test ExecutionHandle and cancel()."""

    def test_handle_wraps_generator(self):
        def gen():
            yield ExecutionEvent(type="test", data={})
            return "done"

        handle = ExecutionHandle(events=gen())
        events = list(handle.events)
        assert len(events) == 1
        assert not handle.cancelled

    def test_cancel_sets_flag(self):
        handle = ExecutionHandle(events=iter([]))
        assert not handle.cancelled
        handle.cancel()
        assert handle.cancelled


# --- _think_stream() Tests ---


class TestThinkStream:
    """Test _think_stream() generator variant."""

    def test_yields_think_events(self):
        llm = Mock()
        llm.chat = Mock(return_value=("Hello!", [], LLMUsage()))

        agent = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )

        gen = agent._think_stream()
        events = []
        think_result = None
        while True:
            try:
                event = next(gen)
                events.append(event)
            except StopIteration as e:
                think_result = e.value
                break

        event_types = [e.type for e in events]
        assert ExecutionEventType.THINK_START in event_types
        assert ExecutionEventType.THINK_TEXT in event_types
        assert ExecutionEventType.THINK_END in event_types
        assert think_result is not None
        assert think_result.response_text == "Hello!"
        assert think_result.is_final is True

    def test_think_wrapper_returns_same_result(self):
        llm = Mock()
        llm.chat = Mock(return_value=("Hello!", [], LLMUsage()))

        agent = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )

        # _think() should return same ThinkResult as _think_stream()
        result = agent._think()
        assert result.response_text == "Hello!"
        assert result.is_final is True


# --- run_stream() Tests ---


class TestRunStream:
    """Test ReActAgent.run_stream() generator."""

    def test_simple_final_answer(self):
        llm = Mock()
        llm.chat = Mock(return_value=("The answer is 42.", [], LLMUsage()))

        agent = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )

        handle = agent.run_stream("What is the answer?")
        events = list(handle.events)
        event_types = [e.type for e in events]

        assert ExecutionEventType.RUN_START in event_types
        assert ExecutionEventType.THINK_START in event_types
        assert ExecutionEventType.THINK_END in event_types
        assert ExecutionEventType.RUN_END in event_types

        # Final result
        result = None
        for e in events:
            if e.type == ExecutionEventType.RUN_END and e.result is not None:
                result = e.result
        assert result is not None
        assert result.success
        assert "42" in result.response

    def test_one_tool_call_round(self):
        llm = Mock()
        tool_call = ToolCall(id="call_1", name="mock_tool", arguments={"input": "test"})
        llm.chat = Mock(
            side_effect=[
                ("Let me check", [tool_call], LLMUsage()),
                ("The result is: Processed: test", [], LLMUsage()),
            ]
        )

        registry = ToolRegistry()
        registry.register(MockTool())

        agent = ReActAgent(
            llm=llm, memory=ShortTermMemory(), tool_registry=registry, verbose=False
        )

        handle = agent.run_stream("Process test")
        events = list(handle.events)
        event_types = [e.type for e in events]

        assert ExecutionEventType.TOOL_CALL in event_types
        assert ExecutionEventType.TOOL_RESULT in event_types

        result = None
        for e in events:
            if e.type == ExecutionEventType.RUN_END and e.result is not None:
                result = e.result
        assert result is not None
        assert "Processed: test" in result.response

    def test_guard_short_circuit(self):
        """Guard clause (routing) yields GUARD_SHORT_CIRCUIT + RUN_END."""
        llm = Mock()
        # Router will classify as SIMPLE → direct answer
        llm.chat = Mock(return_value=("Hi there!", [], LLMUsage()))

        agent = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )

        # "hello" is a simple greeting → routing short-circuit
        handle = agent.run_stream("hello")
        events = list(handle.events)
        event_types = [e.type for e in events]

        assert ExecutionEventType.GUARD_SHORT_CIRCUIT in event_types
        assert ExecutionEventType.RUN_END in event_types

    def test_cancellation(self):
        """Cancelled handle yields CANCELLED + RUN_END."""
        llm = Mock()
        llm.chat = Mock(return_value=("Working...", [], LLMUsage()))

        agent = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
            max_iterations=5,
        )

        handle = agent.run_stream("Do something complex")
        # Cancel immediately
        handle.cancel()

        events = list(handle.events)
        event_types = [e.type for e in events]

        assert ExecutionEventType.CANCELLED in event_types
        assert ExecutionEventType.RUN_END in event_types

        result = next(
            (
                e.result
                for e in events
                if e.type == ExecutionEventType.RUN_END and e.result
            ),
            None,
        )
        assert result is not None
        assert result.termination_reason == TerminationReason.CANCELLED.value

    def test_run_and_run_stream_equivalent(self):
        """run() and run_stream() produce the same final result."""
        llm = Mock()
        llm.chat = Mock(return_value=("The answer is 42.", [], LLMUsage()))

        # Run with run()
        agent1 = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )
        result1 = agent1.run("What is the answer?")

        # Run with run_stream()
        agent2 = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )
        handle = agent2.run_stream("What is the answer?")
        result2 = handle.collect_result()

        assert result1.response == result2.response
        assert result1.success == result2.success


# --- Orchestrator.run_stream() Tests ---


class TestOrchestratorRunStream:
    """Test AgentOrchestrator.run_stream()."""

    def test_basic_orchestrator_stream(self):
        llm = Mock()
        llm.chat = Mock(return_value=("Hello!", [], LLMUsage()))

        agent = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )
        orchestrator = AgentOrchestrator(agent)

        handle = orchestrator.run_stream("Say hello")
        events = list(handle.events)
        event_types = [e.type for e in events]

        assert ExecutionEventType.RUN_END in event_types

        result = next(
            (
                e.result
                for e in events
                if e.type == ExecutionEventType.RUN_END and e.result
            ),
            None,
        )
        assert result is not None
        assert result.success

    def test_run_and_run_stream_equivalent(self):
        """Orchestrator.run() and run_stream() produce same result."""
        llm = Mock()
        llm.chat = Mock(return_value=("The answer is 42.", [], LLMUsage()))

        # run()
        agent1 = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )
        orch1 = AgentOrchestrator(agent1)
        result1 = orch1.run("What is the answer?")

        # run_stream()
        agent2 = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )
        orch2 = AgentOrchestrator(agent2)
        handle = orch2.run_stream("What is the answer?")
        result2 = handle.collect_result()

        assert result1.response == result2.response
        assert result1.success == result2.success

    def test_sanitizer_rejection_yields_run_end(self):
        """Sanitizer rejection yields RUN_END with INPUT_REJECTED."""
        llm = Mock()
        agent = ReActAgent(
            llm=llm,
            memory=ShortTermMemory(),
            tool_registry=ToolRegistry(),
            verbose=False,
        )

        sanitizer = Mock()
        sanitizer.enabled = True
        sanitizer.sanitize = Mock(
            return_value=Mock(rejected=True, reason="Unsafe input", sanitized_input="")
        )

        orchestrator = AgentOrchestrator(agent, sanitizer=sanitizer)
        handle = orchestrator.run_stream("malicious input")
        result = handle.collect_result()
        assert result is not None
        assert not result.success
        assert result.termination_reason == TerminationReason.INPUT_REJECTED.value
