"""
Recall tool for searching long-term memory.
"""

from ...base import BaseTool, ToolResult
from .base import MemoryToolMixin
from ....agent.types import RiskLevel


class RecallTool(MemoryToolMixin, BaseTool):
    """Tool to search long-term memory."""

    name = "recall"
    description = "Search and retrieve information from long-term memory. Use this to recall previously stored preferences, facts, or experiences."
    risk_level = RiskLevel.SAFE  # Read-only operation

    def __init__(self, memory=None):
        super().__init__(memory=memory)

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant memories"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Maximum number of results (default: 5)"
                }
            },
            "required": ["query"]
        }

    def execute(self, query: str, limit: int = 5) -> ToolResult:
        # Check memory availability
        error = self._check_memory_available()
        if error:
            return error

        try:
            entries = self._memory.recall(query, limit)

            if not entries:
                return ToolResult(
                    success=True,
                    output="No matching memories found."
                )

            # Format results
            results = []
            for i, entry in enumerate(entries, 1):
                results.append(
                    f"{i}. [{entry.category}] {entry.content}\n"
                    f"   (importance: {entry.importance:.1f}, stored: {entry.created_at[:10]})"
                )

            return ToolResult(
                success=True,
                output="Found memories:\n" + "\n".join(results)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
