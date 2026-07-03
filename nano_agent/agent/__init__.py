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
    ExecutionEventType,
    ExecutionHandle,
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
from .token_utils import estimate_tokens, estimate_text_tokens
from .token_budget import TokenBudget, TokenBudgetConfig
from .router import QueryRouter, QueryComplexity, RoutingResult
from .confidence import ConfidenceParser, ConfidenceResult
from .prejudgment import QueryPrejudgment, PrejudgmentResult
from .output_simplifier import OutputSimplifier
from .tool_offload import ToolOffloadManager, OffloadedResult
from .semantic_compressor import SemanticCompressor, SemanticCompressorConfig
from .subsystems import AgentSubsystems
from .output_guard import OutputGuard, OutputGuardResult
from .harmful_filter import HarmfulContentFilter, HarmfulFilterResult
from .result_validator import ResultValidator, ValidationResult
from .feedback_loop import FeedbackLoop, DeviationFeedbackResult, SelfCorrectionResult
from .snapshot import SnapshotManager, Snapshot, SnapshotMetadata
from .consecutive_failure_detector import ConsecutiveFailureDetector

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
    "ExecutionEventType",
    "ExecutionHandle",
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
    # Token estimation
    "estimate_tokens",
    "estimate_text_tokens",
    # Token budget
    "TokenBudget",
    "TokenBudgetConfig",
    # Query router
    "QueryRouter",
    "QueryComplexity",
    "RoutingResult",
    # Confidence parser
    "ConfidenceParser",
    "ConfidenceResult",
    "QueryPrejudgment",
    "PrejudgmentResult",
    "OutputSimplifier",
    # Tool offloading
    "ToolOffloadManager",
    "OffloadedResult",
    # Semantic compression
    "SemanticCompressor",
    "SemanticCompressorConfig",
    # Subsystems facade
    "AgentSubsystems",
    # Output guard
    "OutputGuard",
    "OutputGuardResult",
    # Harmful content filter
    "HarmfulContentFilter",
    "HarmfulFilterResult",
    # Result validator
    "ResultValidator",
    "ValidationResult",
    # Feedback loop
    "FeedbackLoop",
    "DeviationFeedbackResult",
    "SelfCorrectionResult",
    # Snapshot
    "SnapshotManager",
    "Snapshot",
    "SnapshotMetadata",
    # Consecutive failure detector
    "ConsecutiveFailureDetector",
]
