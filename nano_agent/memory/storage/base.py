"""
持久化内存的基础存储接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
import json


@dataclass
class MemoryEntry:
    """持久化存储的单个记忆条目。"""

    id: str
    session_id: str
    role: str  # system, user, assistant, tool
    content: str
    timestamp: str  # ISO 格式日期时间
    metadata: dict = field(default_factory=dict)  # 附加信息（如 tool_calls）

    def to_dict(self) -> dict:
        """转换为字典以便序列化。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        """从字典创建实例。"""
        return cls(**data)

    @classmethod
    def create(
        cls,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None
    ) -> "MemoryEntry":
        """创建带有生成的 ID 和时间戳的新条目。"""
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
    """内存存储后端的抽象基类。"""

    @abstractmethod
    def save(self, entry: MemoryEntry) -> str:
        """
        保存记忆条目。

        参数:
            entry: 要保存的记忆条目

        返回:
            条目 ID
        """
        pass

    @abstractmethod
    def load_session(self, session_id: str) -> list[MemoryEntry]:
        """
        加载会话的所有条目。

        参数:
            session_id: 会话标识符

        返回:
            记忆条目列表，按时间戳排序
        """
        pass

    @abstractmethod
    def load_recent(self, session_id: str, limit: int) -> list[MemoryEntry]:
        """
        加载会话的最近条目。

        参数:
            session_id: 会话标识符
            limit: 最大加载条目数

        返回:
            最近的记忆条目列表
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """
        删除会话的所有条目。

        参数:
            session_id: 会话标识符
        """
        pass

    @abstractmethod
    def list_sessions(self) -> list[str]:
        """
        列出所有会话标识符。

        返回:
            会话 ID 列表
        """
        pass

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在。

        参数:
            session_id: 会话标识符

        返回:
            会话存在返回 True
        """
        pass

    @abstractmethod
    def delete_summary(self, session_id: str) -> None:
        """
        删除会话摘要。

        参数:
            session_id: 会话标识符
        """
        pass

    @abstractmethod
    def get_most_recent_session(self) -> str | None:
        """
        获取最近活动的会话。

        返回:
            最近会话的 ID，如无会话则返回 None
        """
        pass

    @abstractmethod
    def get_sessions_below_threshold(self, threshold: int) -> list[str]:
        """
        获取消息数量低于阈值的会话。

        参数:
            threshold: 最小消息数量（不包含）

        返回:
            消息数量少于阈值的会话 ID 列表
        """
        pass
