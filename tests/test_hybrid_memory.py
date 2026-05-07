"""
Tests for hybrid memory functionality.
"""

import pytest

pytestmark = pytest.mark.unit
import tempfile
from pathlib import Path

from nano_agent.memory.long_term import LongTermMemory, LongTermEntry
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.memory.persistent import PersistentMemory
from nano_agent.memory.hybrid import HybridMemory


class TestLongTermEntry:
    """Tests for LongTermEntry dataclass."""

    def test_create_entry(self):
        """Test creating a long-term memory entry."""
        entry = LongTermEntry.create(
            content="User prefers Python over JavaScript",
            category="preference",
            keywords=["python", "javascript", "preference"],
            source_session="session_123",
            importance=0.8
        )

        assert entry.content == "User prefers Python over JavaScript"
        assert entry.category == "preference"
        assert "python" in entry.keywords
        assert entry.importance == 0.8
        assert entry.id.startswith("ltm_")

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        entry = LongTermEntry.create(
            content="Test content",
            category="fact",
            keywords=["test"],
            importance=0.5
        )

        data = entry.to_dict()
        restored = LongTermEntry.from_dict(data)

        assert restored.id == entry.id
        assert restored.content == entry.content
        assert restored.category == entry.category
        assert restored.keywords == entry.keywords
        assert restored.importance == entry.importance


