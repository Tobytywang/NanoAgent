"""
Agent subsystems facade - creates and manages all optimization subsystems.

Reduces ReActAgent.__init__ from 23 parameters to ~12 by centralizing
subsystem creation from config objects.
"""

from .token_budget import TokenBudget, TokenBudgetConfig
from .router import QueryRouter, QueryComplexity
from .confidence import ConfidenceParser
from .duplicate import DuplicateDetector
from .stall_detector import StallDetector, StallConfig
from .cache import ToolResultCache, CacheConfig
from .compressor import MessageCompressor, CompressorConfig
from .semantic_compressor import SemanticCompressor, SemanticCompressorConfig
from .tool_offload import ToolOffloadManager
from .output_simplifier import OutputSimplifier
from .result_summarizer import ToolResultSummarizer
from .tool_merger import ToolCallMerger, ToolMergeConfig
from .prejudgment import QueryPrejudgment
from .context import ContextManager
from .confirmation import ConfirmationManager, ConfirmationConfig
from ..config.schema import (
    SmartOptimizationConfig,
    OutputStyleConfig,
    ToolOffloadConfig,
    AggressiveOutputConfig,
    StandardizedOutputConfig,
    PromptConfig,
)


class AgentSubsystems:
    """门面：根据配置创建所有优化子系统"""

    def __init__(
        self,
        token_budget: TokenBudget | None,
        query_router: QueryRouter | None,
        confidence_parser: ConfidenceParser | None,
        query_prejudgment: QueryPrejudgment | None,
        duplicate_detector: DuplicateDetector,
        stall_detector: StallDetector,
        cache: ToolResultCache,
        compressor: MessageCompressor,
        semantic_compressor: SemanticCompressor,
        offload_manager: ToolOffloadManager,
        output_simplifier: OutputSimplifier | None,
        confirmation: ConfirmationManager,
        context_manager: ContextManager | None,
        # Config references (for ReActAgent convenience accessors)
        smart_optimization_config=None,
        output_style_config=None,
        tool_merge_config=None,
        aggressive_output_config=None,
        standardized_output_config=None,
        offload_config=None,
        prompt_config=None,
    ):
        self.token_budget = token_budget
        self.query_router = query_router
        self.confidence_parser = confidence_parser
        self.query_prejudgment = query_prejudgment
        self.duplicate_detector = duplicate_detector
        self.stall_detector = stall_detector
        self.cache = cache
        self.compressor = compressor
        self.semantic_compressor = semantic_compressor
        self.offload_manager = offload_manager
        self.output_simplifier = output_simplifier
        self.confirmation = confirmation
        self.context_manager = context_manager
        # Store config references for ReActAgent
        self._smart_optimization_config = smart_optimization_config
        self._output_style_config = output_style_config
        self._tool_merge_config = tool_merge_config
        self._aggressive_output_config = aggressive_output_config
        self._standardized_output_config = standardized_output_config
        self._offload_config = offload_config
        self._prompt_config = prompt_config

    @classmethod
    def from_defaults(cls) -> "AgentSubsystems":
        """Create subsystems with all default configs (for tests and simple usage)."""
        return cls.from_configs(
            smart_optimization=SmartOptimizationConfig(),
            output_style=OutputStyleConfig(),
            cache_config=CacheConfig(),
            compressor_config=CompressorConfig(),
            semantic_compressor_config=SemanticCompressorConfig(),
            tool_merge_config=ToolMergeConfig(),
            confirmation_config=ConfirmationConfig(),
            offload_config=ToolOffloadConfig(),
            aggressive_output=AggressiveOutputConfig(),
            standardized_output=StandardizedOutputConfig(),
            prompt_config=PromptConfig(),
        )

    @classmethod
    def from_configs(
        cls,
        smart_optimization: SmartOptimizationConfig,
        output_style: OutputStyleConfig,
        cache_config: CacheConfig,
        compressor_config: CompressorConfig,
        semantic_compressor_config: SemanticCompressorConfig,
        tool_merge_config: ToolMergeConfig,
        confirmation_config: ConfirmationConfig,
        offload_config: ToolOffloadConfig,
        aggressive_output: AggressiveOutputConfig,
        standardized_output: StandardizedOutputConfig | None = None,
        prompt_config: PromptConfig | None = None,
        context_config=None,
        llm=None,
        memory=None,
        llm_config=None,
        verbose: bool = False,
    ) -> "AgentSubsystems":
        """从配置对象创建所有子系统"""
        # Token budget
        if smart_optimization.budget_enabled:
            token_budget_config = TokenBudgetConfig(
                initial_budget=smart_optimization.initial_budget,
                warning_thresholds=smart_optimization.budget_warning_thresholds,
                warning_mode=smart_optimization.budget_warning_mode,
                warning_interval=smart_optimization.budget_warning_interval,
                force_summarize=smart_optimization.budget_force_summarize,
                llm_summary_enabled=smart_optimization.budget_llm_summary_enabled,
                llm_summary_max_tokens=smart_optimization.budget_llm_summary_max_tokens,
                wrapup_enabled=smart_optimization.budget_wrapup_enabled,
                wrapup_threshold=smart_optimization.budget_wrapup_threshold,
                wrapup_free_round=smart_optimization.budget_wrapup_free_round,
                wrapup_max_tokens=smart_optimization.budget_wrapup_max_tokens,
            )
            token_budget = TokenBudget(token_budget_config)
        else:
            token_budget = None

        # Query router
        if smart_optimization.routing_enabled:
            query_router = QueryRouter(
                enabled=True,
                simple_direct=smart_optimization.routing_simple_direct,
                moderate_single_tool=smart_optimization.routing_moderate_single_tool,
                simple_budget_ratio=smart_optimization.complexity_budget_simple_ratio,
                moderate_budget_ratio=smart_optimization.complexity_budget_moderate_ratio,
                complex_budget_ratio=smart_optimization.complexity_budget_complex_ratio,
            )
        else:
            query_router = None

        # Confidence parser
        if smart_optimization.confidence_enabled:
            confidence_parser = ConfidenceParser(
                threshold=smart_optimization.confidence_threshold
            )
        else:
            confidence_parser = None

        # Query prejudgment
        if smart_optimization.prejudgment_enabled and llm:
            query_prejudgment = QueryPrejudgment(
                llm=llm,
                simple_prompt=smart_optimization.prejudgment_simple_prompt,
                max_answer_tokens=smart_optimization.prejudgment_max_answer_tokens,
            )
        else:
            query_prejudgment = None

        # Duplicate detector
        duplicate_detector = DuplicateDetector(
            threshold=smart_optimization.duplicate_threshold,
            deep_equal=smart_optimization.duplicate_deep_equal,
        )

        # Stall detector
        stall_detector = StallDetector(
            StallConfig(
                enabled=smart_optimization.stall_detection_enabled,
                patience=smart_optimization.stall_patience,
                similarity_threshold=smart_optimization.stall_similarity_threshold,
                hint_injection=smart_optimization.stall_hint_injection,
            )
        )

        # Cache
        cache = ToolResultCache(cache_config)
        if cache_config and cache_config.warmup_on_restore and cache_config.persist:
            cache.warmup_from_disk()

        # Compressor
        compressor = MessageCompressor(compressor_config)

        # Semantic compressor
        semantic_compressor = SemanticCompressor(
            semantic_compressor_config, llm_config=llm_config
        )

        # Tool offload
        offload_manager = ToolOffloadManager(offload_config)

        # Output simplifier
        output_simplifier = (
            OutputSimplifier(aggressive_output) if aggressive_output.enabled else None
        )

        # Confirmation
        confirmation = ConfirmationManager(confirmation_config)

        # Context manager
        context_manager = (
            ContextManager(
                memory=memory,
                llm=llm,
                config=context_config,
                verbose=verbose,
                llm_config=llm_config,
            )
            if context_config
            else None
        )

        return cls(
            token_budget=token_budget,
            query_router=query_router,
            confidence_parser=confidence_parser,
            query_prejudgment=query_prejudgment,
            duplicate_detector=duplicate_detector,
            stall_detector=stall_detector,
            cache=cache,
            compressor=compressor,
            semantic_compressor=semantic_compressor,
            offload_manager=offload_manager,
            output_simplifier=output_simplifier,
            confirmation=confirmation,
            context_manager=context_manager,
            # Config references
            smart_optimization_config=smart_optimization,
            output_style_config=output_style,
            tool_merge_config=tool_merge_config,
            aggressive_output_config=aggressive_output,
            standardized_output_config=standardized_output,
            offload_config=offload_config,
            prompt_config=prompt_config,
        )
