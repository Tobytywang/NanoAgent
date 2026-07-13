"""
Tests for persistent memory functionality.
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

pytestmark = pytest.mark.unit

from nano_agent.memory.storage.base import BaseStorage, MemoryEntry
from nano_agent.memory.storage.file_storage import FileStorage
from nano_agent.memory.persistent import PersistentMemory
from nano_agent.memory.short_term import ShortTermMemory


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_create_entry(self):
        """Test creating a memory entry."""
        entry = MemoryEntry.create(
            session_id="test_session", role="user", content="Hello, world!"
        )

        assert entry.session_id == "test_session"
        assert entry.role == "user"
        assert entry.content == "Hello, world!"
        assert entry.id  # Should have generated id
        assert entry.timestamp  # Should have timestamp

    def test_create_entry_with_metadata(self):
        """Test creating entry with metadata."""
        entry = MemoryEntry.create(
            session_id="test",
            role="assistant",
            content="Response",
            metadata={"tool_calls": [{"id": "123"}]},
        )

        assert entry.metadata == {"tool_calls": [{"id": "123"}]}

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        entry = MemoryEntry.create(
            session_id="test", role="user", content="Test message"
        )

        data = entry.to_dict()
        restored = MemoryEntry.from_dict(data)

        assert restored.id == entry.id
        assert restored.session_id == entry.session_id
        assert restored.role == entry.role
        assert restored.content == entry.content
        assert restored.timestamp == entry.timestamp


class TestFileStorage:
    """Tests for FileStorage implementation."""

    def test_init_creates_directory(self, temp_dir):
        """Test that init creates the base directory."""
        base = temp_dir / "memory"
        storage = FileStorage(base_dir=str(base))
        assert base.exists()

    def test_save_and_load_session(self, temp_storage):
        """Test saving and loading a session."""
        entry1 = MemoryEntry.create(session_id="session1", role="user", content="Hello")
        entry2 = MemoryEntry.create(
            session_id="session1", role="assistant", content="Hi there!"
        )

        temp_storage.save(entry1)
        temp_storage.save(entry2)

        entries = temp_storage.load_session("session1")
        assert len(entries) == 2
        assert entries[0].content == "Hello"
        assert entries[1].content == "Hi there!"

    def test_load_nonexistent_session(self, temp_storage):
        """Test loading a session that doesn't exist."""
        entries = temp_storage.load_session("nonexistent")
        assert entries == []

    def test_load_recent(self, temp_storage):
        """Test loading recent entries."""
        for i in range(5):
            entry = MemoryEntry.create(
                session_id="session1", role="user", content=f"Message {i}"
            )
            temp_storage.save(entry)

        recent = temp_storage.load_recent("session1", limit=2)
        assert len(recent) == 2
        assert recent[0].content == "Message 3"
        assert recent[1].content == "Message 4"

    def test_delete_session(self, temp_storage):
        """Test deleting a session."""
        entry = MemoryEntry.create(session_id="session1", role="user", content="Test")
        temp_storage.save(entry)

        assert temp_storage.session_exists("session1")
        temp_storage.delete_session("session1")
        assert not temp_storage.session_exists("session1")

    def test_list_sessions(self, temp_storage):
        """Test listing all sessions."""
        entry1 = MemoryEntry.create(session_id="session1", role="user", content="A")
        entry2 = MemoryEntry.create(session_id="session2", role="user", content="B")

        temp_storage.save(entry1)
        temp_storage.save(entry2)

        sessions = temp_storage.list_sessions()
        assert "session1" in sessions
        assert "session2" in sessions

    def test_session_exists(self, temp_storage):
        """Test checking if session exists."""
        assert not temp_storage.session_exists("nonexistent")

        entry = MemoryEntry.create(session_id="exists", role="user", content="Test")
        temp_storage.save(entry)
        assert temp_storage.session_exists("exists")

    def test_get_session_info(self, temp_storage):
        """Test getting session info."""
        entry = MemoryEntry.create(session_id="session1", role="user", content="Test")
        temp_storage.save(entry)

        info = temp_storage.get_session_info("session1")
        assert info is not None
        assert info["session_id"] == "session1"
        assert info["message_count"] == 1


