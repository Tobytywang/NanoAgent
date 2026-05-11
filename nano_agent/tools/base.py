"""
Tool system base classes and registry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Any, TYPE_CHECKING

from ..core.registry import BaseRegistry

if TYPE_CHECKING:
    from ..agent.types import RiskLevel


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    error: str | None = None
    metadata: dict | None = None  # Optional metadata for tool-specific data
    undo_data: dict | None = None  # Data needed to undo this operation


class BaseTool(ABC):
    """Abstract base class for tools."""

    name: str = ""
    description: str = ""
    risk_level: "RiskLevel" = None  # Will be set to MODERATE by default

    def __init__(self):
        # Import here to avoid circular import
        from ..agent.types import RiskLevel
        if self.risk_level is None:
            self.risk_level = RiskLevel.MODERATE

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """Return JSON Schema format parameter definition."""
        pass

    @property
    def supports_undo(self) -> bool:
        """Whether this tool supports undo operation."""
        return False  # Default: not supported

    def undo(self, undo_data: dict, context: dict) -> bool:
        """
        Undo a previously executed operation.

        Args:
            undo_data: Data returned in ToolResult.undo_data from execute()
            context: Execution context (contains memory, config, tool_registry, etc.)

        Returns:
            True if undo was successful, False otherwise
        """
        return False  # Default: not implemented

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


class ToolRegistry(BaseRegistry["BaseTool"]):
    """Registry for managing tools."""

    def __init__(self):
        super().__init__()

    def register(self, tool: BaseTool, name: str | None = None) -> None:
        """
        Register a tool.

        Args:
            tool: The tool to register
            name: Optional name override (uses tool.name by default)
        """
        super().register(tool, name or tool.name)

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

    def get_all_schemas(self) -> list[dict]:
        """Get all tool schemas in Ollama format."""
        return [tool.to_ollama_tool() for tool in self._items.values()]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return self.list_all()
