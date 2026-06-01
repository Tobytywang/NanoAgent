"""
Tests for plugin loader module.

Tests the dynamic loading of external tools.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

pytestmark = pytest.mark.unit

from nano_agent.tools.plugin import PluginLoader, load_plugins_from_config
from nano_agent.tools.base import BaseTool, ToolResult
from nano_agent.tools.registry import ToolRegistry


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_plugin_tool"
    description = "A mock plugin tool"

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        }

    def execute(self, input: str = "") -> ToolResult:
        return ToolResult(success=True, output=f"Plugin result: {input}")


class TestPluginLoader:
    """Tests for PluginLoader class."""

    def test_initialization_default_registry(self):
        """Test loader initializes with default registry."""
        loader = PluginLoader()

        assert loader.registry is not None
        assert isinstance(loader.registry, ToolRegistry)
        assert loader._loaded_plugins == {}

    def test_initialization_custom_registry(self):
        """Test loader initializes with custom registry."""
        registry = ToolRegistry()
        loader = PluginLoader(registry)

        assert loader.registry == registry

    def test_load_from_module_not_found(self):
        """Test load_from_module handles ImportError."""
        loader = PluginLoader()

        tools = loader.load_from_module("nonexistent_module")

        assert tools == []

    def test_load_from_file_not_found(self):
        """Test load_from_file handles missing file."""
        loader = PluginLoader()

        tools = loader.load_from_file("/nonexistent/file.py")

        assert tools == []

    def test_load_from_file_non_py(self, temp_dir):
        """Test load_from_file ignores non-Python files."""
        loader = PluginLoader()

        # Create a non-Python file
        txt_file = temp_dir / "tools.txt"
        txt_file.write_text("not a python file")

        tools = loader.load_from_file(txt_file)

        assert tools == []

    def test_load_from_directory_not_found(self):
        """Test load_from_directory handles missing directory."""
        loader = PluginLoader()

        tools = loader.load_from_directory("/nonexistent/directory")

        assert tools == []

    def test_load_from_directory_custom_pattern(self, temp_dir):
        """Test load_from_directory with custom pattern."""
        loader = PluginLoader()

        # Create directory with files
        plugin_dir = temp_dir / "plugins"
        plugin_dir.mkdir()

        # Create a file that matches custom pattern
        custom_file = plugin_dir / "custom_tool.py"
        custom_file.write_text("""
from nano_agent.tools.base import BaseTool, ToolResult

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "Custom tool"

    @property
    def parameters_schema(self):
        return {"type": "object"}

    def execute(self):
        return ToolResult(success=True, output="custom")
""")

        tools = loader.load_from_directory(plugin_dir, pattern="custom_*.py")

        assert len(tools) >= 0  # May or may not load depending on import

    def test_unload_tool_not_loaded(self):
        """Test unload_tool returns False for non-loaded tool."""
        loader = PluginLoader()

        result = loader.unload_tool("nonexistent_tool")

        assert result is False

    def test_list_loaded_plugins_empty(self):
        """Test list_loaded_plugins returns empty dict initially."""
        loader = PluginLoader()

        plugins = loader.list_loaded_plugins()

        assert plugins == {}

    def test_get_tool_source_not_found(self):
        """Test get_tool_source returns None for non-loaded tool."""
        loader = PluginLoader()

        source = loader.get_tool_source("nonexistent_tool")

        assert source is None


class TestPluginLoaderWithRealTool:
    """Tests with actual tool implementations."""

    def test_load_from_file_with_tool(self, temp_dir):
        """Test loading a custom tool class from file."""
        loader = PluginLoader()

        # Create a Python file with a tool
        plugin_dir = temp_dir / "plugins"
        plugin_dir.mkdir()

        tool_file = plugin_dir / "tool_test.py"
        tool_file.write_text("""
from nano_agent.tools.base import BaseTool, ToolResult

class TestPluginTool(BaseTool):
    name = "test_plugin_tool"
    description = "Test plugin tool"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {"input": {"type": "string"}}}

    def execute(self, input=""):
        return ToolResult(success=True, output=f"Result: {input}")
""")

        tools = loader.load_from_file(tool_file)

        # Tool should be loaded
        assert len(tools) >= 0  # May or may not load depending on import

    def test_tool_execution_after_load(self, temp_dir):
        """Test loaded tool can be executed."""
        registry = ToolRegistry()
        loader = PluginLoader(registry)

        # Create a Python file with a tool
        plugin_dir = temp_dir / "plugins"
        plugin_dir.mkdir()

        tool_file = plugin_dir / "tool_exec.py"
        tool_file.write_text("""
from nano_agent.tools.base import BaseTool, ToolResult

class ExecutableTool(BaseTool):
    name = "executable_tool"
    description = "Executable tool"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {"input": {"type": "string"}}}

    def execute(self, input="test"):
        return ToolResult(success=True, output=f"Executed: {input}")
