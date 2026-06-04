"""
ReAct Agent implementation.

This module implements the execution layer of the agent architecture,
following the Think -> Act -> Observe cycle.
"""

import time
from typing import Generator

from .base import BaseAgent
from .prompts import (
    REACT_SYSTEM_PROMPT,
    REACT_SYSTEM_PROMPT_CONCISE,
    REACT_SYSTEM_PROMPT_STANDARD,
    REACT_SYSTEM_PROMPT_CONCISE_WITH_CONFIDENCE,
    REACT_SYSTEM_PROMPT_STANDARD_WITH_CONFIDENCE,
    TOOL_DESCRIPTION_TEMPLATE,
    CONFIDENCE_SUFFIX,
)
from .types import ExecutionResult, ThinkResult, AgentEvent, TerminationReason
from .events import EventEmitter
from .budget import Budget, BudgetChecker
from .undo import UndoStack
from .subsystems import AgentSubsystems
from .router import QueryComplexity, QueryRouter
from .tool_merger import ToolCallMerger
from .result_summarizer import ToolResultSummarizer, SummarizerConfig
from .prompt_builder import PromptBuilder
from ..llm.messages import ToolCall
from ..tools.base import ToolResult
from ..monitoring import MetricsTracker, RawLLMCallData, RawToolExecutionData


def _safe_str(text: str) -> str:
    """Safely convert string for printing, removing invalid Unicode characters."""
    if not text:
        return text
    try:
        return text.encode("utf-8", errors="replace").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


# Simple question patterns that don't need tools
SIMPLE_QUESTION_PATTERNS = [
    # Greetings
    "你好",
    "hello",
    "hi",
    "嗨",
    "早上好",
    "下午好",
    "晚上好",
    # Thanks
    "谢谢",
    "thanks",
    "thank you",
    "感谢",
    # Simple questions (can answer directly)
    "你是谁",
    "who are you",
    "你的名字",
    "what is your name",
    "你能做什么",
    "what can you do",
    "你有什么功能",
    # Confirmations
    "好的",
    "ok",
    "okay",
    "明白",
    "了解",
    "清楚了",
]


def _is_simple_question(user_input: str) -> bool:
    """
    Check if the question is simple enough to answer directly without tools.

    Args:
        user_input: User's input text

    Returns:
        True if the question is simple and can be answered directly
    """
    input_lower = user_input.lower().strip()

    # Check against simple patterns
    for pattern in SIMPLE_QUESTION_PATTERNS:
        if pattern in input_lower:
            return True

    # Very short questions (less than 6 chars) are often simple
    if len(input_lower) < 6:
        return True

    return False


