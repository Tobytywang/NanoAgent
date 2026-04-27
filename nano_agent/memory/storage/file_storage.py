"""
File-based storage implementation for persistent memory.
"""

import json
from pathlib import Path
from typing import Optional

from .base import BaseStorage, MemoryEntry


class FileStorage(BaseStorage):
    """File-based storage using JSONL format."""

    def __init__(self, base_dir: str = ".nano_agent/memory"):
        """
        Initialize file storage.

        Args:
            base_dir: Base directory for storing memory files
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, entry: MemoryEntry) -> str:
        """
        Save a memory entry to a JSONL file.

        Args:
            entry: The memory entry to save

        Returns:
            The entry id
        """
        session_file = self.base_dir / f"{entry.session_id}.jsonl"
        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        return entry.id

    def load_session(self, session_id: str) -> list[MemoryEntry]:
        """
        Load all entries for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of memory entries, ordered by timestamp
        """
        session_file = self.base_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return []

        entries = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(MemoryEntry.from_dict(json.loads(line)))

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)
        return entries

    def load_recent(self, session_id: str, limit: int) -> list[MemoryEntry]:
        """
        Load recent entries for a session.

        Args:
            session_id: The session identifier
            limit: Maximum number of entries to load

        Returns:
            List of recent memory entries
        """
        entries = self.load_session(session_id)
        return entries[-limit:] if limit < len(entries) else entries

    def delete_session(self, session_id: str) -> None:
        """
        Delete all entries for a session.

        Args:
            session_id: The session identifier
        """
        session_file = self.base_dir / f"{session_id}.jsonl"
        if session_file.exists():
            session_file.unlink()

    def list_sessions(self) -> list[str]:
        """
        List all session identifiers.

        Returns:
            List of session ids
        """
        sessions = []
        for file in self.base_dir.glob("*.jsonl"):
            sessions.append(file.stem)
        return sorted(sessions)

    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: The session identifier

        Returns:
            True if session exists
        """
        session_file = self.base_dir / f"{session_id}.jsonl"
        return session_file.exists()

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        Get session metadata.

        Args:
            session_id: The session identifier

        Returns:
            Session info dict or None if not exists
        """
        entries = self.load_session(session_id)
        if not entries:
            return None

        return {
            "session_id": session_id,
            "message_count": len(entries),
            "first_message": entries[0].timestamp,
            "last_message": entries[-1].timestamp,
        }