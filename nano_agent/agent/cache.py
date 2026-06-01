"""
Tool result caching system.

Provides in-memory caching of tool results with TTL-based expiry.
v0.7.17: Added multi-turn cache with disk persistence, warmup on
session restore, and mtime-based invalidation for file tools.
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .token_utils import estimate_text_tokens
from ..config.schema import CacheConfig
from ..tools.base import ToolResult


@dataclass
class CacheEntry:
    """A single cached tool result."""

    tool_name: str
    args_key: str
    result: str  # The cached content (may be a summary if offloaded)
    timestamp: float
    token_count: int
    # v0.7.17: File metadata for mtime invalidation
    file_paths: list[str] = field(default_factory=list)
    file_mtimes: dict[str, float] = field(default_factory=dict)
    # v0.7.17: Whether this is an offloaded (summary) result
    is_offloaded: bool = False


class ToolResultCache:
    """
    In-memory tool result cache with optional disk persistence.

    Features:
    - TTL-based expiry
    - Tool-level allow/exclude lists
    - Max cache size with LRU eviction
    - v0.7.17: Disk persistence for cross-session reuse
    - v0.7.17: Warmup (load from disk) on session restore
    - v0.7.17: mtime-based invalidation for file operation tools
    """

    # Tools that operate on files and should have mtime tracking
    FILE_TOOLS = {"file_read", "file_search"}

    def __init__(self, config: CacheConfig | None = None):
        self.config = config or CacheConfig()
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []  # For LRU eviction

    def _make_key(self, tool_name: str, args: dict) -> str:
        """Create a cache key from tool name and arguments."""
        # Sort keys for deterministic hashing
        sorted_args = json.dumps(args, sort_keys=True, ensure_ascii=False)
        return f"{tool_name}:{sorted_args}"

    def should_cache(self, tool_name: str) -> bool:
        """Check if a tool's results should be cached."""
        if not self.config.enabled:
            return False
        if tool_name in self.config.excluded_tools:
            return False
        if self.config.cacheable_tools and tool_name not in self.config.cacheable_tools:
            return False
        return True

    def get_cached_result(self, tool_name: str, args: dict) -> str | None:
        """
        Get a cached result if available and valid.

        Checks TTL and mtime invalidation before returning.
        """
        key = self._make_key(tool_name, args)
        entry = self._cache.get(key)

        if entry is None:
            return None

        # Check TTL
        if time.time() - entry.timestamp > self.config.ttl_seconds:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return None

        # Check mtime invalidation for file tools
        if self.config.mtime_invalidation and self._is_file_entry_stale(entry):
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return None

        # Update LRU order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        return entry.result

    def set_cached_result(
        self,
        tool_name: str,
        args: dict,
        result: str | ToolResult,
        file_paths: list[str] | None = None,
        is_offloaded: bool = False,
    ) -> None:
        """
        Cache a tool result.

        Args:
            tool_name: The tool that produced this result
            args: The tool call arguments
            result: The result content (string or ToolResult object)
            file_paths: File paths involved (for mtime tracking)
            is_offloaded: Whether this is an offloaded summary result
        """
        if not self.should_cache(tool_name):
            return

        # Convert ToolResult to string if needed
        if isinstance(result, ToolResult):
            result_str = (
                f"[cached] {result.output}"
                if result.success
                else f"[cached] Error: {result.error}"
            )
        else:
            result_str = result

        key = self._make_key(tool_name, args)

        # Evict LRU entries if cache is full
        while len(self._cache) >= self.config.max_cache_size:
            if self._access_order:
                lru_key = self._access_order.pop(0)
                self._cache.pop(lru_key, None)
            else:
                break

        # Record file mtimes for invalidation
        file_mtimes = {}
        effective_paths = file_paths or []
        if self.config.mtime_invalidation and tool_name in self.FILE_TOOLS:
            # Auto-detect file path from args if not provided
            if not effective_paths:
                effective_paths = self._extract_file_paths(tool_name, args)
            for fpath in effective_paths:
                try:
                    file_mtimes[fpath] = os.path.getmtime(fpath)
                except OSError:
                    pass

        token_count = estimate_text_tokens(result_str)

        entry = CacheEntry(
            tool_name=tool_name,
            args_key=key,
            result=result_str,
            timestamp=time.time(),
            token_count=token_count,
            file_paths=effective_paths,
            file_mtimes=file_mtimes,
            is_offloaded=is_offloaded,
        )

        self._cache[key] = entry
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _extract_file_paths(self, tool_name: str, args: dict) -> list[str]:
        """Extract file paths from tool arguments for mtime tracking."""
        paths = []
        if tool_name == "file_read":
            if "file_path" in args:
                paths.append(args["file_path"])
        elif tool_name == "file_search":
            if "directory" in args:
                paths.append(args["directory"])
            elif "path" in args:
                paths.append(args["path"])
        return paths

    def _is_file_entry_stale(self, entry: CacheEntry) -> bool:
        """Check if a cached entry is stale due to file modifications."""
        if not entry.file_mtimes:
            return False
        for fpath, old_mtime in entry.file_mtimes.items():
            try:
                current_mtime = os.path.getmtime(fpath)
                if current_mtime != old_mtime:
                    return True
            except OSError:
                # File no longer exists, invalidate
                return True
        return False

    def invalidate(self, tool_name: str, args: dict) -> bool:
        """Remove a specific cache entry."""
        key = self._make_key(tool_name, args)
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    def clear(self) -> int:
        """Clear all cached results."""
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        return count

    # === v0.7.17: Multi-turn persistence ===

    def persist_to_disk(self, persist_dir: str | None = None) -> int:
        """
        Persist cache to disk for cross-session reuse.

        Args:
            persist_dir: Override config persist_dir

        Returns:
            Number of entries persisted
        """
        directory = Path(persist_dir or self.config.persist_dir)
        directory.mkdir(parents=True, exist_ok=True)

        # Write manifest with all entries
        manifest = []
        for key, entry in self._cache.items():
            entry_data = {
                "key": key,
                "tool_name": entry.tool_name,
                "result": entry.result,
                "timestamp": entry.timestamp,
                "token_count": entry.token_count,
                "file_paths": entry.file_paths,
                "file_mtimes": entry.file_mtimes,
                "is_offloaded": entry.is_offloaded,
            }
            manifest.append(entry_data)

        manifest_path = directory / "cache_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return len(manifest)

    def warmup_from_disk(self, persist_dir: str | None = None) -> int:
        """
        Load cache from disk (warmup on session restore).

        Skips expired entries and stale file-based entries.

        Args:
            persist_dir: Override config persist_dir

        Returns:
            Number of entries loaded
        """
        directory = Path(persist_dir or self.config.persist_dir)
        manifest_path = directory / "cache_manifest.json"

        if not manifest_path.exists():
            return 0

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            return 0

        loaded = 0
        now = time.time()

        for entry_data in manifest:
            # Skip expired entries
            if now - entry_data["timestamp"] > self.config.ttl_seconds:
                continue

            # Skip stale file-based entries
            if self.config.mtime_invalidation and entry_data.get("file_mtimes"):
                for fpath, old_mtime in entry_data["file_mtimes"].items():
                    try:
                        if os.path.getmtime(fpath) != old_mtime:
                            break
                    except OSError:
                        break
                else:
                    # All mtimes match, entry is valid
                    pass
                # If we broke out of the for loop, skip this entry
                if entry_data.get("file_mtimes"):
                    try:
                        current = os.path.getmtime(
                            next(iter(entry_data["file_mtimes"].keys()))
                        )
                        if current != next(iter(entry_data["file_mtimes"].values())):
                            continue
                    except (OSError, StopIteration):
                        continue

            key = entry_data["key"]
            entry = CacheEntry(
                tool_name=entry_data["tool_name"],
                args_key=key,
                result=entry_data["result"],
                timestamp=entry_data["timestamp"],
                token_count=entry_data["token_count"],
                file_paths=entry_data.get("file_paths", []),
                file_mtimes=entry_data.get("file_mtimes", {}),
                is_offloaded=entry_data.get("is_offloaded", False),
            )

            # Respect max cache size
            if len(self._cache) >= self.config.max_cache_size:
                break

            self._cache[key] = entry
            if key not in self._access_order:
                self._access_order.append(key)
            loaded += 1

        return loaded

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total_tokens = sum(e.token_count for e in self._cache.values())
        offloaded_count = sum(1 for e in self._cache.values() if e.is_offloaded)

        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.config.max_cache_size,
            "total_cached_tokens": total_tokens,
            "offloaded_entries": offloaded_count,
            "persist_enabled": self.config.persist,
        }
