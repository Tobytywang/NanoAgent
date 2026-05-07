"""
内存协议定义

定义用于类型检查和接口约束的协议类。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LongTermMemoryCapable(Protocol):
    """
    长期内存能力协议。

    实现此协议的类必须提供 memorize, recall, forget, list_memories 方法。
    """

    def memorize(
        self,
        content: str,
        category: str = "note",
        keywords: list[str] | None = None,
        importance: float = 0.5,
        metadata: dict | None = None
    ) -> tuple[str, bool]:
        """
        存储信息到长期内存。

        Args:
            content: 要存储的内容
            category: 内容类别
            keywords: 关键字列表（可选）
            importance: 重要性分数 (0-1)
            metadata: 额外元数据

        Returns:
            (条目 ID, 是否为新条目) 元组
        """
        ...

    def recall(self, query: str, limit: int = 5) -> list:
        """
        从长期内存中检索相关信息。

        Args:
            query: 搜索查询
            limit: 最大返回条目数

        Returns:
            匹配的内存条目列表
        """
        ...

    def forget(self, memory_id: str) -> bool:
        """
        从长期内存中删除指定条目。

        Args:
            memory_id: 要删除的条目 ID

        Returns:
            删除是否成功
        """
        ...

    def get_all_long_term(self, limit: int = 100) -> list:
        """
        列出长期内存中的所有条目。

        Args:
            limit: 最大返回条目数

        Returns:
            内存条目列表
        """
        ...


@runtime_checkable
class SessionCapable(Protocol):
    """
    会话能力协议。

    实现此协议的类必须支持会话管理操作。
    """

    def new_session(self) -> str:
        """创建新会话并返回会话 ID"""
        ...

    def load_session(self, session_id: str) -> bool:
        """加载指定会话"""
        ...

    def list_sessions(self) -> list[str]:
        """列出所有可用会话"""
        ...
