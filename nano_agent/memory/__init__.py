"""记忆模块 - 对话历史管理"""

from .base import BaseMemory
from .short_term import ShortTermMemory
from .persistent import PersistentMemory
from .long_term import (
    LongTermMemory,
    LongTermEntry,
    compute_decay_weight,
    compute_age_days,
)
from .hybrid import HybridMemory
from .storage import BaseStorage, MemoryEntry, FileStorage, SQLiteStorage
from .protocols import LongTermMemoryCapable, SessionCapable
from .gc import MemoryGC, GCResult

__all__ = [
    "BaseMemory",
    "ShortTermMemory",
    "PersistentMemory",
    "LongTermMemory",
    "LongTermEntry",
    "compute_decay_weight",
    "compute_age_days",
    "HybridMemory",
    "BaseStorage",
    "MemoryEntry",
    "FileStorage",
    "SQLiteStorage",
    "LongTermMemoryCapable",
    "SessionCapable",
    "MemoryGC",
    "GCResult",
]
