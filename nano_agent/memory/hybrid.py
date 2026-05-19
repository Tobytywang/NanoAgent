"""
混合内存实现 - 工作内存 + 长期内存。
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import BaseMemory
from .short_term import ShortTermMemory
from .long_term import LongTermMemory, LongTermEntry
from .stopwords import ENGLISH_STOP_WORDS, CHINESE_STOP_WORDS
from .protocols import SessionCapable


@dataclass
class HybridMemory(BaseMemory):
    """
    混合内存：工作内存（短期）+ 长期内存。

    工作内存保存当前对话上下文。
    长期内存跨会话持久化，支持搜索。
    """

    working_memory: ShortTermMemory
    long_term_memory: LongTermMemory
    session_id: str = ""
    auto_extract: bool = True
    _llm: Any = field(default=None, repr=False)

    def __post_init__(self):
        """如未设置则初始化会话 ID。"""
        if not self.session_id:
            import uuid
            self.session_id = f"session_{uuid.uuid4().hex[:8]}"

    def set_llm(self, llm) -> None:
        """设置用于自动提取的 LLM。"""
        self._llm = llm

    # === BaseMemory 接口 ===

    def add(self, message: dict) -> None:
        """添加消息到工作内存。"""
        self.working_memory.add(message)

    def get_all(self) -> list:
        """从工作内存获取所有消息。"""
        return self.working_memory.get_all()

    def clear(self) -> None:
        """清空工作内存（保留长期内存）。"""
        self.working_memory.clear()

    def get_context(self, max_messages: int | None = None) -> list:
        """
        获取 LLM 上下文。

        返回工作内存消息，可选限制数量。
        长期内存通过 recall() 方法单独检索。
        """
        return self.working_memory.get_context(max_messages)

    # === 便捷方法 ===

    def add_user_message(self, content: str) -> None:
        """添加用户消息到工作内存。"""
        self.working_memory.add_user_message(content)

    def add_assistant_message(self, content: str, tool_calls: list | None = None) -> None:
        """添加助手消息到工作内存。"""
        self.working_memory.add_assistant_message(content, tool_calls)

    def add_tool_result(self, tool_call_id: str, content: str, tool_name: str = "unknown") -> None:
        """添加工具结果到工作内存。"""
        self.working_memory.add_tool_result(tool_call_id, content, tool_name)

    def set_system_prompt(self, prompt: str) -> None:
        """设置工作内存中的系统提示。"""
        self.working_memory.set_system_prompt(prompt)

    def set_stable_system_prompt(self, prompt: str) -> None:
        """设置稳定部分 system prompt（用于 prefix caching）。"""
        self.working_memory.set_stable_system_prompt(prompt)

    def get_stable_system_prompt(self) -> str:
        """获取稳定部分 system prompt（用于 prefix caching）。"""
        return self.working_memory.get_stable_system_prompt()

    def get_messages_without_system(self) -> list:
        """获取不含 system prompt 的消息列表。"""
        return self.working_memory.get_messages_without_system()

    @property
    def system_prompt(self) -> str:
        """从工作内存获取系统提示。"""
        return self.working_memory.system_prompt

    def __len__(self) -> int:
        """返回工作内存中的消息数量。"""
        return len(self.working_memory)

    # === 长期内存操作 ===

    def memorize(
        self,
        content: str,
        category: str = "fact",
        keywords: list[str] | None = None,
        importance: float = 0.5,
        metadata: dict | None = None
    ) -> tuple[str, bool]:
        """
        将信息存储到长期内存。

        参数:
            content: 要记忆的信息
            category: 记忆类型（fact, preference, experience, task, note）
            keywords: 搜索关键字（如为 None 则自动提取）
            importance: 重要性评分（0-1）
            metadata: 附加元数据

        返回:
            元组 (entry_id, is_new)，is_new 为 True 表示创建了新条目
        """
        # 如未提供关键字则自动提取
        if keywords is None:
            keywords = self._extract_keywords(content)

        return self.long_term_memory.add(
            content=content,
            category=category,
            keywords=keywords,
            source_session=self.session_id,
            importance=importance,
            metadata=metadata
        )

    def recall(self, query: str, limit: int = 5) -> list[LongTermEntry]:
        """
        搜索长期内存。

        参数:
            query: 搜索查询
            limit: 最大结果数量

        返回:
            匹配的记忆条目列表
        """
        return self.long_term_memory.search(query, limit)

    def get_all_long_term(self) -> list[LongTermEntry]:
        """获取所有长期记忆。"""
        return self.long_term_memory.get_all()

    def forget(self, entry_id: str) -> bool:
        """删除长期记忆条目。"""
        return self.long_term_memory.delete(entry_id)

    def clear_long_term(self) -> None:
        """清空所有长期记忆。"""
        self.long_term_memory.clear()

    # === 自动提取 ===

    def _extract_keywords(self, content: str) -> list[str]:
        """
        从内容中提取关键字（支持中英文）。
        """
        keywords = []

        # 提取英文单词（2字符及以上）
        english_words = re.findall(r'[a-zA-Z]{2,}', content.lower())
        keywords.extend([w for w in english_words if w not in ENGLISH_STOP_WORDS])

        # 提取中文片段（2-4字符滑动窗口）
        chinese_matches = re.findall(r'[一-鿿]+', content)
        for chars in chinese_matches:
            # 始终使用滑动窗口以获得更好的匹配
            for i in range(len(chars)):
                for length in [4, 3, 2]:  # 优先较长的片段
                    if i + length <= len(chars):
                        segment = chars[i:i+length]
                        if segment not in CHINESE_STOP_WORDS:
                            keywords.append(segment)

        # 去重并限制数量（保持顺序）
        keywords = list(dict.fromkeys(keywords))
        return keywords[:15]

    def extract_to_long_term(self, content: str | None = None) -> list[str]:
        """
        使用 LLM 提取重要信息到长期内存。

        参数:
            content: 要分析的内容（如为 None 则使用最近的消息）

        返回:
            提取的条目 ID 列表
        """
        if not self._llm:
            return []

        # 如未提供内容则从最近消息获取
        if content is None:
            messages = self.working_memory.get_all()
            # 获取最近几条用户/助手消息
            recent = [
                m for m in messages[-10:]
                if m.get("role") in ("user", "assistant")
            ]
            content = "\n".join(
                f"{m.get('role')}: {m.get('content', '')}"
                for m in recent
            )

        if not content or len(content) < 50:
            return []

        # 使用 LLM 提取重要信息
        extraction_prompt = f"""Analyze the following conversation and extract important information that should be remembered for future sessions.

