"""
Tests for tool system.
"""

import pytest
import tempfile
import os
from pathlib import Path

from nano_agent.tools.base import BaseTool, ToolResult, ToolRegistry
from nano_agent.tools.python_executor import PythonExecutorTool
from nano_agent.tools.file_ops import FileReadTool, FileWriteTool, FileSearchTool
from nano_agent.tools.shell import ShellTool
from nano_agent.tools.builtin import register_builtin_tools, BUILTIN_TOOLS


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = ToolResult(success=True, output="Done")
        assert result.success is True
        assert result.output == "Done"
        assert result.error is None

    def test_error_result(self):
        """Test error result."""
        result = ToolResult(success=False, output="", error="Failed")
        assert result.success is False
        assert result.output == ""
        assert result.error == "Failed"

    def test_result_with_metadata(self):
        """Test result with metadata."""
        result = ToolResult(
            success=True,
            output="Done",
            metadata={"name_type": "user_name", "name_value": "天宇"}
        )
        assert result.metadata is not None
        assert result.metadata["name_type"] == "user_name"
        assert result.metadata["name_value"] == "天宇"

    def test_result_default_metadata_is_none(self):
        """Test that metadata defaults to None."""
        result = ToolResult(success=True, output="Done")
        assert result.metadata is None
        assert result.error is None


class TestToolRegistry:
    """Test ToolRegistry class."""

    def test_register_and_get(self):
        """Test registering and retrieving tools."""
        registry = ToolRegistry()
        tool = PythonExecutorTool()
        registry.register(tool)
        assert "python_execute" in registry
        assert registry.get("python_execute") is tool

    def test_register_function(self):
        """Test registering a function as a tool."""
        registry = ToolRegistry()

        def greet(name: str) -> str:
            return f"Hello, {name}!"

        registry.register_function(
            name="greet",
            description="Greet someone",
            parameters_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"]
            },
            func=greet
        )

        result = registry.get("greet").execute(name="World")
        assert result.success is True
        assert result.output == "Hello, World!"

    def test_get_all_schemas(self):
        """Test getting all tool schemas."""
        registry = ToolRegistry()
        register_builtin_tools(registry)
        schemas = registry.get_all_schemas()
        assert len(schemas) == len(BUILTIN_TOOLS)
        for schema in schemas:
            assert schema["type"] == "function"
            assert "name" in schema["function"]

    def test_list_tools(self):
        """Test listing all tools."""
        registry = ToolRegistry()
        register_builtin_tools(registry)
        tools = registry.list_tools()
        assert set(tools) == set(BUILTIN_TOOLS)


class TestPythonExecutorTool:
    """Test PythonExecutorTool."""

    def test_simple_calculation(self):
        """Test simple calculation."""
        tool = PythonExecutorTool()
        result = tool.execute(code="print(1 + 1)")
        assert result.success is True
        assert result.output == "2"

    def test_multi_line_code(self):
        """Test multi-line code execution."""
        tool = PythonExecutorTool()
        result = tool.execute(code="""
x = 10
y = 20
print(x * y)
""")
        assert result.success is True
        assert result.output == "200"

    def test_error_handling(self):
        """Test error handling."""
        tool = PythonExecutorTool()
        result = tool.execute(code="raise ValueError('test error')")
        assert result.success is False
        assert "test error" in result.error

    def test_timeout(self):
        """Test timeout handling."""
        tool = PythonExecutorTool()
        result = tool.execute(code="import time; time.sleep(60)", timeout=1)
        assert result.success is False
        assert "timed out" in result.error.lower()

    def test_to_ollama_tool(self):
        """Test Ollama tool format."""
        tool = PythonExecutorTool()
        schema = tool.to_ollama_tool()
        assert schema["function"]["name"] == "python_execute"
        assert "code" in schema["function"]["parameters"]["properties"]


