"""
Memory Garbage Collection - lightweight cleanup of decayed long-term memory entries.

Runs at session start to remove entries whose effective weight has fallen
below a configurable threshold. This prevents storage bloat and retrieval
noise from stale, low-value entries.
"""

import logging
from dataclasses import dataclass
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


class MemoryGC:
    """
    Lightweight garbage collector for long-term memory.

    Removes entries where effective_weight < gc_threshold,
    provided they are older than gc_min_age_days.
    """

    def __init__(self, config: MemoryGCConfig):
        self.config = config

    def run(self, long_term_memory: "LongTermMemory") -> GCResult:
        """
        Run a GC pass on the long-term memory.

        Args:
            long_term_memory: The LongTermMemory instance to clean

        Returns:
            GCResult with statistics
        """
        count = long_term_memory.count()

        if not self.config.gc_enabled:
            return GCResult(
                entries_before=count,
                entries_removed=0,
                entries_after=count,
                removed_ids=[],
            )

        removed_ids = []

        for entry in long_term_memory.get_all():
            age_days = compute_age_days(entry.created_at)
            if age_days < self.config.gc_min_age_days:
                continue

            effective_weight = compute_decay_weight(
                entry, self.config.decay_half_life_days
            )
            if effective_weight < self.config.gc_threshold:
                removed_ids.append(entry.id)

        if removed_ids:
            long_term_memory.delete_batch(removed_ids)

        entries_after = long_term_memory.count()
        entries_removed = count - entries_after

        if entries_removed > 0:
            logger.info(
                f"[MemoryGC] Cleaned {entries_removed} decayed entries "
                f"(threshold={self.config.gc_threshold}, "
                f"min_age={self.config.gc_min_age_days}d, "
                f"remaining={entries_after})"
            )

        return GCResult(
            entries_before=count,
            entries_removed=entries_removed,
            entries_after=entries_after,
            removed_ids=removed_ids,
        )