class TestLongTermMemory:
    """Tests for LongTermMemory implementation."""

    def test_add_and_retrieve(self, long_term_memory):
        """Test adding and retrieving memories."""
        entry_id, is_new = long_term_memory.add(
            content="User likes dark mode",
            category="preference",
            keywords=["dark mode", "ui"],
            importance=0.7
        )

        assert entry_id.startswith("ltm_")
        assert is_new is True
        assert long_term_memory.count() == 1

        entries = long_term_memory.get_all()
        assert entries[0].content == "User likes dark mode"

    def test_search_by_keywords(self, long_term_memory):
        """Test keyword-based search."""
        long_term_memory.add(
            content="User prefers Python",
            category="preference",
            keywords=["python", "programming"],
            importance=0.8
        )
        long_term_memory.add(
            content="User lives in Beijing",
            category="fact",
            keywords=["beijing", "location"],
            importance=0.6
        )

        results = long_term_memory.search("python programming")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_search_by_content(self, long_term_memory):
        """Test content-based search."""
        long_term_memory.add(
            content="The project uses React framework",
            category="fact",
            keywords=["react"],
            importance=0.5
        )

        results = long_term_memory.search("React framework")
        assert len(results) >= 1
        assert "React" in results[0].content

    def test_search_importance_boost(self, long_term_memory):
        """Test that importance affects search ranking."""
        long_term_memory.add(
            content="Important fact about user",
            category="fact",
            keywords=["user", "important"],
            importance=0.9
        )
        long_term_memory.add(
            content="Less important note",
            category="note",
            keywords=["user", "note"],
            importance=0.3
        )

        results = long_term_memory.search("user")
        assert len(results) == 2
        # Higher importance should come first
        assert results[0].importance > results[1].importance

    def test_delete_memory(self, long_term_memory):
        """Test deleting a memory."""
        entry_id, is_new = long_term_memory.add(
            content="Test memory",
            category="fact",
            keywords=["test"]
        )

        assert long_term_memory.count() == 1
        success = long_term_memory.delete(entry_id)
        assert success is True
        assert long_term_memory.count() == 0

    def test_delete_nonexistent(self, long_term_memory):
        """Test deleting a nonexistent memory."""
        success = long_term_memory.delete("ltm_nonexistent")
        assert success is False

    def test_persistence(self, temp_dir):
        """Test that memories persist across instances."""
        memory1 = LongTermMemory(storage_path=temp_dir)
        memory1.add(
            content="Persistent memory test",
            category="fact",
            keywords=["test", "persistence"]
        )

        # Create new instance
        memory2 = LongTermMemory(storage_path=temp_dir)
        assert memory2.count() == 1
        assert memory2.get_all()[0].content == "Persistent memory test"

    def test_get_by_category(self, long_term_memory):
        """Test filtering by category."""
        long_term_memory.add("Fact 1", category="fact", keywords=[])
        long_term_memory.add("Pref 1", category="preference", keywords=[])
        long_term_memory.add("Fact 2", category="fact", keywords=[])

        facts = long_term_memory.get_by_category("fact")
        assert len(facts) == 2

        prefs = long_term_memory.get_by_category("preference")
        assert len(prefs) == 1

    def test_update_importance(self, long_term_memory):
        """Test updating importance."""
        entry_id, is_new = long_term_memory.add(
            content="Test",
            category="fact",
            keywords=[],
            importance=0.5
        )

        success = long_term_memory.update_importance(entry_id, 0.9)
        assert success is True

        entry = long_term_memory.get_by_id(entry_id)
        assert entry.importance == 0.9

    def test_clear(self, long_term_memory):
        """Test clearing all memories."""
        long_term_memory.add("Memory 1", category="fact", keywords=[])
        long_term_memory.add("Memory 2", category="fact", keywords=[])

        assert long_term_memory.count() == 2
        long_term_memory.clear()
        assert long_term_memory.count() == 0

    def test_search_chinese(self, long_term_memory):
        """Test Chinese keyword-based search."""
        long_term_memory.add(
            content="用户的名字是天宇",
            category="fact",
            keywords=["名字", "天宇", "用户"],
            importance=0.7
        )
        long_term_memory.add(
            content="用户住在北京",
            category="fact",
            keywords=["北京", "住址"],
            importance=0.6
        )

        # Search with Chinese query
        results = long_term_memory.search("用户的名字")
        assert len(results) >= 1
        assert "天宇" in results[0].content

    def test_search_chinese_auto_extract(self, long_term_memory):
        """Test Chinese search with automatic keyword extraction from content."""
        long_term_memory.add(
            content="用户的名字是天宇",
            category="fact",
            keywords=[],  # Empty keywords, should extract from content
            importance=0.7
        )

        # Search should work even without pre-defined keywords
        results = long_term_memory.search("我的名字")
        assert len(results) >= 1
        assert "天宇" in results[0].content

    def test_extract_search_keywords_chinese(self, long_term_memory):
        """Test _extract_search_keywords for Chinese text."""
        keywords = long_term_memory._extract_search_keywords("用户的名字")

        # Should extract meaningful segments
        assert len(keywords) > 0
        # Stop words should be filtered
        assert "的" not in keywords
        # Should contain meaningful words
        assert "名字" in keywords or "用户" in keywords

    def test_dedup_same_metadata_type(self, long_term_memory):
        """Test that same metadata.type triggers dedup."""
        # Add first user name
        entry_id1, is_new1 = long_term_memory.add(
            content="用户的名字是天宇",
            category="fact",
            keywords=["名字", "天宇"],
            metadata={"type": "user_name", "value": "天宇"}
        )
        assert is_new1 is True

        # Add second user name - should update first
        entry_id2, is_new2 = long_term_memory.add(
            content="用户的名字是王五",
            category="fact",
            keywords=["名字", "王五"],
            metadata={"type": "user_name", "value": "王五"}
        )
        assert is_new2 is False  # Updated existing
        assert entry_id2 == entry_id1  # Same ID
        assert long_term_memory.count() == 1  # Only one entry

        # Content should be updated
        entry = long_term_memory.get_by_id(entry_id1)
        assert "王五" in entry.content

    def test_dedup_keyword_similarity(self, long_term_memory):
        """Test that high keyword similarity triggers dedup."""
        # Add first project info
        entry_id1, is_new1 = long_term_memory.add(
            content="项目: NanoAgent, 技术栈: Python",
            category="fact",
            keywords=["nanoagent", "python", "项目", "技术栈"]
        )
        assert is_new1 is True

        # Add similar project info - should update first
        entry_id2, is_new2 = long_term_memory.add(
            content="项目: NanoAgent, 技术栈: Python, 版本: 1.0",
            category="fact",
            keywords=["nanoagent", "python", "项目", "技术栈", "版本"]
        )
        assert is_new2 is False  # Updated existing
        assert entry_id2 == entry_id1

    def test_no_dedup_different_category(self, long_term_memory):
        """Test that different category does not trigger dedup."""
        # Add as fact
        entry_id1, is_new1 = long_term_memory.add(
            content="用户喜欢Python",
            category="fact",
            keywords=["python", "用户"]
        )
        assert is_new1 is True

        # Add same content as preference - should create new
        entry_id2, is_new2 = long_term_memory.add(
            content="用户喜欢Python",
            category="preference",
            keywords=["python", "用户"]
        )
        assert is_new2 is True  # New entry
        assert entry_id2 != entry_id1
        assert long_term_memory.count() == 2


