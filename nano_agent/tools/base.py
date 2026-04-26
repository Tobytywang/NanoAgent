"""
Tool system base classes and registry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for tools."""

    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """Return JSON Schema format parameter definition."""
        pass

    def to_ollama_tool(self) -> dict:
        """Convert to Ollama tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        pass


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def register_function(
        self,
        name: str,
        description: str,
        parameters_schema: dict,
        func: Callable
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

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict]:
        """Get all tool schemas in Ollama format."""
        return [tool.to_ollama_tool() for tool in self._tools.values()]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self._tools)
