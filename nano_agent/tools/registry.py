"""
Tool registry for managing registered tools.

Provides centralized tool management with registration and execution.
"""

from typing import Callable

from .base import BaseTool, ToolResult
from ..core.registry import BaseRegistry


class ToolRegistry(BaseRegistry["BaseTool"]):
    """
    Registry for managing tools.

    Example:
        registry = ToolRegistry()

        # Register a tool
        registry.register(my_tool)

        # Execute tool
        result = registry.execute("shell_execute", command="ls -la")
    """

    def register(self, tool: BaseTool, name: str | None = None) -> None:
        """
        Register a tool.

        Args:
            tool: The tool to register
            name: Optional name override (uses tool.name by default)
        """
        super().register(tool, name or tool.name)

    def register_function(
        self, name: str, description: str, parameters_schema: dict, func: Callable
    ) -> None:
        """
        Quickly register a function as a tool.

        Args:
            name: Tool name
            description: Tool description
            parameters_schema: JSON Schema for parameters
            func: Function to execute
        """

        class FunctionTool(BaseTool):
            def __init__(self):
                self.name = name
                self.description = description
                self._schema = parameters_schema
                self._func = func

            @property
            def parameters_schema(self) -> dict:
                return self._schema

            def execute(self, **kwargs) -> ToolResult:
                try:
                    result = self._func(**kwargs)
                    return ToolResult(success=True, output=str(result))
                except Exception as e:
                    return ToolResult(success=False, output="", error=str(e))

        self.register(FunctionTool())

    def execute(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool

        Returns:
            ToolResult from execution
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
        return tool.execute(**kwargs)

    def get_all_schemas(self) -> list[dict]:
        """Get all tool schemas in Ollama format."""
        return [tool.to_ollama_tool() for tool in self._items.values()]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return self.list_all()
