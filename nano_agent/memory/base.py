"""
记忆基类接口
"""

from abc import ABC, abstractmethod
from typing import Any

# 标记消息为临时的 key，PersistentMemory.add() 据此跳过写盘
# 运行时可见但不持久化，不会跨轮次残留
EPHEMERAL_KEY = "ephemeral"


def sanitize_tool_messages(messages: list[dict]) -> list[dict]:
    """Remove orphan tool_calls that have no matching tool result.

    OpenAI requires every assistant message with tool_calls to be followed
    by corresponding tool messages.  Trimming by message count can leave
    tool_calls without their results, causing API 400 errors.

    Returns a new list (does not mutate the input).
    """
    # Collect tool_call_ids that have corresponding tool results
    tool_result_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            tool_result_ids.add(msg["tool_call_id"])

    cleaned: list[dict] = []
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Keep only calls that have matching results
            valid_calls = [
                tc for tc in msg["tool_calls"] if tc.get("id") in tool_result_ids
            ]
            if valid_calls:
                msg_copy = {**msg, "tool_calls": valid_calls}
                cleaned.append(msg_copy)
            # If no valid calls remain, drop this message entirely
        else:
            cleaned.append(msg)

    return cleaned


def demote_summary_messages(messages: list[dict]) -> list[dict]:
    """Demote system-role summary messages to user-role.

    When prefix caching is enabled, the stable system prompt replaces
    the full system prompt.  Any system-role context summary messages
    (from compression) would be discarded.  Demoting them to user role
    preserves them in the conversation so the model doesn't lose context.

    Returns a new list (does not mutate the input).
    """
    return [
        (
            {**msg, "role": "user"}
            if msg.get("role") == "system" and msg.get("name") == "context_summary"
            else msg
        )
        for msg in messages
    ]


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
