"""
Tests for v0.8.12 - Memory Decay and Deduplication.
Covers: LongTermEntry new fields, compute_decay_weight, enhanced dedup in add(),
search with decay, MemoryGC, and HybridMemory GC integration.

v0.8.13 - Adds eviction tests: capacity-based cleanup, protected categories,
mention count protection, GCResult eviction fields.
"""

import math
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from nano_agent.memory.long_term import (
    LongTermEntry,
    LongTermMemory,
    compute_decay_weight,
)
from nano_agent.memory.gc import MemoryGC, GCResult
from nano_agent.config.schema import MemoryGCConfig


def _make_mock_ltm(entries):
    """Create a mock LongTermMemory with working delete_batch/count/get_all."""
    ltm = LongTermMemory.__new__(LongTermMemory)
    ltm.entries = list(entries)
    ltm._save = MagicMock()
    ltm.delete_batch = MagicMock(
        side_effect=lambda ids: (
            setattr(ltm, "entries", [e for e in ltm.entries if e.id not in set(ids)])
            or len(ids)
        )
    )
    ltm.count = MagicMock(side_effect=lambda: len(ltm.entries))
    ltm.get_all = MagicMock(side_effect=lambda: list(ltm.entries))
    return ltm


# ---------------------------------------------------------------------------
# TestLongTermEntryCompat
# ---------------------------------------------------------------------------


class TestLongTermEntryCompat:
    """Backward compatibility for LongTermEntry with new fields."""

    def test_create_has_new_fields(self):
        entry = LongTermEntry.create(content="test", keywords=["k1"])
        assert entry.mention_count == 1
        assert entry.last_mentioned_at != ""
        assert entry.last_mentioned_at == entry.created_at

    def test_to_dict_includes_new_fields(self):
        entry = LongTermEntry.create(content="test")
        d = entry.to_dict()
        assert "mention_count" in d
        assert "last_mentioned_at" in d
        assert d["mention_count"] == 1

    def test_from_dict_backward_compat(self):
        """Old entries without mention_count/last_mentioned_at should still load."""
        old_data = {
            "id": "ltm_abc",
            "content": "old entry",
            "category": "fact",
            "keywords": ["k1"],
            "source_session": "s1",
            "created_at": "2024-01-01T00:00:00",
            "importance": 0.7,
            "metadata": {},
        }
        entry = LongTermEntry.from_dict(old_data)
        assert entry.mention_count == 1
        assert entry.last_mentioned_at == entry.created_at

    def test_from_dict_with_new_fields(self):
        data = {
            "id": "ltm_abc",
            "content": "new entry",
            "category": "fact",
            "keywords": ["k1"],
            "source_session": "s1",
            "created_at": "2024-01-01T00:00:00",
            "importance": 0.7,
            "metadata": {},
            "mention_count": 5,
            "last_mentioned_at": "2024-06-01T00:00:00",
        }
        entry = LongTermEntry.from_dict(data)
        assert entry.mention_count == 5
        assert entry.last_mentioned_at == "2024-06-01T00:00:00"


# ---------------------------------------------------------------------------
# TestDecayWeight
# ---------------------------------------------------------------------------


