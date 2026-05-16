"""
持久化内存实现 - 带持久化的对话历史。
"""

import uuid
from dataclasses import dataclass, field
from typing import Literal

from .base import BaseMemory
from .storage.base import BaseStorage, MemoryEntry


@dataclass
class PersistentMemory(BaseMemory):
    """持久化内存：带文件存储的对话历史。"""

    storage: BaseStorage
    session_id: str | None = None
    max_messages: int = 50
    system_prompt: str = "You are a helpful AI assistant."
    _messages: list = field(default_factory=list)
    _loaded: bool = False

    def __post_init__(self):
        """初始化或加载会话。"""
        if self.session_id is None:
            self.session_id = self._generate_session_id()
        self._load_or_init()

    def _generate_session_id(self) -> str:
        """生成唯一的会话 ID。"""
        return f"session_{uuid.uuid4().hex[:8]}"

    def _load_or_init(self) -> None:
        """加载已有会话或初始化新会话。"""
        if self.storage.session_exists(self.session_id):
            entries = self.storage.load_session(self.session_id)
            # 在开头添加系统消息，然后添加已加载的消息
            self._messages = [{"role": "system", "content": self.system_prompt}]
            self._messages.extend([self._entry_to_message(e) for e in entries])
            self._loaded = True
        else:
            self._messages = [{"role": "system", "content": self.system_prompt}]
            self._loaded = False

    def _entry_to_message(self, entry: MemoryEntry) -> dict:
        """将 MemoryEntry 转换为消息字典。"""
        msg = {"role": entry.role, "content": entry.content}
        if entry.metadata:
            # 添加元数据字段，如 tool_calls、tool_call_id
            for key, value in entry.metadata.items():
                msg[key] = value
        return msg

    def _message_to_entry(self, message: dict) -> MemoryEntry:
        """将消息字典转换为 MemoryEntry。"""
        role = message.get("role", "user")
        content = message.get("content", "")

        # 提取元数据（除 role 和 content 之外的所有字段）
        metadata = {k: v for k, v in message.items() if k not in ["role", "content"]}

        return MemoryEntry.create(
            session_id=self.session_id,
            role=role,
            content=content,
            metadata=metadata if metadata else None
        )

    def add(self, message: dict) -> None:
        """添加消息到历史记录并持久化。"""
        self._messages.append(message)
        entry = self._message_to_entry(message)
        self.storage.save(entry)
        self._trim_if_needed()

    def add_user_message(self, content: str) -> None:
        """添加用户消息。"""
        self.add({"role": "user", "content": content})

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list | None = None
    ) -> None:
        """添加助手消息，可选包含工具调用。"""
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.add(msg)

    def add_tool_result(self, tool_call_id: str, content: str, tool_name: str = "unknown") -> None:
        """添加工具执行结果。"""
        self.add({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
            "name": tool_name  # 添加工具名称用于统计
        })

    def get_all(self) -> list:
        """获取所有消息。"""
        return self._messages.copy()

    def clear(self) -> None:
        """清空历史记录（保留系统消息）并删除存储。"""
        self._messages = [{"role": "system", "content": self.system_prompt}]
        self.storage.delete_session(self.session_id)
        self._loaded = False

    def get_context(self, max_messages: int | None = None) -> list:
        """获取上下文，可选限制消息数量。"""
        if max_messages is None:
            return self.get_all()

        if len(self._messages) <= max_messages:
            return self.get_all()

        system_msg = self._messages[0]
        recent = self._messages[-(max_messages - 1):]
        return [system_msg] + recent

    def _trim_if_needed(self) -> None:
        """如超出限制则裁剪旧消息（仅在内存中）。"""
        if len(self._messages) > self.max_messages:
            system_msg = self._messages[0]
            recent = self._messages[-(self.max_messages - 1):]
            self._messages = [system_msg] + recent

    def set_system_prompt(self, prompt: str) -> None:
        """设置或更新系统提示。"""
        self.system_prompt = prompt  # 更新属性
        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = prompt
        else:
            self._messages.insert(0, {"role": "system", "content": prompt})

    def new_session(self) -> str:
        """开始新会话。"""
        self.session_id = self._generate_session_id()
        self._messages = [{"role": "system", "content": self.system_prompt}]
        self._loaded = False
        return self.session_id

    def load_session(self, session_id: str) -> bool:
        """
        加载已有会话。

        参数:
            session_id: 要加载的会话 ID

        返回:
            如会话已加载返回 True，未找到返回 False
        """
        if self.storage.session_exists(session_id):
            self.session_id = session_id
            self._load_or_init()
            return True
        return False

    def list_sessions(self) -> list[str]:
        """列出所有可用会话。"""
        return self.storage.list_sessions()

    def is_loaded(self) -> bool:
        """检查是否为已加载的会话（而非新建）。"""
        return self._loaded

    def __len__(self) -> int:
        """返回消息数量。"""
        return len(self._messages)
