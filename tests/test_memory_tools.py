"""
Tests for memory tools.
"""

import pytest
import tempfile
from pathlib import Path

from nano_agent.tools.memory_tools import MemorizeTool, RecallTool, ListMemoriesTool, ForgetTool
from nano_agent.tools.base import ToolResult
from nano_agent.memory import HybridMemory, FileStorage, LongTermMemory, ShortTermMemory


class TestMemorizeTool:
    """Tests for MemorizeTool."""

    def test_memorize_tool_properties(self):
        """Test MemorizeTool properties."""
        tool = MemorizeTool()
        assert tool.name == "memorize"
        assert "long-term memory" in tool.description.lower()
        assert "content" in tool.parameters_schema["properties"]
        assert "category" in tool.parameters_schema["properties"]
        assert "importance" in tool.parameters_schema["properties"]

    def test_memorize_without_memory(self):
        """Test memorize without memory configured."""
        tool = MemorizeTool()
        result = tool.execute(content="test content")

        assert result.success is False
        assert "not configured" in result.error.lower()

    def test_memorize_with_short_term_memory(self):
        """Test memorize with short-term memory (no long-term support)."""
        memory = ShortTermMemory()
        tool = MemorizeTool(memory=memory)
        result = tool.execute(content="test content")

        assert result.success is False
        assert "not available" in result.error.lower()

    def test_memorize_with_hybrid_memory(self):
        """Test memorize with hybrid memory."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = MemorizeTool(memory=memory)
            result = tool.execute(
                content="test fact to remember",
                category="fact",
                importance=0.8
            )

            assert result.success is True
            assert "successfully stored" in result.output.lower()

    def test_memorize_set_memory(self):
        """Test set_memory method."""
        tool = MemorizeTool()
        assert tool._memory is None

        tool.set_memory("mock_memory")
        assert tool._memory == "mock_memory"


class TestRecallTool:
    """Tests for RecallTool."""

    def test_recall_tool_properties(self):
        """Test RecallTool properties."""
        tool = RecallTool()
        assert tool.name == "recall"
        assert "search" in tool.description.lower()
        assert "query" in tool.parameters_schema["properties"]

    def test_recall_without_memory(self):
        """Test recall without memory configured."""
        tool = RecallTool()
        result = tool.execute(query="test")

        assert result.success is False
        assert "not configured" in result.error.lower()

    def test_recall_with_hybrid_memory(self):
        """Test recall with hybrid memory."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            # Add a memory first
            long_term.add(
                content="Python is a programming language",
                keywords=["python", "programming"],
                category="fact"
            )

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = RecallTool(memory=memory)
            result = tool.execute(query="python")

            assert result.success is True


class TestListMemoriesTool:
    """Tests for ListMemoriesTool."""

    def test_list_memories_tool_properties(self):
        """Test ListMemoriesTool properties."""
        tool = ListMemoriesTool()
        assert tool.name == "list_memories"
        assert "list" in tool.description.lower()

    def test_list_memories_without_memory(self):
        """Test list_memories without memory configured."""
        tool = ListMemoriesTool()
        result = tool.execute()

        assert result.success is False
        assert "not configured" in result.error.lower()

    def test_list_memories_with_hybrid_memory(self):
        """Test list_memories with hybrid memory."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            # Add some memories
            long_term.add(content="Memory 1", keywords=["test"])
            long_term.add(content="Memory 2", keywords=["test"])

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = ListMemoriesTool(memory=memory)
            result = tool.execute()

            assert result.success is True


class TestForgetTableTool:
    """Tests for ForgetTool."""

    def test_forget_tool_properties(self):
        """Test ForgetTool properties."""
        tool = ForgetTool()
        assert tool.name == "forget"
        assert "delete" in tool.description.lower() or "remove" in tool.description.lower()
        assert "memory_id" in tool.parameters_schema["properties"]

    def test_forget_without_memory(self):
        """Test forget without memory configured."""
        tool = ForgetTool()
        result = tool.execute(memory_id="test-id")

        assert result.success is False
        assert "not configured" in result.error.lower()

    def test_forget_with_hybrid_memory(self):
        """Test forget with hybrid memory."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            # Add a memory and get its ID
            memory_id, is_new = long_term.add(
                content="This will be forgotten",
                keywords=["test"]
            )

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = ForgetTool(memory=memory)
            result = tool.execute(memory_id=memory_id)

            assert result.success is True


class TestNameExtraction:
    """Tests for name extraction regex patterns in MemorizeTool."""

    def test_agent_name_my_name(self):
        """Test extracting agent name from '我的名字是X'."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = MemorizeTool(memory=memory)
            result = tool.execute(content="我的名字是天宇")

            assert result.success is True
            assert result.metadata["name_type"] == "agent_name"
            assert result.metadata["name_value"] == "天宇"

    def test_agent_name_i_call(self):
        """Test extracting agent name from '我叫X'."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = MemorizeTool(memory=memory)
            result = tool.execute(content="我叫小明")

            assert result.success is True
            assert result.metadata["name_type"] == "agent_name"
            assert result.metadata["name_value"] == "小明"

    def test_user_name_with_comma_not_greedy(self):
        """Test that regex is not greedy - stops at comma."""
        # This was the bug: "用户的名字是Nomi，用户王五给我起的名字"
        # should extract "Nomi", not "Nomi，用户王五给我起的名字"
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = MemorizeTool(memory=memory)
            result = tool.execute(content="用户的名字是Nomi，用户王五给我起的名字")

            assert result.success is True
            assert result.metadata["name_type"] == "user_name"
            assert result.metadata["name_value"] == "Nomi"

    def test_user_name_user_call(self):
        """Test extracting user name from '用户叫X'."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = MemorizeTool(memory=memory)
            result = tool.execute(content="用户叫奥特曼")

            assert result.success is True
            assert result.metadata["name_type"] == "user_name"
            assert result.metadata["name_value"] == "奥特曼"

    def test_agent_name_your_name(self):
        """Test extracting agent name from '你的名字是X'."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = MemorizeTool(memory=memory)
            result = tool.execute(content="你的名字是牙签")

            assert result.success is True
            assert result.metadata["name_type"] == "agent_name"
            assert result.metadata["name_value"] == "牙签"

    def test_explicit_name_parameters(self):
        """Test using explicit name_type and name_value parameters."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            tool = MemorizeTool(memory=memory)
            result = tool.execute(
                content="用户的名字是天宇",
                name_type="user_name",
                name_value="天宇"
            )

            assert result.success is True
            assert result.metadata["name_type"] == "user_name"
            assert result.metadata["name_value"] == "天宇"


class TestMemoryToolsIntegration:
    """Integration tests for memory tools."""

    def test_memorize_and_recall_flow(self):
        """Test the memorize and recall flow."""
        with tempfile.TemporaryDirectory() as d:
            storage = FileStorage(base_dir=d)
            working_memory = ShortTermMemory()
            long_term = LongTermMemory(storage_path=d)

            memory = HybridMemory(
                working_memory=working_memory,
                long_term_memory=long_term
            )

            # Memorize
            memorize_tool = MemorizeTool(memory=memory)
            result = memorize_tool.execute(
                content="User prefers dark mode",
                category="preference",
                importance=0.9
            )
            assert result.success is True

            # Recall
            recall_tool = RecallTool(memory=memory)
            result = recall_tool.execute(query="user preference")
            assert result.success is True
