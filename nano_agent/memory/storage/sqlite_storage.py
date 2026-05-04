"""
SQLite storage backend for persistent memory.
"""

import sqlite3
import json
from pathlib import Path
from typing import Any

from .base import BaseStorage, MemoryEntry


class SQLiteStorage(BaseStorage):
    """SQLite-based storage backend for persistent memory."""

    def __init__(self, db_path: str = ".nano_agent/memory.db"):
        """
        Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    message_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id
                ON memory_entries(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON memory_entries(timestamp)
            """)
            conn.commit()

    def save(self, entry: MemoryEntry) -> str:
        """
        Save a memory entry.

        Args:
            entry: The memory entry to save

        Returns:
            The entry id
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_entries
                (id, session_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.session_id,
                entry.role,
                entry.content,
                entry.timestamp,
                json.dumps(entry.metadata)
            ))
            conn.commit()
        return entry.id

    def load_session(self, session_id: str) -> list[MemoryEntry]:
        """
        Load all entries for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of memory entries, ordered by timestamp
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, session_id, role, content, timestamp, metadata
                FROM memory_entries
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))

            entries = []
            for row in cursor.fetchall():
                entries.append(MemoryEntry(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                ))
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
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, session_id, role, content, timestamp, metadata
                FROM memory_entries
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))

            entries = []
            for row in cursor.fetchall():
                entries.append(MemoryEntry(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                ))
            return list(reversed(entries))

    def delete_session(self, session_id: str) -> None:
        """
        Delete all entries for a session.

        Args:
            session_id: The session identifier
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM memory_entries WHERE session_id = ?
            """, (session_id,))
            conn.commit()

    def list_sessions(self) -> list[str]:
        """
        List all session identifiers.

        Returns:
            List of session ids
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT session_id FROM memory_entries
                ORDER BY session_id
            """)
            return [row[0] for row in cursor.fetchall()]

    def session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: The session identifier

        Returns:
            True if session exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM memory_entries WHERE session_id = ?
            """, (session_id,))
            return cursor.fetchone()[0] > 0

    def get_session_info(self, session_id: str) -> dict[str, Any]:
        """
        Get session information.

        Args:
            session_id: The session identifier

        Returns:
            Dictionary with session info
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as message_count,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM memory_entries
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return {
                "session_id": session_id,
                "message_count": row[0],
                "first_message": row[1],
                "last_message": row[2]
            }

    def clear(self) -> None:
        """Clear all entries from the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM memory_entries")
            conn.commit()

    def get_stats(self) -> dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_entries,
                    COUNT(DISTINCT session_id) as total_sessions
                FROM memory_entries
            """)
            row = cursor.fetchone()
            return {
                "total_entries": row[0],
                "total_sessions": row[1],
                "db_path": str(self.db_path)
            }

    def save_summary(self, session_id: str, summary: str, message_count: int) -> None:
        """
        Save session summary.

        Args:
            session_id: The session identifier
            summary: The summary text
            message_count: Number of messages in the session
        """
        from datetime import datetime
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO session_summaries
                (session_id, summary, message_count, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                session_id,
                summary,
                message_count,
                datetime.now().isoformat()
            ))
            conn.commit()

    def load_summary(self, session_id: str) -> dict | None:
        """
        Load session summary.

        Args:
            session_id: The session identifier

        Returns:
            Summary dict or None if not exists
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT session_id, summary, message_count, created_at
                FROM session_summaries
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "summary": row["summary"],
                    "message_count": row["message_count"],
                    "created_at": row["created_at"]
                }
            return None

    def summary_exists(self, session_id: str) -> bool:
        """
        Check if a session summary exists.

        Args:
            session_id: The session identifier

        Returns:
            True if summary exists
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM session_summaries WHERE session_id = ?
            """, (session_id,))
            return cursor.fetchone()[0] > 0