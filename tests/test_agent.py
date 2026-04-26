"""
Tests for Agent system.
"""

import pytest
from unittest.mock import Mock, MagicMock

from nano_agent.agent.base import BaseAgent
from nano_agent.agent.react import ReActAgent
from nano_agent.agent.prompts import REACT_SYSTEM_PROMPT, TOOL_DESCRIPTION_TEMPLATE
from nano_agent.llm.messages import ToolCall
from nano_agent.tools.base import ToolRegistry, ToolResult, BaseTool
from nano_agent.memory.short_term import ShortTermMemory


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

    def execute(self, input: str) -> ToolResult:
        return ToolResult(success=True, output=f"Processed: {input}")


class TestReActAgent:
    """Test ReActAgent class."""

    def test_initialization(self):
        """Test agent initialization."""
        llm = Mock()
        memory = ShortTermMemory()
        registry = ToolRegistry()
        registry.register(MockTool())

        agent = ReActAgent(
            llm=llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=5
        )

        assert agent.max_iterations == 5
        assert len(agent.tool_registry) == 1

    def test_system_prompt_setup(self):
        """Test that system prompt includes tool descriptions."""
        llm = Mock()
        memory = ShortTermMemory()
        registry = ToolRegistry()
        registry.register(MockTool())

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry)

        messages = memory.get_all()
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "mock_tool" in system_msg["content"]

    def test_execute_tool(self):
        """Test tool execution."""
        llm = Mock()
        memory = ShortTermMemory()
        registry = ToolRegistry()
        registry.register(MockTool())

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry)
        result = agent.execute_tool("mock_tool", {"input": "test"})

        assert result.success is True
        assert result.output == "Processed: test"

    def test_execute_unknown_tool(self):
        """Test executing unknown tool."""
        llm = Mock()
        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry)
        result = agent.execute_tool("unknown_tool", {})

        assert result.success is False
        assert "Unknown tool" in result.error

    def test_run_without_tool_calls(self):
        """Test run when LLM returns no tool calls."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello! How can I help?", []))

        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)
        response = agent.run("Hi")

        assert response == "Hello! How can I help?"
        # Check memory has user and assistant messages
        messages = memory.get_all()
        assert len(messages) == 3  # system + user + assistant

    def test_run_with_tool_calls(self):
        """Test run when LLM returns tool calls."""
        llm = Mock()

        # First call returns tool call, second returns final answer
        tool_call = ToolCall(id="call_1", name="mock_tool", arguments={"input": "test"})
        llm.chat = Mock(
            side_effect=[
                ("Let me check", [tool_call]),
                ("The result is: Processed: test", [])
            ]
        )

        memory = ShortTermMemory()
        registry = ToolRegistry()
        registry.register(MockTool())

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)
        response = agent.run("Process test")

        assert "Processed: test" in response

    def test_max_iterations_limit(self):
        """Test that agent stops at max iterations."""
        llm = Mock()

        # Always return a tool call (infinite loop scenario)
        tool_call = ToolCall(id="call_1", name="mock_tool", arguments={"input": "test"})
        llm.chat = Mock(return_value=("Thinking...", [tool_call]))

        memory = ShortTermMemory()
        registry = ToolRegistry()
        registry.register(MockTool())

        agent = ReActAgent(
            llm=llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=3,
            verbose=False
        )
        response = agent.run("Do something")

        assert "iteration limit" in response.lower()

    def test_reset(self):
        """Test agent reset."""
        llm = Mock()
        llm.chat = Mock(return_value=("Response", []))

        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)
        agent.run("Hello")
        agent.reset()

        messages = memory.get_all()
        assert len(messages) == 1  # Only system message

    def test_add_tool(self):
        """Test adding a tool dynamically."""
        llm = Mock()
        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)
        agent.add_tool(MockTool())

        assert "mock_tool" in agent.tool_registry

        # Check system prompt updated
        messages = memory.get_all()
        assert "mock_tool" in messages[0]["content"]


class TestPrompts:
    """Test prompt templates."""

    def test_react_system_prompt_format(self):
        """Test REACT system prompt formatting."""
        tools_desc = "Tool: test\nDescription: A test tool"
        prompt = REACT_SYSTEM_PROMPT.format(tools_description=tools_desc)

        assert tools_desc in prompt
        assert "Think" in prompt
        assert "Act" in prompt
        assert "Observe" in prompt

    def test_tool_description_template(self):
        """Test tool description template."""
        desc = TOOL_DESCRIPTION_TEMPLATE.format(
            name="python_execute",
            description="Execute Python code",
            parameters={"type": "object"}
        )

        assert "python_execute" in desc
        assert "Execute Python code" in desc