"""
长期内存实现 - 持久化知识存储。
"""

import json
import math
import uuid
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from .stopwords import ENGLISH_STOP_WORDS, CHINESE_STOP_WORDS
from ..config.schema import DEFAULT_MERGE_TAG

SECONDS_PER_DAY = 86400


def compute_age_days(timestamp: str) -> float:
    """从 ISO 时间戳计算距今天数，解析失败返回 0.0。"""
    try:
        dt = datetime.fromisoformat(timestamp)
        return (datetime.now() - dt).total_seconds() / SECONDS_PER_DAY
    except (ValueError, TypeError):
        return 0.0


def compute_decay_weight(entry: "LongTermEntry", half_life_days: float) -> float:
    """
    计算条目的衰减有效权重 = importance × e^(-λ × age_days)。

    使用 last_mentioned_at 作为衰减基准时间（更近期被提及的条目衰减更少）。
    """
    reference_time = entry.last_mentioned_at or entry.created_at
    age_days = compute_age_days(reference_time)

    if age_days <= 0:
        return entry.importance

    lam = math.log(2) / half_life_days
    decay_factor = math.exp(-lam * age_days)
    return entry.importance * decay_factor


@dataclass
class LongTermEntry:
    """单个长期记忆条目。"""

    id: str
    content: str
    category: Literal["fact", "preference", "experience", "task", "note"]
    keywords: list[str]
    source_session: str
    created_at: str
    importance: float = 0.5
    metadata: dict = field(default_factory=dict)
    mention_count: int = 1
    last_mentioned_at: str = ""

    @classmethod
    def create(
        cls,
        content: str,
        category: str = "fact",
        keywords: list[str] | None = None,
        source_session: str = "",
        importance: float = 0.5,
        metadata: dict | None = None,
    ) -> "LongTermEntry":
        """创建新的长期记忆条目。"""
        now = datetime.now().isoformat()
        return cls(
            id=f"ltm_{uuid.uuid4().hex[:8]}",
            content=content,
            category=category,
            keywords=keywords or [],
            source_session=source_session,
            created_at=now,
            importance=importance,
            metadata=metadata or {},
            mention_count=1,
            last_mentioned_at=now,
        )

    def to_dict(self) -> dict:
        """转换为字典以便序列化。"""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "keywords": self.keywords,
            "source_session": self.source_session,
            "created_at": self.created_at,
            "importance": self.importance,
            "metadata": self.metadata,
            "mention_count": self.mention_count,
            "last_mentioned_at": self.last_mentioned_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LongTermEntry":
        """从字典创建实例。"""
        created_at = data["created_at"]
        return cls(
            id=data["id"],
            content=data["content"],
            category=data["category"],
            keywords=data.get("keywords", []),
            source_session=data.get("source_session", ""),
            created_at=created_at,
            importance=data.get("importance", 0.5),
            metadata=data.get("metadata", {}),
            mention_count=data.get("mention_count", 1),
            last_mentioned_at=data.get("last_mentioned_at", created_at),
        )