class TestDecayWeight:
    """Test compute_decay_weight with various ages and half-lives."""

    def _make_entry(self, days_ago: float, importance: float = 0.5) -> LongTermEntry:
        created = (datetime.now() - timedelta(days=days_ago)).isoformat()
        return LongTermEntry(
            id="ltm_test",
            content="test",
            category="fact",
            keywords=[],
            source_session="s1",
            created_at=created,
            importance=importance,
            last_mentioned_at=created,
        )

    def test_fresh_entry_weight_equals_importance(self):
        """Age = 0 should yield weight = importance."""
        entry = self._make_entry(days_ago=0)
        weight = compute_decay_weight(entry, half_life_days=30.0)
        assert abs(weight - 0.5) < 0.01

    def test_half_life_decay(self):
        """After one half-life, weight should be ~50% of importance."""
        entry = self._make_entry(days_ago=30, importance=1.0)
        weight = compute_decay_weight(entry, half_life_days=30.0)
        assert abs(weight - 0.5) < 0.05

    def test_two_half_lives(self):
        """After two half-lives, weight should be ~25% of importance."""
        entry = self._make_entry(days_ago=60, importance=1.0)
        weight = compute_decay_weight(entry, half_life_days=30.0)
        assert abs(weight - 0.25) < 0.05

    def test_importance_scaling(self):
        """Higher importance → higher effective weight at same age."""
        entry_high = self._make_entry(days_ago=30, importance=1.0)
        entry_low = self._make_entry(days_ago=30, importance=0.2)
        w_high = compute_decay_weight(entry_high, half_life_days=30.0)
        w_low = compute_decay_weight(entry_low, half_life_days=30.0)
        assert w_high > w_low
        assert abs(w_high / w_low - 5.0) < 0.1  # Ratio matches importance ratio

    def test_invalid_timestamp_fallback(self):
        """Invalid timestamp should fall back to weight = importance."""
        entry = LongTermEntry(
            id="ltm_test",
            content="test",
            category="fact",
            keywords=[],
            source_session="s1",
            created_at="not-a-date",
            importance=0.8,
            last_mentioned_at="not-a-date",
        )
        weight = compute_decay_weight(entry, half_life_days=30.0)
        assert abs(weight - 0.8) < 0.01

    def test_last_mentioned_at_used_for_decay(self):
        """Decay should use last_mentioned_at, not created_at."""
        now = datetime.now()
        entry = LongTermEntry(
            id="ltm_test",
            content="test",
            category="fact",
            keywords=[],
            source_session="s1",
            created_at=(now - timedelta(days=60)).isoformat(),
            importance=1.0,
            last_mentioned_at=(now - timedelta(days=5)).isoformat(),
        )
        weight = compute_decay_weight(entry, half_life_days=30.0)
        # Should be ~0.89 (5-day decay), NOT ~0.25 (60-day decay)
        assert weight > 0.7


# ---------------------------------------------------------------------------
# TestEnhancedDedup
# ---------------------------------------------------------------------------


class TestEnhancedDedup:
    """Test enhanced merge behavior in LongTermMemory.add()."""

    def setup_method(self):
        self.ltm = LongTermMemory.__new__(LongTermMemory)
        self.ltm.entries = []
        self.ltm._save = MagicMock()

    def test_mention_count_increments(self):
        """Adding similar content should increment mention_count."""
        self.ltm.add("I like Python", keywords=["python"], importance=0.5)
        entry_id, is_new = self.ltm.add(
            "I like Python", keywords=["python"], importance=0.5
        )
        assert is_new is False
        assert self.ltm.entries[0].mention_count == 2

    def test_last_mentioned_at_updates(self):
        """last_mentioned_at should be updated on merge."""
        self.ltm.add("I like Python", keywords=["python"], importance=0.5)
        old_last_mentioned = self.ltm.entries[0].last_mentioned_at
        self.ltm.add("I like Python", keywords=["python"], importance=0.5)
        assert self.ltm.entries[0].last_mentioned_at >= old_last_mentioned

    def test_merge_content_keeps_longer(self):
        """Merge should keep the more complete content."""
        self.ltm.add("I like Python", keywords=["python"], importance=0.5)
        self.ltm.add(
            "I really like Python programming language",
            keywords=["python"],
            importance=0.5,
        )
        assert "Python programming language" in self.ltm.entries[0].content
        assert "[merged" in self.ltm.entries[0].content

    def test_merge_keywords_union(self):
        """Merge should take union of keywords."""
        # Use metadata type match to trigger merge (bypasses Jaccard threshold)
        self.ltm.add(
            "I like Python",
            keywords=["python"],
            importance=0.5,
            metadata={"type": "preference"},
        )
        self.ltm.add(
            "I like Python",
            keywords=["python", "coding"],
            importance=0.5,
            metadata={"type": "preference"},
        )
        assert len(self.ltm.entries) == 1, "Should merge into one entry"
        kw_set = set(k.lower() for k in self.ltm.entries[0].keywords)
        assert "python" in kw_set
        assert "coding" in kw_set

    def test_merge_importance_takes_max(self):
        """Merge should take max importance."""
        self.ltm.add("I like Python", keywords=["python"], importance=0.3)
        self.ltm.add("I like Python", keywords=["python"], importance=0.8)
        assert self.ltm.entries[0].importance == 0.8

    def test_merge_tag_custom(self):
        """Custom merge tag should be used."""
        self.ltm.add("I like Python", keywords=["python"], importance=0.5)
        self.ltm.add(
            "I like Python",
            keywords=["python"],
            importance=0.5,
            merge_tag="[已合并{n}条相似]",
        )
        assert "[已合并2条相似]" in self.ltm.entries[0].content

    def test_new_entry_unaffected(self):
        """Dissimilar content should create a new entry normally."""
        self.ltm.add("I like Python", keywords=["python"], importance=0.5)
        entry_id, is_new = self.ltm.add(
            "The sky is blue", keywords=["sky", "blue"], importance=0.5
        )
        assert is_new is True
        assert len(self.ltm.entries) == 2


