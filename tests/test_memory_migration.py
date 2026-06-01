"""
Tests for memory migration module.

Tests the migration from file storage to SQLite storage.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

pytestmark = pytest.mark.unit

from nano_agent.memory.migration import (
    _safe_str,
    migrate_file_to_sqlite,
    list_all_sessions,
)
from nano_agent.memory.storage import MemoryEntry


class TestSafeStr:
    """Tests for _safe_str helper function."""

    def test_safe_str_normal_text(self):
        """Test _safe_str with normal text."""
        text = "Hello World"
        result = _safe_str(text)

        assert result == text

    def test_safe_str_empty_string(self):
        """Test _safe_str with empty string."""
        result = _safe_str("")

        assert result == ""

    def test_safe_str_none(self):
        """Test _safe_str with None."""
        result = _safe_str(None)

        assert result is None

    def test_safe_str_chinese(self):
        """Test _safe_str with Chinese characters."""
        text = "你好世界"
        result = _safe_str(text)

        assert result == text

    def test_safe_str_mixed_content(self):
        """Test _safe_str with mixed content."""
        text = "Hello 你好 World 世界"
        result = _safe_str(text)

        assert result == text

    def test_safe_str_preserves_valid_unicode(self):
        """Test _safe_str preserves valid Unicode."""
        text = "Valid: 中文"  # 中文
        result = _safe_str(text)

        assert result == text


class TestMigrateFileToSQLite:
    """Tests for migrate_file_to_sqlite function."""

    def test_migrate_empty_directory(self, temp_dir):
        """Test migration with no sessions."""
        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        report = migrate_file_to_sqlite(file_dir=str(file_dir), db_path=str(db_path))

        assert report["total_file_sessions"] == 0
        assert report["migrated"] == []
        assert report["errors"] == []

    def test_migrate_single_session(self, temp_dir):
        """Test migrating a single session."""
        from nano_agent.memory.storage import FileStorage, SQLiteStorage

        # Setup file storage with a session
        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        file_storage = FileStorage(base_dir=str(file_dir))
        entry = MemoryEntry.create(
            session_id="test_session", role="user", content="Hello"
        )
        file_storage.save(entry)

        # Run migration
        report = migrate_file_to_sqlite(file_dir=str(file_dir), db_path=str(db_path))

        assert report["total_file_sessions"] == 1
        assert "test_session" in report["migrated"]
        assert report["errors"] == []

        # Verify data in SQLite
        sqlite_storage = SQLiteStorage(db_path=str(db_path))
        sessions = sqlite_storage.list_sessions()
        assert "test_session" in sessions

    def test_migrate_multiple_sessions(self, temp_dir):
        """Test migrating multiple sessions."""
        from nano_agent.memory.storage import FileStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        file_storage = FileStorage(base_dir=str(file_dir))

        # Create multiple sessions
        for i in range(3):
            entry = MemoryEntry.create(
                session_id=f"session_{i}", role="user", content=f"Message {i}"
            )
            file_storage.save(entry)

        # Run migration
        report = migrate_file_to_sqlite(file_dir=str(file_dir), db_path=str(db_path))

        assert report["total_file_sessions"] == 3
        assert len(report["migrated"]) == 3
        assert report["errors"] == []

    def test_migrate_already_exists(self, temp_dir):
        """Test skipping sessions already in SQLite."""
        from nano_agent.memory.storage import FileStorage, SQLiteStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        # Create session in file storage
        file_storage = FileStorage(base_dir=str(file_dir))
        entry = MemoryEntry.create(
            session_id="existing_session", role="user", content="Hello"
        )
        file_storage.save(entry)

        # Create same session in SQLite
        sqlite_storage = SQLiteStorage(db_path=str(db_path))
        sqlite_entry = MemoryEntry.create(
            session_id="existing_session", role="user", content="Already exists"
        )
        sqlite_storage.save(sqlite_entry)

        # Run migration
        report = migrate_file_to_sqlite(file_dir=str(file_dir), db_path=str(db_path))

        assert "existing_session" in report["already_in_sqlite"]
        assert "existing_session" not in report["migrated"]

    def test_migrate_dry_run(self, temp_dir):
        """Test dry run doesn't modify anything."""
        from nano_agent.memory.storage import FileStorage, SQLiteStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        file_storage = FileStorage(base_dir=str(file_dir))
        entry = MemoryEntry.create(
            session_id="test_session", role="user", content="Hello"
        )
        file_storage.save(entry)

        # Run dry run
        report = migrate_file_to_sqlite(
            file_dir=str(file_dir), db_path=str(db_path), dry_run=True
        )

        assert report["dry_run"] is True
        assert "test_session" in report["to_migrate"]
        assert report["migrated"] == []

        # Verify nothing was migrated
        sqlite_storage = SQLiteStorage(db_path=str(db_path))
        sessions = sqlite_storage.list_sessions()
        assert "test_session" not in sessions

    def test_migrate_with_summary(self, temp_dir):
        """Test migrating session with summary."""
        from nano_agent.memory.storage import FileStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        file_storage = FileStorage(base_dir=str(file_dir))
        entry = MemoryEntry.create(
            session_id="session_with_summary", role="user", content="Hello"
        )
        file_storage.save(entry)
        file_storage.save_summary(
            session_id="session_with_summary", summary="Test summary", message_count=1
        )

        # Run migration
        report = migrate_file_to_sqlite(file_dir=str(file_dir), db_path=str(db_path))

        assert "session_with_summary" in report["migrated"]

    def test_migrate_report_structure(self, temp_dir):
        """Test migration report has correct structure."""
        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        report = migrate_file_to_sqlite(file_dir=str(file_dir), db_path=str(db_path))

        assert "total_file_sessions" in report
        assert "already_in_sqlite" in report
        assert "to_migrate" in report
        assert "migrated" in report
        assert "errors" in report
        assert "dry_run" in report


