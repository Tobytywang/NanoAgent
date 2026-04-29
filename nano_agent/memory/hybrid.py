"""
Hybrid memory implementation - working memory + long-term memory.
"""

from dataclasses import dataclass, field
from typing import Any

from .base import BaseMemory
from .short_term import ShortTermMemory
from .long_term import LongTermMemory, LongTermEntry


@dataclass
class HybridMemory(BaseMemory):
    """
    Hybrid memory: working memory (short-term) + long-term memory.

    Working memory holds the current conversation context.
    Long-term memory persists across sessions and can be searched.
    """

    working_memory: ShortTermMemory
    long_term_memory: LongTermMemory
    session_id: str = ""
    auto_extract: bool = True
    _llm: Any = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize session ID if not set."""
        if not self.session_id:
            import uuid
            self.session_id = f"session_{uuid.uuid4().hex[:8]}"

    def set_llm(self, llm) -> None:
        """Set LLM for auto-extraction."""
        self._llm = llm

    # === BaseMemory Interface ===

    def add(self, message: dict) -> None:
        """Add a message to working memory."""
        self.working_memory.add(message)

    def get_all(self) -> list:
        """Get all messages from working memory."""
        return self.working_memory.get_all()

    def clear(self) -> None:
        """Clear working memory (keep long-term memory)."""
        self.working_memory.clear()

    def get_context(self, max_messages: int | None = None) -> list:
        """
        Get context for LLM.

        Returns working memory messages, optionally limited.
        Long-term memory is retrieved separately via recall().
        """
        return self.working_memory.get_context(max_messages)

    # === Convenience Methods ===

    def add_user_message(self, content: str) -> None:
        """Add a user message to working memory."""
        self.working_memory.add_user_message(content)

    def add_assistant_message(self, content: str, tool_calls: list | None = None) -> None:
        """Add an assistant message to working memory."""
        self.working_memory.add_assistant_message(content, tool_calls)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool result to working memory."""
        self.working_memory.add_tool_result(tool_call_id, content)

    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt in working memory."""
        self.working_memory.set_system_prompt(prompt)

    def __len__(self) -> int:
        """Return number of messages in working memory."""
        return len(self.working_memory)

    # === Long-Term Memory Operations ===

    def memorize(
        self,
        content: str,
        category: str = "fact",
        keywords: list[str] | None = None,
        importance: float = 0.5
    ) -> str:
        """
        Store information in long-term memory.

        Args:
            content: The information to remember
            category: Type of memory (fact, preference, experience, task, note)
            keywords: Keywords for search (auto-extracted if None)
            importance: Importance score (0-1)

        Returns:
            The entry ID
        """
        # Auto-extract keywords if not provided
        if keywords is None:
            keywords = self._extract_keywords(content)

        return self.long_term_memory.add(
            content=content,
            category=category,
            keywords=keywords,
            source_session=self.session_id,
            importance=importance
        )

    def recall(self, query: str, limit: int = 5) -> list[LongTermEntry]:
        """
        Search long-term memory.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching memory entries
        """
        return self.long_term_memory.search(query, limit)

    def get_all_long_term(self) -> list[LongTermEntry]:
        """Get all long-term memories."""
        return self.long_term_memory.get_all()

    def forget(self, entry_id: str) -> bool:
        """Delete a long-term memory entry."""
        return self.long_term_memory.delete(entry_id)

    def clear_long_term(self) -> None:
        """Clear all long-term memories."""
        self.long_term_memory.clear()

    # === Auto-Extraction ===

    def _extract_keywords(self, content: str) -> list[str]:
        """
        Extract keywords from content (supports Chinese and English).
        """
        import re

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

        # Chinese stop words (common function words)
        chinese_stop_words = {
            "的", "是", "在", "了", "和", "与", "或", "也", "都", "就",
            "着", "过", "会", "能", "要", "有", "这", "那", "我", "你",
            "他", "她", "它", "们", "个", "上", "下", "不", "没", "很",
            "把", "被", "给", "让", "对", "为", "以", "及", "等", "但"
        }

        keywords = []

        # Extract English words (2+ chars)
        english_words = re.findall(r'[a-zA-Z]{2,}', content.lower())
        keywords.extend([w for w in english_words if w not in stop_words])

        # Extract Chinese segments (2-4 chars sliding window)
        chinese_matches = re.findall(r'[一-鿿]+', content)
        for chars in chinese_matches:
            # Always use sliding window for better matching
            for i in range(len(chars)):
                for length in [4, 3, 2]:  # Prefer longer segments
                    if i + length <= len(chars):
                        segment = chars[i:i+length]
                        if segment not in chinese_stop_words:
                            keywords.append(segment)

        # Deduplicate and limit (preserve order)
        keywords = list(dict.fromkeys(keywords))
        return keywords[:15]

    def extract_to_long_term(self, content: str | None = None) -> list[str]:
        """
        Extract important information to long-term memory using LLM.

        Args:
            content: Content to analyze (uses recent messages if None)

        Returns:
            List of extracted entry IDs
        """
        if not self._llm:
            return []

        # Get content from recent messages if not provided
        if content is None:
            messages = self.working_memory.get_all()
            # Get last few user/assistant messages
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

        # Use LLM to extract important information
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
            response, _ = self._llm.chat(
                messages=[{"role": "user", "content": extraction_prompt}],
                tools=None
            )

            # Parse response
            import json
            import re

            # Extract JSON from response
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

    # === Session Management ===

    def new_session(self) -> str:
        """Start a new session (clear working memory, keep long-term)."""
        if hasattr(self.working_memory, 'new_session'):
            return self.working_memory.new_session()
        else:
            import uuid
            self.session_id = f"session_{uuid.uuid4().hex[:8]}"
            self.working_memory.clear()
            return self.session_id

    def load_session(self, session_id: str) -> bool:
        """
        Load an existing session.

        Args:
            session_id: The session to load

        Returns:
            True if session was loaded, False if not found
        """
        if hasattr(self.working_memory, 'load_session'):
            return self.working_memory.load_session(session_id)
        return False

    def list_sessions(self) -> list[str]:
        """List all available sessions."""
        if hasattr(self.working_memory, 'list_sessions'):
            return self.working_memory.list_sessions()
        return []
