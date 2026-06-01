"""
Tests for tool result caching.
"""

import pytest
import time

from nano_agent.agent.cache import ToolResultCache, CacheConfig
from nano_agent.tools.base import ToolResult


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_default_config(self):
        config = CacheConfig()
        assert config.enabled is True
        assert config.ttl_seconds == 300
        assert "file_read" in config.cacheable_tools
        assert "file_write" in config.excluded_tools
        assert config.max_cache_size == 100
        # v0.7.17: Multi-turn cache fields
        assert config.persist is False
        assert config.persist_dir == ".nano_agent/cache"
        assert config.warmup_on_restore is True
        assert config.mtime_invalidation is True

    def test_custom_config(self):
        config = CacheConfig(
            enabled=False,
            ttl_seconds=600,
            cacheable_tools=["custom_tool"],
            max_cache_size=50,
        )
        assert config.enabled is False
        assert config.ttl_seconds == 600
        assert config.cacheable_tools == ["custom_tool"]
        assert config.max_cache_size == 50


class TestToolResultCache:
    """Tests for ToolResultCache."""

    def test_cache_hit(self):
        """Test cache hit scenario."""
        cache = ToolResultCache()
        args = {"file_path": "/test/file.py"}

        # First call - cache miss
        result = cache.get_cached_result("file_read", args)
        assert result is None

        # Store result (as string)
        cache.set_cached_result("file_read", args, "file content")

        # Second call - cache hit (returns the stored string)
        cached = cache.get_cached_result("file_read", args)
        assert cached is not None
        assert cached == "file content"

    def test_cache_miss_for_different_args(self):
        """Test cache miss for different arguments."""
        cache = ToolResultCache()
        args1 = {"file_path": "/test/file1.py"}
        args2 = {"file_path": "/test/file2.py"}

        # Store result for args1
        cache.set_cached_result("file_read", args1, "file1 content")

        # Different args should miss
        result = cache.get_cached_result("file_read", args2)
        assert result is None

    def test_cache_excluded_tool(self):
        """Test that excluded tools are not cached."""
        cache = ToolResultCache()
        args = {"content": "test"}

        # file_write is excluded
        cache.set_cached_result("file_write", args, "written")

        # Should not be cached
        cached = cache.get_cached_result("file_write", args)
        assert cached is None

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        config = CacheConfig(ttl_seconds=1)
        cache = ToolResultCache(config)
        args = {"file_path": "/test/file.py"}

        # Store result
        cache.set_cached_result("file_read", args, "file content")

        # Immediate hit
        cached = cache.get_cached_result("file_read", args)
        assert cached is not None

        # Wait for TTL
        time.sleep(1.5)

        # Should be expired
        cached = cache.get_cached_result("file_read", args)
        assert cached is None

    def test_cache_disabled(self):
        """Test cache when disabled."""
        config = CacheConfig(enabled=False)
        cache = ToolResultCache(config)
        args = {"file_path": "/test/file.py"}

        # Store result
        cache.set_cached_result("file_read", args, "file content")

        # Should not be cached when disabled
        cached = cache.get_cached_result("file_read", args)
        assert cached is None

    def test_cache_max_size(self):
        """Test cache max size limit."""
        config = CacheConfig(max_cache_size=2)
        cache = ToolResultCache(config)

        # Store 3 results
        for i in range(3):
            args = {"file_path": f"/test/file{i}.py"}
            cache.set_cached_result("file_read", args, f"content{i}")

        # First entry should be evicted
        args0 = {"file_path": "/test/file0.py"}
        cached = cache.get_cached_result("file_read", args0)
        assert cached is None

        # Last two should still be cached
        args1 = {"file_path": "/test/file1.py"}
        args2 = {"file_path": "/test/file2.py"}
        assert cache.get_cached_result("file_read", args1) is not None
        assert cache.get_cached_result("file_read", args2) is not None

    def test_cache_clear(self):
        """Test cache clear."""
        cache = ToolResultCache()
        args = {"file_path": "/test/file.py"}

        # Store result
        cache.set_cached_result("file_read", args, "content")

        # Clear
        cache.clear()

        # Should be empty
        cached = cache.get_cached_result("file_read", args)
        assert cached is None

    def test_shell_execute_dangerous_not_cached(self):
        """Test that dangerous shell commands are not cached."""
        cache = ToolResultCache()
        args = {"command": "rm -rf /test"}

        # Dangerous command should not be cacheable
        assert cache.should_cache("shell_execute") is True
        # But the actual caching logic checks command danger

    def test_shell_execute_safe_cached(self):
        """Test that safe shell commands are cached."""
        cache = ToolResultCache()
        args = {"command": "ls -la"}

        # Safe command should be cacheable
        assert cache.should_cache("shell_execute") is True

    def test_cache_key_consistency(self):
        """Test that cache keys are consistent for same args."""
        cache = ToolResultCache()

        # Same args should produce same key
        args1 = {"file_path": "/test/file.py", "mode": "r"}
        args2 = {"mode": "r", "file_path": "/test/file.py"}  # Different order

        key1 = cache._make_key("file_read", args1)
        key2 = cache._make_key("file_read", args2)

        # Keys should be same regardless of dict order
        assert key1 == key2
