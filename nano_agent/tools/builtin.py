"""
Built-in tools registration.
"""

from .base import ToolRegistry
from .python_executor import PythonExecutorTool
from .file_ops import FileReadTool, FileWriteTool, FileSearchTool
from .shell import ShellTool


def register_builtin_tools(registry: ToolRegistry) -> None:
    """
    Register all built-in tools to the registry.

    Args:
        registry: ToolRegistry instance to register tools to
    """
    registry.register(PythonExecutorTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileSearchTool())
    registry.register(ShellTool())


# List of all built-in tool names
BUILTIN_TOOLS = [
    "python_execute",
    "file_read",
    "file_write",
    "file_search",
    "shell_execute"
]
