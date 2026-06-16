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
    from .feedback_loop import FeedbackLoop
    from .harmful_filter import HarmfulContentFilter
    from .output_guard import OutputGuard
    from .react import ReActAgent
    from .result_validator import ResultValidator
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
        output_guard: "OutputGuard | None" = None,
        harmful_filter: "HarmfulContentFilter | None" = None,
        validator: "ResultValidator | None" = None,
        feedback_loop: "FeedbackLoop | None" = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            agent: The execution layer agent to delegate to
            config: Optional configuration object
            sanitizer: Optional input sanitizer for pre-execution validation
            output_guard: Optional output guard for post-execution sensitive data interception
            harmful_filter: Optional harmful content filter for post-execution safety checks
            validator: Optional result validator for post-execution correctness verification
            feedback_loop: Optional feedback loop for deviation backflow and self-correction
        """
        self.agent = agent
        self.config = config
        self.sanitizer = sanitizer
        self.output_guard = output_guard
        self.harmful_filter = harmful_filter
        self.validator = validator
        self.feedback_loop = feedback_loop
        self.session_id = self._generate_session_id()
        self.stats = SessionStats()
        self.events = EventEmitter()
        self.last_sanitizer_result = None
        self.last_output_guard_result = None
        self.last_harmful_filter_result = None
        self.last_validator_result = None

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

        # Reset feedback loop for new user query
        if self.feedback_loop is not None:
            self.feedback_loop.reset_all()

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

        # Guard output for sensitive information
        if self.output_guard and self.output_guard.enabled:
            guard_result = self.output_guard.guard(result.response)
            self.last_output_guard_result = guard_result
            if guard_result.blocked:
                return ExecutionResult(
                    response=f"Output blocked: {guard_result.reason}",
                    success=False,
                    iterations=result.iterations,
                    tool_calls=result.tool_calls,
                    tokens_used=result.tokens_used,
                    session_id=self.session_id,
                    termination_reason=TerminationReason.OUTPUT_BLOCKED.value,
                )
            if guard_result.matches:
                result = ExecutionResult(
                    response=guard_result.guarded,
                    success=result.success,
                    iterations=result.iterations,
                    tool_calls=result.tool_calls,
                    tokens_used=result.tokens_used,
                    session_id=result.session_id,
                    termination_reason=result.termination_reason,
                )
        else:
            self.last_output_guard_result = None

        # Filter harmful content in output
        if self.harmful_filter and self.harmful_filter.enabled:
            filter_result = self.harmful_filter.filter(result.response)
            self.last_harmful_filter_result = filter_result
            if filter_result.blocked:
                return ExecutionResult(
                    response=f"Output blocked: {filter_result.reason}",
                    success=False,
                    iterations=result.iterations,
                    tool_calls=result.tool_calls,
                    tokens_used=result.tokens_used,
                    session_id=self.session_id,
                    termination_reason=TerminationReason.HARMFUL_CONTENT_BLOCKED.value,
                )
            if filter_result.matches:
                result = ExecutionResult(
                    response=filter_result.filtered,
                    success=result.success,
                    iterations=result.iterations,
                    tool_calls=result.tool_calls,
                    tokens_used=result.tokens_used,
                    session_id=result.session_id,
                    termination_reason=result.termination_reason,
                )
        else:
            self.last_harmful_filter_result = None

        # Validate result correctness — with self-correction loop
        if self.validator and self.validator.enabled:
            max_correction = (
                self.feedback_loop.remaining_correction_attempts
                if self.feedback_loop
                else 0
            )
            cumulative_tokens = result.tokens_used

            for validation_pass in range(max_correction + 1):
                validator_result = self.validator.validate(result.response)
                self.last_validator_result = validator_result

                if not validator_result.blocked:
                    # Validation passed (or only warnings/annotations)
                    if validator_result.failed_checks:
                        result = ExecutionResult(
                            response=validator_result.validated,
                            success=result.success,
                            iterations=result.iterations,
                            tool_calls=result.tool_calls,
                            tokens_used=cumulative_tokens,
                            session_id=result.session_id,
                            termination_reason=result.termination_reason,
                        )
                    break

                # Validation blocked — attempt self-correction if enabled and attempts remain
                if (
                    self.feedback_loop is not None
                    and self.feedback_loop.should_retry(validator_result)
                    and validation_pass < max_correction
                ):
                    # Emit self-correction event
                    failed_check_types = [
                        c.check_type for c in validator_result.failed_checks
                    ]
                    self.feedback_loop.record_correction_attempt()
                    self.feedback_loop.emit_self_correction_event(failed_check_types)

                    # Build feedback and inject into agent memory
                    feedback_msg = self.feedback_loop.build_correction_feedback(
                        validator_result
                    )
                    self.agent.memory.add_user_message(feedback_msg)

                    if self.agent.verbose:
                        print(
                            f"[Self-Correction] Attempt "
                            f"{self.feedback_loop.correction_attempts_used}/"
                            f"{self.feedback_loop.config.self_correction_max_attempts}: "
                            f"retrying..."
                        )

                    # Re-run agent with feedback in memory
                    result = self.agent.run(
                        user_input, dry_run=dry_run, session_id=self.session_id
                    )
                    cumulative_tokens += result.tokens_used
                    continue
                else:
                    # All attempts exhausted or self-correction disabled
                    used_correction = (
                        self.feedback_loop is not None
                        and self.feedback_loop.correction_attempts_used > 0
                    )
                    return ExecutionResult(
                        response=f"Output blocked: {validator_result.reason}",
                        success=False,
                        iterations=result.iterations,
                        tool_calls=result.tool_calls,
                        tokens_used=cumulative_tokens,
                        session_id=self.session_id,
                        termination_reason=(
                            TerminationReason.SELF_CORRECTION_EXHAUSTED.value
                            if used_correction
                            else TerminationReason.VALIDATION_FAILED.value
                        ),
                    )
        else:
            self.last_validator_result = None

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
