"""
Tests for session management functionality.
"""

import pytest
import tempfile
from pathlib import Path

from nano_agent.memory.storage import FileStorage, SQLiteStorage
from nano_agent.memory.storage.base import MemoryEntry


class TestSessionCleanup:
    """Tests for session cleanup functionality."""

    @pytest.fixture
    def file_storage(self, tmp_path):
        """Create a FileStorage instance for testing."""
        return FileStorage(base_dir=str(tmp_path / "memory"))

    @pytest.fixture
    def sqlite_storage(self, tmp_path):
        """Create a SQLiteStorage instance for testing."""
        return SQLiteStorage(db_path=str(tmp_path / "memory.db"))

    def _create_session(self, storage, session_id: str, message_count: int):
        """Helper to create a session with specified message count."""
        for i in range(message_count):
            entry = MemoryEntry.create(
                session_id=session_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}"
            )
            storage.save(entry)

    def test_get_sessions_below_threshold_file(self, file_storage):
        """Test finding low-value sessions in FileStorage."""
        # Create sessions with varying message counts
        self._create_session(file_storage, "session_1", 5)
        self._create_session(file_storage, "session_2", 2)
        self._create_session(file_storage, "session_3", 1)

        low_value = file_storage.get_sessions_below_threshold(3)

        assert "session_2" in low_value  # 2 messages
        assert "session_3" in low_value  # 1 message
        assert "session_1" not in low_value  # 5 messages

    def test_get_sessions_below_threshold_sqlite(self, sqlite_storage):
        """Test finding low-value sessions in SQLiteStorage."""
        # Create sessions with varying message counts
        self._create_session(sqlite_storage, "session_1", 5)
        self._create_session(sqlite_storage, "session_2", 2)
        self._create_session(sqlite_storage, "session_3", 1)

        low_value = sqlite_storage.get_sessions_below_threshold(3)

        assert "session_2" in low_value  # 2 messages
        assert "session_3" in low_value  # 1 message
        assert "session_1" not in low_value  # 5 messages

    def test_get_most_recent_session_file(self, file_storage):
        """Test finding most recent session in FileStorage."""
        import time

        # Create sessions with time gap
        self._create_session(file_storage, "session_old", 2)
        time.sleep(0.1)  # Small delay to ensure different timestamps
        self._create_session(file_storage, "session_new", 2)

        most_recent = file_storage.get_most_recent_session()
        assert most_recent == "session_new"

    def test_get_most_recent_session_sqlite(self, sqlite_storage):
        """Test finding most recent session in SQLiteStorage."""
        import time

        # Create sessions with time gap
        self._create_session(sqlite_storage, "session_old", 2)
        time.sleep(0.1)  # Small delay to ensure different timestamps
        self._create_session(sqlite_storage, "session_new", 2)

        most_recent = sqlite_storage.get_most_recent_session()
        assert most_recent == "session_new"

    def test_get_most_recent_session_empty_file(self, file_storage):
        """Test most recent session when no sessions exist (FileStorage)."""
        assert file_storage.get_most_recent_session() is None

    def test_get_most_recent_session_empty_sqlite(self, sqlite_storage):
        """Test most recent session when no sessions exist (SQLiteStorage)."""
        assert sqlite_storage.get_most_recent_session() is None

    def test_delete_summary_file(self, file_storage):
        """Test deleting session summaries in FileStorage."""
        file_storage.save_summary("session_1", "Test summary", 5)
        assert file_storage.summary_exists("session_1")

        file_storage.delete_summary("session_1")
        assert not file_storage.summary_exists("session_1")

    def test_delete_summary_sqlite(self, sqlite_storage):
        """Test deleting session summaries in SQLiteStorage."""
        sqlite_storage.save_summary("session_1", "Test summary", 5)
        assert sqlite_storage.summary_exists("session_1")

        sqlite_storage.delete_summary("session_1")
        assert not sqlite_storage.summary_exists("session_1")

    def test_delete_session_with_summary_file(self, file_storage):
        """Test deleting session also deletes summary (FileStorage)."""
        self._create_session(file_storage, "session_1", 2)
        file_storage.save_summary("session_1", "Test summary", 2)

        file_storage.delete_session("session_1")
        file_storage.delete_summary("session_1")

        assert not file_storage.session_exists("session_1")
        assert not file_storage.summary_exists("session_1")

    def test_delete_session_with_summary_sqlite(self, sqlite_storage):
        """Test deleting session also deletes summary (SQLiteStorage)."""
        self._create_session(sqlite_storage, "session_1", 2)
        sqlite_storage.save_summary("session_1", "Test summary", 2)

        sqlite_storage.delete_session("session_1")
        sqlite_storage.delete_summary("session_1")

        assert not sqlite_storage.session_exists("session_1")
        assert not sqlite_storage.summary_exists("session_1")

    def test_get_sessions_below_threshold_empty_file(self, file_storage):
        """Test threshold check with no sessions (FileStorage)."""
        assert file_storage.get_sessions_below_threshold(3) == []

    def test_get_sessions_below_threshold_empty_sqlite(self, sqlite_storage):
        """Test threshold check with no sessions (SQLiteStorage)."""
        assert sqlite_storage.get_sessions_below_threshold(3) == []

    def test_delete_summary_nonexistent_file(self, file_storage):
        """Test deleting nonexistent summary doesn't raise error (FileStorage)."""
        # Should not raise an error
        file_storage.delete_summary("nonexistent_session")

    def test_delete_summary_nonexistent_sqlite(self, sqlite_storage):
        """Test deleting nonexistent summary doesn't raise error (SQLiteStorage)."""
        # Should not raise an error
        sqlite_storage.delete_summary("nonexistent_session")
