"""
Tool system base classes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.types import RiskLevel


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
    can_offload: bool = False  # Whether tool output can be offloaded to file
    has_builtin_timeout: bool = False  # Whether tool manages its own timeout internally

    def __init__(self):
        # Import here to avoid circular import
        from ..core.types import RiskLevel

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
                "parameters": self.parameters_schema,
            },
        }

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        pass
