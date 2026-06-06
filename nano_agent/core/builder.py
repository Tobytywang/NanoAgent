"""
Agent Builder - fluent interface for constructing agent instances.

Provides a clean, testable way to assemble agent components.
"""

from typing import Callable, Any

from ..agent import ReActAgent, AgentOrchestrator
from ..agent.subsystems import AgentSubsystems
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

    def with_tools(
        self, registrar: Callable[[ToolRegistry, Any], None]
    ) -> "AgentBuilder":
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

    def with_skills(
        self, loader: Callable[[SkillRegistry, Any], None]
    ) -> "AgentBuilder":
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
        if hasattr(self.config, "llm"):
            self.config.llm.set_llm_client(self._llm)

        # Inject retry config into LLM client
        if hasattr(self.config, "retry"):
            self._llm._retry_config = self.config.retry

        # Create agent subsystems from config
        from ..config.schema import (
            SmartOptimizationConfig,
            OutputStyleConfig,
            CacheConfig,
            CompressorConfig,
            SemanticCompressorConfig,
            ToolMergeConfig,
            ConfirmationConfig,
            ToolOffloadConfig,
            AggressiveOutputConfig,
            StandardizedOutputConfig,
            PromptConfig,
        )

        def _cfg(attr, default_cls):
            val = getattr(self.config, attr, None)
            return val if val is not None else default_cls()

        subsystems = AgentSubsystems.from_configs(
            smart_optimization=_cfg("smart_optimization", SmartOptimizationConfig),
            output_style=_cfg("output_style", OutputStyleConfig),
            cache_config=_cfg("cache", CacheConfig),
            compressor_config=_cfg("compressor", CompressorConfig),
            semantic_compressor_config=_cfg(
                "semantic_compressor", SemanticCompressorConfig
            ),
            tool_merge_config=_cfg("tool_merge", ToolMergeConfig),
            confirmation_config=_cfg("confirmation", ConfirmationConfig),
            offload_config=_cfg("offload", ToolOffloadConfig),
            aggressive_output=_cfg("aggressive_output", AggressiveOutputConfig),
            standardized_output=_cfg("standardized_output", StandardizedOutputConfig),
            prompt_config=_cfg("prompt", PromptConfig),
            context_config=getattr(self.config, "context", None),
            llm=self._llm,
            memory=self._memory,
            llm_config=self.config.llm,
            verbose=self.config.agent.verbose,
        )

        # Create agent
        agent = ReActAgent(
            llm=self._llm,
            memory=self._memory,
            tool_registry=self._tool_registry,
            subsystems=subsystems,
            max_iterations=self.config.agent.max_iterations,
            verbose=self.config.agent.verbose,
            skill_prompt=self._skill_registry.get_combined_system_prompt(),
            tracker=self._tracker,
            prompt_config=self.config.prompt,
            llm_config=self.config.llm,
        )

        # Wire retry callback to agent events
        if hasattr(self.config, "retry") and self.config.retry.enabled:
            from ..agent.types import AgentEvent

            verbose = self.config.agent.verbose

            def _on_llm_retry(event_data: dict):
                agent.events.emit(AgentEvent.LLM_RETRY, event_data)
                if verbose:
                    attempt = event_data["attempt"]
                    max_retries = event_data["max_retries"]
                    delay = event_data["delay"]
                    error = event_data["error"]
                    print(
                        f"[Retry {attempt}/{max_retries}] "
                        f"{error.__class__.__name__}, waiting {delay:.1f}s..."
                    )

            self._llm._on_retry_callback = _on_llm_retry

        # Create orchestrator
        orchestrator = AgentOrchestrator(agent, self.config)

        return orchestrator
