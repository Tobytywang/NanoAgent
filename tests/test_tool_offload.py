"""
Tests for tool result offloading (v0.7.17).
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from nano_agent.agent.tool_offload import ToolOffloadManager, OffloadedResult
from nano_agent.config.schema import ToolOffloadConfig
from nano_agent.tools.base import BaseTool, ToolResult


class TestToolOffloadConfig:
    """Test ToolOffloadConfig dataclass."""

    def test_default_config(self):
        config = ToolOffloadConfig()
        assert config.enabled is True
        assert config.size_threshold_tokens == 1000
        assert config.offload_dir == "/tmp/nano_agent_offload"
        assert config.auto_cleanup is True
        assert config.summary_max_tokens == 200
        assert "memorize" in config.excluded_tools

    def test_custom_config(self):
        config = ToolOffloadConfig(
            enabled=False,
            size_threshold_tokens=500,
            offload_dir="/custom/path",
            summary_max_tokens=100,
        )
        assert config.enabled is False
        assert config.size_threshold_tokens == 500
        assert config.offload_dir == "/custom/path"
        assert config.summary_max_tokens == 100


class TestToolOffloadManager:
    """Test ToolOffloadManager class."""

    @pytest.fixture
    def temp_offload_dir(self, tmp_path):
        return str(tmp_path / "offload")

    @pytest.fixture
    def offload_manager(self, temp_offload_dir):
        config = ToolOffloadConfig(offload_dir=temp_offload_dir)
        return ToolOffloadManager(config)

    def test_should_offload_disabled(self, offload_manager):
        offload_manager.config.enabled = False
        large_content = "x" * 10000
        assert not offload_manager.should_offload(large_content, "file_read", True)

    def test_should_offload_tool_not_supported(self, offload_manager):
        large_content = "x" * 10000
        assert not offload_manager.should_offload(large_content, "file_read", False)

    def test_should_offload_below_threshold(self, offload_manager):
        small_content = "x" * 100
        assert not offload_manager.should_offload(small_content, "file_read", True)

    def test_should_offload_above_threshold(self, offload_manager):
        # Create content that exceeds 1000 tokens threshold
        # ~4 chars per token for English, so ~4000+ chars
        large_content = "x" * 5000
        assert offload_manager.should_offload(large_content, "file_read", True)

    def test_should_offload_excluded_tool(self, offload_manager):
        large_content = "x" * 5000
        offload_manager.config.excluded_tools = ["memorize"]
        assert not offload_manager.should_offload(large_content, "memorize", True)

    def test_offload_creates_file(self, offload_manager, temp_offload_dir):
        content = "test content " * 1000  # Large enough to be meaningful
        summary, offloaded = offload_manager.offload(content, "file_read", "call_123")

        assert Path(offloaded.file_path).exists()
        with open(offloaded.file_path, "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_offload_returns_summary(self, offload_manager, temp_offload_dir):
        content = "test content " * 1000
        summary, offloaded = offload_manager.offload(content, "file_read", "call_123")

        assert "[结果已卸载]" in summary
        assert "file_read" in summary
        assert "file_read(" in summary
        assert offloaded.file_path in summary

    def test_offload_tracks_metadata(self, offload_manager, temp_offload_dir):
        content = "test content " * 1000
        summary, offloaded = offload_manager.offload(content, "file_read", "call_123")

        assert offloaded.tool_name == "file_read"
        assert offloaded.original_size_tokens > 0
        assert offloaded.summary != ""

    def test_cleanup_removes_files(self, offload_manager, temp_offload_dir):
        content = "test content " * 1000
        summary, offloaded = offload_manager.offload(content, "file_read", "call_123")

        assert Path(offloaded.file_path).exists()
        count = offload_manager.cleanup()
        assert count == 1
        assert not Path(offloaded.file_path).exists()

    def test_get_stats(self, offload_manager, temp_offload_dir):
        content = "test content " * 1000
        offload_manager.offload(content, "file_read", "call_1")
        offload_manager.offload(content, "shell_execute", "call_2")

        stats = offload_manager.get_stats()
        assert stats["offloaded_count"] == 2
        assert stats["total_tokens_saved"] > 0

    def test_get_offloaded_by_id(self, offload_manager, temp_offload_dir):
        content = "test content " * 1000
        summary, offloaded = offload_manager.offload(content, "file_read", "call_123")

        result = offload_manager.get_offloaded(offloaded.offload_id)
        assert result is not None
        assert result.tool_name == "file_read"
        assert result.accessed is True

    def test_get_by_path(self, offload_manager, temp_offload_dir):
        content = "test content " * 1000
        summary, offloaded = offload_manager.offload(content, "file_read", "call_123")

        result = offload_manager.get_by_path(offloaded.file_path)
        assert result is not None
        assert result.tool_name == "file_read"


class TestBaseToolCanOffload:
    """Test can_offload attribute on tools."""

    def test_default_can_offload(self):
        class TestTool(BaseTool):
            name = "test"
            description = "test"

            @property
            def parameters_schema(self):
                return {}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="test")

        tool = TestTool()
        assert tool.can_offload is False

    def test_can_offload_set_true(self):
        class TestTool(BaseTool):
            name = "test"
            description = "test"
            can_offload = True

            @property
            def parameters_schema(self):
                return {}

            def execute(self, **kwargs):
                return ToolResult(success=True, output="test")

        tool = TestTool()
        assert tool.can_offload is True
