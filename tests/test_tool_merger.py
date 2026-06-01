"""
Tests for tool call merging.
"""

import pytest
from nano_agent.agent.tool_merger import ToolCallMerger, ToolMergeConfig
from nano_agent.llm.messages import ToolCall


class TestToolCallMerger:
    """Tests for tool merging functionality."""

    def test_disabled_merging_returns_original(self):
        """When disabled, should return original calls."""
        config = ToolMergeConfig(enabled=False)
        merger = ToolCallMerger(config)
        calls = [ToolCall(id="1", name="file_search", arguments={"pattern": "*.py"})]
        result = merger.analyze_and_merge(calls)
        assert result == calls

    def test_single_call_returns_original(self):
        """Single call should not be modified."""
        merger = ToolCallMerger()
        calls = [ToolCall(id="1", name="file_search", arguments={"pattern": "*.py"})]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 1
        assert result[0].arguments["pattern"] == "*.py"

    def test_merge_file_search_patterns(self):
        """Should merge multiple file searches with same directory."""
        config = ToolMergeConfig(enabled=True)
        merger = ToolCallMerger(config)
        calls = [
            ToolCall(
                id="1",
                name="file_search",
                arguments={"directory": ".", "pattern": "*.py"},
            ),
            ToolCall(
                id="2",
                name="file_search",
                arguments={"directory": ".", "pattern": "*.ts"},
            ),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 1
        # Should combine patterns
        pattern = result[0].arguments["pattern"]
        assert "*.py" in pattern or "py" in pattern
        assert "*.ts" in pattern or "ts" in pattern

    def test_merge_multiple_extension_patterns(self):
        """Should use {ext1,ext2} syntax for multiple extensions."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(id="1", name="file_search", arguments={"pattern": "*.py"}),
            ToolCall(id="2", name="file_search", arguments={"pattern": "*.ts"}),
            ToolCall(id="3", name="file_search", arguments={"pattern": "*.js"}),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 1
        # Should use {py,ts,js} syntax
        pattern = result[0].arguments["pattern"]
        assert "{py,ts,js}" in pattern or "py" in pattern

    def test_dont_merge_different_directories(self):
        """Should not merge searches from different directories."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(
                id="1",
                name="file_search",
                arguments={"directory": "/a", "pattern": "*.py"},
            ),
            ToolCall(
                id="2",
                name="file_search",
                arguments={"directory": "/b", "pattern": "*.py"},
            ),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 2

    def test_merge_shell_commands(self):
        """Should merge safe shell commands."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(id="1", name="shell_execute", arguments={"command": "ls"}),
            ToolCall(id="2", name="shell_execute", arguments={"command": "pwd"}),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 1
        assert "&&" in result[0].arguments["command"]
        assert "ls" in result[0].arguments["command"]
        assert "pwd" in result[0].arguments["command"]

    def test_dont_merge_dangerous_commands(self):
        """Should not merge commands containing dangerous operations."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(id="1", name="shell_execute", arguments={"command": "ls"}),
            ToolCall(
                id="2", name="shell_execute", arguments={"command": "rm file.txt"}
            ),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 2

    def test_dont_merge_rm_command(self):
        """rm commands should not be merged."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(
                id="1", name="shell_execute", arguments={"command": "rm -rf /tmp/test"}
            ),
            ToolCall(id="2", name="shell_execute", arguments={"command": "ls"}),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 2

    def test_max_batch_size_limit(self):
        """Should respect max batch size."""
        config = ToolMergeConfig(max_batch_size=2)
        merger = ToolCallMerger(config)
        calls = [
            ToolCall(
                id=f"{i}", name="shell_execute", arguments={"command": f"echo {i}"}
            )
            for i in range(5)
        ]
        result = merger.analyze_and_merge(calls)
        # First 2 should be merged, remaining 3 should be separate
        assert len(result) == 4  # 1 merged + 3 remaining
        # First call should have merged commands
        assert "&&" in result[0].arguments["command"]

    def test_dont_merge_file_read(self):
        """file_read calls should not be merged."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(id="1", name="file_read", arguments={"path": "a.py"}),
            ToolCall(id="2", name="file_read", arguments={"path": "b.py"}),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 2

    def test_merge_tools_config(self):
        """Should only merge tools in merge_tools list."""
        config = ToolMergeConfig(merge_tools=["file_search"])
        merger = ToolCallMerger(config)
        calls = [
            ToolCall(id="1", name="file_search", arguments={"pattern": "*.py"}),
            ToolCall(id="2", name="file_search", arguments={"pattern": "*.ts"}),
            ToolCall(id="3", name="shell_execute", arguments={"command": "ls"}),
            ToolCall(id="4", name="shell_execute", arguments={"command": "pwd"}),
        ]
        result = merger.analyze_and_merge(calls)
        # file_search should be merged, shell_execute should not
        assert len(result) == 3  # 1 merged file_search + 2 shell_execute

    def test_complex_pattern_not_simple_extension(self):
        """Complex patterns should use pipe separator."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(id="1", name="file_search", arguments={"pattern": "test_*.py"}),
            ToolCall(id="2", name="file_search", arguments={"pattern": "*.ts"}),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 1
        # Should use pipe separator for complex patterns
        pattern = result[0].arguments["pattern"]
        assert "|" in pattern

    def test_empty_calls_returns_empty(self):
        """Empty calls list should return empty."""
        merger = ToolCallMerger()
        result = merger.analyze_and_merge([])
        assert result == []

    def test_none_directory_same_directory(self):
        """Calls with None directory should be treated as same directory."""
        merger = ToolCallMerger()
        calls = [
            ToolCall(id="1", name="file_search", arguments={"pattern": "*.py"}),
            ToolCall(id="2", name="file_search", arguments={"pattern": "*.ts"}),
        ]
        result = merger.analyze_and_merge(calls)
        assert len(result) == 1
