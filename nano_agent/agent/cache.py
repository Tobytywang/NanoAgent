"""
Tool result caching for reducing redundant tool calls.

Caches results from read-only tools to avoid repeated calls for the same operation.
"""

import time
import hashlib
import json
from dataclasses import dataclass, field

from ..tools.base import ToolResult


@dataclass
class CacheConfig:
    """Configuration for tool result caching."""

    enabled: bool = True
    ttl_seconds: int = 300  # 5 minutes
    # Only cache read-only tools
    cacheable_tools: list[str] = field(
        default_factory=lambda: ["file_read", "file_search", "shell_execute"]
    )
    # Don't cache write operations
    excluded_tools: list[str] = field(
        default_factory=lambda: ["file_write", "memorize", "forget"]
    )
    max_cache_size: int = 100  # Maximum number of cached results


class ToolResultCache:
    """
    Cache for tool execution results.

    Caches results from read-only tools to avoid repeated calls.
    Uses TTL (time-to-live) to expire stale entries.
    """

    def __init__(self, config: CacheConfig | None = None):
        self.config = config or CacheConfig()
        self._cache: dict[str, tuple[ToolResult, float]] = {}
        self._hits: int = 0
        self._misses: int = 0

    def _make_key(self, tool_name: str, args: dict) -> str:
        """
        Generate a cache key from tool name and arguments.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Cache key string
        """
        # Sort keys for consistent hashing
        args_str = json.dumps(args, sort_keys=True)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
        return f"{tool_name}:{args_hash}"

    def is_cacheable(self, tool_name: str, args: dict) -> bool:
        """
        Check if a tool call should be cached.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            True if the tool call should be cached
        """
        if not self.config.enabled:
            return False

        # Check exclusion list first
        if tool_name in self.config.excluded_tools:
            return False

        # Check cacheable tools
        if tool_name not in self.config.cacheable_tools:
            return False

        # For shell_execute, only cache read-only commands
        if tool_name == "shell_execute":
            command = args.get("command", "")
            # Don't cache commands that modify state
            dangerous_patterns = ["rm", "delete", "write", "mv", "cp", "mkdir", "touch"]
            if any(p in command.lower() for p in dangerous_patterns):
                return False

        return True

    def get_cached_result(self, tool_name: str, args: dict) -> ToolResult | None:
        """
        Check if a cached result exists and is still valid.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Cached ToolResult if valid, None otherwise
        """
        if not self.is_cacheable(tool_name, args):
            return None

        cache_key = self._make_key(tool_name, args)

        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            elapsed = time.time() - timestamp

            if elapsed < self.config.ttl_seconds:
                self._hits += 1
                # Mark result as cached for display
                return ToolResult(
                    success=result.success,
                    output=f"[cached] {result.output}",
                    error=result.error
                )

            # Expired, remove from cache
            del self._cache[cache_key]

        self._misses += 1
        return None

    def set_cached_result(self, tool_name: str, args: dict, result: ToolResult) -> None:
        """
        Cache a tool execution result.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            result: Tool execution result
        """
        if not self.is_cacheable(tool_name, args):
            return

        # Enforce max cache size
        if len(self._cache) >= self.config.max_cache_size:
            # Remove oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        cache_key = self._make_key(tool_name, args)
        self._cache[cache_key] = (result, time.time())

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, size, and hit rate
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "hit_rate": hit_rate,
        }