class TestPersistentMemory:
    """Tests for PersistentMemory implementation."""

    def test_init_new_session(self, temp_storage):
        """Test initializing a new session."""
        memory = PersistentMemory(
            storage=temp_storage, max_messages=50, system_prompt="Test prompt"
        )

        assert memory.session_id  # Should have generated session id
        assert not memory.is_loaded()  # New session, not loaded
        assert len(memory) == 1  # Only system message

    def test_init_with_specific_session_id(self, temp_storage):
        """Test initializing with a specific session id."""
        memory = PersistentMemory(
            storage=temp_storage, session_id="my_session", max_messages=50
        )

        assert memory.session_id == "my_session"

    def test_add_and_persist_messages(self, temp_storage):
        """Test adding messages and persisting them."""
        memory = PersistentMemory(
            storage=temp_storage, max_messages=50, system_prompt="Test"
        )
        session_id = memory.session_id

        memory.add_user_message("Hello")
        memory.add_assistant_message("Hi there!")

        # Create new memory instance with same session and system prompt
        memory2 = PersistentMemory(
            storage=temp_storage,
            session_id=session_id,
            max_messages=50,
            system_prompt="Test",
        )

        assert memory2.is_loaded()  # Should have loaded
        assert len(memory2) == 3  # system + user + assistant

        messages = memory2.get_all()
        assert messages[1]["content"] == "Hello"
        assert messages[2]["content"] == "Hi there!"

    def test_add_tool_result(self, temp_storage):
        """Test adding tool results."""
        memory = PersistentMemory(storage=temp_storage, max_messages=50)

        memory.add_user_message("Test")
        memory.add_assistant_message("", tool_calls=[{"id": "call_123"}])
        memory.add_tool_result("call_123", "Tool output")

        messages = memory.get_all()
        assert len(messages) == 4
        assert messages[3]["role"] == "tool"
        assert messages[3]["tool_call_id"] == "call_123"

    def test_clear(self, temp_storage):
        """Test clearing memory."""
        memory = PersistentMemory(storage=temp_storage, max_messages=50)
        session_id = memory.session_id

        memory.add_user_message("Test")
        assert len(memory) == 2

        memory.clear()
        assert len(memory) == 1  # Only system message
        assert not temp_storage.session_exists(session_id)

    def test_new_session(self, temp_storage):
        """Test starting a new session."""
        memory = PersistentMemory(storage=temp_storage, max_messages=50)
        old_session = memory.session_id

        memory.add_user_message("Test")
        new_session = memory.new_session()

        assert new_session != old_session
        assert len(memory) == 1  # Only system message

    def test_load_session(self, temp_storage):
        """Test loading an existing session."""
        # Create and populate first session
        memory1 = PersistentMemory(storage=temp_storage, max_messages=50)
        session_id = memory1.session_id
        memory1.add_user_message("First message")

        # Create new session
        memory2 = PersistentMemory(storage=temp_storage, max_messages=50)
        memory2.add_user_message("Second message")

        # Load first session
        result = memory2.load_session(session_id)
        assert result is True
        assert memory2.session_id == session_id

        messages = memory2.get_all()
        assert messages[1]["content"] == "First message"

    def test_list_sessions(self, temp_storage):
        """Test listing sessions."""
        memory1 = PersistentMemory(storage=temp_storage, max_messages=50)
        memory1.add_user_message("Session 1")

        memory2 = PersistentMemory(storage=temp_storage, max_messages=50)
        memory2.add_user_message("Session 2")

        sessions = memory1.list_sessions()
        assert len(sessions) == 2

    def test_get_context_with_limit(self, temp_storage):
        """Test getting context with message limit."""
        memory = PersistentMemory(storage=temp_storage, max_messages=50)

        for i in range(10):
            memory.add_user_message(f"Message {i}")

        context = memory.get_context(max_messages=5)
        assert len(context) == 5
        assert context[0]["role"] == "system"  # Always keep system
        assert context[1]["content"] == "Message 6"  # Recent messages

    def test_trim_if_needed(self, temp_storage):
        """Test trimming old messages when exceeding limit."""
        memory = PersistentMemory(storage=temp_storage, max_messages=5)

        for i in range(10):
            memory.add_user_message(f"Message {i}")

        # Memory should be trimmed (in-memory only)
        assert len(memory) <= 5
        messages = memory.get_all()
        assert messages[0]["role"] == "system"  # System message preserved

    def test_set_stable_system_prompt(self, temp_storage):
        """Test setting stable system prompt for prefix caching."""
        memory = PersistentMemory(storage=temp_storage, max_messages=50)

        memory.set_stable_system_prompt("Stable prompt for caching")
        assert memory.stable_system_prompt == "Stable prompt for caching"
        # Full system prompt unchanged
        assert memory.system_prompt == "You are a helpful AI assistant."

    def test_get_stable_system_prompt(self, temp_storage):
        """Test getting stable system prompt."""
        memory = PersistentMemory(storage=temp_storage, max_messages=50)

        # Without stable, returns full system prompt
        assert memory.get_stable_system_prompt() == "You are a helpful AI assistant."

        # With stable, returns stable
        memory.set_stable_system_prompt("Stable prompt")
        assert memory.get_stable_system_prompt() == "Stable prompt"

    def test_stable_system_prompt_persists_across_sessions(self, temp_storage):
        """Test that stable system prompt is an in-memory attribute only."""
        memory = PersistentMemory(
            storage=temp_storage, session_id="test_session", max_messages=50
        )
        memory.set_stable_system_prompt("Stable prompt")
        memory.add_user_message("Hello")

        # Create new instance with same session
        memory2 = PersistentMemory(
            storage=temp_storage, session_id="test_session", max_messages=50
        )
        # stable_system_prompt is NOT persisted (it's regenerated each session)
        assert memory2.stable_system_prompt == ""

    def test_ephemeral_message_not_persisted(self, temp_storage):
        """Ephemeral messages must NOT be saved to storage.

        Regression: PersistentMemory.add() checks metadata.ephemeral
        and skips storage.save(). On session reload, ephemeral messages
        should appear in memory (get_context) but not in the storage file.
        """
        from nano_agent.memory.base import EPHEMERAL_KEY

        mem = PersistentMemory(storage=temp_storage, session_id="ephemeral_test")
        mem.add_user_message("normal message")
        mem.add_user_message("ephemeral msg", metadata={EPHEMERAL_KEY: True})

        # Both should be in memory
        ctx = [m["content"] for m in mem.get_context()]
        assert "normal message" in ctx
        assert "ephemeral msg" in ctx

        # Reload from storage — ephemeral should be absent
        mem2 = PersistentMemory(storage=temp_storage, session_id="ephemeral_test")
        ctx2 = [m["content"] for m in mem2.get_context()]
        assert "normal message" in ctx2
        assert "ephemeral msg" not in ctx2

    def test_load_filters_old_system_messages(self, temp_storage):
        """On session load, [System]-prefixed user messages from pre-fix
        sessions must be filtered out. Normal user/assistant messages
        must be preserved.
        """
        import json, pathlib

        # Write a raw session file simulating pre-fix storage
        sesh_file = pathlib.Path(temp_storage.base_dir) / "session_legacy.jsonl"
        with open(sesh_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "id": "1",
                        "session_id": "session_legacy",
                        "role": "user",
                        "content": "[System] Token 估算偏差过高 (69%)",
                        "timestamp": "",
                        "metadata": {},
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "id": "2",
                        "session_id": "session_legacy",
                        "role": "user",
                        "content": "正常用户消息",
                        "timestamp": "",
                        "metadata": {},
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "id": "3",
                        "session_id": "session_legacy",
                        "role": "assistant",
                        "content": "正常回复",
                        "timestamp": "",
                        "metadata": {},
                    }
                )
                + "\n"
            )

        mem = PersistentMemory(storage=temp_storage, session_id="session_legacy")
        contents = [m["content"] for m in mem.get_context()]

        assert "[System] Token 估算偏差过高 (69%)" not in contents
        assert "正常用户消息" in contents
        assert "正常回复" in contents


