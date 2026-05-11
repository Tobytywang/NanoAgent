"""
Tool execution middleware system.

Provides a flexible way to intercept and extend tool execution with
custom logic like logging, confirmation, tracing, etc.

Example:
    # Add logging middleware
    registry.add_middleware(LoggingMiddleware())

    # Add confirmation middleware for dangerous operations
    registry.add_middleware(ConfirmationMiddleware())

    # Execute tool - middlewares are called automatically
    result = registry.execute("shell_execute", command="ls")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable
from enum import Enum

from .base import ToolResult


class MiddlewarePhase(Enum):
    """When middleware is invoked."""
    BEFORE = "before"    # Before tool execution
    AFTER = "after"      # After successful execution
    ERROR = "error"      # After failed execution


@dataclass
class MiddlewareContext:
    """
    Context passed to middleware during execution.

    Contains all information about the tool call and allows middleware
    to communicate with each other through shared state.
    """
    tool_name: str
    arguments: dict[str, Any]
    result: ToolResult | None = None
    error: Exception | None = None
    start_time: float = 0.0
    end_time: float = 0.0
    state: dict[str, Any] = None  # Shared state between middlewares

    def __post_init__(self):
        if self.state is None:
            self.state = {}


class BaseMiddleware(ABC):
    """
    Abstract base class for tool execution middleware.

    Middleware can intercept tool execution at three phases:
    - before: Called before tool execution, can modify arguments or skip execution
    - after: Called after successful execution, can modify result
    - error: Called after failed execution, can handle or transform error

    Example:
        class LoggingMiddleware(BaseMiddleware):
            priority = 100  # Higher priority runs first

            def before(self, ctx: MiddlewareContext) -> None:
                print(f"Executing: {ctx.tool_name}")

            def after(self, ctx: MiddlewareContext) -> None:
                print(f"Completed: {ctx.tool_name}")
    """

    priority: int = 0  # Higher priority runs first (before) / last (after)

    def before(self, ctx: MiddlewareContext) -> ToolResult | None:
        """
        Called before tool execution.

        Args:
            ctx: Execution context

        Returns:
            If returns a ToolResult, execution is skipped and this result is used.
            This allows middleware to short-circuit execution (e.g., for caching).
        """
        return None

    def after(self, ctx: MiddlewareContext) -> None:
        """
        Called after successful tool execution.

        Args:
            ctx: Execution context (contains result)
        """
        pass

    def error(self, ctx: MiddlewareContext) -> None:
        """
        Called after failed tool execution.

        Args:
            ctx: Execution context (contains error)
        """
        pass


class MiddlewareChain:
    """
    Manages a chain of middlewares and executes them in order.

    Middlewares are sorted by priority:
    - before phase: higher priority runs first
    - after/error phase: higher priority runs last (reverse order)
    """

    def __init__(self):
        self._middlewares: list[BaseMiddleware] = []

    def add(self, middleware: BaseMiddleware) -> None:
        """Add a middleware to the chain."""
        self._middlewares.append(middleware)
        # Sort by priority (descending for before phase)
        self._middlewares.sort(key=lambda m: m.priority, reverse=True)

    def remove(self, middleware: BaseMiddleware) -> bool:
        """Remove a middleware from the chain."""
        try:
            self._middlewares.remove(middleware)
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        """Remove all middlewares."""
        self._middlewares.clear()

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        executor: Callable[[dict[str, Any]], ToolResult]
    ) -> ToolResult:
        """
        Execute tool with middleware chain.

        Args:
            tool_name: Name of the tool being executed
            arguments: Tool arguments
            executor: Function that executes the tool

        Returns:
            ToolResult from execution
        """
        import time

        ctx = MiddlewareContext(
            tool_name=tool_name,
            arguments=arguments.copy()
        )

        # Before phase (higher priority first)
        ctx.start_time = time.time()
        for middleware in self._middlewares:
            skip_result = middleware.before(ctx)
            if skip_result is not None:
                # Middleware short-circuited execution
                ctx.result = skip_result
                ctx.end_time = time.time()
                return skip_result

        # Execute tool
        try:
            ctx.result = executor(ctx.arguments)
            ctx.end_time = time.time()

            # After phase (lower priority first = reverse order)
            for middleware in reversed(self._middlewares):
                middleware.after(ctx)

            return ctx.result

        except Exception as e:
            ctx.error = e
            ctx.end_time = time.time()

            # Error phase (lower priority first)
            for middleware in reversed(self._middlewares):
                middleware.error(ctx)

            # Re-raise if not handled
            raise

    def __len__(self) -> int:
        return len(self._middlewares)

    def __iter__(self):
        return iter(self._middlewares)