Focus on:
- User preferences and settings
- Important facts about the user
- Key decisions or agreements
- Recurring topics or interests

Conversation:
{content}

Output format (JSON array):
[
  {{"content": "...", "category": "fact|preference|experience|task|note", "importance": 0.0-1.0}},
  ...
]

If nothing important to remember, output: []

Only output the JSON array, nothing else."""

        try:
            response, _, _ = self._llm.chat(
                messages=[{"role": "user", "content": extraction_prompt}],
                tools=None
            )

            # 解析响应
            import json
            import re

            # 从响应中提取 JSON
            json_match = re.search(r'\[[\s\S]*\]', response)
            if not json_match:
                return []

            items = json.loads(json_match.group())
            entry_ids = []

            for item in items:
                if isinstance(item, dict) and item.get("content"):
                    entry_id = self.memorize(
                        content=item["content"],
                        category=item.get("category", "fact"),
                        importance=item.get("importance", 0.5)
                    )
                    entry_ids.append(entry_id)

            return entry_ids

        except Exception:
            return []

    # === 会话管理 ===

    def new_session(self) -> str:
        """开始新会话（清空工作内存，保留长期内存）。"""
        if isinstance(self.working_memory, SessionCapable):
            return self.working_memory.new_session()
        else:
            self.session_id = f"session_{uuid.uuid4().hex[:8]}"
            self.working_memory.clear()
            return self.session_id

    def load_session(self, session_id: str) -> bool:
        """
        加载已有会话。

        参数:
            session_id: 要加载的会话 ID

        返回:
            如会话已加载返回 True，未找到返回 False
        """
        if isinstance(self.working_memory, SessionCapable):
            return self.working_memory.load_session(session_id)
        return False

    def list_sessions(self) -> list[str]:
        """列出所有可用会话。"""
        if isinstance(self.working_memory, SessionCapable):
            return self.working_memory.list_sessions()
        return []