class TestMemorizeToolNameDetection:
    """Test MemorizeTool name detection feature."""

    def test_explicit_agent_name_parameter(self):
        """Test using explicit name_type and name_value parameters for agent name."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            # Explicit parameters (preferred way)
            result = tool.execute(
                content="我的名字是奥特曼",
                name_type="agent_name",
                name_value="奥特曼"
            )

            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["name_type"] == "agent_name"
            assert result.metadata["name_value"] == "奥特曼"

    def test_explicit_user_name_parameter(self):
        """Test using explicit name_type and name_value parameters for user name."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            # Explicit parameters (preferred way)
            result = tool.execute(
                content="用户的名字是天宇",
                name_type="user_name",
                name_value="天宇"
            )

            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["name_type"] == "user_name"
            assert result.metadata["name_value"] == "天宇"

    def test_fallback_agent_name_my_name_is(self):
        """Test fallback regex detection for agent name from '我的名字是...'."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            # No explicit parameters, fallback to regex
            result = tool.execute(content="我的名字是奥特曼", category="preference")

            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["name_type"] == "agent_name"
            assert result.metadata["name_value"] == "奥特曼"

    def test_fallback_agent_name_i_am_called(self):
        """Test fallback regex detection for agent name from '我叫...'."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            # No explicit parameters, fallback to regex
            result = tool.execute(content="我叫Nomi", category="preference")

            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["name_type"] == "agent_name"
            assert result.metadata["name_value"] == "Nomi"

    def test_fallback_user_name_explicit(self):
        """Test fallback regex detection for user name from '用户的名字是...'."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            # No explicit parameters, fallback to regex
            result = tool.execute(content="用户的名字是天宇", category="preference")

            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["name_type"] == "user_name"
            assert result.metadata["name_value"] == "天宇"

    def test_detect_agent_name(self):
        """Test detecting agent name from 'Agent的名字是...'."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            result = tool.execute(content="Agent的名字是Nano", category="preference")

            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["name_type"] == "agent_name"
            assert result.metadata["name_value"] == "Nano"

    def test_no_name_detection_for_general_content(self):
        """Test that general content doesn't trigger name detection."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            result = tool.execute(content="今天天气很好", category="fact")

            assert result.success is True
            # metadata should have entry_id but no name_type/name_value
            assert result.metadata is not None
            assert "entry_id" in result.metadata
            assert "name_type" not in result.metadata

    def test_name_extraction_stops_at_punctuation(self):
        """Test that name extraction stops at punctuation."""
        from nano_agent.tools.memory_tools import MemorizeTool
        from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            working_memory = PersistentMemory(storage=storage, session_id="test")
            long_term_memory = LongTermMemory(storage_path=tmpdir)
            memory = HybridMemory(working_memory, long_term_memory)

            tool = MemorizeTool(memory=memory)
            # Test that name extraction stops at comma
            result = tool.execute(content="用户的名字是Nomi，用户王五给我起的名字", category="preference")

            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["name_type"] == "user_name"
            assert result.metadata["name_value"] == "Nomi"
            # Should NOT include "，用户王五给我起的名字"


class TestFileReadTool:
    """Test FileReadTool."""

    def test_read_file(self):
        """Test reading a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\n")
            f.flush()
            path = f.name

        try:
            tool = FileReadTool()
            result = tool.execute(file_path=path)
            assert result.success is True
            assert "Line 1" in result.output
            assert "Line 2" in result.output
        finally:
            os.unlink(path)

    def test_read_with_line_range(self):
        """Test reading with line range."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("A\nB\nC\nD\nE\n")
            f.flush()
            path = f.name

        try:
            tool = FileReadTool()
            result = tool.execute(file_path=path, start_line=2, num_lines=2)
            assert result.success is True
            assert "B" in result.output
            assert "C" in result.output
            assert "D" not in result.output
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        """Test file not found error."""
        tool = FileReadTool()
        result = tool.execute(file_path="/nonexistent/file.txt")
        assert result.success is False
        assert "does not exist" in result.error.lower()


class TestFileWriteTool:
    """Test FileWriteTool."""

    def test_write_file(self):
        """Test writing a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            tool = FileWriteTool()
            result = tool.execute(file_path=path, content="Hello World")
            assert result.success is True

            # Verify content
            with open(path) as f:
                assert f.read() == "Hello World"

    def test_append_file(self):
        """Test appending to a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")

            # Write initial content
            tool = FileWriteTool()
            tool.execute(file_path=path, content="Line 1\n")

            # Append more content
            result = tool.execute(file_path=path, content="Line 2\n", mode="append")
            assert result.success is True

            with open(path) as f:
                content = f.read()
                assert "Line 1" in content
                assert "Line 2" in content


class TestFileSearchTool:
    """Test FileSearchTool."""

    def test_search_files(self):
        """Test searching for files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            Path(tmpdir, "test1.txt").touch()
            Path(tmpdir, "test2.txt").touch()
            Path(tmpdir, "other.py").touch()

            tool = FileSearchTool()
            result = tool.execute(directory=tmpdir, pattern="*.txt")
            assert result.success is True
            assert "test1.txt" in result.output
            assert "test2.txt" in result.output
            assert "other.py" not in result.output


class TestShellTool:
    """Test ShellTool."""

    def test_simple_command(self):
        """Test simple shell command."""
        tool = ShellTool()
        result = tool.execute(command="echo 'Hello'")
        assert result.success is True
        assert "Hello" in result.output

    def test_command_with_error(self):
        """Test command that returns error."""
        tool = ShellTool()
        # Use a command that will fail
        result = tool.execute(command="ls /nonexistent_directory_12345")
        assert result.success is False

    def test_timeout(self):
        """Test command timeout."""
        tool = ShellTool()
        result = tool.execute(command="sleep 60", timeout=1)
        assert result.success is False
        assert "timed out" in result.error.lower()