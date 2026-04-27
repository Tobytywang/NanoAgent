"""
Memory tools for long-term memory operations.
"""

from .base import BaseTool, ToolResult


class MemorizeTool(BaseTool):
    """Tool to store information in long-term memory."""

    name = "memorize"
    description = "Store important information into long-term memory for future sessions. Use this to remember user preferences, important facts, or key decisions."

    def __init__(self, memory=None):
        self._memory = memory

    def set_memory(self, memory) -> None:
        """Set the memory instance."""
        self._memory = memory

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The information to remember"
                },
                "category": {
                    "type": "string",
                    "enum": ["fact", "preference", "experience", "task", "note"],
                    "description": "Type of memory (default: fact)"
                },
                "importance": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Importance score from 0 to 1 (default: 0.5)"
                }
            },
            "required": ["content"]
        }

    def execute(self, content: str, category: str = "fact", importance: float = 0.5) -> ToolResult:
        if not self._memory:
            return ToolResult(
                success=False,
                output="",
                error="Memory not configured"
            )

        # Check if memory has long-term memory support
        if not hasattr(self._memory, 'memorize'):
            return ToolResult(
                success=False,
                output="",
                error="Long-term memory not available. Use hybrid memory type."
            )

        try:
            entry_id = self._memory.memorize(
                content=content,
                category=category,
                importance=importance
            )
            return ToolResult(
                success=True,
                output=f"Successfully stored in long-term memory (ID: {entry_id})"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )


class RecallTool(BaseTool):
    """Tool to search long-term memory."""

    name = "recall"
    description = "Search and retrieve information from long-term memory. Use this to recall previously stored preferences, facts, or experiences."

    def __init__(self, memory=None):
        self._memory = memory

    def set_memory(self, memory) -> None:
        """Set the memory instance."""
        self._memory = memory

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
        if not self._memory:
            return ToolResult(
                success=False,
                output="",
                error="Memory not configured"
            )

        # Check if memory has long-term memory support
        if not hasattr(self._memory, 'recall'):
            return ToolResult(
                success=False,
                output="",
                error="Long-term memory not available. Use hybrid memory type."
            )

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


class ListMemoriesTool(BaseTool):
    """Tool to list all long-term memories."""

    name = "list_memories"
    description = "List all stored long-term memories."

    def __init__(self, memory=None):
        self._memory = memory

    def set_memory(self, memory) -> None:
        """Set the memory instance."""
        self._memory = memory

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
        if not self._memory:
            return ToolResult(
                success=False,
                output="",
                error="Memory not configured"
            )

        # Check if memory has long-term memory support
        if not hasattr(self._memory, 'get_all_long_term'):
            return ToolResult(
                success=False,
                output="",
                error="Long-term memory not available. Use hybrid memory type."
            )

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


class ForgetTool(BaseTool):
    """Tool to delete a long-term memory."""

    name = "forget"
    description = "Delete a specific memory from long-term storage by its ID."

    def __init__(self, memory=None):
        self._memory = memory

    def set_memory(self, memory) -> None:
        """Set the memory instance."""
        self._memory = memory

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
        if not self._memory:
            return ToolResult(
                success=False,
                output="",
                error="Memory not configured"
            )

        # Check if memory has long-term memory support
        if not hasattr(self._memory, 'forget'):
            return ToolResult(
                success=False,
                output="",
                error="Long-term memory not available. Use hybrid memory type."
            )

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
