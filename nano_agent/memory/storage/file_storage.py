"""
持久化内存的基于文件的存储实现。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BaseStorage, MemoryEntry


class FileStorage(BaseStorage):
    """使用 JSONL 格式的基于文件的存储。"""

    def __init__(self, base_dir: str = ".nano_agent/memory"):
        """
        初始化文件存储。

        参数:
            base_dir: 存储内存文件的基目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, entry: MemoryEntry) -> str:
        """
        将记忆条目保存到 JSONL 文件。

        参数:
            entry: 要保存的记忆条目

        返回:
            条目 ID
        """
        session_file = self.base_dir / f"{entry.session_id}.jsonl"
        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return entry.id

    def load_session(self, session_id: str) -> list[MemoryEntry]:
        """
        加载会话的所有条目。

        参数:
            session_id: 会话标识符

        返回:
            记忆条目列表，按时间戳排序
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

        # 按时间戳排序
        entries.sort(key=lambda e: e.timestamp)
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
        entries = self.load_session(session_id)
        return entries[-limit:] if limit < len(entries) else entries

    def delete_session(self, session_id: str) -> None:
        """
        删除会话的所有条目。

        参数:
            session_id: 会话标识符
        """
        session_file = self.base_dir / f"{session_id}.jsonl"
        if session_file.exists():
            session_file.unlink()

    def delete_summary(self, session_id: str) -> None:
        """
        删除会话的摘要文件。

        参数:
            session_id: 会话标识符
        """
        summary_file = self.base_dir / f"{session_id}_summary.json"
        if summary_file.exists():
            summary_file.unlink()

    def get_most_recent_session(self) -> str | None:
        """
        基于最后消息时间戳获取最近活动的会话。

        返回:
            最近会话的 ID，如无会话则返回 None
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
        获取消息数量低于阈值的会话。

        参数:
            threshold: 最小消息数量（不包含）

        返回:
            消息数量少于阈值的会话 ID 列表
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
        列出所有会话标识符。

        返回:
            会话 ID 列表
        """
        sessions = []
        for file in self.base_dir.glob("*.jsonl"):
            sessions.append(file.stem)
        return sorted(sessions)

    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在。

        参数:
            session_id: 会话标识符

        返回:
            会话存在返回 True
        """
        session_file = self.base_dir / f"{session_id}.jsonl"
        return session_file.exists()

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        获取会话元数据。

        参数:
            session_id: 会话标识符

        返回:
            会话信息字典，如不存在返回 None
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
        将会话摘要保存到 JSON 文件。

        参数:
            session_id: 会话标识符
            summary: 摘要文本
            message_count: 会话中的消息数量
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
        从 JSON 文件加载会话摘要。

        参数:
            session_id: 会话标识符

        返回:
            摘要字典，如不存在返回 None
        """
        summary_file = self.base_dir / f"{session_id}_summary.json"
        if not summary_file.exists():
            return None

        with open(summary_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def summary_exists(self, session_id: str) -> bool:
        """
        检查会话摘要是否存在。

        参数:
            session_id: 会话标识符

        返回:
            摘要存在返回 True
        """
        summary_file = self.base_dir / f"{session_id}_summary.json"
        return summary_file.exists()
