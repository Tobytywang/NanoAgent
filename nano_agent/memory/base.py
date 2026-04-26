"""
Base memory interface.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseMemory(ABC):
    """Abstract base class for memory systems."""

    @abstractmethod
    def add(self, message: Any) -> None:
        """Add a message to memory."""
        pass

    @abstractmethod
    def get_all(self) -> list:
        """Get all messages."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all messages."""
        pass

    @abstractmethod
    def get_context(self, max_items: int | None = None) -> list:
        """Get context, optionally limited to max_items."""
        pass
