"""
Tools module - Tool system and built-in tools.

Provides:
- BaseTool, ToolResult: Base classes for tools
- ToolRegistry: Central registry
- Built-in tools: Common tools for file, shell, memory operations
"""

from .base import BaseTool, ToolResult
from .registry import ToolRegistry
from .plugin import PluginLoader, load_plugins_from_config
from .builtin import register_builtin_tools, BUILTIN_TOOLS

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    # Registry
    "ToolRegistry",
    # Plugin system
    "PluginLoader",
    "load_plugins_from_config",
    # Built-in tools
    "register_builtin_tools",
    "BUILTIN_TOOLS",
]
