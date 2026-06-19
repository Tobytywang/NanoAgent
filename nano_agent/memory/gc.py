"""
Memory Garbage Collection - lightweight cleanup of decayed long-term memory entries.

Runs at session start in two phases:
1. Decay-based GC: remove entries whose effective weight has fallen below threshold
2. Capacity-based eviction: when entries exceed max_entries, evict lowest-weight ones

This prevents storage bloat and retrieval noise from stale, low-value entries.
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .long_term import LongTermMemory, LongTermEntry

from .long_term import compute_decay_weight, compute_age_days
from ..config.schema import MemoryGCConfig

logger = logging.getLogger(__name__)


@dataclass
class GCResult:
    """Result of a GC pass."""

    entries_before: int
    entries_removed: int
    entries_after: int
    removed_ids: list[str]
    evicted_ids: list[str] = field(default_factory=list)
    entries_evicted: int = 0
    capacity_before: int | None = None

    def summary(self) -> str:
        """Human-readable summary of the GC pass."""
        parts = []
        if self.entries_removed > 0:
            parts.append(f"{self.entries_removed} decayed")
        if self.entries_evicted > 0:
            parts.append(f"{self.entries_evicted} evicted (capacity)")
        if not parts:
            return ""
        return f"Cleaned {' + '.join(parts)} (remaining={self.entries_after})"


class MemoryGC:
    """
    Lightweight garbage collector for long-term memory.

    Phase 1 (decay): Remove entries where effective_weight < gc_threshold,
    provided they are older than gc_min_age_days.

    Phase 2 (eviction): When entries exceed eviction_max_entries, evict
    lowest effective_weight entries (excluding protected categories and
    high mention_count entries).
    """

    def __init__(self, config: MemoryGCConfig):
        self.config = config
        self._protected_categories = set(config.eviction_protected_categories)

    def run(self, long_term_memory: "LongTermMemory") -> GCResult:
        """
        Run a GC pass on the long-term memory.

        Single pass over entries: collect both decay-removal and eviction
        candidates, then apply deletions in one batch.

        Args:
            long_term_memory: The LongTermMemory instance to clean

        Returns:
            GCResult with statistics
        """
        count = long_term_memory.count()
        removed_ids: list[str] = []
        evicted_ids: list[str] = []
        capacity_before: int | None = None

        if self.config.gc_enabled or self.config.eviction_enabled:
            candidates = []

            for entry in long_term_memory.get_all():
                age_days = compute_age_days(entry.created_at)
                weight = compute_decay_weight(entry, self.config.decay_half_life_days)

                # Phase 1: decay check
                if (
                    self.config.gc_enabled
                    and age_days >= self.config.gc_min_age_days
                    and weight < self.config.gc_threshold
                ):
                    removed_ids.append(entry.id)
                    continue

                # Phase 2: eviction candidate (not decayed, not protected)
                if self.config.eviction_enabled and entry.id not in removed_ids:
                    if (
                        entry.category not in self._protected_categories
                        and entry.mention_count
                        < self.config.eviction_mention_count_threshold
                    ):
                        candidates.append((weight, -age_days, entry.id))

            # Determine eviction from candidates
            if self.config.eviction_enabled:
                post_decay_count = count - len(removed_ids)
                capacity_before = post_decay_count

                if post_decay_count > self.config.eviction_max_entries:
                    candidates.sort()
                    num_to_evict = post_decay_count - self.config.eviction_max_entries
                    evicted_ids = [cid for _, _, cid in candidates[:num_to_evict]]

            # Single batch delete
            all_ids = removed_ids + evicted_ids
            if all_ids:
                long_term_memory.delete_batch(all_ids)

        entries_after = long_term_memory.count()

        if removed_ids or evicted_ids:
            entries_removed = len(removed_ids)
        else:
            entries_removed = 0

        result = GCResult(
            entries_before=count,
            entries_removed=entries_removed,
            entries_after=entries_after,
            removed_ids=removed_ids,
            evicted_ids=evicted_ids,
            entries_evicted=len(evicted_ids),
            capacity_before=capacity_before,
        )
        if removed_ids or evicted_ids:
            logger.info(f"[MemoryGC] {result.summary()}")

        return result
