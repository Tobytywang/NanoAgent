"""
记忆基类接口
"""

from abc import ABC, abstractmethod
from typing import Any

# 标记消息为临时的 key，PersistentMemory.add() 据此跳过写盘
# 运行时可见但不持久化，不会跨轮次残留
EPHEMERAL_KEY = "ephemeral"


class BaseMemory(ABC):
    """记忆系统抽象基类"""

    @abstractmethod
    def add(self, message: Any) -> None:
        """添加消息到记忆"""
        pass

    @abstractmethod
    def get_all(self) -> list:
        """获取所有消息"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清除所有消息"""
        pass

    @abstractmethod
    def get_context(self, max_items: int | None = None) -> list:
        """获取上下文，可选限制最大条目数"""
        pass

    @abstractmethod
    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示"""
        pass

    def get_stable_system_prompt(self) -> str:
        """获取稳定部分 system prompt（用于 prefix caching）

        默认返回完整 system prompt，子类可覆盖以分离 stable/dynamic。
        """
        # Default implementation: return the system prompt from first message
        messages = self.get_all()
        if messages and messages[0].get("role") == "system":
            return messages[0].get("content", "")
        return ""

    def get_messages_without_system(self) -> list:
        """获取不含 system prompt 的消息列表

        用于 prefix caching 场景，将 system prompt 单独传递。
        """
        return [m for m in self.get_all() if m.get("role") != "system"]
