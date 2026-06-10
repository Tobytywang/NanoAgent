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
from .sanitizer import InputSanitizer, SanitizerResult

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
]
