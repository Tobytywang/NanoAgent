"""
End-to-end tests for NanoAgent.

Tests complete user workflows:
- CLI interaction flow
- Session save/resume
- Full agent lifecycle
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from nano_agent.agent.react import ReActAgent
from nano_agent.agent.orchestrator import AgentOrchestrator
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.memory.persistent import PersistentMemory
from nano_agent.memory.hybrid import HybridMemory
from nano_agent.memory.long_term import LongTermMemory
from nano_agent.memory.storage.file_storage import FileStorage
from nano_agent.tools.base import BaseTool, ToolResult
from nano_agent.tools.registry import ToolRegistry
from nano_agent.config.schema import Config, LLMConfig, AgentConfig, MemoryConfig
from nano_agent.llm.base import LLMUsage
from nano_agent.llm.messages import ToolCall
from nano_agent.monitoring.tracker import MetricsTracker


@pytest.mark.e2e
class TestCLIEndToEnd:
    """End-to-end tests for CLI interaction flow."""

    @pytest.fixture
    def mock_config(self, temp_dir):
        """Create a mock configuration for testing."""
        config = Config()
        config.llm = LLMConfig(
            provider="ollama",
            model="test-model",
            base_url="http://localhost:11434",
        )
        config.agent = AgentConfig(
            max_iterations=5,
            verbose=True,
        )
        config.memory = MemoryConfig(
            type="short_term",
            max_messages=100,
        )
        return config

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = Mock()
        client.chat.return_value = ("I understand your request.", [], LLMUsage())
        client.chat_stream.return_value = iter(["I ", "understand", "."])
        return client

    def test_create_agent_and_run(self, mock_llm_client, temp_dir):
        """Test creating an agent and running a simple query."""
        # Setup
        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm_client,
            memory=memory,
            tool_registry=registry,
            max_iterations=3,
        )

        orchestrator = AgentOrchestrator(agent=agent)

        # Execute
        result = orchestrator.run("Hello, agent!")

        # Verify
        assert result is not None
        assert result.response is not None
        assert result.success is True

    def test_agent_handles_empty_input(self, mock_llm_client):
        """Test that agent handles empty input gracefully."""
        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm_client,
            memory=memory,
            tool_registry=registry,
            max_iterations=1,
        )

        # Empty input should still work
        result = agent.run("")

        assert result is not None

    def test_agent_handles_special_characters(self, mock_llm_client):
        """Test that agent handles special characters in input."""
        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm_client,
            memory=memory,
            tool_registry=registry,
            max_iterations=1,
        )

        # Input with special characters
        special_input = "Hello! @#$%^&*() 你好世界 🎉"
        result = agent.run(special_input)

        assert result is not None

    def test_multiple_consecutive_runs(self, mock_llm_client):
        """Test running multiple queries in sequence."""
        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm_client,
            memory=memory,
            tool_registry=registry,
            max_iterations=2,
        )

        # Run multiple queries
        responses = []
        for query in ["First query", "Second query", "Third query"]:
            result = agent.run(query)
            responses.append(result.response)

        # All queries should have responses
        assert len(responses) == 3
        assert all(r is not None for r in responses)

        # Memory should contain all interactions
        messages = memory.get_context()
        user_messages = [m for m in messages if m["role"] == "user"]
        assert len(user_messages) == 3


@pytest.mark.e2e
class TestSessionEndToEnd:
    """End-to-end tests for session management."""

    def test_session_save_and_resume(self, temp_dir):
        """Test saving a session and resuming it later."""
        session_id = "test_session_001"

        # First session: create and save
        storage = FileStorage(base_dir=temp_dir)
        memory1 = PersistentMemory(
            storage=storage,
            session_id=session_id,
        )

        # Add some messages
        memory1.add_user_message("First message")
        memory1.add_assistant_message("First response")

        # Get session info before closing
        sessions_before = storage.list_sessions()
        assert session_id in sessions_before

        # Resume session
        memory2 = PersistentMemory(
            storage=storage,
            session_id=session_id,
        )

        # Verify messages were preserved
        messages = memory2.get_context()
        assert len(messages) >= 2

    def test_session_list(self, temp_dir):
        """Test listing available sessions."""
        storage = FileStorage(base_dir=temp_dir)

        # Create multiple sessions
        for i in range(3):
            session_id = f"session_{i}"
            memory = PersistentMemory(storage=storage, session_id=session_id)
            memory.add_user_message(f"Message for session {i}")

        # List sessions
        sessions = storage.list_sessions()
        assert len(sessions) >= 3

        # Each session should be a session ID string
        for session in sessions:
            assert isinstance(session, str)

    def test_session_delete(self, temp_dir):
        """Test deleting a session."""
        storage = FileStorage(base_dir=temp_dir)
        session_id = "to_be_deleted"

        # Create and save a session
        memory = PersistentMemory(storage=storage, session_id=session_id)
        memory.add_user_message("This will be deleted")

        # Verify session exists
        assert storage.session_exists(session_id)

        # Delete session
        storage.delete_session(session_id)

        # Verify session is gone
        assert not storage.session_exists(session_id)

    def test_hybrid_memory_persistence(self, temp_dir):
        """Test that hybrid memory persists long-term memories across sessions."""
        storage = FileStorage(base_dir=temp_dir)
        long_term = LongTermMemory(storage_path=temp_dir)

        # First session: memorize something
        memory1 = HybridMemory(
            working_memory=ShortTermMemory(),
            long_term_memory=long_term,
        )

        memory1.memorize(
            content="User prefers dark mode",
            category="preference",
            importance=0.9,
        )

        # Second session: recall the memory
        memory2 = HybridMemory(
            working_memory=ShortTermMemory(),
            long_term_memory=long_term,
        )

        results = memory2.recall("dark mode preference")
        assert len(results) >= 1
        assert any("dark mode" in r.content.lower() for r in results)


@pytest.mark.e2e
class TestAgentLifecycleEndToEnd:
    """End-to-end tests for complete agent lifecycle."""

    def test_agent_reset_clears_memory(self, mock_llm):
        """Test that resetting agent clears its memory."""
        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=1,
        )

        # Run some queries
        agent.run("Query 1")
        agent.run("Query 2")

        # Verify memory has content
        messages_before = memory.get_context()
        assert len(messages_before) > 0

        # Reset
        agent.reset()

        # Verify memory is cleared (system prompt remains)
        messages_after = memory.get_context()
        non_system_messages = [m for m in messages_after if m["role"] != "system"]
        assert len(non_system_messages) == 0

    def test_agent_with_tools_workflow(self, mock_llm):
        """Test complete workflow with tool execution."""

        # Create a simple tool
        class EchoTool(BaseTool):
            @property
            def name(self) -> str:
                return "echo"

            @property
            def description(self) -> str:
                return "Echoes the input"

            @property
            def parameters_schema(self) -> dict:
                return {"type": "object", "properties": {"message": {"type": "string"}}}

            def execute(self, message: str = "") -> ToolResult:
                return ToolResult(success=True, output=f"Echo: {message}")

        memory = ShortTermMemory()
        registry = ToolRegistry()
        registry.register(EchoTool())

        agent = ReActAgent(
            llm=mock_llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=3,
        )

        # Run with tool
        tool_call = ToolCall(id="call_1", name="echo", arguments={"message": "hello"})
        mock_llm.chat.side_effect = [
            ("", [tool_call], LLMUsage()),
            ("I echoed your message.", [], LLMUsage()),
        ]

        result = agent.run("Echo hello")

        assert result.success is True

    def test_agent_statistics_tracking(self, mock_llm):
        """Test that agent tracks execution statistics."""
        memory = ShortTermMemory()
        registry = ToolRegistry()
        tracker = MetricsTracker()

        agent = ReActAgent(
            llm=mock_llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=2,
            tracker=tracker,
        )

        orchestrator = AgentOrchestrator(agent=agent)

        # Run a query
        orchestrator.run("Test query")

        # Get statistics
        stats = orchestrator.get_stats()

        assert stats is not None
        assert stats.total_iterations >= 1


@pytest.mark.e2e
class TestToolMergeEndToEnd:
    """End-to-end tests for tool merging with actual tool execution."""

    def test_file_search_with_merged_patterns(self, temp_dir):
        """Test that file_search correctly handles merged patterns with pipe separator.

        This test verifies the fix for BUG-002: file_search tool must support
        pipe separator when tool_merger combines multiple search patterns.
        """
        from nano_agent.tools.builtin.file_ops import FileSearchTool

        # Create test files
        Path(temp_dir, "plan.md").touch()
        Path(temp_dir, "todo.txt").touch()
        Path(temp_dir, "other.py").touch()
        Path(temp_dir, "project_plan.md").touch()

        tool = FileSearchTool()

        # Test merged pattern (what tool_merger produces)
        result = tool.execute(directory=temp_dir, pattern="*plan*|*.txt")

        assert result.success is True
        assert "plan.md" in result.output
        assert "todo.txt" in result.output
        assert "project_plan.md" in result.output
        assert "other.py" not in result.output

    def test_tool_merger_produces_valid_file_search_pattern(self, temp_dir):
        """Test that ToolCallMerger produces patterns that file_search can execute.

        This is an integration test between tool_merger and file_search tool.
        """
        from nano_agent.agent.tool_merger import ToolCallMerger, ToolMergeConfig
        from nano_agent.tools.builtin.file_ops import FileSearchTool

        # Create test files
        Path(temp_dir, "plan.md").touch()
        Path(temp_dir, "todo.txt").touch()

        # Simulate what tool_merger does: merge multiple file_search calls
        merger = ToolCallMerger(ToolMergeConfig(enabled=True))
        calls = [
            ToolCall(
                id="1",
                name="file_search",
                arguments={"directory": temp_dir, "pattern": "*plan*"},
            ),
            ToolCall(
                id="2",
                name="file_search",
                arguments={"directory": temp_dir, "pattern": "*.txt"},
            ),
        ]

        merged = merger.analyze_and_merge(calls)
        assert len(merged) == 1  # Should merge into one call

        # Execute the merged call
        merged_pattern = merged[0].arguments["pattern"]
        tool = FileSearchTool()
        result = tool.execute(
            directory=merged[0].arguments["directory"], pattern=merged_pattern
        )

        # Verify the merged pattern works correctly
        assert result.success is True
        assert "plan.md" in result.output
        assert "todo.txt" in result.output