class TestHybridMemory:
    """Tests for HybridMemory implementation."""

    def test_add_to_working_memory(self, hybrid_memory):
        """Test adding messages to working memory."""
        hybrid_memory.add_user_message("Hello")
        hybrid_memory.add_assistant_message("Hi there!")

        assert len(hybrid_memory) == 3  # system + user + assistant

    def test_memorize_to_long_term(self, hybrid_memory):
        """Test storing in long-term memory."""
        entry_id, is_new = hybrid_memory.memorize(
            content="User prefers dark mode",
            category="preference",
            keywords=["dark mode", "ui"]
        )

        assert entry_id.startswith("ltm_")
        assert is_new is True
        assert hybrid_memory.long_term_memory.count() == 1

    def test_recall_from_long_term(self, hybrid_memory):
        """Test retrieving from long-term memory."""
        hybrid_memory.memorize(
            content="User likes Python",
            category="preference",
            keywords=["python", "programming"]
        )

        results = hybrid_memory.recall("Python programming")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_forget_from_long_term(self, hybrid_memory):
        """Test deleting from long-term memory."""
        entry_id, is_new = hybrid_memory.memorize(
            content="Test memory",
            category="fact"
        )

        assert hybrid_memory.long_term_memory.count() == 1
        success = hybrid_memory.forget(entry_id)
        assert success is True
        assert hybrid_memory.long_term_memory.count() == 0

    def test_clear_working_memory_only(self, hybrid_memory):
        """Test that clear only affects working memory."""
        hybrid_memory.add_user_message("Test message")
        hybrid_memory.memorize("Important fact", category="fact")

        hybrid_memory.clear()

        # Working memory should be cleared (only system message)
        assert len(hybrid_memory) == 1
        # Long-term memory should remain
        assert hybrid_memory.long_term_memory.count() == 1

    def test_get_context(self, hybrid_memory):
        """Test getting context with limit."""
        for i in range(10):
            hybrid_memory.add_user_message(f"Message {i}")

        context = hybrid_memory.get_context(max_messages=5)
        assert len(context) == 5
        assert context[0]["role"] == "system"

    def test_system_prompt_property(self, hybrid_memory):
        """Test that system_prompt property is accessible."""
        # Should be able to read system_prompt
        assert hybrid_memory.system_prompt == "Test prompt"

    def test_set_system_prompt(self, hybrid_memory):
        """Test setting system prompt."""
        hybrid_memory.set_system_prompt("New prompt")

        # Should be reflected in the property
        assert hybrid_memory.system_prompt == "New prompt"

        # Should be reflected in context
        context = hybrid_memory.get_context()
        assert context[0]["role"] == "system"
        assert context[0]["content"] == "New prompt"

    def test_extract_keywords(self, hybrid_memory):
        """Test automatic keyword extraction."""
        keywords = hybrid_memory._extract_keywords(
            "The user prefers Python programming language"
        )

        # Should extract meaningful words (stop words like 'the' should be filtered)
        assert "the" not in keywords  # stop word
        # Should contain some meaningful words
        assert len(keywords) > 0
        # Should contain Python or programming
        assert "python" in keywords or "programming" in keywords

    def test_extract_keywords_chinese(self, hybrid_memory):
        """Test automatic keyword extraction for Chinese text."""
        keywords = hybrid_memory._extract_keywords("用户的名字是天宇")

        # Should extract Chinese segments
        assert len(keywords) > 0
        # Should contain meaningful segments
        assert "名字" in keywords or "天宇" in keywords or "用户" in keywords

    def test_extract_keywords_chinese_with_stop_words(self, hybrid_memory):
        """Test that Chinese stop words are filtered."""
        keywords = hybrid_memory._extract_keywords("我的名字是什么")

        # Stop words should be filtered
        assert "的" not in keywords
        assert "是" not in keywords
        assert "我" not in keywords
        # Should still extract meaningful segments
        assert len(keywords) > 0
        assert "名字" in keywords

    def test_extract_keywords_mixed(self, hybrid_memory):
        """Test keyword extraction for mixed Chinese-English text."""
        keywords = hybrid_memory._extract_keywords("用户使用 Python 进行开发")

        # Should extract both Chinese and English
        assert "python" in keywords
        assert any(k for k in keywords if "用户" in k or "开发" in k)

    def test_new_session(self, hybrid_memory):
        """Test starting a new session."""
        hybrid_memory.add_user_message("Test")
        hybrid_memory.memorize("Important", category="fact")

        old_session = hybrid_memory.session_id
        new_session = hybrid_memory.new_session()

        assert new_session != old_session
        assert len(hybrid_memory) == 1  # Only system message
        # Long-term memory should persist
        assert hybrid_memory.long_term_memory.count() == 1

    def test_session_management_with_persistent_working_memory(self, temp_dir):
        """Test session management when working memory is PersistentMemory."""
        from nano_agent.memory import FileStorage

        # Create hybrid memory with PersistentMemory as working memory
        storage = FileStorage(base_dir=temp_dir)
        working = PersistentMemory(
            storage=storage,
            max_messages=50,
            system_prompt="Test"
        )
        long_term = LongTermMemory(storage_path=temp_dir)
        hybrid = HybridMemory(
            working_memory=working,
            long_term_memory=long_term
        )

        # Add a message and save
        hybrid.add_user_message("Hello")
        session_id = working.session_id

        # Create new session and add a message
        new_id = hybrid.new_session()
        hybrid.add_user_message("New session message")

        # Load old session
        success = hybrid.load_session(session_id)
        assert success is True

        # List sessions (only sessions with messages are listed)
        sessions = hybrid.list_sessions()
        assert session_id in sessions
        assert new_id in sessions


