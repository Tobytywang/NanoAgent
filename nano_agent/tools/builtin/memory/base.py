"""
Memory tools dependency injection mixin.

Provides standardized pattern for memory-dependent tools.
"""

from ...base import ToolResult
from ....memory.protocols import LongTermMemoryCapable


class MemoryToolMixin:
    """
    Mixin providing dependency injection for memory-dependent tools.

    Tools can receive memory via:
    1. Constructor: SomeTool(memory=obj)
    2. Setter: tool.set_memory(obj) (for late binding)

    Late binding is useful when tools are registered before
    memory is created (e.g., in AgentBuilder).
    """

    def __init__(self, memory=None, **kwargs):
        # Call parent __init__ if present (for cooperative multiple inheritance)
        super().__init__(**kwargs)
        self._memory = memory

    def set_memory(self, memory) -> None:
        """Set the memory instance (for late binding)."""
        self._memory = memory

    def _check_memory_available(self) -> ToolResult | None:
        """
        Check if memory is configured and supports long-term operations.

        Returns:
            ToolResult with error if memory not available, None if OK.
        """
        if not self._memory:
            return ToolResult(
                success=False,
                output="",
                error="Memory not configured"
            )

        if not isinstance(self._memory, LongTermMemoryCapable):
            return ToolResult(
                success=False,
                output="",
                error="Long-term memory not available. Use hybrid memory type."
            )

        return None