# ---------------------------------------------------------------------------
# TestSearchWithDecay
# ---------------------------------------------------------------------------


class TestSearchWithDecay:
    """Test search() with half_life_days parameter."""

    def setup_method(self):
        self.ltm = LongTermMemory.__new__(LongTermMemory)
        self.ltm.entries = []
        self.ltm._save = MagicMock()
        # Stub _extract_search_keywords
        self.ltm._extract_search_keywords = lambda text: set(
            w.lower() for w in text.split() if len(w) > 2
        )

    def test_new_entry_ranks_higher_than_old(self):
        """With decay enabled, newer entries should rank higher."""
        now = datetime.now()
        self.ltm.entries = [
            LongTermEntry(
                id="old",
                content="python programming language",
                category="fact",
                keywords=["python"],
                source_session="s1",
                created_at=(now - timedelta(days=90)).isoformat(),
                importance=0.5,
                last_mentioned_at=(now - timedelta(days=90)).isoformat(),
            ),
            LongTermEntry(
                id="new",
                content="python data analysis framework",
                category="fact",
                keywords=["python"],
                source_session="s1",
                created_at=(now - timedelta(days=1)).isoformat(),
                importance=0.5,
                last_mentioned_at=(now - timedelta(days=1)).isoformat(),
            ),
        ]

        results = self.ltm.search("python", limit=2, half_life_days=30.0)
        assert len(results) == 2
        assert results[0].id == "new"

    def test_no_decay_when_none(self):
        """half_life_days=None should not apply decay."""
        now = datetime.now()
        self.ltm.entries = [
            LongTermEntry(
                id="old",
                content="python programming language",
                category="fact",
                keywords=["python"],
                source_session="s1",
                created_at=(now - timedelta(days=90)).isoformat(),
                importance=0.8,
                last_mentioned_at=(now - timedelta(days=90)).isoformat(),
            ),
            LongTermEntry(
                id="new",
                content="python data analysis",
                category="fact",
                keywords=["python"],
                source_session="s1",
                created_at=(now - timedelta(days=1)).isoformat(),
                importance=0.5,
                last_mentioned_at=(now - timedelta(days=1)).isoformat(),
            ),
        ]

        # Without decay, higher importance wins
        results = self.ltm.search("python", limit=2, half_life_days=None)
        assert results[0].id == "old"

    def test_mention_count_boost(self):
        """Entries with higher mention_count should get slight boost."""
        now = datetime.now()
        self.ltm.entries = [
            LongTermEntry(
                id="mentioned_once",
                content="python framework",
                category="fact",
                keywords=["python"],
                source_session="s1",
                created_at=now.isoformat(),
                importance=0.5,
                mention_count=1,
                last_mentioned_at=now.isoformat(),
            ),
            LongTermEntry(
                id="mentioned_many",
                content="python framework",
                category="fact",
                keywords=["python"],
                source_session="s1",
                created_at=now.isoformat(),
                importance=0.5,
                mention_count=5,
                last_mentioned_at=now.isoformat(),
            ),
        ]

        results = self.ltm.search("python", limit=2, half_life_days=30.0)
        assert results[0].id == "mentioned_many"


# ---------------------------------------------------------------------------
# TestMemoryGC
# ---------------------------------------------------------------------------


