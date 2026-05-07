"""
Event emitter for agent execution monitoring.

This module provides a simple event system that allows external code
to listen to execution events without coupling to the execution logic.
"""

from typing import Callable, Any
from .types import AgentEvent


class EventEmitter:
    """
    Event emitter - supports external monitoring of execution process.

    This class implements a simple publish-subscribe pattern where
    handlers can register for specific events and be notified when
    those events occur during execution.
    """

    def __init__(self):
        self._handlers: dict[AgentEvent, list[Callable[[AgentEvent, dict], None]]] = {}

    def on(self, event: AgentEvent, handler: Callable[[AgentEvent, dict], None]) -> None:
        """
        Register an event listener.

        Args:
            event: The event type to listen for
            handler: Callback function that receives (event, data)
        """
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def off(self, event: AgentEvent, handler: Callable[[AgentEvent, dict], None] = None) -> None:
        """
        Remove an event listener.

        Args:
            event: The event type
            handler: Specific handler to remove, or None to remove all
        """
        if event not in self._handlers:
            return
        if handler is None:
            self._handlers[event] = []
        else:
            self._handlers[event] = [h for h in self._handlers[event] if h != handler]

    def emit(self, event: AgentEvent, data: dict) -> None:
        """
        Emit an event to all registered listeners.

        Args:
            event: The event type to emit
            data: Event data to pass to handlers

        Note:
            Exceptions in handlers are caught and ignored to prevent
            handler failures from affecting the main execution flow.
        """
        for handler in self._handlers.get(event, []):
            try:
                handler(event, data)
            except Exception:
                # Ignore handler exceptions to protect main execution
                pass

    def clear(self) -> None:
        """Remove all event listeners."""
        self._handlers.clear()
