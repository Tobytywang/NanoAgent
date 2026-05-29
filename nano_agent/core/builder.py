"""
Agent Builder - fluent interface for constructing agent instances.

Provides a clean, testable way to assemble agent components.
"""

from typing import Callable, Any

from ..agent import ReActAgent, AgentOrchestrator
from ..llm import BaseLLM
from ..memory import BaseMemory
from ..tools import ToolRegistry
from ..skills import SkillRegistry, SkillLoader
from ..monitoring import MetricsTracker


class AgentBuilder:
    """
    Builder pattern for constructing AgentOrchestrator instances.

    Provides a fluent interface for configuring and assembling
    agent components (LLM, Memory, Tools, Skills).

    Example:
        builder = AgentBuilder(config)
        orchestrator = (builder
            .with_llm(create_llm_from_config)
            .with_memory(create_memory)
            .with_tools(register_builtin_tools)
            .with_skills(load_skills)
            .build())
    """

    def __init__(self, config: Any):
        """
        Initialize builder with configuration.

        Args:
            config: Configuration object containing all settings
        """
        self.config = config
        self._llm: BaseLLM | None = None
        self._memory: BaseMemory | None = None
        self._tool_registry: ToolRegistry | None = None
        self._skill_registry: SkillRegistry | None = None
        self._tracker: MetricsTracker | None = None

    def with_llm(self, factory: Callable[[Any], BaseLLM]) -> "AgentBuilder":
        """
        Set LLM client using a factory function.

        Args:
            factory: Function that takes config and returns BaseLLM instance

        Returns:
            self for chaining
        """
        self._llm = factory(self.config.llm)
        return self

    def with_llm_instance(self, llm: BaseLLM) -> "AgentBuilder":
        """
        Set LLM client directly.

        Args:
            llm: BaseLLM instance

        Returns:
            self for chaining
        """
        self._llm = llm
        return self

    def with_memory(self, factory: Callable[[Any], BaseMemory]) -> "AgentBuilder":
        """
        Set memory using a factory function.

        Args:
            factory: Function that takes config and returns BaseMemory instance

        Returns:
            self for chaining
        """
        self._memory = factory(self.config)
        return self

    def with_memory_instance(self, memory: BaseMemory) -> "AgentBuilder":
        """
        Set memory directly.

        Args:
            memory: BaseMemory instance

        Returns:
            self for chaining
        """
        self._memory = memory
        return self

    def with_tools(self, registrar: Callable[[ToolRegistry, Any], None]) -> "AgentBuilder":
        """
        Register tools using a registrar function.

        Args:
            registrar: Function that takes (registry, config) and registers tools

        Returns:
            self for chaining
        """
        if self._tool_registry is None:
            self._tool_registry = ToolRegistry()
        registrar(self._tool_registry, self.config)
        return self

    def with_tool_registry(self, registry: ToolRegistry) -> "AgentBuilder":
        """
        Set tool registry directly.

        Args:
            registry: ToolRegistry instance

        Returns:
            self for chaining
        """
        self._tool_registry = registry
        return self

    def with_skills(self, loader: Callable[[SkillRegistry, Any], None]) -> "AgentBuilder":
        """
        Load skills using a loader function.

        Args:
            loader: Function that takes (registry, config) and loads skills

        Returns:
            self for chaining
        """
        if self._skill_registry is None:
            self._skill_registry = SkillRegistry()
        loader(self._skill_registry, self.config)
        return self

    def with_skill_registry(self, registry: SkillRegistry) -> "AgentBuilder":
        """
        Set skill registry directly.

        Args:
            registry: SkillRegistry instance

        Returns:
            self for chaining
        """
        self._skill_registry = registry
        return self

    def with_tracker(self, tracker: MetricsTracker) -> "AgentBuilder":
        """
        Set metrics tracker.

        Args:
            tracker: MetricsTracker instance

        Returns:
            self for chaining
        """
        self._tracker = tracker
        return self

    def build(self) -> AgentOrchestrator:
        """
        Build and return the configured AgentOrchestrator.

        Returns:
            Configured AgentOrchestrator instance

        Raises:
            ValueError: If required components (LLM, memory) are not set
        """
        if self._llm is None:
            raise ValueError("LLM must be set before building agent")
        if self._memory is None:
            raise ValueError("Memory must be set before building agent")
        if self._tool_registry is None:
            self._tool_registry = ToolRegistry()
        if self._skill_registry is None:
            self._skill_registry = SkillRegistry()

        # Inject LLM client into config so get_context_length() can query API
        if hasattr(self.config, 'llm'):
            self.config.llm.set_llm_client(self._llm)

        # Create agent
        agent = ReActAgent(
            llm=self._llm,
            memory=self._memory,
            tool_registry=self._tool_registry,
            max_iterations=self.config.agent.max_iterations,
            verbose=self.config.agent.verbose,
            skill_prompt=self._skill_registry.get_combined_system_prompt(),
            tracker=self._tracker,
            context_config=self.config.context if hasattr(self.config, 'context') else None,
            confirmation_config=self.config.confirmation if hasattr(self.config, 'confirmation') else None,
            output_style_config=self.config.output_style if hasattr(self.config, 'output_style') else None,
            tool_merge_config=self.config.tool_merge if hasattr(self.config, 'tool_merge') else None,
            cache_config=self.config.cache if hasattr(self.config, 'cache') else None,
            compressor_config=self.config.compressor if hasattr(self.config, 'compressor') else None,
            smart_optimization_config=self.config.smart_optimization if hasattr(self.config, 'smart_optimization') else None,
            prompt_config=self.config.prompt if hasattr(self.config, 'prompt') else None,
            llm_config=self.config.llm,
        )

        # Create orchestrator
        orchestrator = AgentOrchestrator(agent, self.config)

        return orchestrator