class TestMemoryConfig:
    """Tests for hybrid memory configuration."""

    def test_hybrid_memory_config(self):
        """Test hybrid memory configuration."""
        from nano_agent.config.schema import MemoryConfig

        config = MemoryConfig(
            type="hybrid",
            max_messages=100,
            long_term_storage_path="/custom/long_term",
            auto_extract=False
        )

        assert config.type == "hybrid"
        assert config.max_messages == 100
        assert config.long_term_storage_path == "/custom/long_term"
        assert config.auto_extract is False


class TestCreateMemory:
    """Tests for create_memory factory function."""

    def test_create_hybrid_memory(self):
        """Test creating hybrid memory."""
        from nano_agent.cli.main import create_memory
        from nano_agent.config.schema import Config
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            config = Config()
            config.memory.type = "hybrid"
            config.memory.long_term_storage_path = d

            memory = create_memory(config)
            assert isinstance(memory, HybridMemory)
            assert memory.auto_extract is True

    def test_create_hybrid_memory_no_auto_extract(self):
        """Test creating hybrid memory without auto-extraction."""
        from nano_agent.cli.main import create_memory
        from nano_agent.config.schema import Config
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            config = Config()
            config.memory.type = "hybrid"
            config.memory.long_term_storage_path = d
            config.memory.auto_extract = False

            memory = create_memory(config)
            assert memory.auto_extract is False
