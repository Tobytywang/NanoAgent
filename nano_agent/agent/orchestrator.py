"""
Agent orchestrator - the orchestration layer.

This module provides the unified entry point for agent execution,
handling session management, statistics collection, and event routing.
"""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator, Generator

from .types import (
    ExecutionResult,
    ExecutionEvent,
    ExecutionEventType,
    ExecutionHandle,
    AsyncExecutionHandle,
    AgentEvent,
    TerminationReason,
)
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
        self.snapshot_manager = None  # Set by AgentBuilder

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
        Execute user input synchronously (collects stream result).

        Args:
            user_input: The user's input text
            dry_run: If True, tools are not actually executed

        Returns:
            ExecutionResult containing response and execution metadata
        """
        handle = self.run_stream(user_input, dry_run)
        return handle.collect_result() or ExecutionResult(
            response="No result produced.",
            success=False,
            iterations=0,
            tool_calls=[],
            tokens_used=0,
            session_id=self.session_id,
            termination_reason=TerminationReason.COMPLETED.value,
        )

    def run_stream(self, user_input: str, dry_run: bool = False) -> ExecutionHandle:
        """
        Stream execution via events.

        Yields ExecutionEvent objects for each phase, allowing callers
        to observe progress in real-time. Post-processing (output guard,
        harmful filter, validator) runs after the agent generator completes.

        Args:
            user_input: The user's input text
            dry_run: If True, tools are not actually executed

        Returns:
            ExecutionHandle wrapping an event generator
        """

        def event_generator():
            # Capture original input (user_input may be shadowed by sanitizer)
            original_input = user_input

            # Emit start event
            self.events.emit(
                AgentEvent.RUN_START,
                {"input": original_input, "session_id": self.session_id},
            )

            # Auto-snapshot before run
            if self.snapshot_manager is not None:
                self.snapshot_manager.maybe_auto_snapshot(self.agent, self)

            # Reset feedback loop for new user query
            if self.feedback_loop is not None:
                self.feedback_loop.reset_all()

            # Sanitize input before processing
            sanitized_input = user_input
            if self.sanitizer and self.sanitizer.enabled:
                sanitizer_result = self.sanitizer.sanitize(sanitized_input)
                self.last_sanitizer_result = sanitizer_result
                if sanitizer_result.rejected:
                    early_result = ExecutionResult(
                        response=f"Input rejected: {sanitizer_result.reason}",
                        success=False,
                        iterations=0,
                        tool_calls=[],
                        tokens_used=0,
                        session_id=self.session_id,
                        termination_reason=TerminationReason.INPUT_REJECTED.value,
                    )
                    yield ExecutionEvent(
                        type=ExecutionEventType.RUN_END, data={}, result=early_result
                    )
                    return early_result
                sanitized_input = sanitizer_result.sanitized_input
            else:
                self.last_sanitizer_result = None

            # Delegate to execution layer — forward agent events
            agent_handle = self.agent.run_stream(
                sanitized_input, dry_run=dry_run, session_id=self.session_id
            )
            result = None
            for event in agent_handle.events:
                # Suppress agent's RUN_END — orchestrator yields its own
                if event.type == ExecutionEventType.RUN_END:
                    if event.result is not None:
                        result = event.result
                    continue
                yield event

            if result is None:
                result = ExecutionResult(
                    response="No result produced.",
                    success=False,
                    iterations=0,
                    tool_calls=[],
                    tokens_used=0,
                    session_id=self.session_id,
                    termination_reason=TerminationReason.COMPLETED.value,
                )

            # Auto-rollback on consecutive failures (v0.8.15)
            if (
                result.termination_reason == TerminationReason.AUTO_ROLLBACK.value
                and self.snapshot_manager is not None
            ):
                failure_result = self.agent.get_failure_result()
                rolled_back = self.snapshot_manager.attempt_auto_rollback(
                    self.agent, self, failure_result
                )
                if rolled_back:
                    snapshot_cfg = getattr(self.config, "snapshot", None)
                    on_failure = getattr(
                        snapshot_cfg, "auto_rollback_on_failure", "error"
                    )
                    if on_failure == "retry":
                        # Re-run with restored state (only once) — synchronous
                        result = self.agent.run(
                            sanitized_input, dry_run=dry_run, session_id=self.session_id
                        )

            # Guard output for sensitive information
            if self.output_guard and self.output_guard.enabled:
                guard_result = self.output_guard.guard(result.response)
                self.last_output_guard_result = guard_result
                if guard_result.blocked:
                    result = ExecutionResult(
                        response=f"Output blocked: {guard_result.reason}",
                        success=False,
                        iterations=result.iterations,
                        tool_calls=result.tool_calls,
                        tokens_used=result.tokens_used,
                        session_id=self.session_id,
                        termination_reason=TerminationReason.OUTPUT_BLOCKED.value,
                    )
                    yield ExecutionEvent(
                        type=ExecutionEventType.RUN_END, data={}, result=result
                    )
                    return result
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
                    result = ExecutionResult(
                        response=f"Output blocked: {filter_result.reason}",
                        success=False,
                        iterations=result.iterations,
                        tool_calls=result.tool_calls,
                        tokens_used=result.tokens_used,
                        session_id=self.session_id,
                        termination_reason=TerminationReason.HARMFUL_CONTENT_BLOCKED.value,
                    )
                    yield ExecutionEvent(
                        type=ExecutionEventType.RUN_END, data={}, result=result
                    )
                    return result
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

                    # Validation blocked — attempt self-correction
                    if (
                        self.feedback_loop is not None
                        and self.feedback_loop.should_retry(validator_result)
                        and validation_pass < max_correction
                    ):
                        failed_check_types = [
                            c.check_type for c in validator_result.failed_checks
                        ]
                        self.feedback_loop.record_correction_attempt()
                        self.feedback_loop.emit_self_correction_event(
                            failed_check_types
                        )

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

                        # Re-run agent with feedback — synchronous (not streamed)
                        result = self.agent.run(
                            sanitized_input, dry_run=dry_run, session_id=self.session_id
                        )
                        cumulative_tokens += result.tokens_used
                        continue
                    else:
                        used_correction = (
                            self.feedback_loop is not None
                            and self.feedback_loop.correction_attempts_used > 0
                        )
                        result = ExecutionResult(
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
                        yield ExecutionEvent(
                            type=ExecutionEventType.RUN_END,
                            data={},
                            result=result,
                        )
                        return result
            else:
                self.last_validator_result = None

            # Collect statistics
            self._collect_stats(result)

            # Emit end event
            self.events.emit(AgentEvent.RUN_END, {"result": result})

            # Yield final RUN_END with (possibly post-processed) result
            yield ExecutionEvent(
                type=ExecutionEventType.RUN_END, data={}, result=result
            )
            return result

        return ExecutionHandle(events=event_generator())

    async def run_async(
        self, user_input: str, dry_run: bool = False
    ) -> ExecutionResult:
        """
        Async execute user input (collects async stream result).

        Args:
            user_input: The user's input text
            dry_run: If True, tools are not actually executed

        Returns:
            ExecutionResult containing response and execution metadata
        """
        handle = self.run_stream_async(user_input, dry_run)
        return await handle.collect_result() or ExecutionResult(
            response="No result produced.",
            success=False,
            iterations=0,
            tool_calls=[],
            tokens_used=0,
            session_id=self.session_id,
            termination_reason=TerminationReason.COMPLETED.value,
        )

    def run_stream_async(
        self, user_input: str, dry_run: bool = False
    ) -> AsyncExecutionHandle:
        """
        Async streaming execution via events.

        Like run_stream() but uses async generators and the agent's
        run_stream_async() for true token-by-token output.

        Args:
            user_input: The user's input text
            dry_run: If True, tools are not actually executed

        Returns:
            AsyncExecutionHandle wrapping an async event generator
        """

        async def event_generator() -> AsyncGenerator[ExecutionEvent, None]:
            # Emit start event
            self.events.emit(
                AgentEvent.RUN_START,
                {"input": user_input, "session_id": self.session_id},
            )

            # Auto-snapshot before run
            if self.snapshot_manager is not None:
                self.snapshot_manager.maybe_auto_snapshot(self.agent, self)

            # Reset feedback loop for new user query
            if self.feedback_loop is not None:
                self.feedback_loop.reset_all()

            # Sanitize input before processing
            sanitized_input = user_input
            if self.sanitizer and self.sanitizer.enabled:
                sanitizer_result = self.sanitizer.sanitize(sanitized_input)
                self.last_sanitizer_result = sanitizer_result
                if sanitizer_result.rejected:
                    early_result = ExecutionResult(
                        response=f"Input rejected: {sanitizer_result.reason}",
                        success=False,
                        iterations=0,
                        tool_calls=[],
                        tokens_used=0,
                        session_id=self.session_id,
                        termination_reason=TerminationReason.INPUT_REJECTED.value,
                    )
                    yield ExecutionEvent(
                        type=ExecutionEventType.RUN_END,
                        data={},
                        result=early_result,
                    )
                    return
                sanitized_input = sanitizer_result.sanitized_input
            else:
                self.last_sanitizer_result = None

            # Delegate to execution layer — forward agent async events
            agent_handle = self.agent.run_stream_async(
                sanitized_input, dry_run=dry_run, session_id=self.session_id
            )
            result = None
            async for event in agent_handle.events:
                # Propagate cancellation to agent
                if handle.cancelled:
                    agent_handle.cancel()
                # Suppress agent's RUN_END — orchestrator yields its own
                if event.type == ExecutionEventType.RUN_END:
                    if event.result is not None:
                        result = event.result
                    continue
                yield event

            if result is None:
                result = ExecutionResult(
                    response="No result produced.",
                    success=False,
                    iterations=0,
                    tool_calls=[],
                    tokens_used=0,
                    session_id=self.session_id,
                    termination_reason=TerminationReason.COMPLETED.value,
                )

            # Auto-rollback on consecutive failures
            if (
                result.termination_reason == TerminationReason.AUTO_ROLLBACK.value
                and self.snapshot_manager is not None
            ):
                failure_result = self.agent.get_failure_result()
                rolled_back = self.snapshot_manager.attempt_auto_rollback(
                    self.agent, self, failure_result
                )
                if rolled_back:
                    snapshot_cfg = getattr(self.config, "snapshot", None)
                    on_failure = getattr(
                        snapshot_cfg, "auto_rollback_on_failure", "error"
                    )
                    if on_failure == "retry":
                        result = await self.agent.run_async(
                            sanitized_input,
                            dry_run=dry_run,
                            session_id=self.session_id,
                        )

            # Guard output for sensitive information
            if self.output_guard and self.output_guard.enabled:
                guard_result = self.output_guard.guard(result.response)
                self.last_output_guard_result = guard_result
                if guard_result.blocked:
                    result = ExecutionResult(
                        response=f"Output blocked: {guard_result.reason}",
                        success=False,
                        iterations=result.iterations,
                        tool_calls=result.tool_calls,
                        tokens_used=result.tokens_used,
                        session_id=self.session_id,
                        termination_reason=TerminationReason.OUTPUT_BLOCKED.value,
                    )
                    yield ExecutionEvent(
                        type=ExecutionEventType.RUN_END, data={}, result=result
                    )
                    return
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
                    result = ExecutionResult(
                        response=f"Output blocked: {filter_result.reason}",
                        success=False,
                        iterations=result.iterations,
                        tool_calls=result.tool_calls,
                        tokens_used=result.tokens_used,
                        session_id=self.session_id,
                        termination_reason=TerminationReason.HARMFUL_CONTENT_BLOCKED.value,
                    )
                    yield ExecutionEvent(
                        type=ExecutionEventType.RUN_END, data={}, result=result
                    )
                    return
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

                    # Validation blocked — attempt self-correction
                    if (
                        self.feedback_loop is not None
                        and self.feedback_loop.should_retry(validator_result)
                        and validation_pass < max_correction
                    ):
                        failed_check_types = [
                            c.check_type for c in validator_result.failed_checks
                        ]
                        self.feedback_loop.record_correction_attempt()
                        self.feedback_loop.emit_self_correction_event(
                            failed_check_types
                        )

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

                        # Re-run agent with feedback — async
                        result = await self.agent.run_async(
                            sanitized_input,
                            dry_run=dry_run,
                            session_id=self.session_id,
                        )
                        cumulative_tokens += result.tokens_used
                        continue
                    else:
                        used_correction = (
                            self.feedback_loop is not None
                            and self.feedback_loop.correction_attempts_used > 0
                        )
                        result = ExecutionResult(
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
                        yield ExecutionEvent(
                            type=ExecutionEventType.RUN_END,
                            data={},
                            result=result,
                        )
                        return
            else:
                self.last_validator_result = None

            # Collect statistics
            self._collect_stats(result)

            # Emit end event
            self.events.emit(AgentEvent.RUN_END, {"result": result})

            # Yield final RUN_END with (possibly post-processed) result
            yield ExecutionEvent(
                type=ExecutionEventType.RUN_END, data={}, result=result
            )

        return AsyncExecutionHandle(events=event_generator())

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
