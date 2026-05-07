"""
内存存储迁移工具。
"""

import json
from pathlib import Path
from typing import Optional

from .storage import FileStorage, SQLiteStorage, MemoryEntry


def _safe_str(text: str) -> str:
    """安全转换字符串，移除无效的 Unicode 字符。"""
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
    从文件存储迁移会话到 SQLite 存储。

    参数:
        file_dir: 包含基于文件的会话的目录
        db_path: SQLite 数据库路径
        dry_run: 如为 True，仅报告将要迁移的内容，不实际执行迁移

    返回:
        迁移报告字典
    """
    file_storage = FileStorage(base_dir=file_dir)
    sqlite_storage = SQLiteStorage(db_path=db_path)

    # 获取文件存储中的所有会话
    file_sessions = file_storage.list_sessions()

    # 获取 SQLite 中已存在的会话
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
            # 从文件加载条目
            entries = file_storage.load_session(session_id)

            # 保存到 SQLite（清理内容以处理代理字符）
            for entry in entries:
                # 清理内容以移除无效的 Unicode 字符
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

            # 如存在摘要则迁移
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
    列出文件和 SQLite 存储中的所有会话。

    参数:
        file_dir: 包含基于文件的会话的目录
        db_path: SQLite 数据库路径

    返回:
        包含两种存储源会话的字典
    """
    file_storage = FileStorage(base_dir=file_dir)
    sqlite_storage = SQLiteStorage(db_path=db_path)

    file_sessions = file_storage.list_sessions()
    sqlite_sessions = sqlite_storage.list_sessions()

    # 获取每个会话的信息
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