class TestMemoryGC:
    """Test MemoryGC cleanup behavior."""

    def test_gc_disabled_no_cleanup(self):
        """gc_enabled=False should not remove anything."""
        config = MemoryGCConfig(gc_enabled=False)
        gc = MemoryGC(config)
        entry = LongTermEntry(
            id="test",
            content="test",
            category="fact",
            keywords=[],
            source_session="s1",
            created_at="2024-01-01T00:00:00",
            importance=0.5,
            last_mentioned_at="2024-01-01T00:00:00",
        )
        ltm = _make_mock_ltm([entry])
        result = gc.run(ltm)
        assert result.entries_removed == 0
        ltm.delete_batch.assert_not_called()

    def test_gc_removes_low_weight_old_entries(self):
        """Entries with effective_weight < threshold and age > min_age_days should be removed."""
        now = datetime.now()
        old_decayed = LongTermEntry(
            id="old_decayed",
            content="forgotten fact",
            category="fact",
            keywords=["old"],
            source_session="s1",
            created_at=(now - timedelta(days=100)).isoformat(),
            importance=0.01,
            last_mentioned_at=(now - timedelta(days=100)).isoformat(),
        )
        fresh = LongTermEntry(
            id="fresh",
            content="recent fact",
            category="fact",
            keywords=["recent"],
            source_session="s1",
            created_at=(now - timedelta(days=1)).isoformat(),
            importance=0.8,
            last_mentioned_at=(now - timedelta(days=1)).isoformat(),
        )

        ltm = _make_mock_ltm([old_decayed, fresh])
        config = MemoryGCConfig(gc_enabled=True, gc_threshold=0.05, gc_min_age_days=7)
        gc = MemoryGC(config)
        result = gc.run(ltm)

        assert result.entries_removed == 1
        assert "old_decayed" in result.removed_ids
        assert "fresh" not in result.removed_ids

    def test_gc_preserves_young_entries(self):
        """Entries younger than gc_min_age_days should not be removed even with low weight."""
        now = datetime.now()
        young = LongTermEntry(
            id="young",
            content="just added",
            category="fact",
            keywords=["new"],
            source_session="s1",
            created_at=(now - timedelta(days=2)).isoformat(),
            importance=0.01,
            last_mentioned_at=(now - timedelta(days=2)).isoformat(),
        )

        ltm = _make_mock_ltm([young])
        config = MemoryGCConfig(gc_enabled=True, gc_threshold=0.05, gc_min_age_days=7)
        gc = MemoryGC(config)
        result = gc.run(ltm)

        assert result.entries_removed == 0
        ltm.delete_batch.assert_not_called()


# ---------------------------------------------------------------------------
# TestHybridMemoryGC
# ---------------------------------------------------------------------------


class TestHybridMemoryGC:
    """Test HybridMemory GC integration."""

    def test_recall_passes_half_life_days(self):
        """When decay is enabled, recall should pass half_life_days to search."""
        from nano_agent.memory.hybrid import HybridMemory
        from nano_agent.memory.short_term import ShortTermMemory

        config = MemoryGCConfig(decay_enabled=True, decay_half_life_days=45.0)
        stm = ShortTermMemory()
        ltm = MagicMock()
        ltm.search = MagicMock(return_value=[])

        hm = HybridMemory(working_memory=stm, long_term_memory=ltm, session_id="test")
        hm.set_memory_gc_config(config)
        hm.recall("query")

        ltm.search.assert_called_once_with("query", 5, half_life_days=45.0)

    def test_recall_no_decay_when_disabled(self):
        """When decay is disabled, recall should pass half_life_days=None."""
        from nano_agent.memory.hybrid import HybridMemory
        from nano_agent.memory.short_term import ShortTermMemory

        config = MemoryGCConfig(decay_enabled=False)
        stm = ShortTermMemory()
        ltm = MagicMock()
        ltm.search = MagicMock(return_value=[])

        hm = HybridMemory(working_memory=stm, long_term_memory=ltm, session_id="test")
        hm.set_memory_gc_config(config)
        hm.recall("query")

        ltm.search.assert_called_once_with("query", 5, half_life_days=None)

    def test_run_gc_delegates(self):
        """run_gc should delegate to MemoryGC."""
        from nano_agent.memory.hybrid import HybridMemory
        from nano_agent.memory.short_term import ShortTermMemory

        config = MemoryGCConfig(gc_enabled=True)
        stm = ShortTermMemory()
        ltm = MagicMock()
        ltm.get_all = MagicMock(return_value=[])
        ltm.count = MagicMock(return_value=0)
        ltm.delete_batch = MagicMock(return_value=0)

        hm = HybridMemory(working_memory=stm, long_term_memory=ltm, session_id="test")
        hm.set_memory_gc_config(config)
        result = hm.run_gc()

        assert result is not None
        assert result.entries_removed == 0

    def test_run_gc_no_config_returns_none(self):
        """run_gc without config should return None."""
        from nano_agent.memory.hybrid import HybridMemory
        from nano_agent.memory.short_term import ShortTermMemory

        stm = ShortTermMemory()
        ltm = MagicMock()

        hm = HybridMemory(working_memory=stm, long_term_memory=ltm, session_id="test")
        result = hm.run_gc()

        assert result is None


# ---------------------------------------------------------------------------
# TestGCResultEvictionFields (v0.8.13)
# ---------------------------------------------------------------------------


