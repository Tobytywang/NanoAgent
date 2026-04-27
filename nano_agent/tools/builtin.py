"""
Built-in tools registration.
"""

from .base import ToolRegistry
from .python_executor import PythonExecutorTool
from .file_ops import FileReadTool, FileWriteTool, FileSearchTool
from .shell import ShellTool
from .memory_tools import MemorizeTool, RecallTool, ListMemoriesTool, ForgetTool


def register_builtin_tools(registry: ToolRegistry, memory=None) -> None:
    """
    Register all built-in tools to the registry.

    Args:
        registry: ToolRegistry instance to register tools to
        memory: Optional memory instance for memory tools
    """
    registry.register(PythonExecutorTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileSearchTool())
    registry.register(ShellTool())

    # Register memory tools
    memorize_tool = MemorizeTool(memory)
    recall_tool = RecallTool(memory)
    list_memories_tool = ListMemoriesTool(memory)
    forget_tool = ForgetTool(memory)

    registry.register(memorize_tool)
    registry.register(recall_tool)
    registry.register(list_memories_tool)
    registry.register(forget_tool)


# List of all built-in tool names
BUILTIN_TOOLS = [
    "python_execute",
    "file_read",
    "file_write",
    "file_search",
    "shell_execute",
    "memorize",
    "recall",
    "list_memories",
    "forget"
]