class LongTermMemory:
    """长期内存管理，支持基于关键字的搜索。"""

    def __init__(self, storage_path: str = ".nano_agent/long_term_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.entries: list[LongTermEntry] = []
        self._load()

    def _get_storage_file(self) -> Path:
        """获取存储文件路径。"""
        return self.storage_path / "long_term_memory.jsonl"

    def _load(self) -> None:
        """从存储加载条目。"""
        storage_file = self._get_storage_file()
        if not storage_file.exists():
            return

        self.entries = []
        with open(storage_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        self.entries.append(LongTermEntry.from_dict(data))
                    except json.JSONDecodeError:
                        continue

        # 按重要性排序（高优先），然后按创建时间排序（新优先）
        self.entries.sort(key=lambda e: (-e.importance, e.created_at), reverse=True)

    def _save(self) -> None:
        """保存所有条目到存储。"""
        storage_file = self._get_storage_file()
        with open(storage_file, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def add(
        self,
        content: str,
        category: str = "fact",
        keywords: list[str] | None = None,
        source_session: str = "",
        importance: float = 0.5,
        metadata: dict | None = None,
        merge_tag: str | None = None,
    ) -> tuple[str, bool]:
        """
        添加或更新长期记忆条目。

        参数:
            content: 记忆内容
            category: 记忆类型（fact, preference, experience, task, note）
            keywords: 搜索关键字
            source_session: 创建此记忆的会话 ID
            importance: 重要性评分（0-1）
            metadata: 附加元数据
            merge_tag: 合并标注模板

        返回:
            元组 (entry_id, is_new)，is_new 为 True 表示创建了新条目
        """
        if merge_tag is None:
            merge_tag = DEFAULT_MERGE_TAG

        # 检查是否存在相似条目
        similar_entry = self._find_similar_entry(content, keywords, category, metadata)

        if similar_entry:
            now = datetime.now().isoformat()

            similar_entry.mention_count = similar_entry.mention_count + 1

            similar_entry.last_mentioned_at = now

            same_meta_type = (
                metadata
                and similar_entry.metadata
                and metadata.get("type") == similar_entry.metadata.get("type")
                and metadata.get("type") is not None
            )
            if same_meta_type:
                similar_entry.content = content
            elif len(content) > len(similar_entry.content):
                similar_entry.content = (
                    content + " " + merge_tag.format(n=similar_entry.mention_count)
                )
            elif similar_entry.mention_count <= 2:
                similar_entry.content = (
                    similar_entry.content
                    + " "
                    + merge_tag.format(n=similar_entry.mention_count)
                )
            # else: already merged multiple times and new content is not richer — keep existing

            existing_kw = set(k.lower() for k in similar_entry.keywords)
            new_kw = set(k.lower() for k in (keywords or []))
            similar_entry.keywords = list(existing_kw | new_kw)

            similar_entry.importance = max(similar_entry.importance, importance)

            if metadata:
                similar_entry.metadata = {**similar_entry.metadata, **metadata}

            similar_entry.source_session = source_session

            self._save()
            return (similar_entry.id, False)

        # 创建新条目
        entry = LongTermEntry.create(
            content=content,
            category=category,
            keywords=keywords,
            source_session=source_session,
            importance=importance,
            metadata=metadata,
        )

        self.entries.append(entry)
        self._save()

        return (entry.id, True)

    def search(
        self,
        query: str,
        limit: int = 5,
        half_life_days: float | None = None,
    ) -> list[LongTermEntry]:
        """
        使用关键字匹配搜索记忆（支持中文），考虑衰减权重。

        参数:
            query: 搜索查询
            limit: 最大结果数量
            half_life_days: 衰减半衰期（None 表示不衰减）

        返回:
            匹配的条目列表
        """
        # 从查询中提取关键字
        query_keywords = self._extract_search_keywords(query)

        if not query_keywords:
            return []

        # 为每个条目评分
        scored_entries = []
        for entry in self.entries:
            # 检查关键字匹配
            entry_keywords = set(k.lower() for k in entry.keywords)
            content_keywords = self._extract_search_keywords(entry.content)

            # 计算匹配分数
            keyword_matches = len(query_keywords & entry_keywords)
            content_matches = len(query_keywords & content_keywords)

            # 加权评分：关键字匹配权重高于内容匹配
            score = keyword_matches * 2 + content_matches

            if score > 0:
                # Use effective_weight with decay
                if half_life_days is not None:
                    weight = compute_decay_weight(entry, half_life_days)
                else:
                    weight = entry.importance

                # Mention count boost: slight bonus for frequently mentioned (cap 1.5x)
                mention_boost = 1.0 + 0.1 * min(entry.mention_count - 1, 5)
                final_score = score * (0.5 + weight * 0.5) * mention_boost
                scored_entries.append((final_score, entry))

        # 按分数降序排序
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        return [entry for _, entry in scored_entries[:limit]]

    def _extract_search_keywords(self, text: str) -> set[str]:
        """
        提取搜索关键字（支持中英文）。
        """
        keywords = []

        # 提取英文单词
        english_words = re.findall(r"[a-zA-Z]{2,}", text.lower())
        keywords.extend([w for w in english_words if w not in ENGLISH_STOP_WORDS])

        # 提取中文片段
        chinese_matches = re.findall(r"[一-鿿]+", text)
        for chars in chinese_matches:
            # 始终使用滑动窗口以获得更好的匹配
            for i in range(len(chars)):
                for length in [4, 3, 2]:
                    if i + length <= len(chars):
                        segment = chars[i : i + length]
                        if segment not in CHINESE_STOP_WORDS:
                            keywords.append(segment)

        return set(k.lower() for k in keywords)

    def _calculate_similarity(
        self, entry: LongTermEntry, new_keywords: set[str]
    ) -> float:
        """
        基于关键字重叠计算条目与新内容的相似度。

        参数:
            entry: 已有的记忆条目
            new_keywords: 新内容的关键字

        返回:
            相似度评分，范围 0.0 到 1.0
        """
        entry_keywords = set(k.lower() for k in entry.keywords)

        if not entry_keywords or not new_keywords:
            return 0.0

        intersection = len(entry_keywords & new_keywords)
        union = len(entry_keywords | new_keywords)

        return intersection / union if union > 0 else 0.0

    def _find_similar_entry(
        self,
        content: str,
        keywords: list[str] | None,
        category: str,
        metadata: dict | None = None,
    ) -> LongTermEntry | None:
        """
        查找与新内容相似的已有条目。

        参数:
            content: 要存储的新内容
            keywords: 新内容的关键字
            category: 新内容的类别
            metadata: 新内容的元数据

        返回:
            如找到相似条目则返回，否则返回 None
        """
        # 从新内容提取关键字
        new_keywords = (
            set(k.lower() for k in keywords)
            if keywords
            else self._extract_search_keywords(content)
        )

        for entry in self.entries:
            # 要求类别相同
            if entry.category != category:
                continue

            # 元数据中 type 相同（如 user_name、agent_name）则视为重复
            if metadata and entry.metadata:
                new_type = metadata.get("type")
                existing_type = entry.metadata.get("type")
                if new_type and existing_type and new_type == existing_type:
                    return entry

            # 关键字相似度超过 70%
            similarity = self._calculate_similarity(entry, new_keywords)
            if similarity > 0.7:
                return entry

        return None

    def get_all(self) -> list[LongTermEntry]:
        """获取所有记忆条目。"""
        return self.entries.copy()

    def get_by_category(self, category: str) -> list[LongTermEntry]:
        """按类别获取条目。"""
        return [e for e in self.entries if e.category == category]

    def get_by_id(self, entry_id: str) -> LongTermEntry | None:
        """按 ID 获取条目。"""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def delete(self, entry_id: str) -> bool:
        """
        删除记忆条目。

        参数:
            entry_id: 要删除的条目 ID

        返回:
            删除成功返回 True，未找到返回 False
        """
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                self._save()
                return True
        return False

    def delete_batch(self, entry_ids: list[str]) -> int:
        """
        批量删除记忆条目，仅保存一次。

        参数:
            entry_ids: 要删除的条目 ID 列表

        返回:
            实际删除的条目数量
        """
        ids_to_remove = set(entry_ids)
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if e.id not in ids_to_remove]
        removed = original_count - len(self.entries)
        if removed > 0:
            self._save()
        return removed

    def clear(self) -> None:
        """清空所有记忆。"""
        self.entries = []
        self._save()

    def count(self) -> int:
        """获取记忆总数。"""
        return len(self.entries)

    def update_importance(self, entry_id: str, importance: float) -> bool:
        """更新条目的重要性。"""
        entry = self.get_by_id(entry_id)
        if entry:
            entry.importance = max(0.0, min(1.0, importance))
            self._save()
            return True
        return False