class TestMemoryConfig:
    """Tests for memory configuration."""

    def test_default_memory_config(self):
        """Test default memory configuration."""
        from nano_agent.config.schema import MemoryConfig

        config = MemoryConfig()
        assert config.type == "short_term"
        assert config.max_messages == 50
        assert config.storage_type == "file"
        assert config.storage_path == ".nano_agent/memory"
        assert config.session_id is None

    def test_persistent_memory_config(self):
        """Test persistent memory configuration."""
        from nano_agent.config.schema import MemoryConfig

        config = MemoryConfig(
            type="persistent", storage_path="/custom/path", session_id="my_session"
        )
        assert config.type == "persistent"
        assert config.storage_path == "/custom/path"
        assert config.session_id == "my_session"


class TestCreateMemory:
    """Tests for create_memory factory function."""

    def test_create_short_term_memory(self):
        """Test creating short-term memory."""
        from nano_agent.cli.main import create_memory
        from nano_agent.config.schema import Config

        config = Config()
        config.memory.type = "short_term"

        memory = create_memory(config)
        assert isinstance(memory, ShortTermMemory)

    def test_create_persistent_memory(self, temp_dir):
        """Test creating persistent memory."""
        from nano_agent.cli.main import create_memory
        from nano_agent.config.schema import Config

        config = Config()
        config.memory.type = "persistent"
        config.memory.storage_path = str(temp_dir)

        memory = create_memory(config)
        assert isinstance(memory, PersistentMemory)
