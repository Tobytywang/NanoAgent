"""
Agent type definitions.

This module defines the core types used for communication between
the orchestration layer and execution layer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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


@dataclass
class ExecutionEvent:
    """
    Execution event - the basic unit for streaming output.

    Each event represents a discrete step in the execution process,
    allowing external listeners to react to progress updates.
    """
    type: str  # "run_start" / "think" / "tool_call" / "tool_result" / "end"
    data: dict


class AgentEvent(Enum):
    """Event type enumeration for the event system."""
    RUN_START = "run_start"
    THINK_START = "think_start"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RUN_END = "run_end"
