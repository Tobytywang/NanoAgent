"""
Forget tool for deleting long-term memories.
"""

from ...base import BaseTool, ToolResult
from .base import MemoryToolMixin
from ....agent.types import RiskLevel


class ForgetTool(MemoryToolMixin, BaseTool):
    """Tool to delete a long-term memory."""

    name = "forget"
    description = "Delete a specific memory from long-term storage by its ID."
    risk_level = RiskLevel.DANGEROUS  # Delete operation

    def __init__(self, memory=None):
        super().__init__(memory=memory)

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "The ID of the memory to delete (e.g., ltm_abc123)"
                }
            },
            "required": ["memory_id"]
        }

    def execute(self, memory_id: str) -> ToolResult:
        # Check memory availability
        error = self._check_memory_available()
        if error:
            return error

        try:
            success = self._memory.forget(memory_id)

            if success:
                return ToolResult(
                    success=True,
                    output=f"Memory {memory_id} has been deleted."
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Memory {memory_id} not found."
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )
