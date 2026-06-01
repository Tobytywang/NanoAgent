"""
Tests for message compression.
"""

import pytest

from nano_agent.agent.compressor import MessageCompressor, CompressorConfig
from nano_agent.agent.token_utils import estimate_tokens


class TestCompressorConfig:
    """Tests for CompressorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CompressorConfig()
        assert config.enabled is True
        assert config.threshold_tokens == 2000
        assert config.keep_recent == 3
        assert config.summary_max_tokens == 500

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CompressorConfig(
            enabled=False, threshold_tokens=1000, keep_recent=2, summary_max_tokens=300
        )
        assert config.enabled is False
        assert config.threshold_tokens == 1000
        assert config.keep_recent == 2
        assert config.summary_max_tokens == 300


class TestMessageCompressor:
    """Tests for MessageCompressor."""

    def test_should_compress_below_threshold(self):
        """Test that compression is not needed below threshold."""
        config = CompressorConfig(threshold_tokens=1000)
        compressor = MessageCompressor(config)

        # Small message list should not need compression
        messages = [
            {"role": "system", "content": "You are an assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        assert compressor.should_compress(messages) is False

    def test_should_compress_above_threshold(self):
        """Test that compression is needed above threshold."""
        config = CompressorConfig(threshold_tokens=100)
        compressor = MessageCompressor(config)

        # Large message list should need compression
        messages = [
            {"role": "system", "content": "You are an assistant. " * 50},
            {"role": "user", "content": "Hello " * 50},
            {"role": "assistant", "content": "Hi there! " * 50},
            {"role": "user", "content": "How are you? " * 50},
            {"role": "assistant", "content": "I'm good! " * 50},
        ]

        assert compressor.should_compress(messages) is True

    def test_compress_disabled(self):
        """Test that compression is skipped when disabled."""
        config = CompressorConfig(enabled=False, threshold_tokens=100)
        compressor = MessageCompressor(config)

        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User"},
        ]

        # Should return original messages when disabled
        compressed = compressor.compress(messages)
        assert compressed == messages

    def test_compress_keeps_system_message(self):
        """Test that system message is preserved."""
        config = CompressorConfig(threshold_tokens=100, keep_recent=1)
        compressor = MessageCompressor(config)

        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Query 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Query 2"},
            {"role": "assistant", "content": "Response 2"},
        ]

        compressed = compressor.compress(messages)

        # System message should be first
        assert compressed[0]["role"] == "system"
        assert compressed[0]["content"] == "System prompt"

    def test_compress_keeps_recent_messages(self):
        """Test that recent messages are preserved."""
        config = CompressorConfig(threshold_tokens=100, keep_recent=2)
        compressor = MessageCompressor(config)

        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Query 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Query 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Query 3"},
            {"role": "assistant", "content": "Response 3"},
        ]

        compressed = compressor.compress(messages)

        # Should keep last 2 rounds (4 messages) + system + summary
        # Recent messages should be at the end
        assert compressed[-1]["content"] == "Response 3"
        assert compressed[-2]["content"] == "Query 3"
        assert compressed[-3]["content"] == "Response 2"
        assert compressed[-4]["content"] == "Query 2"

    def test_compress_creates_summary(self):
        """Test that compression creates a summary message."""
        config = CompressorConfig(threshold_tokens=50, keep_recent=1)
        compressor = MessageCompressor(config)

        # Use longer messages to exceed threshold
        messages = [
            {"role": "system", "content": "System " * 20},
            {"role": "user", "content": "Query 1 " * 20},
            {"role": "assistant", "content": "Response 1 " * 20},
            {"role": "user", "content": "Query 2 " * 20},
            {"role": "assistant", "content": "Response 2 " * 20},
        ]

        compressed = compressor.compress(messages)

        # Should have summary message
        summary_found = False
        for msg in compressed:
            if msg["content"].startswith("[历史摘要]"):
                summary_found = True
                break

        assert summary_found is True

    def test_compress_handles_tool_calls(self):
        """Test that compression handles tool calls."""
        config = CompressorConfig(threshold_tokens=50, keep_recent=1)
        compressor = MessageCompressor(config)

        # Use longer messages to exceed threshold
        messages = [
            {"role": "system", "content": "System " * 20},
            {"role": "user", "content": "Query " * 20},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "file_read"}}],
            },
            {"role": "tool", "content": "file content " * 20, "name": "file_read"},
            {"role": "user", "content": "Recent query"},
            {"role": "assistant", "content": "Recent response"},
        ]

        compressed = compressor.compress(messages)

        # Summary should mention tool calls
        summary_msg = None
        for msg in compressed:
            if msg["content"].startswith("[历史摘要]"):
                summary_msg = msg
                break

        assert summary_msg is not None
        assert "工具调用" in summary_msg["content"]

    def test_compress_no_compression_needed(self):
        """Test that messages are unchanged when no compression needed."""
        config = CompressorConfig(threshold_tokens=10000)
        compressor = MessageCompressor(config)

        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Query"},
            {"role": "assistant", "content": "Response"},
        ]

        compressed = compressor.compress(messages)

        # Should return original when no compression needed
        assert compressed == messages

    def test_compress_stats(self):
        """Test compression statistics."""
        config = CompressorConfig(threshold_tokens=100, keep_recent=1)
        compressor = MessageCompressor(config)

        messages = [
            {"role": "system", "content": "System " * 20},
            {"role": "user", "content": "Query 1 " * 20},
            {"role": "assistant", "content": "Response 1 " * 20},
            {"role": "user", "content": "Query 2 " * 20},
            {"role": "assistant", "content": "Response 2 " * 20},
        ]

        # Compress twice
        compressor.compress(messages)
        compressor.compress(messages)

        stats = compressor.get_stats()
        assert stats["compression_count"] == 2

    def test_compress_reset_stats(self):
        """Test resetting compression statistics."""
        config = CompressorConfig(threshold_tokens=100, keep_recent=1)
        compressor = MessageCompressor(config)

        messages = [
            {"role": "system", "content": "System " * 20},
            {"role": "user", "content": "Query " * 20},
            {"role": "assistant", "content": "Response " * 20},
        ]

        compressor.compress(messages)
        compressor.reset_stats()

        stats = compressor.get_stats()
        assert stats["compression_count"] == 0

    def test_compress_truncates_long_content(self):
        """Test that long content is truncated in summary."""
        config = CompressorConfig(
            threshold_tokens=100, keep_recent=1, summary_max_tokens=50
        )
        compressor = MessageCompressor(config)

        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Very long query " * 100},
            {"role": "assistant", "content": "Very long response " * 100},
            {"role": "user", "content": "Recent"},
            {"role": "assistant", "content": "Recent response"},
        ]

        compressed = compressor.compress(messages)

        # Find summary
        summary_msg = None
        for msg in compressed:
            if msg["content"].startswith("[历史摘要]"):
                summary_msg = msg
                break

        # Summary should be truncated
        assert summary_msg is not None
        # Should not exceed max tokens * 4 (rough char estimate)
        assert len(summary_msg["content"]) < 250
