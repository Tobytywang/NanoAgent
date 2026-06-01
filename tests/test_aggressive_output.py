"""Tests for aggressive output simplification (v0.7.15)."""

import pytest
from nano_agent.config.schema import AggressiveOutputConfig
from nano_agent.agent.output_simplifier import OutputSimplifier
from nano_agent.agent.prompt_modules import (
    MODULES,
    AGGRESSIVE_OUTPUT_CONTENTS,
    STYLE_PRESETS,
)


class TestAggressiveOutputConfig:
    """Test AggressiveOutputConfig dataclass."""

    def test_defaults(self):
        config = AggressiveOutputConfig()
        assert config.enabled is False
        assert config.level == "mild"
        assert config.max_response_sentences == 0
        assert config.strip_emoji is True
        assert config.strip_markdown_tables is True
        assert config.strip_markdown_lists is False
        assert config.max_response_chars == 0

    def test_custom_level(self):
        config = AggressiveOutputConfig(enabled=True, level="aggressive")
        assert config.enabled is True
        assert config.level == "aggressive"

    def test_valid_levels(self):
        for level in ("mild", "aggressive", "extreme"):
            config = AggressiveOutputConfig(level=level)
            assert config.level == level

    def test_default_disabled(self):
        config = AggressiveOutputConfig()
        assert config.enabled is False


class TestOutputSimplifier:
    """Test OutputSimplifier post-processing."""

    def test_disabled_no_change(self):
        config = AggressiveOutputConfig(enabled=False)
        simplifier = OutputSimplifier(config)
        text = "Hello world! 🎉"
        assert simplifier.simplify(text) == text

    def test_strip_emoji(self):
        config = AggressiveOutputConfig(
            enabled=True,
            strip_emoji=True,
            strip_markdown_tables=False,
            strip_markdown_lists=False,
        )
        simplifier = OutputSimplifier(config)
        assert "🎉" not in simplifier.simplify("Hello 🎉 world")
        assert "Hello" in simplifier.simplify("Hello 🎉 world")

    def test_strip_markdown_tables(self):
        config = AggressiveOutputConfig(
            enabled=True,
            strip_emoji=False,
            strip_markdown_tables=True,
            strip_markdown_lists=False,
        )
        simplifier = OutputSimplifier(config)
        text = "Results:\n| A | B |\n|---|---|\n| 1 | 2 |\nDone."
        result = simplifier.simplify(text)
        assert "| A |" not in result
        assert "---" not in result

    def test_strip_markdown_lists(self):
        config = AggressiveOutputConfig(
            enabled=True,
            strip_emoji=False,
            strip_markdown_tables=False,
            strip_markdown_lists=True,
        )
        simplifier = OutputSimplifier(config)
        text = "Items:\n- First\n- Second\n- Third"
        result = simplifier.simplify(text)
        assert "- First" not in result

    def test_truncate_sentences_mild(self):
        config = AggressiveOutputConfig(
            enabled=True,
            max_response_sentences=3,
            strip_emoji=False,
            strip_markdown_tables=False,
            strip_markdown_lists=False,
        )
        simplifier = OutputSimplifier(config)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = simplifier.simplify(text)
        assert "Fourth" not in result

    def test_truncate_sentences_aggressive(self):
        config = AggressiveOutputConfig(
            enabled=True,
            max_response_sentences=1,
            strip_emoji=False,
            strip_markdown_tables=False,
            strip_markdown_lists=False,
        )
        simplifier = OutputSimplifier(config)
        text = "First sentence. Second sentence."
        result = simplifier.simplify(text)
        assert "Second" not in result

    def test_truncate_chars(self):
        config = AggressiveOutputConfig(
            enabled=True,
            max_response_chars=20,
            strip_emoji=False,
            strip_markdown_tables=False,
            strip_markdown_lists=False,
        )
        simplifier = OutputSimplifier(config)
        text = "This is a very long response that should be truncated."
        result = simplifier.simplify(text)
        assert len(result) <= 23  # 20 chars + "..."
        assert result.endswith("...")

    def test_chained_operations(self):
        config = AggressiveOutputConfig(
            enabled=True,
            level="aggressive",
            max_response_sentences=1,
            max_response_chars=0,
            strip_emoji=True,
            strip_markdown_tables=True,
            strip_markdown_lists=True,
        )
        simplifier = OutputSimplifier(config)
        text = "Summary 📊\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- Item 1\n- Item 2\n\nFirst point. Second point."
        result = simplifier.simplify(text)
        assert "📊" not in result
        assert "|" not in result

    def test_empty_input(self):
        config = AggressiveOutputConfig(enabled=True)
        simplifier = OutputSimplifier(config)
        assert simplifier.simplify("") == ""
        assert simplifier.simplify(None) is None

    def test_from_level_mild(self):
        simplifier = OutputSimplifier.from_level("mild")
        assert simplifier.config.level == "mild"
        assert simplifier.config.max_response_sentences == 3

    def test_from_level_aggressive(self):
        simplifier = OutputSimplifier.from_level("aggressive")
        assert simplifier.config.level == "aggressive"
        assert simplifier.config.max_response_sentences == 1
        assert simplifier.config.strip_markdown_lists is True

    def test_from_level_extreme(self):
        simplifier = OutputSimplifier.from_level("extreme")
        assert simplifier.config.level == "extreme"
        assert simplifier.config.max_response_chars == 200

    def test_from_level_invalid_defaults_mild(self):
        simplifier = OutputSimplifier.from_level("nonexistent")
        assert simplifier.config.level == "mild"


class TestAggressiveOutputPromptModule:
    """Test aggressive_output prompt module definition."""

    def test_module_exists(self):
        assert "aggressive_output" in MODULES

    def test_module_properties(self):
        module = MODULES["aggressive_output"]
        assert module.priority == 41
        assert module.category == "output"
        assert module.is_stable is True

    def test_three_level_contents(self):
        assert "mild" in AGGRESSIVE_OUTPUT_CONTENTS
        assert "aggressive" in AGGRESSIVE_OUTPUT_CONTENTS
        assert "extreme" in AGGRESSIVE_OUTPUT_CONTENTS
        for level, content in AGGRESSIVE_OUTPUT_CONTENTS.items():
            assert len(content) > 0
            assert "Output Constraints" in content

    def test_output_style_in_all_presets(self):
        """v0.7.15: output_style should be in all style presets."""
        for style in ("concise", "standard", "detailed"):
            assert (
                "output_style" in STYLE_PRESETS[style]["modules"]
            ), f"output_style missing from {style}"