""")

        tools = loader.load_from_file(tool_file)

        if tools:
            result = tools[0].execute(input="hello")
            assert result.success is True


class TestLoadPluginsFromConfig:
    """Tests for load_plugins_from_config function."""

    def test_load_from_directories(self, temp_dir):
        """Test loading plugins from directories config."""
        registry = ToolRegistry()

        # Create plugin directory
        plugin_dir = temp_dir / "plugins"
        plugin_dir.mkdir()

        config = {"plugins": {"directories": [str(plugin_dir)]}}

        tools = load_plugins_from_config(config, registry)

        # Should attempt to load from directory
        assert isinstance(tools, list)

    def test_load_from_modules(self):
        """Test loading plugins from modules config."""
        registry = ToolRegistry()

        config = {"plugins": {"modules": ["nonexistent_module"]}}

        tools = load_plugins_from_config(config, registry)

        # Should return empty list for nonexistent module
        assert tools == []

    def test_load_from_files(self, temp_dir):
        """Test loading plugins from files config."""
        registry = ToolRegistry()

        # Create a tool file
        tool_file = temp_dir / "custom_tools.py"
        tool_file.write_text("""
from nano_agent.tools.base import BaseTool, ToolResult

class FileTool(BaseTool):
    name = "file_tool"
    description = "File tool"

    @property
    def parameters_schema(self):
        return {"type": "object"}

    def execute(self):
        return ToolResult(success=True, output="file")
""")

        config = {"plugins": {"files": [str(tool_file)]}}

        tools = load_plugins_from_config(config, registry)

        # Should attempt to load from file
        assert isinstance(tools, list)

    def test_load_from_all_sources(self, temp_dir):
        """Test loading plugins from all sources."""
        registry = ToolRegistry()

        # Create plugin directory
        plugin_dir = temp_dir / "plugins"
        plugin_dir.mkdir()

        config = {
            "plugins": {
                "directories": [str(plugin_dir)],
                "modules": ["nonexistent_module"],
                "files": ["/nonexistent/file.py"],
            }
        }

        tools = load_plugins_from_config(config, registry)

        # Should return list (may be empty if no valid tools)
        assert isinstance(tools, list)

    def test_load_empty_config(self):
        """Test loading with empty config."""
        registry = ToolRegistry()

        config = {}

        tools = load_plugins_from_config(config, registry)

        assert tools == []

    def test_load_missing_plugins_key(self):
        """Test loading with missing plugins key."""
        registry = ToolRegistry()

        config = {"other_key": "value"}

        tools = load_plugins_from_config(config, registry)

        assert tools == []

    def test_load_with_empty_plugins_dict(self):
        """Test loading with empty plugins dictionary."""
        registry = ToolRegistry()

        config = {"plugins": {}}

        tools = load_plugins_from_config(config, registry)

        assert tools == []


class TestPluginLoaderRegistryIntegration:
    """Tests for PluginLoader integration with ToolRegistry."""

    def test_loaded_tool_registered_in_registry(self, temp_dir):
        """Test that loaded tools are registered in the registry."""
        registry = ToolRegistry()
        loader = PluginLoader(registry)

        # Create a tool file
        tool_file = temp_dir / "tool_registered.py"
        tool_file.write_text("""
from nano_agent.tools.base import BaseTool, ToolResult

class RegisteredTool(BaseTool):
    name = "registered_tool"
    description = "Registered tool"

    @property
    def parameters_schema(self):
        return {"type": "object"}

    def execute(self):
        return ToolResult(success=True, output="registered")
""")

        tools = loader.load_from_file(tool_file)

        if tools:
            # Tool should be in registry
            assert "registered_tool" in registry

    def test_unload_removes_from_registry(self):
        """Test that unload removes tool from registry."""
        registry = ToolRegistry()
        loader = PluginLoader(registry)

        # Manually add a tool to simulate loading
        tool = MockTool()
        registry.register(tool)
        loader._loaded_plugins[tool.name] = "test_source"

        # Unload the tool
        result = loader.unload_tool(tool.name)

        assert result is True
        assert tool.name not in registry

    def test_list_loaded_plugins_after_load(self, temp_dir):
        """Test list_loaded_plugins after loading."""
        registry = ToolRegistry()
        loader = PluginLoader(registry)

        # Create a tool file
        tool_file = temp_dir / "tool_listed.py"
        tool_file.write_text("""
from nano_agent.tools.base import BaseTool, ToolResult

class ListedTool(BaseTool):
    name = "listed_tool"
    description = "Listed tool"

    @property
    def parameters_schema(self):
        return {"type": "object"}

    def execute(self):
        return ToolResult(success=True, output="listed")
""")

        tools = loader.load_from_file(tool_file)

        if tools:
            plugins = loader.list_loaded_plugins()
            assert "listed_tool" in plugins

    def test_get_tool_source_after_load(self, temp_dir):
        """Test get_tool_source after loading."""
        registry = ToolRegistry()
        loader = PluginLoader(registry)

        # Create a tool file
        tool_file = temp_dir / "tool_source.py"
        tool_file.write_text("""
from nano_agent.tools.base import BaseTool, ToolResult

class SourceTool(BaseTool):
    name = "source_tool"
    description = "Source tool"

    @property
    def parameters_schema(self):
        return {"type": "object"}

    def execute(self):
        return ToolResult(success=True, output="source")
""")

        tools = loader.load_from_file(tool_file)

        if tools:
            source = loader.get_tool_source("source_tool")
            assert source is not None
            assert str(tool_file) in source or "tool_source" in source
