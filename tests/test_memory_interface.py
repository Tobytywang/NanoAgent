"""
Tests for Memory interface consistency.

Ensures all BaseMemory implementations provide the same interface.
This prevents bugs where a method is added to one memory type but not others.
"""

import pytest
import inspect
from abc import ABC

pytestmark = pytest.mark.unit

from nano_agent.memory.base import BaseMemory
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.memory.persistent import PersistentMemory
from nano_agent.memory.hybrid import HybridMemory
from nano_agent.memory.long_term import LongTermMemory
from nano_agent.memory.storage.file_storage import FileStorage


class TestMemoryInterfaceConsistency:
    """Tests to ensure all memory implementations follow the same interface."""

    def get_memory_classes(self) -> list:
        """Get all BaseMemory subclasses."""
        return [ShortTermMemory, PersistentMemory, HybridMemory]

    def get_expected_methods(self) -> set:
        """Get methods that should be implemented by all memory classes."""
        # These are the core methods that all memory implementations should have
        expected = {
            "add",
            "get_all",
            "clear",
            "get_context",
            "add_user_message",
            "add_assistant_message",
            "add_tool_result",
            "set_system_prompt",
            "set_stable_system_prompt",
            "get_stable_system_prompt",
            "__len__",
        }
        return expected

    def test_all_memory_classes_implement_core_methods(self):
        """Verify all memory classes implement the core interface methods."""
        memory_classes = self.get_memory_classes()
        expected_methods = self.get_expected_methods()

        for cls in memory_classes:
            cls_methods = set()
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                cls_methods.add(name)
            # Also include methods from dataclass fields that act as properties
            for name, attr in inspect.getmembers(cls):
                if not name.startswith("_") and not inspect.isfunction(attr):
                    cls_methods.add(name)

            missing = expected_methods - cls_methods
            assert not missing, f"{cls.__name__} missing methods: {missing}"

    def test_short_term_memory_has_stable_system_prompt(self):
        """ShortTermMemory must have stable_system_prompt attribute."""
        memory = ShortTermMemory()
        assert hasattr(memory, "stable_system_prompt")
        memory.set_stable_system_prompt("Test")
        assert memory.get_stable_system_prompt() == "Test"

    def test_persistent_memory_has_stable_system_prompt(self):
        """PersistentMemory must have stable_system_prompt attribute."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_dir=tmpdir)
            memory = PersistentMemory(storage=storage, max_messages=50)
            assert hasattr(memory, "stable_system_prompt")
            memory.set_stable_system_prompt("Test")
            assert memory.get_stable_system_prompt() == "Test"

    def test_hybrid_memory_delegates_stable_system_prompt(self):
        """HybridMemory must delegate stable_system_prompt to working memory."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with ShortTermMemory
            long_term = LongTermMemory()
            working = ShortTermMemory()
            memory = HybridMemory(working_memory=working, long_term_memory=long_term)
            memory.set_stable_system_prompt("Test ShortTerm")
            assert memory.get_stable_system_prompt() == "Test ShortTerm"

            # Test with PersistentMemory (this was the bug)
            storage = FileStorage(base_dir=tmpdir)
            working2 = PersistentMemory(storage=storage, max_messages=50)
            memory2 = HybridMemory(working_memory=working2, long_term_memory=long_term)
            memory2.set_stable_system_prompt("Test Persistent")
            assert memory2.get_stable_system_prompt() == "Test Persistent"

    def test_base_memory_is_abstract(self):
        """BaseMemory should be an abstract class."""
        assert issubclass(BaseMemory, ABC)

    def test_cannot_instantiate_base_memory_directly(self):
        """BaseMemory cannot be instantiated directly."""
        # BaseMemory has abstract methods, so it shouldn't be instantiable
        # This test ensures the abstract methods are properly defined
        abstract_methods = set()
        for name, method in inspect.getmembers(BaseMemory):
            if hasattr(method, "__isabstractmethod__"):
                abstract_methods.add(name)
        # We expect at least some abstract methods
        assert len(abstract_methods) > 0, "BaseMemory should have abstract methods"
