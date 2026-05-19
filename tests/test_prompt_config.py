"""
Tests for v0.7.6 Prompt configurability.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from nano_agent.agent.prompt_builder import (
    PromptBuilder,
    PromptBuilderConfig,
    ExcelConfigManager,
    build_prompt,
)
from nano_agent.agent.prompt_modules import MODULES, PromptModule, STYLE_PRESETS
from nano_agent.config.schema import PromptConfig
from nano_agent.agent.react import ReActAgent
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.tools import ToolRegistry


class TestPromptModule:
    """Tests for PromptModule dataclass."""

    def test_create_prompt_module(self):
        """Test creating a PromptModule."""
        module = PromptModule(
            name="test",
            description="Test module",
            content="Test content",
            priority=50,
            always_on=False,
            token_estimate=100,
            enabled=True,
            is_stable=True,
            category="core",
        )
        assert module.name == "test"
        assert module.is_stable is True
        assert module.category == "core"

    def test_prompt_module_defaults(self):
        """Test PromptModule default values."""
        module = PromptModule(
            name="test",
            description="Test",
            content="Content",
        )
        assert module.priority == 50
        assert module.always_on is False
        assert module.enabled is True
        assert module.is_stable is True
        assert module.category == "core"


class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    def test_create_builder(self):
        """Test creating a PromptBuilder."""
        builder = PromptBuilder()
        assert builder.config is not None

    def test_set_style(self):
        """Test setting style."""
        builder = PromptBuilder()
        builder.set_style("concise")
        assert builder.config.style == "concise"

    def test_build_stable(self):
        """Test building stable portion."""
        builder = PromptBuilder()
        builder.set_style("standard")
        stable = builder.build_stable("Test tools")
        assert len(stable) > 0
        assert "Test tools" in stable

    def test_build_dynamic(self):
        """Test building dynamic portion."""
        builder = PromptBuilder()
        builder.set_style("standard")
        dynamic = builder.build_dynamic(
            skill_prompt="Test skill",
            confidence_enabled=True,
            confidence_suffix="[CONFIDENCE]",
        )
        assert "Test skill" in dynamic
        assert "[CONFIDENCE]" in dynamic

    def test_build_dynamic_empty(self):
        """Test building dynamic portion with no content."""
        builder = PromptBuilder()
        builder.set_style("standard")
        dynamic = builder.build_dynamic()
        # Should be empty or minimal
        assert isinstance(dynamic, str)

    def test_get_cache_key(self):
        """Test getting cache key."""
        builder = PromptBuilder()
        builder.set_style("standard")
        key1 = builder.get_cache_key("Tools v1")
        key2 = builder.get_cache_key("Tools v1")
        # Same input should produce same key
        assert key1 == key2

    def test_get_cache_key_different(self):
        """Test cache key changes with different input."""
        builder = PromptBuilder()
        builder.set_style("standard")
        key1 = builder.get_cache_key("Tools v1")
        key2 = builder.get_cache_key("Tools v2")
        # Different input should produce different key
        assert key1 != key2

    def test_get_stable_module_names(self):
        """Test getting stable module names."""
        builder = PromptBuilder()
        builder.set_style("standard")
        names = builder.get_stable_module_names()
        assert "core" in names
        assert "tools" in names

    def test_get_dynamic_module_names(self):
        """Test getting dynamic module names."""
        builder = PromptBuilder()
        builder.set_style("standard")
        names = builder.get_dynamic_module_names()
        # Standard style should have no dynamic modules by default
        assert isinstance(names, list)

    def test_add_module(self):
        """Test adding a module."""
        builder = PromptBuilder()
        builder.add_module("efficiency")
        assert "efficiency" in builder.config.modules

    def test_remove_module(self):
        """Test removing a module."""
        builder = PromptBuilder()
        builder.set_style("standard")
        builder.remove_module("efficiency")
        assert "efficiency" not in builder.config.modules

    def test_estimate_tokens(self):
        """Test estimating tokens."""
        builder = PromptBuilder()
        builder.set_style("standard")
        tokens = builder.estimate_tokens()
        assert tokens > 0

    def test_get_module_info(self):
        """Test getting module info."""
        builder = PromptBuilder()
        info = builder.get_module_info()
        assert len(info) > 0
        assert "name" in info[0]
        assert "is_stable" in info[0]
        assert "category" in info[0]


class TestPromptBuilderStability:
    """Tests for prompt stability features."""

    def test_stable_modules_are_stable(self):
        """Test that stable modules have is_stable=True."""
        builder = PromptBuilder()
        builder.set_style("standard")
        stable_names = builder.get_stable_module_names()

        for name in stable_names:
            module = builder._modules[name]
            assert module.is_stable is True

    def test_dynamic_modules_are_not_stable(self):
        """Test that dynamic modules have is_stable=False."""
        builder = PromptBuilder()
        builder.set_style("standard")
        dynamic_names = builder.get_dynamic_module_names()

        for name in dynamic_names:
            module = builder._modules[name]
            assert module.is_stable is False

    def test_stable_portion_does_not_change(self):
        """Test that stable portion remains constant."""
        builder = PromptBuilder()
        builder.set_style("standard")

        # Build stable portion twice
        stable1 = builder.build_stable("Same tools")
        stable2 = builder.build_stable("Same tools")

        assert stable1 == stable2


class TestExcelConfigManager:
    """Tests for ExcelConfigManager class."""

    def test_create_manager(self):
        """Test creating ExcelConfigManager."""
        manager = ExcelConfigManager()
        assert manager.config_path is not None

    def test_save_and_load(self, tmp_path):
        """Test saving and loading configuration."""
        config_path = tmp_path / "test_prompts.xlsx"
        manager = ExcelConfigManager(config_path)

        # Save default config
        manager.save()

        # Load it back
        loaded_modules = manager.load()

        assert len(loaded_modules) > 0
        assert "core" in loaded_modules

    def test_load_styles(self, tmp_path):
        """Test loading style configurations."""
        config_path = tmp_path / "test_prompts.xlsx"
        manager = ExcelConfigManager(config_path)
        manager.save()

        styles = manager.load_styles()

        assert len(styles) > 0
        assert "standard" in styles

    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file."""
        manager = ExcelConfigManager("/nonexistent/path.xlsx")
        modules = manager.load()
        assert modules == {}


