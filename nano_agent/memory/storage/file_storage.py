"""
File-based storage implementation for persistent memory.
"""

import json
from datetime import datetime
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

    def delete_summary(self, session_id: str) -> None:
        """
        Delete summary file for a session.

        Args:
            session_id: The session identifier
        """
        summary_file = self.base_dir / f"{session_id}_summary.json"
        if summary_file.exists():
            summary_file.unlink()

    def get_most_recent_session(self) -> str | None:
        """
        Get the most recently active session based on last_message timestamp.

        Returns:
            Session ID of most recent session, or None if no sessions exist
        """
        sessions = self.list_sessions()
        if not sessions:
            return None

        most_recent = None
        most_recent_time = None

        for session_id in sessions:
            info = self.get_session_info(session_id)
            if info and info.get("last_message"):
                last_time = info["last_message"]
                if most_recent_time is None or last_time > most_recent_time:
                    most_recent_time = last_time
                    most_recent = session_id

        return most_recent

    def get_sessions_below_threshold(self, threshold: int) -> list[str]:
        """
        Get sessions with message count below threshold.

        Args:
            threshold: Minimum message count (exclusive)

        Returns:
            List of session IDs with fewer messages than threshold
        """
        sessions = self.list_sessions()
        low_value = []

        for session_id in sessions:
            info = self.get_session_info(session_id)
            if info and info.get("message_count", 0) < threshold:
                low_value.append(session_id)

        return low_value

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

    def save_summary(self, session_id: str, summary: str, message_count: int) -> None:
        """
        Save session summary to a JSON file.

        Args:
            session_id: The session identifier
            summary: The summary text
            message_count: Number of messages in the session
        """
        summary_file = self.base_dir / f"{session_id}_summary.json"
        data = {
            "session_id": session_id,
            "summary": summary,
            "message_count": message_count,
            "created_at": datetime.now().isoformat(),
        }
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_summary(self, session_id: str) -> Optional[dict]:
        """
        Load session summary from a JSON file.

        Args:
            session_id: The session identifier

        Returns:
            Summary dict or None if not exists
        """
        summary_file = self.base_dir / f"{session_id}_summary.json"
        if not summary_file.exists():
            return None

        with open(summary_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def summary_exists(self, session_id: str) -> bool:
        """
        Check if a session summary exists.

        Args:
            session_id: The session identifier

        Returns:
            True if summary exists
        """
        summary_file = self.base_dir / f"{session_id}_summary.json"
        return summary_file.exists()