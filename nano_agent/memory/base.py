"""
记忆基类接口
"""

from abc import ABC, abstractmethod
from typing import Any


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