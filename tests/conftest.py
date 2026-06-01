"""
Shared pytest fixtures for NanoAgent tests.

This module provides reusable fixtures to reduce code duplication
and standardize test data creation across all test files.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from nano_agent.memory.storage import FileStorage, SQLiteStorage
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.memory.persistent import PersistentMemory
from nano_agent.memory.long_term import LongTermMemory
from nano_agent.memory.hybrid import HybridMemory
from nano_agent.tools import ToolRegistry
from nano_agent.tools.base import BaseTool, ToolResult
from nano_agent.llm.base import LLMUsage

# === Directory and Storage Fixtures ===


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def temp_storage(temp_dir):
    """Create a temporary FileStorage for testing."""
    return FileStorage(base_dir=str(temp_dir / "memory"))


@pytest.fixture
def temp_sqlite_storage(temp_dir):
    """Create a temporary SQLiteStorage for testing."""
    return SQLiteStorage(db_path=str(temp_dir / "test.db"))


# === Memory Fixtures ===


@pytest.fixture
def short_term_memory():
    """Create a ShortTermMemory instance."""
    return ShortTermMemory(max_messages=50)


@pytest.fixture
def persistent_memory(temp_storage):
    """Create a PersistentMemory instance with temporary storage."""
    return PersistentMemory(
        storage=temp_storage, session_id="test_session", system_prompt="Test prompt"
    )


@pytest.fixture
def long_term_memory(temp_dir):
    """Create a LongTermMemory instance with temporary storage."""
    return LongTermMemory(storage_path=str(temp_dir / "long_term"))


@pytest.fixture
def hybrid_memory(persistent_memory, long_term_memory):
    """Create a HybridMemory instance."""
    return HybridMemory(
        working_memory=persistent_memory,
        long_term_memory=long_term_memory,
        session_id="test_session",
    )


# === Mock Fixtures ===


@pytest.fixture
def mock_llm():
    """Create a mock LLM client."""
    llm = Mock()
    llm.chat.return_value = ("Mock response", [], LLMUsage())
    llm.chat_stream.return_value = iter(["Mock ", "stream ", "response"])
    llm.model = "mock-model"
    return llm


@pytest.fixture
def mock_tool():
    """Create a mock tool for testing."""
    return _create_mock_tool()


@pytest.fixture
def mock_tool_registry(mock_tool):
    """Create a tool registry with a mock tool."""
    registry = ToolRegistry()
    registry.register(mock_tool)
    return registry


# === Test Data Fixtures ===


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there!"},
    ]


@pytest.fixture
def sample_config_dict():
    """Create a sample configuration dictionary."""
    return {
        "llm": {
            "provider": "ollama",
            "model": "llama3",
            "base_url": "http://localhost:11434",
        },
        "agent": {
            "max_iterations": 10,
            "verbose": True,
        },
        "memory": {
            "max_messages": 50,
            "type": "short_term",
        },
    }


# === Helper Functions ===


def _create_mock_tool(name: str = "mock_tool", output: str = "mock result") -> BaseTool:
    """Create a mock tool instance."""

    class MockTool(BaseTool):
        def __init__(self, tool_name, tool_output):
            self.name = tool_name
            self.description = f"A mock tool: {tool_name}"
            self._output = tool_output

        @property
        def parameters_schema(self) -> dict:
            return {
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
            }

        def execute(self, input: str = "") -> ToolResult:
            return ToolResult(success=True, output=self._output)

    return MockTool(name, output)
