"""
ReAct Agent implementation.

This module implements the execution layer of the agent architecture,
following the Think -> Act -> Observe cycle.
"""

import time
from typing import Generator

from .base import BaseAgent
from .prompts import (
    REACT_SYSTEM_PROMPT, REACT_SYSTEM_PROMPT_CONCISE, REACT_SYSTEM_PROMPT_STANDARD,
    REACT_SYSTEM_PROMPT_CONCISE_WITH_CONFIDENCE, REACT_SYSTEM_PROMPT_STANDARD_WITH_CONFIDENCE,
    TOOL_DESCRIPTION_TEMPLATE, CONFIDENCE_SUFFIX
)
from .types import ExecutionResult, ThinkResult, AgentEvent
from .events import EventEmitter
from .budget import Budget, BudgetChecker
from .undo import UndoStack
from .context import ContextManager
from .confirmation import ConfirmationManager, ConfirmationConfig
from .result_summarizer import ToolResultSummarizer, SummarizerConfig
from .tool_merger import ToolCallMerger, ToolMergeConfig
from .cache import ToolResultCache, CacheConfig
from .compressor import MessageCompressor, CompressorConfig
from .token_budget import TokenBudget, TokenBudgetConfig
from .router import QueryRouter, QueryComplexity
from .confidence import ConfidenceParser
from ..llm.messages import ToolCall
from ..tools.base import ToolResult
from ..monitoring import MetricsTracker
from ..config.schema import OutputStyleConfig, SmartOptimizationConfig


def _safe_str(text: str) -> str:
    """Safely convert string for printing, removing invalid Unicode characters."""
    if not text:
        return text
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


