"""
Tests for multi-turn cache persistence (v0.7.17).
"""

import json
import pytest
import time
from pathlib import Path

from nano_agent.agent.cache import ToolResultCache, CacheEntry
from nano_agent.config.schema import CacheConfig


class TestCacheConfigExtended:
    """Test extended CacheConfig fields."""

    def test_default_multi_turn_fields(self):
        config = CacheConfig()
        assert config.persist is False
        assert config.persist_dir == ".nano_agent/cache"
        assert config.warmup_on_restore is True
        assert config.mtime_invalidation is True

    def test_custom_multi_turn_fields(self):
        config = CacheConfig(
            persist=True,
            persist_dir="/custom/cache",
            warmup_on_restore=False,
            mtime_invalidation=False,
        )
        assert config.persist is True
        assert config.persist_dir == "/custom/cache"
        assert config.warmup_on_restore is False
        assert config.mtime_invalidation is False


class TestCacheMtimeInvalidation:
    """Test mtime-based cache invalidation."""

    @pytest.fixture
    def cache(self):
        config = CacheConfig(
            ttl_seconds=300,
            mtime_invalidation=True,
        )
        return ToolResultCache(config)

    def test_file_read_cache_stale_on_mtime_change(self, cache, tmp_path):
        """Cache should be invalidated when file mtime changes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("original content")

        # Cache result with file mtime
        cache.set_cached_result(
            "file_read",
            {"file_path": str(test_file)},
            "file content",
            file_paths=[str(test_file)],
        )

        # Should hit cache initially
        result = cache.get_cached_result("file_read", {"file_path": str(test_file)})
        assert result == "file content"

        # Modify the file (update mtime)
        test_file.write_text("modified content")

        # Should miss cache now
        result = cache.get_cached_result("file_read", {"file_path": str(test_file)})
        assert result is None

    def test_file_read_cache_valid_same_mtime(self, cache, tmp_path):
        """Cache should be valid when file mtime unchanged."""
        test_file = tmp_path / "test.py"
        test_file.write_text("original content")

        cache.set_cached_result(
            "file_read",
            {"file_path": str(test_file)},
            "file content",
            file_paths=[str(test_file)],
        )

        # Should still hit cache (file unchanged)
        result = cache.get_cached_result("file_read", {"file_path": str(test_file)})
        assert result == "file content"

    def test_non_file_tool_no_mtime_check(self, cache):
        """Non-file tools should not be affected by mtime invalidation."""
        # shell_execute is in cacheable_tools, not a FILE_TOOL
        cache.set_cached_result(
            "shell_execute",
            {"command": "ls"},
            "command output",
        )

        result = cache.get_cached_result("shell_execute", {"command": "ls"})
        assert result == "command output"

    def test_auto_extract_file_path_from_args(self, cache, tmp_path):
        """Should auto-detect file path from tool arguments."""
        test_file = tmp_path / "auto.py"
        test_file.write_text("content")

        cache.set_cached_result(
            "file_read",
            {"file_path": str(test_file)},
            "file content",
        )

        # Should track mtime automatically
        result = cache.get_cached_result("file_read", {"file_path": str(test_file)})
        assert result == "file content"

        # Modify file
        test_file.write_text("new content")
        result = cache.get_cached_result("file_read", {"file_path": str(test_file)})
        assert result is None

    def test_mtime_invalidation_disabled(self, tmp_path):
        """When mtime_invalidation is False, file changes should not invalidate."""
        config = CacheConfig(
            ttl_seconds=300,
            mtime_invalidation=False,
        )
        cache = ToolResultCache(config)

        test_file = tmp_path / "test.py"
        test_file.write_text("original")

        cache.set_cached_result(
            "file_read",
            {"file_path": str(test_file)},
            "file content",
            file_paths=[str(test_file)],
        )

        # Modify file
        test_file.write_text("modified")

        # Should still hit cache (mtime check disabled)
        result = cache.get_cached_result("file_read", {"file_path": str(test_file)})
        assert result == "file content"


class TestCachePersistence:
    """Test cache persistence to disk."""

    @pytest.fixture
    def cache(self):
        config = CacheConfig(
            ttl_seconds=300,
            persist=True,
            persist_dir=str(Path(".nano_agent/cache")),
        )
        return ToolResultCache(config)

    def test_persist_to_disk(self, cache, tmp_path):
        """Cache should persist entries to disk."""
        cache.set_cached_result("file_read", {"file_path": "/test.py"}, "file content")
        cache.set_cached_result("shell_execute", {"command": "ls"}, "command output")

        count = cache.persist_to_disk(str(tmp_path))
        assert count == 2

        manifest_path = tmp_path / "cache_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        assert len(manifest) == 2

    def test_warmup_from_disk(self, cache, tmp_path):
        """Cache should load entries from disk."""
        cache.set_cached_result("file_read", {"file_path": "/test.py"}, "file content")
        cache.persist_to_disk(str(tmp_path))

        # Create new cache and warmup
        new_cache = ToolResultCache(CacheConfig(ttl_seconds=300))
        loaded = new_cache.warmup_from_disk(str(tmp_path))
        assert loaded == 1

        result = new_cache.get_cached_result("file_read", {"file_path": "/test.py"})
        assert result == "file content"

    def test_warmup_skips_expired(self, tmp_path):
        """Warmup should skip expired entries."""
        cache = ToolResultCache(CacheConfig(ttl_seconds=1))
        cache.set_cached_result("file_read", {"file_path": "/test.py"}, "old content")

        # Wait for TTL to expire
        time.sleep(1.1)

        cache.persist_to_disk(str(tmp_path))

        new_cache = ToolResultCache(CacheConfig(ttl_seconds=1))
        loaded = new_cache.warmup_from_disk(str(tmp_path))
        assert loaded == 0

    def test_warmup_skips_stale_files(self, tmp_path):
        """Warmup should skip entries where file mtime changed."""
        test_file = tmp_path / "test.py"
        test_file.write_text("original")

        cache = ToolResultCache(CacheConfig(ttl_seconds=300, mtime_invalidation=True))
        cache.set_cached_result(
            "file_read",
            {"file_path": str(test_file)},
            "file content",
            file_paths=[str(test_file)],
        )
        cache.persist_to_disk(str(tmp_path / "cache"))

        # Modify file
        test_file.write_text("modified")

        new_cache = ToolResultCache(
            CacheConfig(ttl_seconds=300, mtime_invalidation=True)
        )
        loaded = new_cache.warmup_from_disk(str(tmp_path / "cache"))
        assert loaded == 0

    def test_warmup_empty_manifest(self, tmp_path):
        """Warmup with missing manifest should return 0."""
        cache = ToolResultCache(CacheConfig(ttl_seconds=300))
        loaded = cache.warmup_from_disk(str(tmp_path / "nonexistent"))
        assert loaded == 0


class TestCacheOffloadIntegration:
    """Test cache + offload integration."""

    def test_cache_stores_offloaded_summary(self):
        """Cache should store offloaded summary, not raw content."""
        config = CacheConfig(ttl_seconds=300)
        cache = ToolResultCache(config)

        # Simulate offloaded result (summary)
        summary = '[结果已卸载] file_read 返回约 5000 tokens\n摘要: ...\n完整结果: file_read("/tmp/xxx")'
        cache.set_cached_result(
            "file_read",
            {"file_path": "/test.py"},
            summary,
            is_offloaded=True,
        )

        result = cache.get_cached_result("file_read", {"file_path": "/test.py"})
        assert result == summary

    def test_cache_stats_track_offloaded(self):
        """Cache stats should track offloaded entries."""
        config = CacheConfig(ttl_seconds=300)
        cache = ToolResultCache(config)

        cache.set_cached_result(
            "file_read",
            {"file_path": "/test.py"},
            "normal content",
            is_offloaded=False,
        )
        cache.set_cached_result(
            "shell_execute",
            {"command": "ls"},
            "[结果已卸载] summary",
            is_offloaded=True,
        )

        stats = cache.get_stats()
        assert stats["offloaded_entries"] == 1


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_entry_with_offload_flag(self):
        entry = CacheEntry(
            tool_name="file_read",
            args_key='file_read:{"file_path": "/test.py"}',
            result="content",
            timestamp=time.time(),
            token_count=100,
            is_offloaded=True,
        )
        assert entry.is_offloaded is True

    def test_entry_with_file_mtimes(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("content")

        entry = CacheEntry(
            tool_name="file_read",
            args_key="file_read:...",
            result="content",
            timestamp=time.time(),
            token_count=100,
            file_paths=[str(test_file)],
            file_mtimes={str(test_file): test_file.stat().st_mtime},
        )
        assert len(entry.file_mtimes) == 1
