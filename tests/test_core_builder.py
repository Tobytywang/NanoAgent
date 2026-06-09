"""
Tests for Agent Builder module.

Tests the fluent interface for constructing agent instances.
"""

import pytest
from unittest.mock import Mock, MagicMock

pytestmark = pytest.mark.unit

from nano_agent.core.builder import AgentBuilder
from nano_agent.agent import AgentOrchestrator
from nano_agent.tools import ToolRegistry
from nano_agent.skills import SkillRegistry
from nano_agent.monitoring import MetricsTracker


class TestAgentBuilder:
    """Tests for AgentBuilder class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for testing."""
        config = Mock()
        config.llm = Mock()
        config.agent = Mock(max_iterations=10, verbose=False)
        config.context = None
        config.confirmation = None
        config.output_style = None
        config.tool_merge = None
        config.cache = None
        config.compressor = None
        config.smart_optimization = None
        config.prompt = Mock(
            source="default",
            style="standard",
            excel_path=None,
            stable_modules=["core", "tools"],
            enable_caching=True,
        )
        # Explicitly set retry and rate_limiter to None (no retry/rate limiting in tests)
        config.retry = None
        config.rate_limiter = None
        return config

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM for testing."""
        llm = Mock()
        llm.model = "test-model"
        return llm

    @pytest.fixture
    def mock_memory(self):
        """Create a mock memory for testing."""
        from nano_agent.memory import ShortTermMemory

        return ShortTermMemory()

    def test_initialization(self, mock_config):
        """Test builder initializes with config."""
        builder = AgentBuilder(mock_config)

        assert builder.config == mock_config
        assert builder._llm is None
        assert builder._memory is None
        assert builder._tool_registry is None
        assert builder._skill_registry is None
        assert builder._tracker is None

    def test_with_llm_factory(self, mock_config, mock_llm):
        """Test with_llm() sets LLM from factory."""
        builder = AgentBuilder(mock_config)

        def factory(llm_config):
            return mock_llm

        result = builder.with_llm(factory)

        assert builder._llm == mock_llm
        assert result == builder  # Returns self for chaining

    def test_with_llm_instance(self, mock_config, mock_llm):
        """Test with_llm_instance() sets LLM directly."""
        builder = AgentBuilder(mock_config)

        result = builder.with_llm_instance(mock_llm)

        assert builder._llm == mock_llm
        assert result == builder

    def test_with_memory_factory(self, mock_config, mock_memory):
        """Test with_memory() sets memory from factory."""
        builder = AgentBuilder(mock_config)

        def factory(config):
            return mock_memory

        result = builder.with_memory(factory)

        assert builder._memory == mock_memory
        assert result == builder

    def test_with_memory_instance(self, mock_config, mock_memory):
        """Test with_memory_instance() sets memory directly."""
        builder = AgentBuilder(mock_config)

        result = builder.with_memory_instance(mock_memory)

        assert builder._memory == mock_memory
        assert result == builder

    def test_with_tools_creates_registry(self, mock_config):
        """Test with_tools() creates registry if needed."""
        builder = AgentBuilder(mock_config)

        def registrar(registry, config):
            pass

        result = builder.with_tools(registrar)

        assert builder._tool_registry is not None
        assert isinstance(builder._tool_registry, ToolRegistry)
        assert result == builder

    def test_with_tools_registers_tools(self, mock_config):
        """Test with_tools() calls registrar function."""
        builder = AgentBuilder(mock_config)
        registrar_called = False

        def registrar(registry, config):
            nonlocal registrar_called
            registrar_called = True

        builder.with_tools(registrar)

        assert registrar_called is True

    def test_with_tool_registry(self, mock_config):
        """Test with_tool_registry() sets registry directly."""
        builder = AgentBuilder(mock_config)
        registry = ToolRegistry()

        result = builder.with_tool_registry(registry)

        assert builder._tool_registry == registry
        assert result == builder

    def test_with_skills(self, mock_config):
        """Test with_skills() loads skills."""
        builder = AgentBuilder(mock_config)
        loader_called = False

        def loader(registry, config):
            nonlocal loader_called
            loader_called = True

        result = builder.with_skills(loader)

        assert builder._skill_registry is not None
        assert loader_called is True
        assert result == builder

    def test_with_skill_registry(self, mock_config):
        """Test with_skill_registry() sets registry directly."""
        builder = AgentBuilder(mock_config)
        registry = SkillRegistry()

        result = builder.with_skill_registry(registry)

        assert builder._skill_registry == registry
        assert result == builder

    def test_with_tracker(self, mock_config):
        """Test with_tracker() sets metrics tracker."""
        builder = AgentBuilder(mock_config)
        tracker = MetricsTracker()

        result = builder.with_tracker(tracker)

        assert builder._tracker == tracker
        assert result == builder

    def test_build_creates_orchestrator(self, mock_config, mock_llm, mock_memory):
        """Test build() returns AgentOrchestrator."""
        builder = AgentBuilder(mock_config)
        builder.with_llm_instance(mock_llm)
        builder.with_memory_instance(mock_memory)

        orchestrator = builder.build()

        assert orchestrator is not None
        assert isinstance(orchestrator, AgentOrchestrator)

    def test_build_raises_without_llm(self, mock_config, mock_memory):
        """Test build() raises error if LLM not set."""
        builder = AgentBuilder(mock_config)
        builder.with_memory_instance(mock_memory)

        with pytest.raises(ValueError, match="LLM must be set"):
            builder.build()

    def test_build_raises_without_memory(self, mock_config, mock_llm):
        """Test build() raises error if memory not set."""
        builder = AgentBuilder(mock_config)
        builder.with_llm_instance(mock_llm)

        with pytest.raises(ValueError, match="Memory must be set"):
            builder.build()

    def test_build_creates_default_registries(self, mock_config, mock_llm, mock_memory):
        """Test build() creates default tool registry."""
        builder = AgentBuilder(mock_config)
        builder.with_llm_instance(mock_llm)
        builder.with_memory_instance(mock_memory)

        orchestrator = builder.build()

        assert orchestrator.agent.tool_registry is not None

    def test_fluent_interface(self, mock_config, mock_llm, mock_memory):
        """Test builder supports method chaining."""
        builder = AgentBuilder(mock_config)

        result = (
            builder.with_llm_instance(mock_llm)
            .with_memory_instance(mock_memory)
            .with_tool_registry(ToolRegistry())
            .with_skill_registry(SkillRegistry())
        )

        assert result == builder

        orchestrator = result.build()
        assert orchestrator is not None

    def test_build_uses_config_values(self, mock_config, mock_llm, mock_memory):
        """Test build() uses config values for agent setup."""
        mock_config.agent.max_iterations = 15
        mock_config.agent.verbose = True

        builder = AgentBuilder(mock_config)
        builder.with_llm_instance(mock_llm)
        builder.with_memory_instance(mock_memory)

        orchestrator = builder.build()

        assert orchestrator.agent.max_iterations == 15
        assert orchestrator.agent.verbose is True

    def test_build_with_tracker(self, mock_config, mock_llm, mock_memory):
        """Test build() uses provided tracker."""
        builder = AgentBuilder(mock_config)
        tracker = MetricsTracker()

        builder.with_llm_instance(mock_llm)
        builder.with_memory_instance(mock_memory)
        builder.with_tracker(tracker)

        orchestrator = builder.build()

        assert orchestrator.agent.tracker == tracker

    def test_build_with_existing_registries(self, mock_config, mock_llm, mock_memory):
        """Test build() uses provided registries."""
        builder = AgentBuilder(mock_config)
        tool_registry = ToolRegistry()

        builder.with_llm_instance(mock_llm)
        builder.with_memory_instance(mock_memory)
        builder.with_tool_registry(tool_registry)

        orchestrator = builder.build()

        assert orchestrator.agent.tool_registry == tool_registry


class TestAgentBuilderIntegration:
    """Integration tests for AgentBuilder."""

    @pytest.mark.integration
    def test_build_full_agent(self, temp_dir):
        """Test building a complete agent with all components."""
        from nano_agent.config.schema import (
            Config,
            LLMConfig,
            AgentConfig,
            MemoryConfig,
        )
        from nano_agent.llm import create_llm_from_config
        from nano_agent.memory import ShortTermMemory

        config = Config()
        config.llm = LLMConfig(provider="ollama", model="test-model")
        config.agent = AgentConfig(max_iterations=5, verbose=False)
        config.memory = MemoryConfig(type="short_term", max_messages=50)

        builder = AgentBuilder(config)

        # Use a mock LLM for testing
        mock_llm = Mock()
        mock_llm.model = "test-model"

        memory = ShortTermMemory()

        orchestrator = (
            builder.with_llm_instance(mock_llm)
            .with_memory_instance(memory)
            .with_tool_registry(ToolRegistry())
            .with_skill_registry(SkillRegistry())
            .with_tracker(MetricsTracker())
            .build()
        )

        assert orchestrator is not None
        assert orchestrator.agent is not None
