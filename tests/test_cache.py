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
        """Test default configuration values."""
        config = CacheConfig()
        assert config.enabled is True
        assert config.ttl_seconds == 300
        assert "file_read" in config.cacheable_tools
        assert "file_write" in config.excluded_tools
        assert config.max_cache_size == 100

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CacheConfig(
            enabled=False,
            ttl_seconds=600,
            cacheable_tools=["custom_tool"],
            max_cache_size=50
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

        # Store result
        original = ToolResult(success=True, output="file content")
        cache.set_cached_result("file_read", args, original)

        # Second call - cache hit
        cached = cache.get_cached_result("file_read", args)
        assert cached is not None
        assert cached.success is True
        assert "[cached]" in cached.output

    def test_cache_miss_for_different_args(self):
        """Test cache miss for different arguments."""
        cache = ToolResultCache()
        args1 = {"file_path": "/test/file1.py"}
        args2 = {"file_path": "/test/file2.py"}

        # Store result for args1
        original = ToolResult(success=True, output="file1 content")
        cache.set_cached_result("file_read", args1, original)

        # Different args should miss
        result = cache.get_cached_result("file_read", args2)
        assert result is None

    def test_cache_excluded_tool(self):
        """Test that excluded tools are not cached."""
        cache = ToolResultCache()
        args = {"content": "test"}

        # file_write is excluded
        result = ToolResult(success=True, output="written")
        cache.set_cached_result("file_write", args, result)

        # Should not be cached
        cached = cache.get_cached_result("file_write", args)
        assert cached is None

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        config = CacheConfig(ttl_seconds=1)
        cache = ToolResultCache(config)
        args = {"file_path": "/test/file.py"}

        # Store result
        original = ToolResult(success=True, output="file content")
        cache.set_cached_result("file_read", args, original)

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
        original = ToolResult(success=True, output="file content")
        cache.set_cached_result("file_read", args, original)

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
            result = ToolResult(success=True, output=f"content{i}")
            cache.set_cached_result("file_read", args, result)

        # First entry should be evicted
        args0 = {"file_path": "/test/file0.py"}
        cached = cache.get_cached_result("file_read", args0)
        assert cached is None

        # Last two should still be cached
        args1 = {"file_path": "/test/file1.py"}
        args2 = {"file_path": "/test/file2.py"}
        assert cache.get_cached_result("file_read", args1) is not None
        assert cache.get_cached_result("file_read", args2) is not None

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = ToolResultCache()
        args = {"file_path": "/test/file.py"}

        # Miss
        cache.get_cached_result("file_read", args)

        # Store and hit
        result = ToolResult(success=True, output="content")
        cache.set_cached_result("file_read", args, result)
        cache.get_cached_result("file_read", args)
        cache.get_cached_result("file_read", args)

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 2/3

    def test_cache_clear(self):
        """Test cache clear."""
        cache = ToolResultCache()
        args = {"file_path": "/test/file.py"}

        # Store result
        result = ToolResult(success=True, output="content")
        cache.set_cached_result("file_read", args, result)

        # Clear
        cache.clear()

        # Should be empty
        cached = cache.get_cached_result("file_read", args)
        assert cached is None
        stats = cache.get_stats()
        assert stats["size"] == 0

    def test_shell_execute_dangerous_not_cached(self):
        """Test that dangerous shell commands are not cached."""
        cache = ToolResultCache()
        args = {"command": "rm -rf /test"}

        # Dangerous command should not be cacheable
        assert cache.is_cacheable("shell_execute", args) is False

    def test_shell_execute_safe_cached(self):
        """Test that safe shell commands are cached."""
        cache = ToolResultCache()
        args = {"command": "ls -la"}

        # Safe command should be cacheable
        assert cache.is_cacheable("shell_execute", args) is True

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