# Simple question patterns that don't need tools
SIMPLE_QUESTION_PATTERNS = [
    # Greetings
    "你好", "hello", "hi", "嗨", "早上好", "下午好", "晚上好",
    # Thanks
    "谢谢", "thanks", "thank you", "感谢",
    # Simple questions (can answer directly)
    "你是谁", "who are you", "你的名字", "what is your name",
    "你能做什么", "what can you do", "你有什么功能",
    # Confirmations
    "好的", "ok", "okay", "明白", "了解", "清楚了",
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
        max_iterations: int = 10,
        verbose: bool = True,
        skill_prompt: str = "",
        tracker: MetricsTracker | None = None,
        events: EventEmitter | None = None,
        budget: Budget | None = None,
        context_config=None,
        confirmation_config: ConfirmationConfig | None = None,
        output_style_config: OutputStyleConfig | None = None,
        tool_merge_config: ToolMergeConfig | None = None,
        cache_config: CacheConfig | None = None,
        compressor_config: CompressorConfig | None = None,
        smart_optimization_config: SmartOptimizationConfig | None = None,
    ):
        """
        Initialize the ReAct agent.

        Args:
            llm: LLM client instance
            memory: Memory system instance
            tool_registry: Tool registry instance
            max_iterations: Maximum reasoning iterations
            verbose: Whether to print debug information
            skill_prompt: Additional prompt from skills
            tracker: Metrics tracker for monitoring
            events: Event emitter for external listeners
            budget: Budget constraints for execution
            context_config: Context management configuration
            confirmation_config: Confirmation mechanism configuration
            output_style_config: Output style configuration for token efficiency
            tool_merge_config: Tool merging configuration for token efficiency
            cache_config: Tool result caching configuration
            compressor_config: Message compression configuration
            smart_optimization_config: Smart optimization configuration for v0.7.5
        """
        super().__init__(llm, memory, tool_registry, max_iterations)
        self.verbose = verbose
        self.skill_prompt = skill_prompt
        self.tracker = tracker or MetricsTracker()
        self.events = events or EventEmitter()
        self.budget_checker = BudgetChecker(budget or Budget(max_iterations=max_iterations))

        # Output style configuration
        self.output_style_config = output_style_config or OutputStyleConfig()

        # Tool merge configuration
        self.tool_merge_config = tool_merge_config or ToolMergeConfig()

        # Tool result cache
        self.cache = ToolResultCache(cache_config)

        # Message compressor
        self.compressor = MessageCompressor(compressor_config)

        # Smart optimization configuration (v0.7.5)
        self.smart_optimization_config = smart_optimization_config or SmartOptimizationConfig()

        # Token budget management
        if self.smart_optimization_config.budget_enabled:
            token_budget_config = TokenBudgetConfig(
                initial_budget=self.smart_optimization_config.initial_budget,
                warning_threshold=self.smart_optimization_config.budget_warning_threshold,
                force_summarize=self.smart_optimization_config.budget_force_summarize,
            )
            self.token_budget = TokenBudget(token_budget_config)
        else:
            self.token_budget = None

        # Query router
        if self.smart_optimization_config.routing_enabled:
            self.query_router = QueryRouter(
                enabled=True,
                simple_direct=self.smart_optimization_config.routing_simple_direct,
                moderate_single_tool=self.smart_optimization_config.routing_moderate_single_tool,
            )
        else:
            self.query_router = None

        # Confidence parser
        if self.smart_optimization_config.confidence_enabled:
            self.confidence_parser = ConfidenceParser(
                threshold=self.smart_optimization_config.confidence_threshold
            )
        else:
            self.confidence_parser = None

        # Context manager
        self.context_manager = ContextManager(
            memory=memory,
            llm=llm,
            config=context_config,
            verbose=verbose
        ) if context_config else None

        # Confirmation manager
        self.confirmation = ConfirmationManager(confirmation_config)

        # Execution state
        self._undo_stack = UndoStack()
        self._round_counter = 0
        self._tool_call_records: list[dict] = []
        self._total_tokens: int = 0
        self._session_id: str = ""
        self._routing_max_tools: int = -1  # Max tools for current query (-1 = unlimited)

        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """Set up the system prompt with tool descriptions."""
        style = self.output_style_config.style
        tools_desc = self._format_tools_description(style)

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

    def _format_tools_description(self, style: str = "detailed") -> str:
        """Format tool descriptions for the system prompt.

        Args:
            style: Output style - "concise", "standard", or "detailed"
        """
        descriptions = []
        for tool_name in self.tool_registry.list_tools():
            tool = self.tool_registry.get(tool_name)

            if style == "concise":
                # Only tool names, comma separated (minimal tokens)
                descriptions.append(tool.name)
            elif style == "standard":
                # Name + first sentence + required params
                first_sentence = tool.description.split('.')[0]
                required = tool.parameters_schema.get("required", [])
                params_str = ", ".join(required) if required else "none"
                desc = f"- {tool.name}: {first_sentence}\n  params: {params_str}"
                descriptions.append(desc)
            else:
                # Full description (original format)
                desc = TOOL_DESCRIPTION_TEMPLATE.format(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters_schema
                )
                descriptions.append(desc)

        if style == "concise":
            # Return comma-separated list for minimal tokens
            return ", ".join(descriptions)
        return "\n".join(descriptions)

    def run(
        self,
        user_input: str,
        dry_run: bool = False,
        session_id: str = ""
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

        # Query routing (v0.7.5)
        if self.query_router is not None:
            routing_result = self.query_router.classify(user_input)
            self._routing_max_tools = routing_result.suggested_max_tools

            if self.verbose:
                print(f"[Router] Complexity: {routing_result.complexity.value}, "
                      f"max_tools: {self._routing_max_tools}")

            # Simple queries: direct answer without LLM
            if routing_result.complexity == QueryComplexity.SIMPLE:
                response = self._answer_simple_question(user_input)
                self.tracker.end_run(response)
                return self._build_result(response, 0, success=True)

        # Pre-check: simple questions can be answered directly (legacy)
        if self.output_style_config.style == "concise" and _is_simple_question(user_input):
            # Direct answer for simple questions (skip tool calls)
            response = self._answer_simple_question(user_input)
            self.tracker.end_run(response)
            return self._build_result(response, 0, success=True)

        iteration = 0
        tool_calls_in_round = 0  # Track tool calls for routing limits

        while iteration < self.max_iterations:
            iteration += 1

            # Budget check
            if not self.budget_checker.can_continue(
                iteration, self._total_tokens, len(self._tool_call_records)
            ):
                break

            # Token budget check (v0.7.5)
            if self.token_budget is not None:
                if self.token_budget.should_summarize():
                    # Budget exhausted, force summarize
                    response = self._force_summarize()
                    self.tracker.end_run(response)
                    return self._build_result(response, iteration, success=True)

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
                    return self._build_result(conf_result.cleaned_response, iteration, success=True)

            if think.is_final:
                self.tracker.end_iteration()
                self.tracker.end_run(think.response_text)
                return self._build_result(think.response_text, iteration, success=True)

            # Merge similar tool calls for token efficiency
            merged_tool_calls = self._merge_tool_calls(think.tool_calls)

            # Act and Observe phases
            for tool_call in merged_tool_calls:
                # Check routing limit (v0.7.5)
                if self._routing_max_tools >= 0:
                    if tool_calls_in_round >= self._routing_max_tools:
                        if self.verbose:
                            print(f"[Router] Reached max tools limit: {self._routing_max_tools}")
                        # Force summarize with current info
                        response = self._force_summarize()
                        self.tracker.end_run(response)
                        return self._build_result(response, iteration, success=True)

                result = self._act(tool_call, dry_run)
                self._observe(tool_call, result)
                tool_calls_in_round += 1

                # Update token budget (v0.7.5)
                if self.token_budget is not None:
                    self.token_budget.consume(think.usage.total_tokens)

            self.tracker.end_iteration()

        # Reached max iterations or budget exhausted
        response = "I apologize, I couldn't complete this task within the iteration limit. Please try simplifying your request."
        self.tracker.end_run(response)
        return self._build_result(response, iteration, success=False)

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

        # Add user message to memory
        self.memory.add_user_message(user_input)

        # Start tracking
        self.tracker.start_run(user_input)

        # Emit start event
        self.events.emit(AgentEvent.RUN_START, {"input": user_input, "session_id": session_id})

    def _think(self) -> ThinkResult:
        """
        Think phase: Call LLM and get response.

        Returns:
            ThinkResult containing response text and any tool calls
        """
        self.events.emit(AgentEvent.THINK_START, {"iteration": len(self._tool_call_records) + 1})

        # Context pressure check and compression (existing context manager)
        if self.context_manager:
            self.context_manager.check_and_compress()

        # Get context and tools
        messages = self.memory.get_all()

        # Apply message compression if needed
        if self.compressor.should_compress(messages):
            original_count = len(messages)
            messages = self.compressor.compress(messages)
            if self.verbose and len(messages) < original_count:
                print(f"[Compressor] Reduced {original_count} messages to {len(messages)}")

        tools_schema = self.tool_registry.get_all_schemas()

        # Call LLM
        llm_start = time.perf_counter()
        response_text, tool_calls, usage = self.llm.chat(
            messages=messages,
            tools=tools_schema if tools_schema else None
        )
        llm_latency = (time.perf_counter() - llm_start) * 1000

        # Convert tool_calls to dict for reporting
        tool_calls_dict = [tc.to_dict() for tc in tool_calls] if tool_calls else []

        # Record LLM call with input/output
        self.tracker.record_llm_call(
            model=self.llm.model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=llm_latency,
            tool_calls_count=len(tool_calls),
            input_messages=messages,
            output_text=response_text,
            tool_calls=tool_calls_dict,
        )

        # Update token count
        self._total_tokens += usage.total_tokens

        # Verbose output
        if self.verbose and response_text:
            print(f"[Think] {_safe_str(response_text[:200])}...")

        # Add assistant message to memory if there are tool calls
        if tool_calls:
            self.memory.add_assistant_message(
                response_text,
                tool_calls=[tc.to_dict() for tc in tool_calls]
            )

        return ThinkResult(
            response_text=response_text,
            tool_calls=tool_calls or [],
            usage=usage,
            is_final=not tool_calls
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
        print(f"[Merge] enabled={self.tool_merge_config.enabled}, concise_only={self.tool_merge_config.concise_only}, style={self.output_style_config.style}")

        if not tool_calls or not self.tool_merge_config.enabled:
            print("[Merge] Skipping: no calls or disabled")
            return tool_calls

        # Only merge in concise mode if configured
        if self.tool_merge_config.concise_only and self.output_style_config.style != "concise":
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
        # Emit tool call event
        self.events.emit(AgentEvent.TOOL_CALL, {
            "tool": tool_call.name,
            "arguments": tool_call.arguments
        })

        # Handle dry-run mode
        if dry_run:
            result = ToolResult(
                success=True,
                output="[预览模式] 未实际执行"
            )
        else:
            # Check cache first
            cached_result = self.cache.get_cached_result(tool_call.name, tool_call.arguments)
            if cached_result is not None:
                result = cached_result
                if self.verbose:
                    print(f"[Cache] Hit for {tool_call.name}")
            else:
                # Check if confirmation is needed
                tool = self.tool_registry.get(tool_call.name)
                if tool and self.confirmation.needs_confirmation(tool):
                    # Request confirmation
                    self.confirmation.request_confirmation()
                    self.events.emit(AgentEvent.CONFIRMATION_REQUIRED, {
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "risk_level": tool.risk_level.value
                    })

                    # Wait for confirmation (blocking)
                    confirmed = self.confirmation.wait_for_result()

                    if not confirmed:
                        # User denied
                        result = ToolResult(
                            success=False,
                            output="",
                            error="用户取消操作"
                        )
                        # Record and return early
                        self._tool_call_records.append({
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                            "success": False,
                            "output_preview": None,
                        })
                        self.events.emit(AgentEvent.TOOL_RESULT, {
                            "tool": tool_call.name,
                            "result": result
                        })
                        return result

                # Execute the tool
                tool_start = time.perf_counter()
                result = self._execute_tool_call(tool_call)
                tool_latency = (time.perf_counter() - tool_start) * 1000

                # Cache the result if cacheable
                self.cache.set_cached_result(tool_call.name, tool_call.arguments, result)

                # Record tool execution
                self.tracker.record_tool_execution(
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                    success=result.success,
                    latency_ms=tool_latency,
                    output_length=len(result.output) if result.output else 0,
                    error=result.error,
                )

        # Record tool call
        self._tool_call_records.append({
            "name": tool_call.name,
            "arguments": tool_call.arguments,
            "success": result.success,
            "output_preview": result.output[:100] if result.output else None,
        })

        # Emit tool result event
        self.events.emit(AgentEvent.TOOL_RESULT, {
            "tool": tool_call.name,
            "result": result
        })

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

        # Summarize tool output for token efficiency
        if self.output_style_config.style == "concise":
            # Use intelligent summarization with config
            summarizer_config = SummarizerConfig(
                enabled=self.output_style_config.smart_summarization,
                extract_imports=self.output_style_config.extract_imports,
                extract_signatures=self.output_style_config.extract_signatures,
                extract_errors=self.output_style_config.extract_errors,
                file_search_count_only=self.output_style_config.file_search_count_only,
            )
            summarizer = ToolResultSummarizer(summarizer_config)
            result_content = summarizer.summarize(result_content, tool_call.name)

        # Truncate long output based on output style config
        max_tokens = self.output_style_config.tool_output_max_tokens
        # Rough estimate: 1 token ~ 4 characters for English
        max_chars = max_tokens * 4
        if len(result_content) > max_chars:
            result_content = result_content[:max_chars] + "\n... [输出已截断]"

        self.memory.add_tool_result(
            tool_call_id=tool_call.id,
            content=result_content,
            tool_name=tool_call.name
        )

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

    def _force_summarize(self) -> str:
        """
        Force summarize when budget exhausted or routing limit reached.

        Returns:
            Summarized response based on current context
        """
        if self.verbose:
            print("[Budget] Forcing summarize due to budget/routing constraints")

        # Get current context
        messages = self.memory.get_all()

        # If we have tool results, summarize them
        if self._tool_call_records:
            tool_summary = "Based on the information gathered:\n"
            for record in self._tool_call_records:
                if record.get("output_preview"):
                    tool_summary += f"- {record['name']}: {record['output_preview']}\n"
            return tool_summary

        # Otherwise, return a generic response
        return "Based on the current context, I need more resources to complete this task. Please try simplifying your request."

    def _build_result(
        self,
        response: str,
        iterations: int,
        success: bool
    ) -> ExecutionResult:
        """
        Build the execution result.

        Args:
            response: The final response text
            iterations: Number of iterations executed
            success: Whether execution completed successfully

        Returns:
            ExecutionResult with all execution metadata
        """
        # Add final assistant message if not already added
        if success:
            self.memory.add_assistant_message(response)

        return ExecutionResult(
            response=response,
            success=success,
            iterations=iterations,
            tool_calls=self._tool_call_records,
            tokens_used=self._total_tokens,
            session_id=self._session_id
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
        # Update system prompt with new tool
        self._setup_system_prompt()
