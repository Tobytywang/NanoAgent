"""
Agent orchestrator - the orchestration layer.

This module provides the unified entry point for agent execution,
handling session management, statistics collection, and event routing.
"""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .types import ExecutionResult, AgentEvent, TerminationReason
from .events import EventEmitter

if TYPE_CHECKING:
    from .react import ReActAgent
    from .sanitizer import InputSanitizer


@dataclass
class SessionStats:
    """
    Session statistics - cumulative metrics across multiple runs.

    Tracks totals for tokens, tool calls, and iterations within
    a session.
    """

    total_tokens: int = 0
    total_tool_calls: int = 0
    total_iterations: int = 0


class AgentOrchestrator:
    """
    Orchestrator - the unified entry point for agent execution.

    This class provides:
    - Session management (session ID generation)
    - Statistics collection (cumulative tracking)
    - Event routing (emit events for external listeners)
    - Execution mode switching (real vs dry-run)
    """

    def __init__(
        self,
        agent: "ReActAgent",
        config: Any = None,
        sanitizer: "InputSanitizer | None" = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            agent: The execution layer agent to delegate to
            config: Optional configuration object
            sanitizer: Optional input sanitizer for pre-execution validation
        """
        self.agent = agent
        self.config = config
        self.sanitizer = sanitizer
        self.session_id = self._generate_session_id()
        self.stats = SessionStats()
        self.events = EventEmitter()
        self.last_sanitizer_result = None

    # Property proxies for backward compatibility with CLI
    @property
    def memory(self):
        """Proxy to the wrapped agent's memory."""
        return self.agent.memory

    @property
    def llm(self):
        """Proxy to the wrapped agent's LLM."""
        return self.agent.llm

    @property
    def verbose(self):
        """Proxy to the wrapped agent's verbose setting."""
        return self.agent.verbose

    @verbose.setter
    def verbose(self, value: bool):
        """Set the wrapped agent's verbose setting."""
        self.agent.verbose = value

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())[:8]

    def run(self, user_input: str, dry_run: bool = False) -> ExecutionResult:
        """
        Execute user input - the unified entry point.

        Args:
            user_input: The user's input text
            dry_run: If True, tools are not actually executed

        Returns:
            ExecutionResult containing response and execution metadata
        """
        # Emit start event
        self.events.emit(
            AgentEvent.RUN_START, {"input": user_input, "session_id": self.session_id}
        )

        # Sanitize input before processing
        if self.sanitizer and self.sanitizer.enabled:
            sanitizer_result = self.sanitizer.sanitize(user_input)
            self.last_sanitizer_result = sanitizer_result
            if sanitizer_result.rejected:
                return ExecutionResult(
                    response=f"Input rejected: {sanitizer_result.reason}",
                    success=False,
                    iterations=0,
                    tool_calls=[],
                    tokens_used=0,
                    session_id=self.session_id,
                    termination_reason=TerminationReason.INPUT_REJECTED.value,
                )
            user_input = sanitizer_result.sanitized_input
        else:
            self.last_sanitizer_result = None

        # Delegate to execution layer
        result = self.agent.run(user_input, dry_run=dry_run, session_id=self.session_id)

        # Collect statistics
        self._collect_stats(result)

        # Emit end event
        self.events.emit(AgentEvent.RUN_END, {"result": result})

        return result

    def run_dry(self, user_input: str) -> ExecutionResult:
        """
        Execute in dry-run mode - preview without actual tool execution.

        Args:
            user_input: The user's input text

        Returns:
            ExecutionResult with placeholder tool results
        """
        return self.run(user_input, dry_run=True)

    def _collect_stats(self, result: ExecutionResult) -> None:
        """
        Accumulate statistics from an execution result.

        Args:
            result: The execution result to collect stats from
        """
        self.stats.total_tokens += result.tokens_used
        self.stats.total_tool_calls += len(result.tool_calls)
        self.stats.total_iterations += result.iterations

    def get_stats(self) -> SessionStats:
        """
        Get cumulative session statistics.

        Returns:
            SessionStats with totals for this session
        """
        return self.stats

    def reset_stats(self) -> None:
        """Reset session statistics to zero."""
        self.stats = SessionStats()

    def new_session(self) -> str:
        """
        Start a new session with a fresh session ID.

        Returns:
            The new session ID
        """
        self.session_id = self._generate_session_id()
        self.reset_stats()
        return self.session_id
