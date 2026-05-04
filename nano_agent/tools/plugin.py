"""
Plugin tool loader for dynamically loading external tools.
"""

import importlib
import sys
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolRegistry


class PluginLoader:
    """
    插件工具加载器

    支持从以下位置加载工具：
    1. Python 模块路径 (如 "my_package.tools")
    2. Python 文件路径 (如 "/path/to/tools.py")
    3. 目录路径 (自动加载目录下所有 tool_*.py 文件)
    """

    def __init__(self, registry: ToolRegistry | None = None):
        """
        Initialize the plugin loader.

        Args:
            registry: Tool registry to register loaded tools
        """
        self.registry = registry or ToolRegistry()
        self._loaded_plugins: dict[str, str] = {}  # tool_name -> source_path

    def load_from_module(self, module_path: str) -> list[BaseTool]:
        """
        Load tools from a Python module.

        Args:
            module_path: Python module path (e.g., "my_package.tools")

        Returns:
            List of loaded tools
        """
        tools = []
        try:
            module = importlib.import_module(module_path)

            # Find all BaseTool subclasses in the module
            for name in dir(module):
                obj = getattr(module, name)

                # Check if it's a tool class (not the base class itself)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and hasattr(obj, 'name')
                ):
                    try:
                        tool_instance = obj()
                        tools.append(tool_instance)
                        self.registry.register(tool_instance)
                        self._loaded_plugins[tool_instance.name] = f"{module_path}.{name}"
                    except Exception:
                        pass  # Skip tools that fail to instantiate

            return tools

        except ImportError:
            return []

    def load_from_file(self, file_path: str | Path) -> list[BaseTool]:
        """
        Load tools from a Python file.

        Args:
            file_path: Path to Python file

        Returns:
            List of loaded tools
        """
        path = Path(file_path)
        if not path.exists() or not path.suffix == '.py':
            return []

        tools = []
        try:
            # Create unique module name
            module_name = f"plugin_{path.stem}_{id(path)}"

            # Load module from file
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                return []

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find all BaseTool subclasses
            for name in dir(module):
                obj = getattr(module, name)

                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and hasattr(obj, 'name')
                ):
                    try:
                        tool_instance = obj()
                        tools.append(tool_instance)
                        self.registry.register(tool_instance)
                        self._loaded_plugins[tool_instance.name] = str(path)
                    except Exception:
                        pass

            return tools

        except Exception:
            return []

    def load_from_directory(
        self,
        directory: str | Path,
        pattern: str = "tool_*.py"
    ) -> list[BaseTool]:
        """
        Load tools from all matching files in a directory.

        Args:
            directory: Directory path
            pattern: Glob pattern for tool files (default: "tool_*.py")

        Returns:
            List of loaded tools
        """
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return []

        tools = []
        for file_path in dir_path.glob(pattern):
            loaded = self.load_from_file(file_path)
            tools.extend(loaded)

        return tools

    def unload_tool(self, tool_name: str) -> bool:
        """
        Unload a tool from the registry.

        Args:
            tool_name: Name of the tool to unload

        Returns:
            True if tool was unloaded, False if not found
        """
        if tool_name in self._loaded_plugins:
            del self._loaded_plugins[tool_name]
            return self.registry.unregister(tool_name)
        return False

    def list_loaded_plugins(self) -> dict[str, str]:
        """
        List all loaded plugins.

        Returns:
            Dictionary mapping tool names to source paths
        """
        return self._loaded_plugins.copy()

    def get_tool_source(self, tool_name: str) -> str | None:
        """
        Get the source path for a loaded tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Source path or None if not found
        """
        return self._loaded_plugins.get(tool_name)


def load_plugins_from_config(config: dict, registry: ToolRegistry) -> list[BaseTool]:
    """
    Load plugins from configuration.

    Config format:
    ```yaml
    plugins:
      directories:
        - .nano_agent/plugins
      modules:
        - my_package.tools
      files:
        - /path/to/custom_tools.py
    ```

    Args:
        config: Configuration dictionary
        registry: Tool registry

    Returns:
        List of loaded tools
    """
    loader = PluginLoader(registry)
    tools = []

    plugins_config = config.get("plugins", {})

    # Load from directories
    for directory in plugins_config.get("directories", []):
        loaded = loader.load_from_directory(directory)
        tools.extend(loaded)

    # Load from modules
    for module_path in plugins_config.get("modules", []):
        loaded = loader.load_from_module(module_path)
        tools.extend(loaded)

    # Load from files
    for file_path in plugins_config.get("files", []):
        loaded = loader.load_from_file(file_path)
        tools.extend(loaded)

    return tools