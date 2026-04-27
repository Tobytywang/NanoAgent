"""
Tests for hybrid memory functionality.
"""

import pytest
import tempfile
from pathlib import Path

from nano_agent.memory.long_term import LongTermMemory, LongTermEntry
from nano_agent.memory.short_term import ShortTermMemory
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

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def long_term_memory(self, temp_dir):
        """Create a LongTermMemory instance."""
        return LongTermMemory(storage_path=temp_dir)

    def test_add_and_retrieve(self, long_term_memory):
        """Test adding and retrieving memories."""
        entry_id = long_term_memory.add(
            content="User likes dark mode",
            category="preference",
            keywords=["dark mode", "ui"],
            importance=0.7
        )

        assert entry_id.startswith("ltm_")
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
        entry_id = long_term_memory.add(
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
        entry_id = long_term_memory.add(
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


class TestHybridMemory:
    """Tests for HybridMemory implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def hybrid_memory(self, temp_dir):
        """Create a HybridMemory instance."""
        working = ShortTermMemory(max_messages=50, system_prompt="Test prompt")
        long_term = LongTermMemory(storage_path=temp_dir)
        return HybridMemory(
            working_memory=working,
            long_term_memory=long_term
        )

    def test_add_to_working_memory(self, hybrid_memory):
        """Test adding messages to working memory."""
        hybrid_memory.add_user_message("Hello")
        hybrid_memory.add_assistant_message("Hi there!")

        assert len(hybrid_memory) == 3  # system + user + assistant

    def test_memorize_to_long_term(self, hybrid_memory):
        """Test storing in long-term memory."""
        entry_id = hybrid_memory.memorize(
            content="User prefers dark mode",
            category="preference",
            keywords=["dark mode", "ui"]
        )

        assert entry_id.startswith("ltm_")
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
        entry_id = hybrid_memory.memorize(
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