class TestGCResultEvictionFields:
    """Test GCResult eviction fields default correctly."""

    def test_default_eviction_fields(self):
        result = GCResult(
            entries_before=10,
            entries_removed=2,
            entries_after=8,
            removed_ids=["a", "b"],
        )
        assert result.evicted_ids == []
        assert result.entries_evicted == 0
        assert result.capacity_before is None

    def test_eviction_fields_populated(self):
        result = GCResult(
            entries_before=600,
            entries_removed=5,
            entries_after=500,
            removed_ids=["a"],
            evicted_ids=["c", "d"],
            entries_evicted=2,
            capacity_before=600,
        )
        assert result.entries_evicted == 2
        assert "c" in result.evicted_ids
        assert result.capacity_before == 600


# ---------------------------------------------------------------------------
# TestMemoryGCEviction (v0.8.13)
# ---------------------------------------------------------------------------


class TestMemoryGCEviction:
    """Test capacity-based eviction in MemoryGC."""

    def _make_entry(
        self,
        entry_id: str,
        category: str = "fact",
        importance: float = 0.5,
        days_ago: float = 30,
        mention_count: int = 1,
    ) -> LongTermEntry:
        created = (datetime.now() - timedelta(days=days_ago)).isoformat()
        return LongTermEntry(
            id=entry_id,
            content=f"content-{entry_id}",
            category=category,
            keywords=[f"k-{entry_id}"],
            source_session="s1",
            created_at=created,
            importance=importance,
            mention_count=mention_count,
            last_mentioned_at=created,
        )

    def test_eviction_disabled_no_removal(self):
        """eviction_enabled=False should not evict even when over capacity."""
        entries = [self._make_entry(f"e{i}", importance=0.3) for i in range(10)]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=False,
            eviction_max_entries=5,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        assert result.entries_evicted == 0

    def test_eviction_no_op_when_below_capacity(self):
        """No eviction when count <= max_entries."""
        entries = [self._make_entry(f"e{i}") for i in range(5)]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=True,
            eviction_max_entries=10,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        assert result.entries_evicted == 0
        assert result.capacity_before == 5

    def test_eviction_removes_lowest_weight(self):
        """When over capacity, lowest effective_weight entries should be evicted."""
        high_weight = self._make_entry("high", importance=0.9, days_ago=1)
        low_weight = self._make_entry("low", importance=0.1, days_ago=90)
        mid_weight = self._make_entry("mid", importance=0.5, days_ago=30)
        entries = [high_weight, low_weight, mid_weight]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=True,
            eviction_max_entries=2,
            decay_half_life_days=30.0,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        assert result.entries_evicted == 1
        assert "low" in result.evicted_ids

    def test_eviction_protected_category_not_removed(self):
        """Entries in protected categories should survive eviction."""
        preference = self._make_entry(
            "pref", category="preference", importance=0.1, days_ago=90
        )
        fact = self._make_entry("fact", category="fact", importance=0.1, days_ago=90)
        entries = [preference, fact]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=True,
            eviction_max_entries=1,
            eviction_protected_categories=["preference"],
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        assert result.entries_evicted == 1
        assert "pref" not in result.evicted_ids
        assert "fact" in result.evicted_ids

    def test_eviction_mention_count_protection(self):
        """Entries with mention_count >= threshold should survive eviction."""
        mentioned = self._make_entry(
            "mentioned", importance=0.1, days_ago=90, mention_count=5
        )
        unmentioned = self._make_entry(
            "unmentioned", importance=0.1, days_ago=90, mention_count=1
        )
        entries = [mentioned, unmentioned]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=True,
            eviction_max_entries=1,
            eviction_mention_count_threshold=3,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        assert result.entries_evicted == 1
        assert "mentioned" not in result.evicted_ids
        assert "unmentioned" in result.evicted_ids

    def test_eviction_respects_max_entries(self):
        """Exactly enough entries should be evicted to reach max_entries."""
        entries = [self._make_entry(f"e{i}", importance=0.3) for i in range(10)]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=True,
            eviction_max_entries=7,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        assert result.entries_evicted == 3
        assert result.entries_after == 7

    def test_eviction_after_decay_cleanup(self):
        """Eviction should run after decay cleanup, on remaining entries."""
        now = datetime.now()
        decayed = LongTermEntry(
            id="decayed",
            content="old",
            category="fact",
            keywords=[],
            source_session="s1",
            created_at=(now - timedelta(days=100)).isoformat(),
            importance=0.01,
            last_mentioned_at=(now - timedelta(days=100)).isoformat(),
        )
        normal = self._make_entry("normal", importance=0.5, days_ago=30)
        entries = [decayed, normal]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=True,
            gc_threshold=0.05,
            gc_min_age_days=7,
            eviction_enabled=True,
            eviction_max_entries=1,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        # Decay removes "decayed", eviction not needed (count already <= 1 after decay)
        assert "decayed" in result.removed_ids
        assert result.entries_evicted == 0

    def test_eviction_tiebreak_by_age(self):
        """Among equal-weight entries, older ones should be evicted first."""
        old = self._make_entry("old", importance=0.3, days_ago=60)
        new = self._make_entry("new", importance=0.3, days_ago=5)
        entries = [old, new]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=True,
            eviction_max_entries=1,
            decay_half_life_days=30.0,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        assert result.entries_evicted == 1
        # old has lower effective weight due to age, should be evicted
        assert "old" in result.evicted_ids

    def test_eviction_combined_with_decay(self):
        """Full integration: decay removes some, eviction removes more."""
        now = datetime.now()
        decayed = LongTermEntry(
            id="decayed",
            content="very old",
            category="fact",
            keywords=[],
            source_session="s1",
            created_at=(now - timedelta(days=200)).isoformat(),
            importance=0.01,
            last_mentioned_at=(now - timedelta(days=200)).isoformat(),
        )
        # weight = 0.5 * e^(-ln2*30/30) ≈ 0.25 > gc_threshold(0.05), survives decay
        low = self._make_entry("low", importance=0.5, days_ago=30)
        high = self._make_entry("high", importance=0.9, days_ago=1)
        entries = [decayed, low, high]
        ltm = _make_mock_ltm(entries)
        config = MemoryGCConfig(
            gc_enabled=True,
            gc_threshold=0.05,
            gc_min_age_days=7,
            eviction_enabled=True,
            eviction_max_entries=1,
            decay_half_life_days=30.0,
        )
        gc = MemoryGC(config)
        result = gc.run(ltm)
        # Decay removes "decayed" (weight < 0.05)
        assert "decayed" in result.removed_ids
        # "low" survives decay (weight ~0.25 > 0.05) but gets evicted (capacity)
        assert result.entries_evicted >= 1
        assert "high" not in result.evicted_ids


