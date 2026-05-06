"""
Tests for unified undo mechanism.
"""

import tempfile
import os
from pathlib import Path

import pytest

from nano_agent.tools.base import BaseTool, ToolResult
from nano_agent.tools.memory_tools import MemorizeTool
from nano_agent.tools.file_ops import FileWriteTool
from nano_agent.agent.undo import UndoStack, UndoRecord
from nano_agent.memory import HybridMemory, ShortTermMemory, LongTermMemory


class TestUndoStack:
    """Tests for UndoStack class."""

    def test_start_round(self):
        """Test starting a new round."""
        stack = UndoStack()
        stack.start_round("round_1")
        assert stack._current_round == "round_1"

    def test_push_record(self):
        """Test pushing a record to the stack."""
        stack = UndoStack()
        stack.start_round("round_1")
        stack.push("memorize", {"entry_id": "ltm_abc123"})

        assert stack.count() == 1
        assert stack.count_round() == 1

    def test_get_round_records(self):
        """Test getting records for current round."""
        stack = UndoStack()
        stack.start_round("round_1")
        stack.push("memorize", {"entry_id": "ltm_abc123"})
        stack.push("file_write", {"path": "/tmp/test.txt"})

        records = stack.get_round_records()
        assert len(records) == 2
        assert records[0].tool_name == "memorize"
        assert records[1].tool_name == "file_write"

    def test_multiple_rounds(self):
        """Test that records are separated by round."""
        stack = UndoStack()
        stack.start_round("round_1")
        stack.push("memorize", {"entry_id": "ltm_abc123"})
        stack.start_round("round_2")
        stack.push("file_write", {"path": "/tmp/test.txt"})

        # Round 1 should still have its record
        stack.start_round("round_1")
        records = stack.get_round_records()
        assert len(records) == 1
        assert records[0].tool_name == "memorize"

    def test_clear_round(self):
        """Test clearing records for current round."""
        stack = UndoStack()
        stack.start_round("round_1")
        stack.push("memorize", {"entry_id": "ltm_abc123"})
        stack.clear_round()

        assert stack.count_round() == 0
        assert stack.count() == 0

    def test_remove_record(self):
        """Test removing a specific record."""
        stack = UndoStack()
        stack.start_round("round_1")
        stack.push("memorize", {"entry_id": "ltm_abc123"})
        stack.push("file_write", {"path": "/tmp/test.txt"})

        records = stack.get_round_records()
        stack.remove_record(records[0])

        assert stack.count() == 1
        assert stack.get_round_records()[0].tool_name == "file_write"

    def test_has_round_records(self):
        """Test checking if round has records."""
        stack = UndoStack()
        stack.start_round("round_1")
        assert not stack.has_round_records()

        stack.push("memorize", {"entry_id": "ltm_abc123"})
        assert stack.has_round_records()


class TestMemorizeToolUndo:
    """Tests for MemorizeTool undo functionality."""

    def test_supports_undo(self):
        """Test that MemorizeTool supports undo."""
        tool = MemorizeTool()
        assert tool.supports_undo is True

    def test_undo_with_memory(self):
        """Test undo operation with memory context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            long_term = LongTermMemory(storage_path=tmpdir)
            working_memory = ShortTermMemory()
            memory = HybridMemory(working_memory, long_term)

            tool = MemorizeTool(memory=memory)

            # Execute memorize
            result = tool.execute(content="Test memory", category="fact")
            assert result.success is True
            assert result.undo_data is not None
            entry_id = result.undo_data["entry_id"]

            # Verify memory was stored
            assert long_term.count() == 1

            # Undo the operation
            context = {"memory": memory}
            undo_success = tool.undo(result.undo_data, context)
            assert undo_success is True

            # Verify memory was deleted
            assert long_term.count() == 0

    def test_undo_without_memory_context(self):
        """Test undo fails without memory context."""
        tool = MemorizeTool()
        undo_success = tool.undo({"entry_id": "ltm_abc123"}, {})
        assert undo_success is False


class TestFileWriteToolUndo:
    """Tests for FileWriteTool undo functionality."""

    def test_supports_undo(self):
        """Test that FileWriteTool supports undo."""
        tool = FileWriteTool()
        assert tool.supports_undo is True

    def test_undo_new_file(self):
        """Test undo for newly created file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriteTool()
            file_path = os.path.join(tmpdir, "test.txt")

            # Write new file
            result = tool.execute(file_path=file_path, content="Hello World")
            assert result.success is True
            assert result.undo_data is not None
            assert result.undo_data["file_existed"] is False

            # Verify file was created
            assert os.path.exists(file_path)

            # Undo - should delete the file
            undo_success = tool.undo(result.undo_data, {})
            assert undo_success is True

            # Verify file was deleted
            assert not os.path.exists(file_path)

    def test_undo_overwrite_file(self):
        """Test undo for overwriting existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriteTool()
            file_path = os.path.join(tmpdir, "test.txt")

            # Create initial file
            with open(file_path, "w") as f:
                f.write("Original content")

            # Overwrite file
            result = tool.execute(file_path=file_path, content="New content")
            assert result.success is True
            assert result.undo_data["file_existed"] is True
            assert result.undo_data["previous_content"] == "Original content"

            # Undo - should restore original content
            undo_success = tool.undo(result.undo_data, {})
            assert undo_success is True

            # Verify content was restored
            with open(file_path, "r") as f:
                content = f.read()
            assert content == "Original content"

    def test_append_mode_no_undo_data(self):
        """Test that append mode doesn't provide undo data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileWriteTool()
            file_path = os.path.join(tmpdir, "test.txt")

            # Append to file
            result = tool.execute(file_path=file_path, content="Hello", mode="append")
            assert result.success is True
            assert result.undo_data is None  # Append mode doesn't support undo


class TestToolResultUndoData:
    """Tests for ToolResult undo_data field."""

    def test_tool_result_with_undo_data(self):
        """Test ToolResult can hold undo_data."""
        result = ToolResult(
            success=True,
            output="Test output",
            undo_data={"key": "value"}
        )
        assert result.undo_data == {"key": "value"}

    def test_tool_result_without_undo_data(self):
        """Test ToolResult without undo_data."""
        result = ToolResult(success=True, output="Test output")
        assert result.undo_data is None


class TestBaseToolUndo:
    """Tests for BaseTool undo interface."""

    def test_default_supports_undo(self):
        """Test that default tools don't support undo."""

        class SimpleTool(BaseTool):
            name = "simple"
            description = "A simple tool"

            @property
            def parameters_schema(self):
                return {"type": "object"}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="done")

        tool = SimpleTool()
        assert tool.supports_undo is False

    def test_default_undo_returns_false(self):
        """Test that default undo returns False."""

        class SimpleTool(BaseTool):
            name = "simple"
            description = "A simple tool"

            @property
            def parameters_schema(self):
                return {"type": "object"}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="done")

        tool = SimpleTool()
        assert tool.undo({}, {}) is False