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
        if hasattr(self.config, "retry") and self.config.retry is not None:
            self._llm._retry_config = self.config.retry

        # Inject rate limiter config and instance into LLM client
        if (
            hasattr(self.config, "rate_limiter")
            and self.config.rate_limiter is not None
        ):
            self._llm._rate_limiter_config = self.config.rate_limiter
            from ..llm.rate_limiter import TokenBucketRateLimiter

            self._llm._rate_limiter = TokenBucketRateLimiter(self.config.rate_limiter)

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
            CircuitBreakerConfig,
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
            circuit_breaker_config=getattr(
                self.config.smart_optimization, "circuit_breaker", None
            ),
            tool_resource_limiter_config=getattr(
                self.config, "tool_resource_limiter", None
            ),
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
        if (
            hasattr(self.config, "retry")
            and self.config.retry is not None
            and self.config.retry.enabled
        ):
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

        # Wire rate limiter callback to agent events
        if (
            hasattr(self.config, "rate_limiter")
            and self.config.rate_limiter is not None
            and self.config.rate_limiter.enabled
        ):
            from ..agent.types import AgentEvent

            verbose = self.config.agent.verbose

            def _on_llm_rate_limit(event_data: dict):
                agent.events.emit(AgentEvent.LLM_RATE_LIMITED, event_data)
                if verbose:
                    wait_time = event_data["wait_time"]
                    rpm = event_data["rpm"]
                    print(
                        f"[Rate Limit] Waiting {wait_time:.2f}s "
                        f"(limit: {rpm} rpm)..."
                    )

            self._llm._on_rate_limit_callback = _on_llm_rate_limit

        # Create input sanitizer
        sanitizer = None
        if hasattr(self.config, "sanitizer") and self.config.sanitizer is not None:
            from ..agent.sanitizer import InputSanitizer

            sanitizer = InputSanitizer(self.config.sanitizer, events=agent.events)

        # Create output guard
        output_guard = None
        if (
            hasattr(self.config, "output_guard")
            and self.config.output_guard is not None
        ):
            from ..agent.output_guard import OutputGuard

            output_guard = OutputGuard(self.config.output_guard, events=agent.events)

        # Create harmful content filter
        harmful_filter = None
        if (
            hasattr(self.config, "harmful_content_filter")
            and self.config.harmful_content_filter is not None
        ):
            from ..agent.harmful_filter import HarmfulContentFilter
            from ..config.schema import HarmfulContentFilterConfig

            if isinstance(
                self.config.harmful_content_filter, HarmfulContentFilterConfig
            ):
                harmful_filter = HarmfulContentFilter(
                    self.config.harmful_content_filter, events=agent.events
                )

        # Create result validator
        validator = None
        if (
            hasattr(self.config, "result_validator")
            and self.config.result_validator is not None
        ):
            from ..agent.result_validator import ResultValidator
            from ..config.schema import ResultValidatorConfig

            if isinstance(self.config.result_validator, ResultValidatorConfig):
                validator = ResultValidator(
                    self.config.result_validator, events=agent.events
                )

        # Wire result validator to agent subsystems for schema validation in _observe()
        if validator is not None:
            agent._subsystems.result_validator = validator

        # Create feedback loop
        feedback_loop = None
        if (
            hasattr(self.config, "feedback_loop")
            and self.config.feedback_loop is not None
        ):
            from ..agent.feedback_loop import FeedbackLoop
            from ..config.schema import FeedbackLoopConfig

            if isinstance(self.config.feedback_loop, FeedbackLoopConfig):
                if (
                    self.config.feedback_loop.deviation_feedback_enabled
                    or self.config.feedback_loop.self_correction_enabled
                ):
                    feedback_loop = FeedbackLoop(
                        self.config.feedback_loop, events=agent.events
                    )

        # Wire feedback loop to agent subsystems for deviation injection in _think()
        if feedback_loop is not None:
            agent._subsystems.feedback_loop = feedback_loop

        # Create orchestrator
        orchestrator = AgentOrchestrator(
            agent,
            self.config,
            sanitizer=sanitizer,
            output_guard=output_guard,
            harmful_filter=harmful_filter,
            validator=validator,
            feedback_loop=feedback_loop,
        )

        return orchestrator
