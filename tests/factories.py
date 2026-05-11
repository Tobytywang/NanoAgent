"""
Test data factories for NanoAgent tests.

This module provides factory functions to create test data objects
in a consistent and reusable way.
"""

from typing import Any

from nano_agent.memory.storage import MemoryEntry
from nano_agent.memory.long_term import LongTermEntry
from nano_agent.tools.base import BaseTool, ToolResult
from nano_agent.config.schema import (
    Config, LLMConfig, AgentConfig, MemoryConfig,
    ToolConfig, PluginsConfig, SkillsConfig, LoggingConfig
)


# === Message Factories ===

def create_message(
    role: str = "user",
    content: str = "test message",
    **kwargs
) -> dict[str, Any]:
    """
    Create a test message dictionary.

    Args:
        role: Message role (user, assistant, system, tool)
        content: Message content
        **kwargs: Additional message fields

    Returns:
        Message dictionary
    """
    msg = {"role": role, "content": content}
    msg.update(kwargs)
    return msg


def create_user_message(content: str = "Hello") -> dict[str, Any]:
    """Create a user message."""
    return create_message(role="user", content=content)


def create_assistant_message(
    content: str = "Response",
    tool_calls: list | None = None
) -> dict[str, Any]:
    """Create an assistant message."""
    msg = create_message(role="assistant", content=content)
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def create_system_message(content: str = "System prompt") -> dict[str, Any]:
    """Create a system message."""
    return create_message(role="system", content=content)


def create_tool_result_message(
    tool_call_id: str = "call_123",
    content: str = "Tool result"
) -> dict[str, Any]:
    """Create a tool result message."""
    return create_message(
        role="tool",
        content=content,
        tool_call_id=tool_call_id
    )


# === Memory Entry Factories ===

def create_memory_entry(
    session_id: str = "test_session",
    role: str = "user",
    content: str = "test content",
    metadata: dict | None = None
) -> MemoryEntry:
    """
    Create a test MemoryEntry.

    Args:
        session_id: Session identifier
        role: Entry role
        content: Entry content
        metadata: Optional metadata

    Returns:
        MemoryEntry instance
    """
    return MemoryEntry.create(
        session_id=session_id,
        role=role,
        content=content,
        metadata=metadata
    )


def create_long_term_entry(
    content: str = "Test fact",
    category: str = "fact",
    keywords: list[str] | None = None,
    importance: float = 0.5,
    source_session: str = "test_session"
) -> LongTermEntry:
    """
    Create a test LongTermEntry.

    Args:
        content: Memory content
        category: Memory category (fact, preference, experience, task, note)
        keywords: Search keywords
        importance: Importance score (0-1)
        source_session: Source session ID

    Returns:
        LongTermEntry instance
    """
    return LongTermEntry.create(
        content=content,
        category=category,
        keywords=keywords or ["test"],
        source_session=source_session,
        importance=importance
    )


# === Config Factories ===

def create_config(**overrides) -> Config:
    """
    Create a test Config with default values.

    Args:
        **overrides: Fields to override in the config

    Returns:
        Config instance
    """
    defaults = {
        "llm": LLMConfig(),
        "agent": AgentConfig(),
        "memory": MemoryConfig(),
        "tools": ToolConfig(),
        "plugins": PluginsConfig(),
        "skills": SkillsConfig(),
        "logging": LoggingConfig(),
    }
    defaults.update(overrides)
    return Config(**defaults)


def create_llm_config(**overrides) -> LLMConfig:
    """Create a test LLMConfig."""
    defaults = {
        "provider": "ollama",
        "model": "test-model",
        "base_url": "http://localhost:11434",
    }
    defaults.update(overrides)
    return LLMConfig(**defaults)


def create_memory_config(**overrides) -> MemoryConfig:
    """Create a test MemoryConfig."""
    defaults = {
        "max_messages": 50,
        "type": "short_term",
    }
    defaults.update(overrides)
    return MemoryConfig(**defaults)


# === Tool Factories ===

def create_mock_tool(
    name: str = "mock_tool",
    description: str = "A mock tool for testing",
    output: str = "mock result",
    should_fail: bool = False
) -> BaseTool:
    """
    Create a mock tool for testing.

    Args:
        name: Tool name
        description: Tool description
        output: Output to return on execution
        should_fail: If True, return error result

    Returns:
        Mock tool instance
    """
    class MockTool(BaseTool):
        def __init__(self):
            self.name = name
            self.description = description
            self._output = output
            self._should_fail = should_fail

        @property
        def parameters_schema(self) -> dict:
            return {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                },
                "required": ["input"]
            }

        def execute(self, input: str = "", **kwargs) -> ToolResult:
            if self._should_fail:
                return ToolResult(success=False, output="", error="Mock error")
            return ToolResult(success=True, output=self._output)

    return MockTool()


def create_tool_registry_with_tools(*tool_names: str) -> "ToolRegistry":
    """
    Create a ToolRegistry with mock tools.

    Args:
        *tool_names: Names of mock tools to create

    Returns:
        ToolRegistry with mock tools
    """
    from nano_agent.tools import ToolRegistry

    registry = ToolRegistry()
    for name in tool_names:
        registry.register(create_mock_tool(name=name, output=f"{name} result"))
    return registry
