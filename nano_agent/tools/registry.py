"""
Tool registry for managing registered tools.

Provides centralized tool management with middleware support for
flexible execution interception and extension.
"""

from typing import Callable

from .base import BaseTool, ToolResult
from .middleware import MiddlewareChain, BaseMiddleware, MiddlewareContext
from ..core.registry import BaseRegistry


class ToolRegistry(BaseRegistry["BaseTool"]):
    """
    Registry for managing tools with middleware support.

    Supports adding middlewares to intercept tool execution for
    logging, confirmation, caching, tracing, etc.

    Example:
        registry = ToolRegistry()

        # Add middlewares
        registry.add_middleware(LoggingMiddleware())
        registry.add_middleware(ConfirmationMiddleware())

        # Execute tool - middlewares are called automatically
        result = registry.execute("shell_execute", command="ls -la")
    """

    def __init__(self):
        super().__init__()
        self._middleware_chain = MiddlewareChain()

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

    def add_middleware(self, middleware: BaseMiddleware) -> None:
        """
        Add a middleware to the execution chain.

        Args:
            middleware: Middleware instance to add
        """
        self._middleware_chain.add(middleware)

    def remove_middleware(self, middleware: BaseMiddleware) -> bool:
        """
        Remove a middleware from the execution chain.

        Args:
            middleware: Middleware instance to remove

        Returns:
            True if middleware was removed, False if not found
        """
        return self._middleware_chain.remove(middleware)

    def clear_middlewares(self) -> None:
        """Remove all middlewares."""
        self._middleware_chain.clear()

    def execute(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name with middleware chain.

        This is the recommended way to execute tools when middlewares
        are needed. The execute_tool method bypasses middlewares.

        Args:
            name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool

        Returns:
            ToolResult from execution
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}"
            )

        def executor(args: dict) -> ToolResult:
            # Pass tool to middleware via state
            return tool.execute(**args)

        # Create context with tool reference for confirmation middleware
        ctx = MiddlewareContext(tool_name=name, arguments=kwargs)
        ctx.state["tool"] = tool

        return self._middleware_chain.execute(name, kwargs, executor)

    def execute_tool(self, name: str, arguments: dict) -> ToolResult:
        """
        Execute a tool directly without middleware.

        Use execute() instead to go through middleware chain.

        Args:
            name: Name of the tool
            arguments: Arguments to pass to the tool

        Returns:
            ToolResult from execution
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}"
            )
        return tool.execute(**arguments)

    def get_all_schemas(self) -> list[dict]:
        """Get all tool schemas in Ollama format."""
        return [tool.to_ollama_tool() for tool in self._items.values()]

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return self.list_all()
