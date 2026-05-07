"""
Agent module - ReAct implementation.

This module provides the execution layer (ReActAgent) and orchestration
layer (AgentOrchestrator) for the NanoAgent framework.
"""

from .base import BaseAgent
from .react import ReActAgent
from .types import (
    ExecutionResult, ThinkResult, ExecutionEvent, AgentEvent,
    Plan, PlanPhase
)
from .events import EventEmitter
from .budget import Budget, BudgetChecker
from .orchestrator import AgentOrchestrator, SessionStats
from .context import ContextManager, NineSectionSummary
from .token_utils import estimate_tokens, estimate_text_tokens

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
    "Plan",
    "PlanPhase",
    # Events
    "EventEmitter",
    # Budget
    "Budget",
    "BudgetChecker",
    # Context management
    "ContextManager",
    "NineSectionSummary",
    "estimate_tokens",
    "estimate_text_tokens",
]