class TestBuildPromptFunction:
    """Tests for build_prompt convenience function."""

    def test_build_prompt_default(self):
        """Test building prompt with defaults."""
        prompt = build_prompt("Test tools")
        assert len(prompt) > 0
        assert "Test tools" in prompt

    def test_build_prompt_with_style(self):
        """Test building prompt with specific style."""
        prompt_concise = build_prompt("Tools", style="concise")
        prompt_detailed = build_prompt("Tools", style="detailed")

        # Detailed should be longer
        assert len(prompt_detailed) > len(prompt_concise)

    def test_build_prompt_with_env(self):
        """Test building prompt with environment info."""
        prompt = build_prompt("Tools", include_env=True)
        assert "Environment" in prompt or "Working directory" in prompt


class TestPromptConfig:
    """Tests for PromptConfig dataclass."""

    def test_default_prompt_config(self):
        """Test default PromptConfig values."""
        config = PromptConfig()
        assert config.source == "default"
        assert config.style == "standard"
        assert config.token_budget == 2000
        assert config.include_environment is False
        assert config.include_git_status is False
        assert len(config.stable_modules) > 0

    def test_custom_prompt_config(self):
        """Test custom PromptConfig values."""
        config = PromptConfig(
            source="excel",
            excel_path="/path/to/config.xlsx",
            style="concise",
            modules=["core", "tools"],
            token_budget=500,
            include_environment=True,
            include_git_status=True,
        )
        assert config.source == "excel"
        assert config.style == "concise"
        assert config.token_budget == 500


class TestAgentPromptIntegration:
    """Tests for Agent integration with modular prompt system."""

    def test_agent_with_default_prompt(self):
        """Test agent with default prompt configuration."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)))

        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        assert agent._prompt_builder is not None
        assert len(agent._stable_system_prompt) > 0

    def test_agent_with_custom_prompt_config(self):
        """Test agent with custom prompt configuration."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)))

        memory = ShortTermMemory()
        registry = ToolRegistry()

        prompt_config = PromptConfig(
            style="concise",
            modules=["core", "tools", "language"],
            token_budget=500,
        )

        agent = ReActAgent(
            llm=llm,
            memory=memory,
            tool_registry=registry,
            verbose=False,
            prompt_config=prompt_config,
        )

        assert agent.prompt_config.style == "concise"
        assert agent._prompt_builder is not None

    def test_agent_system_prompt_contains_tools(self):
        """Test that agent system prompt contains tool descriptions."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)))

        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        messages = memory.get_all()
        system_msg = messages[0]

        # System prompt should contain tool-related content
        assert "Tool" in system_msg["content"] or "tool" in system_msg["content"]

    def test_agent_with_skill_prompt(self):
        """Test agent with skill prompt."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)))

        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=llm,
            memory=memory,
            tool_registry=registry,
            verbose=False,
            skill_prompt="You are a coding assistant.",
        )

        messages = memory.get_all()
        system_msg = messages[0]

        assert "coding assistant" in system_msg["content"]

    def test_stable_prompt_caching(self):
        """Test that stable prompt can be used for caching."""
        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)))

        memory = ShortTermMemory()
        registry = ToolRegistry()

        agent = ReActAgent(llm=llm, memory=memory, tool_registry=registry, verbose=False)

        # Get cache key
        cache_key = agent._prompt_builder.get_cache_key("Test tools")

        # Cache key should be consistent
        assert cache_key.startswith("prompt_")
        assert len(cache_key) == len("prompt_XXXXXXXX")
