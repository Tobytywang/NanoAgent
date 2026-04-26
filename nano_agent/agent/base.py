"""
Base Agent class.
"""

from abc import ABC, abstractmethod
from ..llm.base import BaseLLM
from ..memory.base import BaseMemory
from ..tools.base import ToolRegistry, ToolResult


class BaseAgent(ABC):
    """Abstract base class for agents."""

    def __init__(
        self,
        llm: BaseLLM,
        memory: BaseMemory,
        tool_registry: ToolRegistry,
        max_iterations: int = 10
    ):
        """
        Initialize the agent.

        Args:
            llm: LLM client instance
            memory: Memory system instance
            tool_registry: Tool registry instance
            max_iterations: Maximum number of reasoning iterations
        """
        self.llm = llm
        self.memory = memory
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    @abstractmethod
    def run(self, user_input: str) -> str:
        """
        Process user input and return a response.

        Args:
            user_input: The user's input text

        Returns:
            The agent's response
        """
        pass

    def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """
        Execute a tool by name with given arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool

        Returns:
            ToolResult from the tool execution
        """
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}"
            )
        return tool.execute(**arguments)

    def reset(self) -> None:
        """Reset the agent's memory."""
        self.memory.clear()