# ---------------------------------------------------------------------------
# TestHybridMemoryEviction (v0.8.13)
# ---------------------------------------------------------------------------


class TestHybridMemoryEviction:
    """Test HybridMemory eviction integration."""

    def test_run_gc_returns_eviction_stats(self):
        """run_gc should return GCResult with eviction fields."""
        from nano_agent.memory.hybrid import HybridMemory
        from nano_agent.memory.short_term import ShortTermMemory

        config = MemoryGCConfig(
            gc_enabled=False,
            eviction_enabled=True,
            eviction_max_entries=1,
        )
        stm = ShortTermMemory()
        ltm = MagicMock()
        ltm.get_all = MagicMock(return_value=[])
        ltm.count = MagicMock(return_value=0)
        ltm.delete_batch = MagicMock(return_value=0)

        hm = HybridMemory(working_memory=stm, long_term_memory=ltm, session_id="test")
        hm.set_memory_gc_config(config)
        result = hm.run_gc()

        assert result is not None
        assert hasattr(result, "entries_evicted")
        assert hasattr(result, "evicted_ids")
        assert hasattr(result, "capacity_before")

    def test_eviction_config_propagates(self):
        """Setting MemoryGCConfig with eviction fields should work through set_memory_gc_config."""
        from nano_agent.memory.hybrid import HybridMemory
        from nano_agent.memory.short_term import ShortTermMemory

        config = MemoryGCConfig(
            eviction_enabled=True,
            eviction_max_entries=200,
            eviction_protected_categories=["preference", "experience"],
            eviction_mention_count_threshold=5,
        )
        stm = ShortTermMemory()
        ltm = MagicMock()

        hm = HybridMemory(working_memory=stm, long_term_memory=ltm, session_id="test")
        hm.set_memory_gc_config(config)

        assert hm._memory_gc_config.eviction_enabled is True
        assert hm._memory_gc_config.eviction_max_entries == 200
        assert hm._memory_gc_config.eviction_protected_categories == [
            "preference",
            "experience",
        ]
        assert hm._memory_gc_config.eviction_mention_count_threshold == 5