class ReActAgent(BaseAgent):
    """
    ReAct (Reasoning + Acting) Agent implementation.

    This is the execution layer that follows the Think -> Act -> Observe cycle.
    It is designed to be controlled by the orchestration layer (AgentOrchestrator).
    """

    def __init__(
        self,
        llm,
        memory,
        tool_registry,
        subsystems: AgentSubsystems | None = None,
        max_iterations: int = 10,
        verbose: bool = True,
        skill_prompt: str = "",
        tracker: MetricsTracker | None = None,
        events: EventEmitter | None = None,
        budget: Budget | None = None,
        prompt_config=None,
        llm_config=None,
    ):
        """
        Initialize the ReAct agent.

        Args:
            llm: LLM client instance
            memory: Memory system instance
            tool_registry: Tool registry instance
            subsystems: Agent optimization subsystems facade (default: created from defaults)
            max_iterations: Maximum reasoning iterations
            verbose: Whether to print debug information
            skill_prompt: Additional prompt from skills
            tracker: Metrics tracker for monitoring
            events: Event emitter for external listeners
            budget: Budget constraints for execution
            prompt_config: Prompt configuration for v0.7.6
            llm_config: LLM configuration
        """
        super().__init__(llm, memory, tool_registry, max_iterations)
        self.verbose = verbose
        self.skill_prompt = skill_prompt
        self.tracker = tracker or MetricsTracker()
        self.events = events or EventEmitter()
        self.budget_checker = BudgetChecker(
            budget or Budget(max_iterations=max_iterations)
        )

        # Subsystems facade (replaces 15+ individual config params)
        if subsystems is None:
            subsystems = AgentSubsystems.from_defaults()
        self._subsystems = subsystems

        # Convenience accessors for frequently-used subsystems and configs
        self.token_budget = subsystems.token_budget
        self.query_router = subsystems.query_router
        self.confidence_parser = subsystems.confidence_parser
        self.query_prejudgment = subsystems.query_prejudgment
        self.cache = subsystems.cache
        self.compressor = subsystems.compressor
        self.semantic_compressor = subsystems.semantic_compressor
        self.confirmation = subsystems.confirmation
        self.context_manager = subsystems.context_manager

        # Config accessors (read by methods outside __init__)
        self.smart_optimization_config = subsystems._smart_optimization_config
        self.output_style_config = subsystems._output_style_config
        self.tool_merge_config = subsystems._tool_merge_config
        self.aggressive_output_config = subsystems._aggressive_output_config
        self.standardized_output_config = subsystems._standardized_output_config
        self.offload_config = subsystems._offload_config
        self.prompt_config = prompt_config or subsystems._prompt_config

        # Execution state
        self._undo_stack = UndoStack()
        self._round_counter = 0
        self._tool_call_records: list[dict] = []
        self._total_tokens: int = 0
        self._session_id: str = ""
        self._routing_max_tools: int = (
            -1
        )  # Max tools for current query (-1 = unlimited)

        self._wrapup_issued = False

        # Real token tracking for v0.7.12 decision points
        self._last_prompt_tokens: int | None = None

        # Prompt builder (v0.7.6)
        self._prompt_builder: PromptBuilder | None = None
        self._stable_system_prompt: str = ""

        self._setup_prompt_builder()
        self._setup_system_prompt()

    def _setup_prompt_builder(self) -> None:
        """Initialize PromptBuilder and build stable portion (v0.7.6)."""
        if self.prompt_config.source == "excel" and self.prompt_config.excel_path:
            try:
                self._prompt_builder = PromptBuilder.from_excel(
                    self.prompt_config.excel_path
                )
            except Exception as e:
                if self.verbose:
                    print(f"[Prompt] Failed to load Excel config: {e}, using default")
                self._prompt_builder = PromptBuilder()
        else:
            self._prompt_builder = PromptBuilder()

        # Set style
        style = self.prompt_config.style or self.output_style_config.style
        self._prompt_builder.set_style(style)

        # v0.7.15: Inject aggressive_output module if enabled
        if self.aggressive_output_config.enabled:
            from .prompt_modules import AGGRESSIVE_OUTPUT_CONTENTS, PromptModule

            level = self.aggressive_output_config.level
            if level in AGGRESSIVE_OUTPUT_CONTENTS:
                aggressive_module = PromptModule(
                    name="aggressive_output",
                    description=f"Aggressive output ({level})",
                    content=AGGRESSIVE_OUTPUT_CONTENTS[level],
                    priority=41,
                    always_on=False,
                    token_estimate=40,
                    enabled=True,
                    is_stable=True,
                    category="output",
                )
                self._prompt_builder._modules["aggressive_output"] = aggressive_module
                if "aggressive_output" not in self._prompt_builder.config.modules:
                    self._prompt_builder.config.modules.append("aggressive_output")

        # Build stable portion (only once)
        tools_desc = PromptBuilder.format_tools_description(self.tool_registry, style)
        self._stable_system_prompt = self._prompt_builder.build_stable(
            tools_description=tools_desc,
            stable_modules=self.prompt_config.stable_modules,
        )

        # Set stable system prompt to memory for prefix caching (v0.7.7)
        if self.prompt_config.enable_caching:
            self.memory.set_stable_system_prompt(self._stable_system_prompt)

        if self.verbose:
            stable_names = self._prompt_builder.get_stable_module_names()
            print(f"[Prompt] Stable modules: {stable_names}")
            if self.prompt_config.enable_caching:
                print(f"[Prompt] Prefix caching enabled")

    def _setup_system_prompt(self) -> None:
        """Set up the system prompt with tool descriptions."""
        # If using modular prompt system (v0.7.6)
        if self._prompt_builder is not None and self._stable_system_prompt:
            # Build dynamic portion
            dynamic_parts = []

            # Add skill prompt if available
            if self.skill_prompt:
                dynamic_parts.append(f"## Skills\n\n{self.skill_prompt}")

            # Add confidence suffix if enabled
            if (
                self.smart_optimization_config.confidence_enabled
                and self.confidence_parser is not None
            ):
                dynamic_parts.append(CONFIDENCE_SUFFIX)

            # Build dynamic portion from prompt builder
            dynamic_content = self._prompt_builder.build_dynamic(
                skill_prompt="",  # Already added above
                confidence_enabled=False,  # Already added above
            )
            if dynamic_content:
                dynamic_parts.append(dynamic_content)

            # Combine stable + dynamic
            full_prompt = self._stable_system_prompt
            if dynamic_parts:
                full_prompt += "\n\n" + "\n\n".join(dynamic_parts)

            self.memory.set_system_prompt(full_prompt)
            return

        # Fallback to legacy prompt system
        style = self.output_style_config.style
        tools_desc = PromptBuilder.format_tools_description(self.tool_registry, style)

        # Determine if confidence markers should be added
        use_confidence = (
            self.smart_optimization_config.confidence_enabled
            and self.confidence_parser is not None
        )

        # Select prompt template based on style and confidence
        if style == "concise":
            template = (
                REACT_SYSTEM_PROMPT_CONCISE_WITH_CONFIDENCE
                if use_confidence
                else REACT_SYSTEM_PROMPT_CONCISE
            )
        elif style == "standard":
            template = (
                REACT_SYSTEM_PROMPT_STANDARD_WITH_CONFIDENCE
                if use_confidence
                else REACT_SYSTEM_PROMPT_STANDARD
            )
        else:
            # Detailed mode: append confidence suffix if enabled
            template = REACT_SYSTEM_PROMPT
            if use_confidence:
                template = template + CONFIDENCE_SUFFIX

        system_prompt = template.format(tools_description=tools_desc)

        # Add skill prompt if available
        if self.skill_prompt:
            system_prompt = f"{system_prompt}\n\n## Skills\n\n{self.skill_prompt}"

        self.memory.set_system_prompt(system_prompt)

    def run(
        self, user_input: str, dry_run: bool = False, session_id: str = ""
    ) -> ExecutionResult:
        """
        Run the ReAct loop to process user input.

        Args:
            user_input: The user's input text
            dry_run: If True, tools are not actually executed
            session_id: Session identifier for tracking

        Returns:
            ExecutionResult containing response and execution metadata
        """
        # Prepare execution
        self._prepare_run(user_input, session_id)

        # Phase 1: Rule-based routing (QueryRouter, zero cost)
        routing_result = None
        if self.query_router is not None:
            routing_result = self.query_router.classify(user_input)
            self._routing_max_tools = routing_result.suggested_max_tools

            if self.verbose:
                print(
                    f"[Router] Complexity: {routing_result.complexity.value}, "
                    f"max_tools: {self._routing_max_tools}, "
                    f"budget_ratio: {routing_result.suggested_budget_ratio:.0%}"
                )

            # Adjust token budget based on complexity (v0.7.16)
            if (
                self.token_budget is not None
                and self.smart_optimization_config.complexity_budget_enabled
                and routing_result.suggested_budget_ratio < 1.0
            ):
                base_budget = self.smart_optimization_config.initial_budget
                self.token_budget.set_budget_ratio(
                    routing_result.suggested_budget_ratio, base_budget
                )
                if self.verbose:
                    print(
                        f"[Router] Budget adjusted to {self.token_budget.initial_budget} "
                        f"({routing_result.suggested_budget_ratio:.0%} of {base_budget})"
                    )

            # Rule-based SIMPLE -> LLM-generated answer
            if routing_result.complexity == QueryComplexity.SIMPLE:
                response = QueryRouter.answer_simple(self.llm, user_input)
                self.tracker.end_run(response)
                return self._build_result(
                    response,
                    0,
                    success=True,
                    termination_reason=TerminationReason.COMPLETED.value,
                )

        # Phase 2: LLM-based prejudgment (only when router defaulted to COMPLEX)
        if self.query_prejudgment is not None:
            should_prejudge = routing_result is None or (
                routing_result.complexity == QueryComplexity.COMPLEX
                and "defaulting to complex" in routing_result.reason.lower()
            )
            if should_prejudge:
                prejudgment_result = self.query_prejudgment.prejudge(user_input)
                if self.verbose:
                    print(
                        f"[Prejudgment] Complexity: {prejudgment_result.complexity.value}, "
                        f"tokens: {prejudgment_result.prejudgment_tokens}"
                    )

                if prejudgment_result.complexity == QueryComplexity.SIMPLE:
                    response = prejudgment_result.answer or QueryRouter.answer_simple(
                        self.llm, user_input
                    )
                    self.tracker.end_run(response)
                    return self._build_result(
                        response,
                        0,
                        success=True,
                        termination_reason=TerminationReason.PREJUDGMENT_SIMPLE.value,
                    )
                elif prejudgment_result.complexity == QueryComplexity.MODERATE:
                    self._routing_max_tools = 1

        # Concise mode simple question check
        if (
            self.output_style_config.style == "concise"
            and QueryRouter.is_simple_greeting(user_input)
        ):
            # Direct answer for simple questions (skip tool calls)
            response = QueryRouter.answer_simple(self.llm, user_input)
            self.tracker.end_run(response)
            return self._build_result(
                response,
                0,
                success=True,
                termination_reason=TerminationReason.COMPLETED.value,
            )

        iteration = 0
        tool_calls_in_round = 0  # Track tool calls for routing limits

        while iteration < self.max_iterations:
            iteration += 1

            # Budget check
            if not self.budget_checker.can_continue(
                iteration, self._total_tokens, len(self._tool_call_records)
            ):
                break

            # Token budget check with progressive warnings (v0.7.8)
            if self.token_budget is not None:
                # Check for progressive warnings
                warning = self.token_budget.check_warning(iteration)
                if warning:
                    self._handle_budget_warning(warning)

                # Budget wrap-up round (v0.7.9)
                if self.token_budget.should_wrapup() and not self._wrapup_issued:
                    self._wrapup_issued = True
                    self.events.emit(
                        AgentEvent.BUDGET_WRAPUP,
                        {"remaining": self.token_budget.remaining},
                    )
                    self.memory.add_user_message(
                        "[System] Token budget is critically low. This is the final round. "
                        "Please summarize your findings, list any unfinished work, "
                        "and provide the best answer you can."
                    )
                    if self.verbose:
                        print(
                            "[Budget Wrap-Up] Token budget critically low — entering final round"
                        )

                    self.tracker.start_iteration(iteration)
                    think = self._think()

                    # Track usage properly then refund if free round
                    self.token_budget.consume(think.usage.total_tokens)
                    if self.token_budget.config.wrapup_free_round:
                        self.token_budget.remaining += think.usage.total_tokens

                    # If LLM gave a final answer → return it
                    if think.is_final:
                        self.tracker.end_iteration()
                        self.tracker.end_run(think.response_text)
                        return self._build_result(
                            think.response_text,
                            iteration,
                            success=True,
                            termination_reason=TerminationReason.BUDGET_WRAP_UP.value,
                        )

                    # If LLM still wants tools → force summarize instead
                    response = self._force_summarize()
                    self.tracker.end_run(response)
                    return self._build_result(
                        response,
                        iteration,
                        success=True,
                        termination_reason=TerminationReason.BUDGET_WRAP_UP.value,
                    )

                # Check for force summarize
                if self.token_budget.should_summarize():
                    response = self._force_summarize()
                    self.tracker.end_run(response)
                    return self._build_result(
                        response,
                        iteration,
                        success=True,
                        termination_reason=TerminationReason.BUDGET_EXHAUSTED.value,
                    )

            self.tracker.start_iteration(iteration)

            if self.verbose:
                print(f"\n[Iteration {iteration}/{self.max_iterations}]")

            # Think phase
            think = self._think()

            # Confidence-based early stop (v0.7.5)
            if self.confidence_parser is not None and think.is_final:
                should_stop, conf_result = self.confidence_parser.should_stop_early(
                    think.response_text
                )
                if should_stop:
                    if self.verbose:
                        print(f"[Confidence] Early stop: {conf_result.confidence:.2f}")
                    self.tracker.end_iteration()
                    self.tracker.end_run(conf_result.cleaned_response)
                    return self._build_result(
                        conf_result.cleaned_response,
                        iteration,
                        success=True,
                        termination_reason=TerminationReason.CONFIDENCE_EARLY_STOP.value,
                    )

            if think.is_final:
                self.tracker.end_iteration()
                self.tracker.end_run(think.response_text)
                return self._build_result(
                    think.response_text,
                    iteration,
                    success=True,
                    termination_reason=TerminationReason.COMPLETED.value,
                )

            # Merge similar tool calls for token efficiency
            merged_tool_calls = self._merge_tool_calls(think.tool_calls)

            # Act and Observe phases
            for tool_call in merged_tool_calls:
                # Check routing limit (v0.7.5)
                if self._routing_max_tools >= 0:
                    if tool_calls_in_round >= self._routing_max_tools:
                        if self.verbose:
                            print(
                                f"[Router] Reached max tools limit: {self._routing_max_tools}"
                            )
                        # Record all remaining tool calls as skipped
                        remaining_calls = merged_tool_calls[
                            merged_tool_calls.index(tool_call) :
                        ]
                        for skipped_call in remaining_calls:
                            self.tracker.record_skipped_tool_call(
                                skipped_call.name,
                                skipped_call.arguments,
                                "routing_limit",
                            )
                        # Force summarize with current info
                        response = self._force_summarize()
                        self.tracker.end_run(response)
                        return self._build_result(
                            response,
                            iteration,
                            success=True,
                            termination_reason=TerminationReason.ROUTING_LIMIT.value,
                        )

                result = self._act(tool_call, dry_run)
                self._observe(tool_call, result)
                tool_calls_in_round += 1

                # Update token budget (v0.7.5)
                if self.token_budget is not None:
                    self.token_budget.consume(think.usage.total_tokens)

            self.tracker.end_iteration()

            # Stall detection (v0.7.16)
            if self._subsystems.stall_detector.config.enabled:
                iter_tool_names = [tc.name for tc in merged_tool_calls]
                iter_tool_results = []
                for tc in merged_tool_calls:
                    for rec in self._tool_call_records:
                        if rec.get("tool") == tc.name:
                            iter_tool_results.append(str(rec.get("result", "")))
                            break
                    else:
                        iter_tool_results.append("")

                self._subsystems.stall_detector.record_iteration(
                    iter_tool_names, iter_tool_results
                )
                stall_result = self._subsystems.stall_detector.check_stall()
                if stall_result.is_stalled and stall_result.hint:
                    self.events.emit(
                        AgentEvent.STALL_DETECTED,
                        {
                            "stalled_iterations": stall_result.stalled_iterations,
                        },
                    )
                    self.memory.add_user_message(f"[System] {stall_result.hint}")
                    if self.verbose:
                        print(
                            f"[Stall] Detected ({stall_result.stalled_iterations}x), hint injected"
                        )

        # Reached max iterations or budget exhausted
        response = "I apologize, I couldn't complete this task within the iteration limit. Please try simplifying your request."
        self.tracker.end_run(response)
        return self._build_result(
            response,
            iteration,
            success=False,
            termination_reason=TerminationReason.MAX_ITERATIONS.value,
        )

    def _prepare_run(self, user_input: str, session_id: str) -> None:
        """
        Prepare for execution.

        Args:
            user_input: The user's input text
            session_id: Session identifier
        """
        # Reset execution state
        self._round_counter += 1
        self._undo_stack.start_round(f"round_{self._round_counter}")
        self._tool_call_records = []
        self._total_tokens = 0
        self._session_id = session_id
        self._pending_name_updates = []

        # Reset duplicate detection state (v0.7.9)
        self._subsystems.duplicate_detector.reset()
        self._wrapup_issued = False

        # Reset stall detection state (v0.7.16)
        self._subsystems.stall_detector.reset()

        # Reset real token tracking for v0.7.12
        self._last_prompt_tokens = None

        # Add user message to memory
        self.memory.add_user_message(user_input)

        # Start tracking
        self.tracker.start_run(user_input)

        # Emit start event
        self.events.emit(
            AgentEvent.RUN_START, {"input": user_input, "session_id": session_id}
        )

    def _think(self) -> ThinkResult:
        """
        Think phase: Call LLM and get response.

        Returns:
            ThinkResult containing response text and any tool calls
        """
        self.events.emit(
            AgentEvent.THINK_START, {"iteration": len(self._tool_call_records) + 1}
        )

        # v0.7.12: Context pressure check using real tokens from previous iteration
        # v0.7.13: Pass calibration factor for more accurate estimation
        calibration_factor = self.token_budget.get_calibration_factor()
        if self.context_manager:
            self.context_manager.check_and_compress(
                last_prompt_tokens=self._last_prompt_tokens,
                calibration_factor=calibration_factor,
            )

        # Get context and tools
        messages = self.memory.get_all()

        # v0.7.12: Apply message compression using real tokens from previous iteration
        # v0.7.13: Pass calibration factor
        if self.compressor.should_compress(
            messages,
            last_prompt_tokens=self._last_prompt_tokens,
            calibration_factor=calibration_factor,
        ):
            original_count = len(messages)
            messages = self.compressor.compress(
                messages,
                last_prompt_tokens=self._last_prompt_tokens,
                calibration_factor=calibration_factor,
            )
            if self.verbose and len(messages) < original_count:
                print(
                    f"[Compressor] Reduced {original_count} messages to {len(messages)}"
                )

        # v0.7.19: Semantic compression (second pass, after rule-based compression)
        if self.semantic_compressor.should_compress(messages):
            original_count = len(messages)
            messages = self.semantic_compressor.compress(messages)
            if self.verbose and len(messages) < original_count:
                print(
                    f"[SemanticCompressor] Merged similar messages: "
                    f"{original_count} -> {len(messages)}"
                )

        tools_schema = self.tool_registry.get_all_schemas()

        # Prefix caching support (v0.7.7)
        system_stable = None
        if self.prompt_config.enable_caching and self._stable_system_prompt:
            system_stable = self._stable_system_prompt
            if self.verbose:
                print(
                    f"[Caching] Using stable system prompt ({len(system_stable)} chars)"
                )

        # Call LLM
        llm_start = time.perf_counter()
        response_text, tool_calls, usage = self.llm.chat(
            messages=messages,
            tools=tools_schema if tools_schema else None,
            system_stable=system_stable,
        )
        llm_latency = (time.perf_counter() - llm_start) * 1000

        # Report cache hit if available (Anthropic)
        if usage.cache_read_tokens > 0 and self.verbose:
            print(f"[Caching] Cache hit: {usage.cache_read_tokens} tokens saved")

        # v0.7.12: Store real prompt_tokens for next iteration's decision
        # v0.7.13: Record calibration data (actual vs estimated)
        # v0.7.18: Compute estimated before RawLLMCallData
        estimated_prompt_tokens = 0
        if usage.prompt_tokens > 0:
            self._last_prompt_tokens = usage.prompt_tokens

            from .token_utils import estimate_tokens

            estimated_prompt_tokens = estimate_tokens(messages)
            self.token_budget.record_calibration_data(
                estimated=estimated_prompt_tokens, actual=usage.prompt_tokens
            )

        # Record LLM call with raw data (decoupled API, v0.7.18: include estimation fields)
        self.tracker.record_raw_llm_call(
            RawLLMCallData(
                llm=self.llm,
                messages=messages,
                tools_schema=tools_schema,
                response_text=response_text,
                tool_calls=tool_calls,  # Pass raw ToolCall objects
                usage=usage,
                latency_ms=llm_latency,
                estimated_tokens=estimated_prompt_tokens,
                calibration_factor=self.token_budget.get_calibration_factor(),
            )
        )

        # Update token count
        self._total_tokens += usage.total_tokens

        # v0.7.18: Structured deviation logging (replaces temporary verbose print)
        if usage.prompt_tokens > 0 and estimated_prompt_tokens > 0:
            deviation_pct = abs(usage.prompt_tokens - estimated_prompt_tokens) / max(
                estimated_prompt_tokens, 1
            )
            if deviation_pct > 0.50 and self.verbose:
                print(
                    f"[Estimation] WARNING: Deviation {deviation_pct:.0%} "
                    f"(estimated={estimated_prompt_tokens}, actual={usage.prompt_tokens})"
                )
            elif deviation_pct > 0.10 and self.verbose:
                print(
                    f"[Estimation] Deviation: {deviation_pct:.0%} "
                    f"(estimated={estimated_prompt_tokens}, actual={usage.prompt_tokens})"
                )

        # Verbose output
        if self.verbose and response_text:
            print(f"[Think] {_safe_str(response_text[:200])}...")

        # Add assistant message to memory if there are tool calls
        if tool_calls:
            self.memory.add_assistant_message(
                response_text, tool_calls=[tc.to_dict() for tc in tool_calls]
            )

        return ThinkResult(
            response_text=response_text,
            tool_calls=tool_calls or [],
            usage=usage,
            is_final=not tool_calls,
        )

    def _merge_tool_calls(self, tool_calls: list[ToolCall]) -> list[ToolCall]:
        """
        Merge similar tool calls to reduce iteration count.

        Args:
            tool_calls: Original tool calls from LLM

        Returns:
            Merged tool calls (possibly fewer than input)
        """
        print(f"[Merge] Called with {len(tool_calls) if tool_calls else 0} tool calls")
        print(
            f"[Merge] enabled={self.tool_merge_config.enabled}, concise_only={self.tool_merge_config.concise_only}, style={self.output_style_config.style}"
        )

        if not tool_calls or not self.tool_merge_config.enabled:
            print("[Merge] Skipping: no calls or disabled")
            return tool_calls

        # Only merge in concise mode if configured
        if (
            self.tool_merge_config.concise_only
            and self.output_style_config.style != "concise"
        ):
            print("[Merge] Skipping: concise_only check failed")
            return tool_calls

        merger = ToolCallMerger(self.tool_merge_config)
        original_count = len(tool_calls)
        merged = merger.analyze_and_merge(tool_calls)

        # Always print merge result for debugging
        print(f"[Merge] Input: {original_count} calls, Output: {len(merged)} calls")

        return merged

    def _act(self, tool_call: ToolCall, dry_run: bool = False) -> ToolResult:
        """
        Act phase: Execute a tool call.

        Args:
            tool_call: The tool call to execute
            dry_run: If True, return placeholder result without executing

        Returns:
            ToolResult from the execution
        """
        # Check for duplicate tool calls (v0.7.8)
        if not dry_run and self._check_duplicate_tool_call(tool_call):
            # Record as skipped
            self.tracker.record_skipped_tool_call(
                tool_call.name, tool_call.arguments, "duplicate"
            )
            # Return cached result or empty result
            cached_result = self.cache.get_cached_result(
                tool_call.name, tool_call.arguments
            )
            if cached_result is not None:
                result = cached_result
            else:
                result = ToolResult(
                    success=True, output="[跳过] 检测到重复调用，已跳过"
                )
            # Record tool call
            self._tool_call_records.append(
                {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                    "success": result.success,
                    "output_preview": result.output[:100] if result.output else None,
                }
            )
            return result

        # Emit tool call event
        self.events.emit(
            AgentEvent.TOOL_CALL,
            {"tool": tool_call.name, "arguments": tool_call.arguments},
        )

        # Handle dry-run mode
        if dry_run:
            result = ToolResult(success=True, output="[预览模式] 未实际执行")
        else:
            # Check cache first
            cached_result = self.cache.get_cached_result(
                tool_call.name, tool_call.arguments
            )
            if cached_result is not None:
                # Cache now returns string content, wrap in ToolResult
                result = ToolResult(success=True, output=cached_result)
                if self.verbose:
                    print(f"[Cache] Hit for {tool_call.name}")
            else:
                # Check if confirmation is needed
                tool = self.tool_registry.get(tool_call.name)
                if tool and self.confirmation.needs_confirmation(tool):
                    # Request confirmation
                    self.confirmation.request_confirmation()
                    self.events.emit(
                        AgentEvent.CONFIRMATION_REQUIRED,
                        {
                            "tool": tool_call.name,
                            "arguments": tool_call.arguments,
                            "risk_level": tool.risk_level.value,
                        },
                    )

                    # Wait for confirmation (blocking)
                    confirmed = self.confirmation.wait_for_result()

                    if not confirmed:
                        # User denied
                        result = ToolResult(
                            success=False, output="", error="用户取消操作"
                        )
                        # Record and return early
                        self._tool_call_records.append(
                            {
                                "name": tool_call.name,
                                "arguments": tool_call.arguments,
                                "success": False,
                                "output_preview": None,
                            }
                        )
                        self.events.emit(
                            AgentEvent.TOOL_RESULT,
                            {"tool": tool_call.name, "result": result},
                        )
                        return result

                # Execute the tool
                tool_start = time.perf_counter()
                result = self._execute_tool_call(tool_call)
                tool_latency = (time.perf_counter() - tool_start) * 1000

                # Record tool execution with raw data (decoupled API)
                self.tracker.record_raw_tool_execution(
                    RawToolExecutionData(
                        tool_call=tool_call,
                        result=result,
                        latency_ms=tool_latency,
                    )
                )

        # Record tool call
        self._tool_call_records.append(
            {
                "name": tool_call.name,
                "arguments": tool_call.arguments,
                "success": result.success,
                "output_preview": result.output[:100] if result.output else None,
            }
        )

        # Emit tool result event
        self.events.emit(
            AgentEvent.TOOL_RESULT, {"tool": tool_call.name, "result": result}
        )

        # Verbose output
        if self.verbose:
            status = "success" if result.success else "failed"
            args_str = _safe_str(str(tool_call.arguments))
            print(f"[Tool Call] {tool_call.name}({args_str}) -> {status}")
            if result.output:
                output = _safe_str(result.output)
                preview = output[:200] + "..." if len(output) > 200 else output
                print(f"[Observe] {preview}")

        return result

    def _observe(self, tool_call: ToolCall, result: ToolResult) -> None:
        """
        Observe phase: Record tool result to memory.

        Args:
            tool_call: The tool call that was executed
            result: The result from the tool execution
        """
        result_content = result.output if result.success else f"Error: {result.error}"

        # v0.7.15: Standardized output takes priority over summarizer
        if (
            result.success
            and result.metadata
            and "standard_output" in result.metadata
            and self.standardized_output_config.enabled
        ):
            result_content = result.metadata["standard_output"].to_llm_message(
                detailed=self.standardized_output_config.detailed
            )
        elif self.output_style_config.style == "concise":
            # Use intelligent summarization with config
            summarizer_config = SummarizerConfig(
                enabled=self.output_style_config.smart_summarization,
                extract_imports=self.output_style_config.extract_imports,
                extract_signatures=self.output_style_config.extract_signatures,
                extract_errors=self.output_style_config.extract_errors,
                file_search_count_only=self.output_style_config.file_search_count_only,
            )
            summarizer = ToolResultSummarizer(summarizer_config)
            result_content = summarizer.summarize(
                result_content,
                tool_call.name,
                calibration_factor=self.token_budget.get_calibration_factor(),
            )

        # v0.7.17: Tool Offloading - check before truncation
        is_offloaded = False
        tool = self.tool_registry.get(tool_call.name)
        tool_can_offload = getattr(tool, "can_offload", False) if tool else False

        if self._subsystems.offload_manager.should_offload(
            result_content, tool_call.name, tool_can_offload
        ):
            summary_content, offloaded = self._subsystems.offload_manager.offload(
                result_content, tool_call.name, tool_call.id
            )
            result_content = summary_content
            is_offloaded = True

        # Cache the result (summary if offloaded, full content otherwise)
        self.cache.set_cached_result(
            tool_call.name,
            tool_call.arguments,
            result_content,
            is_offloaded=is_offloaded,
        )

        # v0.7.15: Activate tool_processor config for truncation
        if (
            self.smart_optimization_config.tool_processor_enabled
            and self.smart_optimization_config.tool_processor_max_output_tokens > 0
        ):
            max_tokens = self.smart_optimization_config.tool_processor_max_output_tokens
        else:
            max_tokens = self.output_style_config.tool_output_max_tokens
        from .token_utils import calculate_max_chars

        max_chars = calculate_max_chars(result_content, max_tokens)
        if len(result_content) > max_chars:
            result_content = result_content[:max_chars] + "\n... [输出已截断]"

        self.memory.add_tool_result(
            tool_call_id=tool_call.id, content=result_content, tool_name=tool_call.name
        )

    def _answer_simple_via_llm(self, user_input: str) -> str:
        """Answer simple questions via lightweight LLM call (no tools, no history)."""
        simple_prompt = (
            self.smart_optimization_config.prejudgment_simple_prompt
            or "Answer briefly and directly in the user's language."
        )
        messages = [
            {"role": "system", "content": simple_prompt},
            {"role": "user", "content": user_input},
        ]
        try:
            response, _, _ = self.llm.chat(
                messages=messages, tools=None, system_stable=None
            )
            return response
        except Exception:
            return self._answer_simple_question(user_input)

    def _answer_simple_question(self, user_input: str) -> str:
        """
        Answer simple questions directly without tool calls.

        Args:
            user_input: User's input text

        Returns:
            Direct response string
        """
        input_lower = user_input.lower().strip()

        # Greetings
        if any(g in input_lower for g in ["你好", "hello", "hi", "嗨"]):
            return f"你好！我是{self.skill_prompt.split('名字是')[-1] if '名字是' in self.skill_prompt else '助手'}，有什么可以帮助你的？"

        # Thanks
        if any(t in input_lower for t in ["谢谢", "thanks", "thank you", "感谢"]):
            return "不客气！"

        # Identity
        if any(i in input_lower for i in ["你是谁", "who are you", "你的名字"]):
            return f"我是一个 AI 助手，可以帮助你处理各种任务。"

        # Capabilities
        if any(c in input_lower for c in ["你能做什么", "what can you do"]):
            return "我可以帮你：查看文件、执行命令、搜索内容、管理记忆等。"

        # Confirmations
        if any(c in input_lower for c in ["好的", "ok", "okay", "明白"]):
            return "好的，请告诉我你需要什么帮助。"

        # Default: let LLM handle it
        return "请继续说明你的需求。"

    def _handle_budget_warning(self, warning: dict) -> None:
        """
        Handle budget warning based on configured mode.

        Args:
            warning: Warning information dict from check_warning()
        """
        if self.token_budget is None:
            return

        mode = self.token_budget.config.warning_mode

        if mode == "silent":
            # No output, just tracking
            pass

        elif mode == "console":
            if self.verbose:
                print(warning["message"])
                status = self.token_budget.get_status()
                print(f"   剩余: {status['remaining']}/{status['initial']} tokens")

        elif mode == "event":
            # Emit event for external handlers
            if hasattr(self, "events"):
                self.events.emit("budget_warning", warning)

    def _force_summarize(self) -> str:
        """
        Force summarize when budget exhausted or routing limit reached.

        Uses LLM to generate a structured summary of gathered information
        instead of simple concatenation of tool result previews.

        Returns:
            Structured summary response
        """
        if self.verbose:
            print("[Budget] 预算耗尽，正在生成结构化摘要...")

        # Check if LLM summary is enabled and we have tool results
        if (
            self.token_budget
            and self.token_budget.config.llm_summary_enabled
            and self._tool_call_records
        ):
            return self._generate_llm_summary()

        # Fallback: simple summary (existing behavior)
        return self._generate_simple_summary()

    def _generate_llm_summary(self) -> str:
        """
        Use LLM to generate a structured summary of gathered information.

        Returns:
            LLM-generated structured summary
        """
        # Get user's original request (first user message)
        messages = self.memory.get_all()
        user_request = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_request = msg.get("content", "")
                break

        # Format tool results
        tool_summary_parts = []
        for record in self._tool_call_records:
            tool_name = record.get("name", "unknown")
            output_preview = record.get("output_preview", "")
            success = record.get("success", False)
            status = "成功" if success else "失败"
            tool_summary_parts.append(
                f"- {tool_name} ({status}): {output_preview[:200]}"
            )

        tool_summary = "\n".join(tool_summary_parts)

        # Build summary prompt
        prompt = f"""请基于以下收集的信息，生成一个结构化的摘要回答。

用户原始请求:
{user_request[:500]}

已执行的工具调用:
{tool_summary}

请按以下格式输出摘要:
---
## 信息收集情况
[简要说明已收集了哪些信息]

## 主要发现
[列出关键发现和结果]

## 当前结论
[基于已有信息能得出的结论]

## 需要补充
[还需要什么信息才能完整回答]
---

注意:
1. 如果信息足够回答用户问题，直接给出结论
2. 如果信息不足，说明缺少什么
3. 保持简洁，不超过10行"""

        try:
            response, _, _ = self.llm.chat(
                messages=[{"role": "user", "content": prompt}], tools=None
            )
            return response
        except Exception as e:
            if self.verbose:
                print(f"[Budget] LLM 摘要生成失败: {e}, 使用简单摘要")
            return self._generate_simple_summary()

    def _generate_simple_summary(self) -> str:
        """
        Generate simple summary as fallback.

        Returns:
            Simple concatenated summary
        """
        if self._tool_call_records:
            tool_summary = "基于已收集的信息:\n"
            for record in self._tool_call_records:
                if record.get("output_preview"):
                    tool_summary += f"- {record['name']}: {record['output_preview']}\n"
            tool_summary += "\n由于 Token 预算耗尽，无法继续收集更多信息。"
            return tool_summary

        return "由于 Token 预算耗尽，无法完成任务。请尝试简化请求或增加预算。"

    def _build_result(
        self,
        response: str,
        iterations: int,
        success: bool,
        termination_reason: str = "",
    ) -> ExecutionResult:
        """
        Build the execution result.

        Args:
            response: The final response text
            iterations: Number of iterations executed
            success: Whether execution completed successfully
            termination_reason: Why the loop terminated

        Returns:
            ExecutionResult with all execution metadata
        """
        # Add final assistant message if not already added
        if success:
            # v0.7.15: Apply aggressive output simplification
            if self._subsystems.output_simplifier is not None:
                response = self._subsystems.output_simplifier.simplify(response)
            self.memory.add_assistant_message(response)

        # v0.7.17: Persist cache and cleanup offloaded files
        if self.cache and self.cache.config and self.cache.config.persist:
            self.cache.persist_to_disk()
        if self.offload_config and self.offload_config.auto_cleanup:
            self._subsystems.offload_manager.cleanup()

        return ExecutionResult(
            response=response,
            success=success,
            iterations=iterations,
            tool_calls=self._tool_call_records,
            tokens_used=self._total_tokens,
            session_id=self._session_id,
            termination_reason=termination_reason,
        )

    def run_stream(self, user_input: str) -> Generator[str, None, None]:
        """
        Stream the response (simplified version).

        For now, this runs the full loop and yields the final result.
        True streaming with tool calls requires more complex handling.

        Args:
            user_input: The user's input text

        Yields:
            Text chunks from the response
        """
        result = self.run(user_input)
        yield result.response

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a single tool call.

        Args:
            tool_call: The tool call to execute

        Returns:
            ToolResult from the execution
        """
        result = self.execute_tool(tool_call.name, tool_call.arguments)

        # Track undoable operations
        if result.success and result.undo_data:
            tool = self.tool_registry.get(tool_call.name)
            if tool and tool.supports_undo:
                self._undo_stack.push(tool_call.name, result.undo_data)

        return result

    def _check_duplicate_tool_call(self, tool_call: ToolCall) -> bool:
        """
        Check if this tool call is a duplicate and should be blocked.

        Args:
            tool_call: The tool call to check

        Returns:
            True if the call is a duplicate and should be skipped
        """
        result = self._subsystems.duplicate_detector.check(tool_call)

        if result.should_skip:
            if not self._subsystems.duplicate_detector.warning_issued:
                if self.verbose:
                    print(f"[Duplicate] 检测到重复工具调用: {tool_call.name}")
                    print(f"   已调用 {result.count} 次，跳过后续重复调用")
                self._subsystems.duplicate_detector.warning_issued = True
            return True

        if result.is_duplicate and self.verbose:
            print(f"[Duplicate] {tool_call.name} 已调用 {result.count} 次")

        return False

    def undo_current_round(self, context: dict) -> list[str]:
        """
        Undo all operations in the current round.

        Args:
            context: Execution context (contains memory, config, etc.)

        Returns:
            List of tool names that were successfully undone
        """
        undone = []
        records = self._undo_stack.get_round_records()

        # Undo in reverse order
        for record in reversed(records):
            tool = self.tool_registry.get(record.tool_name)
            if tool and tool.supports_undo:
                if tool.undo(record.undo_data, context):
                    undone.append(record.tool_name)
                    self._undo_stack.remove_record(record)

        self._undo_stack.clear_round()
        return undone

    def has_undoable_operations(self) -> bool:
        """Check if current round has any undoable operations."""
        return self._undo_stack.has_round_records()

    def confirm_tool(self, confirmed: bool) -> None:
        """
        Set confirmation result for pending tool execution.

        Called by external handler (CLI, UI, etc.) after user interaction.

        Args:
            confirmed: Whether the user confirmed the operation
        """
        self.confirmation.set_result(confirmed)

    def add_tool_to_whitelist(self, tool_name: str) -> None:
        """
        Add a tool to the confirmation whitelist.

        Args:
            tool_name: Name of the tool to whitelist
        """
        self.confirmation.add_to_whitelist(tool_name)

    def add_tool(self, tool) -> None:
        """
        Add a new tool to the agent.

        Args:
            tool: Tool instance to add
        """
        self.tool_registry.register(tool)
        # Rebuild stable portion with new tool
        if self._prompt_builder is not None:
            style = self.prompt_config.style or self.output_style_config.style
            tools_desc = PromptBuilder.format_tools_description(
                self.tool_registry, style
            )
            self._stable_system_prompt = self._prompt_builder.build_stable(
                tools_description=tools_desc,
                stable_modules=self.prompt_config.stable_modules,
            )
        # Update system prompt with new tool
        self._setup_system_prompt()
