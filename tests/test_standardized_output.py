"""Tests for standardized tool output (v0.7.15)."""

import pytest
from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat
from nano_agent.config.schema import StandardizedOutputConfig


class TestStandardToolOutput:
    """Test StandardToolOutput dataclass and formatting."""

    def test_format_structure_compact(self):
        sto = StandardToolOutput(
            format=OutputFormat.STRUCTURE,
            data={"imports": ["os", "sys"], "classes": 2},
            summary="Module structure",
        )
        result = sto.to_llm_message(detailed=False)
        assert "os" in result
        assert "sys" in result
        assert "2" in result

    def test_format_list_compact(self):
        sto = StandardToolOutput(
            format=OutputFormat.LIST,
            data={"items": [{"path": "a.py"}, {"path": "b.py"}], "total": 2},
            summary="2 files",
        )
        result = sto.to_llm_message(detailed=False)
        assert "a.py" in result
        assert "b.py" in result
        assert "Total: 2" in result

    def test_format_list_empty(self):
        sto = StandardToolOutput(
            format=OutputFormat.LIST,
            data={"items": [], "total": 0},
        )
        result = sto.to_llm_message(detailed=False)
        assert "No results" in result

    def test_format_list_truncation(self):
        items = [{"path": f"file_{i}.py"} for i in range(20)]
        sto = StandardToolOutput(
            format=OutputFormat.LIST,
            data={"items": items, "total": 20, "max_display": 10},
        )
        result = sto.to_llm_message(detailed=False)
        assert "+10 more" in result

    def test_format_status_success(self):
        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"status": "success", "exit_code": 0, "stdout": "hello", "stderr": ""},
        )
        result = sto.to_llm_message(detailed=False)
        assert "[ok]" in result
        assert "hello" in result

    def test_format_status_error(self):
        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"status": "error", "exit_code": 1, "stdout": "", "stderr": "fail"},
        )
        result = sto.to_llm_message(detailed=False)
        assert "[error:1]" in result
        assert "fail" in result

    def test_format_content_compact(self):
        sto = StandardToolOutput(
            format=OutputFormat.CONTENT,
            data={"source": "test.py", "lines_total": 100, "lines_shown": 10, "start_line": 1, "content": "import os"},
            summary="test.py: 100 lines",
        )
        result = sto.to_llm_message(detailed=False)
        assert "test.py" in result
        assert "100L" in result
        assert "import os" in result

    def test_format_content_detailed(self):
        sto = StandardToolOutput(
            format=OutputFormat.CONTENT,
            data={"source": "test.py", "lines_total": 100, "lines_shown": 10, "start_line": 1, "content": "import os"},
            summary="test.py: 100 lines",
        )
        result = sto.to_llm_message(detailed=True)
        assert "Source: test.py" in result
        assert "Lines: 100" in result

    def test_format_error(self):
        sto = StandardToolOutput(
            format=OutputFormat.ERROR,
            data={"error_type": "FileNotFound", "message": "No such file"},
        )
        result = sto.to_llm_message(detailed=False)
        assert "[FileNotFound]" in result
        assert "No such file" in result

    def test_to_llm_message_all_formats(self):
        for fmt in OutputFormat:
            sto = StandardToolOutput(format=fmt, data={})
            result = sto.to_llm_message()
            assert isinstance(result, str)


class TestStandardizedOutputConfig:
    """Test StandardizedOutputConfig dataclass."""

    def test_defaults(self):
        config = StandardizedOutputConfig()
        assert config.enabled is True
        assert config.detailed is False

    def test_custom(self):
        config = StandardizedOutputConfig(enabled=False, detailed=True)
        assert config.enabled is False
        assert config.detailed is True

    def test_default_enabled(self):
        config = StandardizedOutputConfig()
        assert config.enabled is True


class TestFileReadStandardOutput:
    """Test FileReadTool produces StandardToolOutput in metadata."""

    def test_metadata_has_standard_output(self):
        from nano_agent.tools.builtin.file_ops import FileReadTool
        import tempfile, os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\nimport sys\n")
            f.flush()
            tool = FileReadTool()
            result = tool.execute(file_path=f.name)
            os.unlink(f.name)

        assert result.success
        assert result.metadata is not None
        assert "standard_output" in result.metadata

    def test_format_is_content(self):
        from nano_agent.tools.builtin.file_ops import FileReadTool
        import tempfile, os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("import os\n")
            f.flush()
            tool = FileReadTool()
            result = tool.execute(file_path=f.name)
            os.unlink(f.name)

        sto = result.metadata["standard_output"]
        assert sto.format == OutputFormat.CONTENT
        assert "source" in sto.data

    def test_summary_contains_line_count(self):
        from nano_agent.tools.builtin.file_ops import FileReadTool
        import tempfile, os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            f.flush()
            tool = FileReadTool()
            result = tool.execute(file_path=f.name)
            os.unlink(f.name)

        sto = result.metadata["standard_output"]
        assert "3 lines" in sto.summary


class TestFileSearchStandardOutput:
    """Test FileSearchTool produces StandardToolOutput in metadata."""

    def test_metadata_has_standard_output(self):
        from nano_agent.tools.builtin.file_ops import FileSearchTool
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.py", "b.py"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("# test\n")
            tool = FileSearchTool()
            result = tool.execute(pattern="*.py", directory=tmpdir)

        assert result.success
        assert "standard_output" in result.metadata

    def test_format_is_list(self):
        from nano_agent.tools.builtin.file_ops import FileSearchTool
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.py"), "w") as f:
                f.write("# test\n")
            tool = FileSearchTool()
            result = tool.execute(pattern="*.py", directory=tmpdir)

        sto = result.metadata["standard_output"]
        assert sto.format == OutputFormat.LIST

    def test_total_count(self):
        from nano_agent.tools.builtin.file_ops import FileSearchTool
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.py", "b.py", "c.py"]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write("# test\n")
            tool = FileSearchTool()
            result = tool.execute(pattern="*.py", directory=tmpdir)

        sto = result.metadata["standard_output"]
        assert sto.data["total"] >= 3


class TestShellStandardOutput:
    """Test ShellTool produces StandardToolOutput in metadata."""

    def test_metadata_has_standard_output(self):
        from nano_agent.tools.builtin.shell import ShellTool
        tool = ShellTool()
        result = tool.execute(command="echo hello")
        assert result.success
        assert "standard_output" in result.metadata

    def test_format_is_status(self):
        from nano_agent.tools.builtin.shell import ShellTool
        tool = ShellTool()
        result = tool.execute(command="echo hello")
        sto = result.metadata["standard_output"]
        assert sto.format == OutputFormat.STATUS

    def test_exit_code(self):
        from nano_agent.tools.builtin.shell import ShellTool
        tool = ShellTool()
        result = tool.execute(command="echo hello")
        sto = result.metadata["standard_output"]
        assert sto.data["exit_code"] == 0


class TestPythonExecutorStandardOutput:
    """Test PythonExecutorTool produces StandardToolOutput in metadata."""

    def test_metadata_has_standard_output(self):
        from nano_agent.tools.builtin.python_executor import PythonExecutorTool
        tool = PythonExecutorTool()
        result = tool.execute(code="print('hello')")
        assert result.success
        assert "standard_output" in result.metadata

    def test_format_is_status(self):
        from nano_agent.tools.builtin.python_executor import PythonExecutorTool
        tool = PythonExecutorTool()
        result = tool.execute(code="print('hello')")
        sto = result.metadata["standard_output"]
        assert sto.format == OutputFormat.STATUS
