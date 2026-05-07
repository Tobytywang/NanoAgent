"""
短期记忆实现 - 对话历史管理
"""

from dataclasses import dataclass, field
from typing import Literal
from .base import BaseMemory


@dataclass
class ShortTermMemory(BaseMemory):
    """短期记忆：对话历史管理"""

    max_messages: int = 50  # 最大消息数量
    system_prompt: str = "You are a helpful AI assistant."
    _messages: list = field(default_factory=list)

    def __post_init__(self):
        """用系统消息初始化"""
        if not self._messages:
            self._messages = [{"role": "system", "content": self.system_prompt}]

    def add(self, message: dict) -> None:
        """添加消息到历史"""
        self._messages.append(message)
        self._trim_if_needed()

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add({"role": "user", "content": content})

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list | None = None
    ) -> None:
        """添加助手消息，可选包含工具调用"""
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.add(msg)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """添加工具执行结果"""
        self.add({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })

    def get_all(self) -> list:
        """获取所有消息"""
        return self._messages.copy()

    def clear(self) -> None:
        """清除历史（保留系统消息）"""
        self._messages = [{"role": "system", "content": self.system_prompt}]

    def get_context(self, max_messages: int | None = None) -> list:
        """获取上下文，可选限制最大消息数"""
        if max_messages is None:
            return self.get_all()

        # 始终保留系统消息
        if len(self._messages) <= max_messages:
            return self.get_all()

        system_msg = self._messages[0]
        recent = self._messages[-(max_messages - 1):]
        return [system_msg] + recent

    def _trim_if_needed(self) -> None:
        """超出限制时裁剪旧消息"""
        if len(self._messages) > self.max_messages:
            # 保留系统消息和最近消息
            system_msg = self._messages[0]
            recent = self._messages[-(self.max_messages - 1):]
            self._messages = [system_msg] + recent

    def set_system_prompt(self, prompt: str) -> None:
        """设置或更新系统提示"""
        self.system_prompt = prompt  # 更新属性
        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = prompt
        else:
            self._messages.insert(0, {"role": "system", "content": prompt})

    def __len__(self) -> int:
        """返回消息数量"""
        return len(self._messages)