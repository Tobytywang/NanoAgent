"""
Agent module - ReAct implementation.

This module provides the execution layer (ReActAgent) and orchestration
layer (AgentOrchestrator) for the NanoAgent framework.
"""

from .base import BaseAgent
from .react import ReActAgent
from .types import (
    ExecutionResult,
    ThinkResult,
    ExecutionEvent,
    AgentEvent,
    TerminationReason,
    Plan,
    PlanPhase,
    RiskLevel,
)
from .events import EventEmitter
from .budget import Budget, BudgetChecker
from .orchestrator import AgentOrchestrator, SessionStats
from .context import ContextManager, NineSectionSummary
from .confirmation import ConfirmationManager, ConfirmationConfig
from .git_manager import GitManager, GitCommit
from .token_utils import estimate_tokens, estimate_text_tokens
from .token_budget import TokenBudget, TokenBudgetConfig
from .router import QueryRouter, QueryComplexity, RoutingResult
from .confidence import ConfidenceParser, ConfidenceResult
from .prejudgment import QueryPrejudgment, PrejudgmentResult
from .output_simplifier import OutputSimplifier
from .tool_offload import ToolOffloadManager, OffloadedResult
from .semantic_compressor import SemanticCompressor, SemanticCompressorConfig
from .subsystems import AgentSubsystems
from .sanitizer import (
    InputSanitizer,
    SanitizerResult,
    PIIDesensitizer,
    PIIMatch,
    summarize_pii_matches,
    remove_overlapping,
)
from .output_guard import (
    OutputGuard,
    OutputGuardResult,
    SensitiveMatch,
    summarize_sensitive_matches,
)
from .harmful_filter import (
    HarmfulContentFilter,
    HarmfulFilterResult,
    HarmfulMatch,
    summarize_harmful_matches,
)
from .result_validator import (
    ResultValidator,
    ValidationResult,
    ValidationCheck,
    summarize_validation_checks,
)
from .feedback_loop import (
    FeedbackLoop,
    DeviationFeedbackResult,
    SelfCorrectionResult,
)
from .snapshot import SnapshotManager, Snapshot, SnapshotMetadata
from ..tools.resource_limiter import (
    ToolTimeoutWrapper,
    ToolRateLimiter,
    RateLimitResult,
    RateLimitType,
)

__all__ = [
    # Base
    "BaseAgent",
    # Execution layer
    "ReActAgent",
    # Orchestration layer
    "AgentOrchestrator",
    "SessionStats",
    # Types
    "ExecutionResult",
    "ThinkResult",
    "ExecutionEvent",
    "AgentEvent",
    "TerminationReason",
    "Plan",
    "PlanPhase",
    "RiskLevel",
    # Events
    "EventEmitter",
    # Budget
    "Budget",
    "BudgetChecker",
    # Context management
    "ContextManager",
    "NineSectionSummary",
    # Confirmation
    "ConfirmationManager",
    "ConfirmationConfig",
    # Git integration
    "GitManager",
    "GitCommit",
    # Token estimation
    "estimate_tokens",
    "estimate_text_tokens",
    # Token budget (v0.7.5)
    "TokenBudget",
    "TokenBudgetConfig",
    # Query router (v0.7.5)
    "QueryRouter",
    "QueryComplexity",
    "RoutingResult",
    # Confidence parser (v0.7.5)
    "ConfidenceParser",
    "ConfidenceResult",
    "QueryPrejudgment",
    "PrejudgmentResult",
    "OutputSimplifier",
    # Tool offloading (v0.7.17)
    "ToolOffloadManager",
    "OffloadedResult",
    # Semantic compression (v0.7.19)
    "SemanticCompressor",
    "SemanticCompressorConfig",
    # Subsystems facade (v0.7.20)
    "AgentSubsystems",
    # Input sanitizer (v0.8.3)
    "InputSanitizer",
    "SanitizerResult",
    # PII desensitization (v0.8.4)
    "PIIDesensitizer",
    "PIIMatch",
    "summarize_pii_matches",
    "remove_overlapping",
    # Output guard (v0.8.5)
    "OutputGuard",
    "OutputGuardResult",
    "SensitiveMatch",
    "summarize_sensitive_matches",
    # Harmful content filter (v0.8.6)
    "HarmfulContentFilter",
    "HarmfulFilterResult",
    "HarmfulMatch",
    "summarize_harmful_matches",
    # Result validator (v0.8.7)
    "ResultValidator",
    "ValidationResult",
    "ValidationCheck",
    "summarize_validation_checks",
    # Feedback loop (v0.8.9)
    "FeedbackLoop",
    "DeviationFeedbackResult",
    "SelfCorrectionResult",
    # Tool resource limiter (v0.8.10)
    "ToolTimeoutWrapper",
    "ToolRateLimiter",
    "RateLimitResult",
    "RateLimitType",
]
