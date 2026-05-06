"""
Long-term memory implementation - persistent knowledge storage.
"""

import json
import uuid
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class LongTermEntry:
    """A single long-term memory entry."""

    id: str
    content: str
    category: Literal["fact", "preference", "experience", "task", "note"]
    keywords: list[str]
    source_session: str
    created_at: str
    importance: float = 0.5
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        content: str,
        category: str = "fact",
        keywords: list[str] | None = None,
        source_session: str = "",
        importance: float = 0.5,
        metadata: dict | None = None
    ) -> "LongTermEntry":
        """Create a new long-term memory entry."""
        return cls(
            id=f"ltm_{uuid.uuid4().hex[:8]}",
            content=content,
            category=category,
            keywords=keywords or [],
            source_session=source_session,
            created_at=datetime.now().isoformat(),
            importance=importance,
            metadata=metadata or {}
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "keywords": self.keywords,
            "source_session": self.source_session,
            "created_at": self.created_at,
            "importance": self.importance,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LongTermEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            category=data["category"],
            keywords=data.get("keywords", []),
            source_session=data.get("source_session", ""),
            created_at=data["created_at"],
            importance=data.get("importance", 0.5),
            metadata=data.get("metadata", {})
        )


class LongTermMemory:
    """Long-term memory management with keyword-based search."""

    def __init__(self, storage_path: str = ".nano_agent/long_term_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.entries: list[LongTermEntry] = []
        self._load()

    def _get_storage_file(self) -> Path:
        """Get the storage file path."""
        return self.storage_path / "long_term_memory.jsonl"

    def _load(self) -> None:
        """Load entries from storage."""
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

        # Sort by importance (higher first), then by created_at (newer first)
        self.entries.sort(key=lambda e: (-e.importance, e.created_at), reverse=True)

    def _save(self) -> None:
        """Save all entries to storage."""
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
        metadata: dict | None = None
    ) -> tuple[str, bool]:
        """
        Add or update a long-term memory entry.

        Args:
            content: The memory content
            category: Type of memory (fact, preference, experience, task, note)
            keywords: Keywords for search
            source_session: Session ID where this memory was created
            importance: Importance score (0-1)
            metadata: Additional metadata

        Returns:
            Tuple of (entry_id, is_new) where is_new is True if new entry was created
        """
        # Check for similar existing entry
        similar_entry = self._find_similar_entry(content, keywords, category, metadata)

        if similar_entry:
            # Update existing entry
            similar_entry.content = content
            similar_entry.keywords = keywords or []
            similar_entry.source_session = source_session
            similar_entry.importance = importance
            similar_entry.metadata = metadata or {}
            similar_entry.created_at = datetime.now().isoformat()
            self._save()
            return (similar_entry.id, False)

        # Create new entry
        entry = LongTermEntry.create(
            content=content,
            category=category,
            keywords=keywords,
            source_session=source_session,
            importance=importance,
            metadata=metadata
        )

        self.entries.append(entry)
        self._save()

        return (entry.id, True)

    def search(self, query: str, limit: int = 5) -> list[LongTermEntry]:
        """
        Search for memories using keyword matching (supports Chinese).

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching entries
        """
        # Extract keywords from query
        query_keywords = self._extract_search_keywords(query)

        if not query_keywords:
            return []

        # Score each entry
        scored_entries = []
        for entry in self.entries:
            # Check keyword matches
            entry_keywords = set(k.lower() for k in entry.keywords)
            content_keywords = self._extract_search_keywords(entry.content)

            # Calculate match score
            keyword_matches = len(query_keywords & entry_keywords)
            content_matches = len(query_keywords & content_keywords)

            # Weighted score: keywords worth more than content matches
            score = keyword_matches * 2 + content_matches

            if score > 0:
                # Boost by importance
                final_score = score * (0.5 + entry.importance * 0.5)
                scored_entries.append((final_score, entry))

        # Sort by score (descending)
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        return [entry for _, entry in scored_entries[:limit]]

    def _extract_search_keywords(self, text: str) -> set[str]:
        """
        Extract keywords for search (supports Chinese and English).
        """
        # English stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "here", "there", "when", "where", "why", "how", "all", "each",
            "few", "more", "most", "other", "some", "such", "no", "nor",
            "not", "only", "own", "same", "so", "than", "too", "very",
            "just", "and", "but", "if", "or", "because", "until", "while",
            "this", "that", "these", "those", "i", "me", "my", "myself",
            "we", "our", "ours", "ourselves", "you", "your", "yours",
            "yourself", "yourselves", "he", "him", "his", "himself",
            "she", "her", "hers", "herself", "it", "its", "itself",
            "they", "them", "their", "theirs", "themselves", "what",
            "which", "who", "whom", "this", "that", "am"
        }

        # Chinese stop words
        chinese_stop_words = {
            "的", "是", "在", "了", "和", "与", "或", "也", "都", "就",
            "着", "过", "会", "能", "要", "有", "这", "那", "我", "你",
            "他", "她", "它", "们", "个", "上", "下", "不", "没", "很",
            "把", "被", "给", "让", "对", "为", "以", "及", "等", "但"
        }

        keywords = []

        # Extract English words
        english_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
        keywords.extend([w for w in english_words if w not in stop_words])

        # Extract Chinese segments
        chinese_matches = re.findall(r'[一-鿿]+', text)
        for chars in chinese_matches:
            # Always use sliding window for better matching
            for i in range(len(chars)):
                for length in [4, 3, 2]:
                    if i + length <= len(chars):
                        segment = chars[i:i+length]
                        if segment not in chinese_stop_words:
                            keywords.append(segment)

        return set(k.lower() for k in keywords)

    def _calculate_similarity(self, entry: LongTermEntry, new_keywords: set[str]) -> float:
        """Calculate similarity between entry and new content based on keyword overlap.

        Args:
            entry: Existing memory entry
            new_keywords: Keywords from new content

        Returns:
            Similarity score from 0.0 to 1.0
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
        metadata: dict | None = None
    ) -> LongTermEntry | None:
        """Find existing entry that is similar to new content.

        Args:
            content: New content to store
            keywords: Keywords for new content
            category: Category of new content
            metadata: Metadata of new content

        Returns:
            Similar entry if found, else None
        """
        # Extract keywords from new content
        new_keywords = set(k.lower() for k in keywords) if keywords else self._extract_search_keywords(content)

        for entry in self.entries:
            # Same category required
            if entry.category != category:
                continue

            # Same metadata.type (e.g., user_name, agent_name) is always duplicate
            if metadata and entry.metadata:
                new_type = metadata.get("type")
                existing_type = entry.metadata.get("type")
                if new_type and existing_type and new_type == existing_type:
                    return entry

            # Keyword similarity > 70%
            similarity = self._calculate_similarity(entry, new_keywords)
            if similarity > 0.7:
                return entry

        return None

    def get_all(self) -> list[LongTermEntry]:
        """Get all memory entries."""
        return self.entries.copy()

    def get_by_category(self, category: str) -> list[LongTermEntry]:
        """Get entries by category."""
        return [e for e in self.entries if e.category == category]

    def get_by_id(self, entry_id: str) -> LongTermEntry | None:
        """Get entry by ID."""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def delete(self, entry_id: str) -> bool:
        """
        Delete a memory entry.

        Args:
            entry_id: The entry ID to delete

        Returns:
            True if deleted, False if not found
        """
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                self._save()
                return True
        return False

    def clear(self) -> None:
        """Clear all memories."""
        self.entries = []
        self._save()

    def count(self) -> int:
        """Get total number of memories."""
        return len(self.entries)

    def update_importance(self, entry_id: str, importance: float) -> bool:
        """Update the importance of an entry."""
        entry = self.get_by_id(entry_id)
        if entry:
            entry.importance = max(0.0, min(1.0, importance))
            self._save()
            return True
        return False
