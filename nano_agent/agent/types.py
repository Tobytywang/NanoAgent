"""
Agent type definitions.

This module defines the core types used for communication between
the orchestration layer and execution layer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..core.types import RiskLevel, Plan, PlanPhase  # noqa: F401


class TerminationReason(str, Enum):
    """Reason why the ReAct loop terminated."""

    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    BUDGET_EXHAUSTED = "budget_exhausted"
    BUDGET_WRAP_UP = "budget_wrap_up"
    STALL_DETECTED = "stall_detected"
    CONFIDENCE_EARLY_STOP = "confidence_early_stop"
    CONFIDENCE_VERIFIED = "confidence_verified"
    ROUTING_LIMIT = "routing_limit"
    DUPLICATE_BLOCKED = "duplicate_blocked"
    PREJUDGMENT_SIMPLE = "prejudgment_simple"
    INPUT_REJECTED = "input_rejected"
    OUTPUT_BLOCKED = "output_blocked"
    HARMFUL_CONTENT_BLOCKED = "harmful_content_blocked"
    VALIDATION_FAILED = "validation_failed"
    SELF_CORRECTION_EXHAUSTED = "self_correction_exhausted"
    AUTO_ROLLBACK = "auto_rollback"


@dataclass(frozen=True)
class ExecutionResult:
    """
    Execution result - the contract between orchestration and execution layers.

    This is an immutable dataclass that captures all information about
    a completed execution, including the response, statistics, and metadata.
    """

    response: str
    success: bool
    iterations: int
    tool_calls: list[dict]
    tokens_used: int
    session_id: str
    termination_reason: str = ""


@dataclass
class ThinkResult:
    """
    Think phase result.

    Represents the output of the _think() method, which calls the LLM
    and returns the response along with any tool calls.
    """

    response_text: str
    tool_calls: list[Any]  # List of ToolCall
    usage: Any  # LLMUsage
    is_final: bool  # True if no tool calls (final answer)
    # Confidence-based early stop fields
    confidence: float = 1.0  # Confidence level (0.0-1.0), from LLM response
    can_answer: bool = True  # Whether LLM has enough info to answer definitively


@dataclass
class ExecutionEvent:
    """
    Execution event - the basic unit for streaming output.

    Each event represents a discrete step in the execution process,
    allowing external listeners to react to progress updates.
    """

    type: str  # "run_start" / "think" / "tool_call" / "tool_result" / "end"
    data: dict


class ExecutionMode(Enum):
    """Agent execution mode — controlled by circuit breaker."""

    AUTO = "auto"  # Fully automatic execution
    SUPERVISED = "supervised"  # Every tool call requires user confirmation


class AgentEvent(Enum):
    """Event type enumeration for the event system."""

    RUN_START = "run_start"
    THINK_START = "think_start"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RUN_END = "run_end"
    CONFIRMATION_REQUIRED = "confirmation_required"
    BUDGET_WRAPUP = "budget_wrapup"
    DUPLICATE_BLOCKED = "duplicate_blocked"
    STALL_DETECTED = "stall_detected"
    LLM_RETRY = "llm_retry"
    LLM_RATE_LIMITED = "llm_rate_limited"
    CIRCUIT_BREAKER = "circuit_breaker"
    INPUT_REJECTED = "input_rejected"
    OUTPUT_BLOCKED = "output_blocked"
    HARMFUL_CONTENT_DETECTED = "harmful_content_detected"
    VALIDATION_FAILED = "validation_failed"
    DEVIATION_FEEDBACK = "deviation_feedback"
    SELF_CORRECTION = "self_correction"
    TOOL_RATE_LIMITED = "tool_rate_limited"
    SNAPSHOT_SAVED = "snapshot_saved"
    SNAPSHOT_RESTORED = "snapshot_restored"
    SNAPSHOT_DELETED = "snapshot_deleted"
    AUDIT_LOG_ENTRY = "audit_log_entry"
    AUTO_ROLLBACK_TRIGGERED = "auto_rollback_triggered"
    AUTO_ROLLBACK_COMPLETED = "auto_rollback_completed"
