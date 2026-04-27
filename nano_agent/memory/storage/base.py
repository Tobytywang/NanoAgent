"""
Base storage interface for persistent memory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
import json


@dataclass
class MemoryEntry:
    """A single memory entry for persistent storage."""

    id: str
    session_id: str
    role: str  # system, user, assistant, tool
    content: str
    timestamp: str  # ISO format datetime
    metadata: dict = field(default_factory=dict)  # Additional info (e.g., tool_calls)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def create(
        cls,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None
    ) -> "MemoryEntry":
        """Create a new entry with generated id and timestamp."""
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )


class BaseStorage(ABC):
    """Abstract base class for memory storage backends."""

    @abstractmethod
    def save(self, entry: MemoryEntry) -> str:
        """
        Save a memory entry.

        Args:
            entry: The memory entry to save

        Returns:
            The entry id
        """
        pass

    @abstractmethod
    def load_session(self, session_id: str) -> list[MemoryEntry]:
        """
        Load all entries for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of memory entries, ordered by timestamp
        """
        pass

    @abstractmethod
    def load_recent(self, session_id: str, limit: int) -> list[MemoryEntry]:
        """
        Load recent entries for a session.

        Args:
            session_id: The session identifier
            limit: Maximum number of entries to load

        Returns:
            List of recent memory entries
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """
        Delete all entries for a session.

        Args:
            session_id: The session identifier
        """
        pass

    @abstractmethod
    def list_sessions(self) -> list[str]:
        """
        List all session identifiers.

        Returns:
            List of session ids
        """
        pass

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: The session identifier

        Returns:
            True if session exists
        """
        pass
