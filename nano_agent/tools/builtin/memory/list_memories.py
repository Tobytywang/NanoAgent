"""
List memories tool for listing all long-term memories.
"""

from ...base import BaseTool, ToolResult
from .base import MemoryToolMixin
from ....agent.types import RiskLevel


class ListMemoriesTool(MemoryToolMixin, BaseTool):
    """Tool to list all long-term memories."""

    name = "list_memories"
    description = "List all stored long-term memories."
    risk_level = RiskLevel.SAFE  # Read-only operation

    def __init__(self, memory=None):
        super().__init__(memory=memory)

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["fact", "preference", "experience", "task", "note"],
                    "description": "Filter by category (optional)"
                }
            }
        }

    def execute(self, category: str | None = None) -> ToolResult:
        # Check memory availability
        error = self._check_memory_available()
        if error:
            return error

        try:
            entries = self._memory.get_all_long_term()

            if category:
                entries = [e for e in entries if e.category == category]

            if not entries:
                return ToolResult(
                    success=True,
                    output="No memories stored yet."
                )

            # Format results
            results = []
            for i, entry in enumerate(entries, 1):
                results.append(
                    f"{i}. [{entry.category}] {entry.content[:100]}{'...' if len(entry.content) > 100 else ''}"
                )

            return ToolResult(
                success=True,
                output=f"Total {len(entries)} memories:\n" + "\n".join(results)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
