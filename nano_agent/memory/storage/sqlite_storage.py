"""
持久化内存的 SQLite 存储后端。
"""

import sqlite3
import json
from pathlib import Path
from typing import Any

from .base import BaseStorage, MemoryEntry


class SQLiteStorage(BaseStorage):
    """持久化内存的 SQLite 存储后端。"""

    def __init__(self, db_path: str = ".nano_agent/memory.db"):
        """
        初始化 SQLite 存储。

        参数:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库模式。"""
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
        保存记忆条目。

        参数:
            entry: 要保存的记忆条目

        返回:
            条目 ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_entries
                (id, session_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.id,
                    entry.session_id,
                    entry.role,
                    entry.content,
                    entry.timestamp,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()
        return entry.id

    def load_session(self, session_id: str) -> list[MemoryEntry]:
        """
        加载会话的所有条目。

        参数:
            session_id: 会话标识符

        返回:
            记忆条目列表，按时间戳排序
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, session_id, role, content, timestamp, metadata
                FROM memory_entries
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """,
                (session_id,),
            )

            entries = []
            for row in cursor.fetchall():
                entries.append(
                    MemoryEntry(
                        id=row["id"],
                        session_id=row["session_id"],
                        role=row["role"],
                        content=row["content"],
                        timestamp=row["timestamp"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                )
            return entries

    def load_recent(self, session_id: str, limit: int) -> list[MemoryEntry]:
        """
        加载会话的最近条目。

        参数:
            session_id: 会话标识符
            limit: 最大加载条目数

        返回:
            最近的记忆条目列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, session_id, role, content, timestamp, metadata
                FROM memory_entries
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (session_id, limit),
            )

            entries = []
            for row in cursor.fetchall():
                entries.append(
                    MemoryEntry(
                        id=row["id"],
                        session_id=row["session_id"],
                        role=row["role"],
                        content=row["content"],
                        timestamp=row["timestamp"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                )
            return list(reversed(entries))

    def delete_session(self, session_id: str) -> None:
        """
        删除会话的所有条目。

        参数:
            session_id: 会话标识符
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM memory_entries WHERE session_id = ?
            """,
                (session_id,),
            )
            conn.commit()

    def delete_summary(self, session_id: str) -> None:
        """
        删除会话的摘要记录。

        参数:
            session_id: 会话标识符
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM session_summaries WHERE session_id = ?
            """,
                (session_id,),
            )
            conn.commit()

    def get_most_recent_session(self) -> str | None:
        """
        获取最近活动的会话。

        返回:
            最近会话的 ID，如无会话则返回 None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT session_id
                FROM memory_entries
                GROUP BY session_id
                ORDER BY MAX(timestamp) DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            return row[0] if row else None

    def get_sessions_below_threshold(self, threshold: int) -> list[str]:
        """
        获取消息数量低于阈值的会话。

        参数:
            threshold: 最小消息数量（不包含）

        返回:
            消息数量少于阈值的会话 ID 列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT session_id
                FROM memory_entries
                GROUP BY session_id
                HAVING COUNT(*) < ?
            """,
                (threshold,),
            )
            return [row[0] for row in cursor.fetchall()]

    def list_sessions(self) -> list[str]:
        """
        列出所有会话标识符。

        返回:
            会话 ID 列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT session_id FROM memory_entries
                ORDER BY session_id
            """)
            return [row[0] for row in cursor.fetchall()]

    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在。

        参数:
            session_id: 会话标识符

        返回:
            会话存在返回 True
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM memory_entries WHERE session_id = ?
            """,
                (session_id,),
            )
            return cursor.fetchone()[0] > 0

    def get_session_info(self, session_id: str) -> dict[str, Any]:
        """
        获取会话信息。

        参数:
            session_id: 会话标识符

        返回:
            包含会话信息的字典
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as message_count,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message
                FROM memory_entries
                WHERE session_id = ?
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return {
                "session_id": session_id,
                "message_count": row[0],
                "first_message": row[1],
                "last_message": row[2],
            }

    def clear(self) -> None:
        """清空数据库中的所有条目。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM memory_entries")
            conn.commit()

    def get_stats(self) -> dict[str, Any]:
        """
        获取存储统计信息。

        返回:
            包含存储统计的字典
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
                "db_path": str(self.db_path),
            }

    def save_summary(self, session_id: str, summary: str, message_count: int) -> None:
        """
        保存会话摘要。

        参数:
            session_id: 会话标识符
            summary: 摘要文本
            message_count: 会话中的消息数量
        """
        from datetime import datetime

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO session_summaries
                (session_id, summary, message_count, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (session_id, summary, message_count, datetime.now().isoformat()),
            )
            conn.commit()

    def load_summary(self, session_id: str) -> dict | None:
        """
        加载会话摘要。

        参数:
            session_id: 会话标识符

        返回:
            摘要字典，如不存在返回 None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT session_id, summary, message_count, created_at
                FROM session_summaries
                WHERE session_id = ?
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "summary": row["summary"],
                    "message_count": row["message_count"],
                    "created_at": row["created_at"],
                }
            return None

    def summary_exists(self, session_id: str) -> bool:
        """
        检查会话摘要是否存在。

        参数:
            session_id: 会话标识符

        返回:
            摘要存在返回 True
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM session_summaries WHERE session_id = ?
            """,
                (session_id,),
            )
            return cursor.fetchone()[0] > 0