class TestListAllSessions:
    """Tests for list_all_sessions function."""

    def test_list_empty(self, temp_dir):
        """Test listing with no sessions."""
        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        result = list_all_sessions(file_dir=str(file_dir), db_path=str(db_path))

        assert result["file_storage"]["sessions"] == []
        assert result["sqlite_storage"]["sessions"] == []
        assert result["total_unique_sessions"] == 0

    def test_list_file_sessions(self, temp_dir):
        """Test listing file storage sessions."""
        from nano_agent.memory.storage import FileStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        file_storage = FileStorage(base_dir=str(file_dir))
        entry = MemoryEntry.create(
            session_id="file_session", role="user", content="Hello"
        )
        file_storage.save(entry)

        result = list_all_sessions(file_dir=str(file_dir), db_path=str(db_path))

        assert "file_session" in result["file_storage"]["sessions"]
        assert result["total_unique_sessions"] == 1

    def test_list_sqlite_sessions(self, temp_dir):
        """Test listing SQLite storage sessions."""
        from nano_agent.memory.storage import SQLiteStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        sqlite_storage = SQLiteStorage(db_path=str(db_path))
        entry = MemoryEntry.create(
            session_id="sqlite_session", role="user", content="Hello"
        )
        sqlite_storage.save(entry)

        result = list_all_sessions(file_dir=str(file_dir), db_path=str(db_path))

        assert "sqlite_session" in result["sqlite_storage"]["sessions"]
        assert result["total_unique_sessions"] == 1

    def test_list_both_storages(self, temp_dir):
        """Test listing from both storages."""
        from nano_agent.memory.storage import FileStorage, SQLiteStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        # Add to file storage
        file_storage = FileStorage(base_dir=str(file_dir))
        entry1 = MemoryEntry.create(
            session_id="file_session", role="user", content="Hello"
        )
        file_storage.save(entry1)

        # Add to SQLite
        sqlite_storage = SQLiteStorage(db_path=str(db_path))
        entry2 = MemoryEntry.create(
            session_id="sqlite_session", role="user", content="Hello"
        )
        sqlite_storage.save(entry2)

        result = list_all_sessions(file_dir=str(file_dir), db_path=str(db_path))

        assert "file_session" in result["file_storage"]["sessions"]
        assert "sqlite_session" in result["sqlite_storage"]["sessions"]
        assert result["total_unique_sessions"] == 2

    def test_list_returns_session_info(self, temp_dir):
        """Test listing returns session information."""
        from nano_agent.memory.storage import FileStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        file_storage = FileStorage(base_dir=str(file_dir))
        entry = MemoryEntry.create(
            session_id="test_session", role="user", content="Hello"
        )
        file_storage.save(entry)

        result = list_all_sessions(file_dir=str(file_dir), db_path=str(db_path))

        assert "info" in result["file_storage"]
        assert "test_session" in result["file_storage"]["info"]

    def test_list_total_unique_count(self, temp_dir):
        """Test total_unique_sessions is correct."""
        from nano_agent.memory.storage import FileStorage, SQLiteStorage

        file_dir = temp_dir / "memory"
        file_dir.mkdir()
        db_path = temp_dir / "test.db"

        # Add same session to both (simulating migration)
        file_storage = FileStorage(base_dir=str(file_dir))
        entry1 = MemoryEntry.create(
            session_id="shared_session", role="user", content="Hello"
        )
        file_storage.save(entry1)

        sqlite_storage = SQLiteStorage(db_path=str(db_path))
        entry2 = MemoryEntry.create(
            session_id="shared_session", role="user", content="Hello"
        )
        sqlite_storage.save(entry2)

        result = list_all_sessions(file_dir=str(file_dir), db_path=str(db_path))

        # Should count unique sessions
        assert result["total_unique_sessions"] == 1
