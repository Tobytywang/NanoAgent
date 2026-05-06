"""
Migration tools for memory storage.
"""

import json
from pathlib import Path
from typing import Optional

from .storage import FileStorage, SQLiteStorage, MemoryEntry


def _safe_str(text: str) -> str:
    """Safely convert string, removing invalid Unicode characters."""
    if not text:
        return text
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def migrate_file_to_sqlite(
    file_dir: str = ".nano_agent/memory",
    db_path: str = ".nano_agent/memory.db",
    dry_run: bool = False
) -> dict:
    """
    Migrate sessions from file storage to SQLite storage.

    Args:
        file_dir: Directory containing file-based sessions
        db_path: Path to SQLite database
        dry_run: If True, only report what would be migrated without actually migrating

    Returns:
        Migration report dict
    """
    file_storage = FileStorage(base_dir=file_dir)
    sqlite_storage = SQLiteStorage(db_path=db_path)

    # Get all sessions from file storage
    file_sessions = file_storage.list_sessions()

    # Get existing sessions in SQLite
    sqlite_sessions = set(sqlite_storage.list_sessions())

    report = {
        "total_file_sessions": len(file_sessions),
        "already_in_sqlite": [],
        "to_migrate": [],
        "migrated": [],
        "errors": [],
        "dry_run": dry_run
    }

    for session_id in file_sessions:
        if session_id in sqlite_sessions:
            report["already_in_sqlite"].append(session_id)
            continue

        report["to_migrate"].append(session_id)

        if dry_run:
            continue

        try:
            # Load entries from file
            entries = file_storage.load_session(session_id)

            # Save to SQLite (sanitize content to handle surrogates)
            for entry in entries:
                # Sanitize content to remove invalid Unicode characters
                safe_content = _safe_str(entry.content)
                safe_entry = MemoryEntry(
                    id=entry.id,
                    session_id=entry.session_id,
                    role=entry.role,
                    content=safe_content,
                    timestamp=entry.timestamp,
                    metadata=entry.metadata or {}
                )
                sqlite_storage.save(safe_entry)

            # Migrate summary if exists
            summary = file_storage.load_summary(session_id)
            if summary:
                safe_summary = _safe_str(summary.get("summary", ""))
                sqlite_storage.save_summary(
                    session_id=session_id,
                    summary=safe_summary,
                    message_count=summary.get("message_count", 0)
                )

            report["migrated"].append(session_id)

        except Exception as e:
            report["errors"].append({
                "session_id": session_id,
                "error": str(e)
            })

    return report


def list_all_sessions(
    file_dir: str = ".nano_agent/memory",
    db_path: str = ".nano_agent/memory.db"
) -> dict:
    """
    List all sessions from both file and SQLite storage.

    Args:
        file_dir: Directory containing file-based sessions
        db_path: Path to SQLite database

    Returns:
        Dict with sessions from both sources
    """
    file_storage = FileStorage(base_dir=file_dir)
    sqlite_storage = SQLiteStorage(db_path=db_path)

    file_sessions = file_storage.list_sessions()
    sqlite_sessions = sqlite_storage.list_sessions()

    # Get session info for each
    file_info = {}
    for session_id in file_sessions:
        info = file_storage.get_session_info(session_id)
        if info:
            file_info[session_id] = info

    sqlite_info = {}
    for session_id in sqlite_sessions:
        info = sqlite_storage.get_session_info(session_id)
        if info:
            sqlite_info[session_id] = info

    return {
        "file_storage": {
            "path": file_dir,
            "sessions": file_sessions,
            "info": file_info
        },
        "sqlite_storage": {
            "path": db_path,
            "sessions": sqlite_sessions,
            "info": sqlite_info
        },
        "total_unique_sessions": len(set(file_sessions) | set(sqlite_sessions))
    }
