"""
Metrics tracker for runtime monitoring.
"""

import time
import uuid
from datetime import datetime
from typing import Any

from .metrics import (
    LLMCallMetrics,
    ToolExecutionMetrics,
    IterationMetrics,
    RunMetrics,
    SkippedToolCall,
)
from .raw_data import RawLLMCallData, RawToolExecutionData
from .token_analyzer import TokenAnalyzer
from .estimation_audit import EstimationAudit, EstimationAuditConfig


class MetricsTracker:
    """运行时指标追踪器"""

    def __init__(self, enabled: bool = True, max_run_history: int = 50):
        """
        Initialize the tracker.

        Args:
            enabled: Whether tracking is enabled
            max_run_history: Maximum number of run records to keep (prevents memory leak)
        """
        self.enabled = enabled
        self._max_run_history = max_run_history
        self.run_metrics: RunMetrics | None = None
        self._current_iteration: IterationMetrics | None = None
        self._base_tool_chars: int = 0
        self._base_system_chars: int = 0
        self._base_skill_chars: int = 0
        self._base_ratio: float = 0.0
        self._base_ratio_initialized: bool = False
        self._base_ratio_iteration: int = 0
        self._base_tool_chars: int = 0
        self._base_system_chars: int = 0
        self._base_skill_chars: int = 0
        self._iteration_start_time: float = 0.0
        self._run_start_time: float = 0.0

        # Accumulated session statistics
        self._session_total_tokens: int = 0
        self._session_total_iterations: int = 0
        self._session_total_llm_calls: int = 0  # LLM API 调用次数
        self._session_total_tool_calls: int = 0
        self._session_successful_tool_calls: int = 0
        self._session_failed_tool_calls: int = 0
        self._session_start_time: float = time.perf_counter()

        # Cross-run history for detailed usage display
        self._run_history: list[RunMetrics] = []
        self._run_counter: int = 0  # Global run counter (轮次)

        # Token analyzer
        self.token_analyzer = TokenAnalyzer()

        # Base ratio for stable token estimation (固定部分使用基准比例)
        # (owned by token_analyzer, but tracker needs to reset it on new runs)

        # v0.7.18: Estimation audit
        self._estimation_audit = EstimationAudit()

    def start_run(self, user_input: str) -> None:
        """
        Start tracking a new run.

        Args:
            user_input: The user's input text
        """
        if not self.enabled:
            return

        self._run_counter += 1
        self.run_metrics = RunMetrics(
            session_id=f"run_{uuid.uuid4().hex[:8]}",
            start_time=datetime.now(),
            user_input=user_input,
            run_number=self._run_counter,  # Track run number
        )
        self._run_start_time = time.perf_counter()

        # Reset base_ratio for new run (each run starts fresh)
        self.token_analyzer.reset_base_ratio()

    def end_run(self, response: str) -> None:
        """
        End tracking the current run.

        Args:
            response: The final response
        """
        if not self.enabled or not self.run_metrics:
            return

        self.run_metrics.end_time = datetime.now()
        self.run_metrics.final_response = response
        self.run_metrics.total_latency_ms = (
            time.perf_counter() - self._run_start_time
        ) * 1000

        # Calculate total tokens for this run
        self.run_metrics.total_tokens = sum(
            i.llm_call.total_tokens for i in self.run_metrics.iterations if i.llm_call
        )

        # Store run in history for cross-run analysis
        self._run_history.append(self.run_metrics)
        # Bound history to prevent memory leak in long sessions
        if len(self._run_history) > self._max_run_history:
            self._run_history = self._run_history[-self._max_run_history :]

        # Accumulate session statistics
        self._session_total_tokens += self.run_metrics.total_tokens
        self._session_total_iterations += len(self.run_metrics.iterations)
        for iteration in self.run_metrics.iterations:
            for tool in iteration.tool_executions:
                self._session_total_tool_calls += 1
                if tool.success:
                    self._session_successful_tool_calls += 1
                else:
                    self._session_failed_tool_calls += 1

    def start_iteration(self, number: int) -> None:
        """
        Start tracking a new iteration.

        Args:
            number: The iteration number
        """
        if not self.enabled or not self.run_metrics:
            return

        self._current_iteration = IterationMetrics(iteration_number=number)
        self._iteration_start_time = time.perf_counter()

    def end_iteration(self) -> None:
        """End tracking the current iteration."""
        if not self.enabled or not self.run_metrics or not self._current_iteration:
            return

        self._current_iteration.total_latency_ms = (
            time.perf_counter() - self._iteration_start_time
        ) * 1000
        self.run_metrics.iterations.append(self._current_iteration)
        self._current_iteration = None

    def record_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        tool_calls_count: int,
        input_messages: list[dict] | None = None,
        output_text: str = "",
        tool_calls: list[dict] | None = None,
        tools_schema: list[dict] | None = None,
    ) -> None:
        """
        Record an LLM call.

        .. deprecated::
            Use ``record_raw_llm_call(RawLLMCallData(...))`` instead.
        """
        import warnings

        warnings.warn(
            "record_llm_call() is deprecated, use record_raw_llm_call() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self.enabled or not self._current_iteration:
            return

        self._current_iteration.llm_call = LLMCallMetrics(
            timestamp=datetime.now(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            tool_calls_count=tool_calls_count,
            input_messages=input_messages or [],
            output_text=output_text,
            tool_calls=tool_calls or [],
            tools_schema=tools_schema or [],
        )

        # Increment LLM call count
        self._session_total_llm_calls += 1

        # Analyze token consumption
        self.token_analyzer.analyze_llm_call(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_messages=input_messages or [],
            tool_calls=tool_calls,
        )

    def record_tool_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool,
        latency_ms: float,
        output_length: int,
        error: str | None = None,
    ) -> None:
        """
        Record a tool execution.

        .. deprecated::
            Use ``record_raw_tool_execution(RawToolExecutionData(...))`` instead.
        """
        import warnings

        warnings.warn(
            "record_tool_execution() is deprecated, use record_raw_tool_execution() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self.enabled or not self._current_iteration:
            return

        self._current_iteration.tool_executions.append(
            ToolExecutionMetrics(
                timestamp=datetime.now(),
                tool_name=tool_name,
                arguments=arguments,
                success=success,
                latency_ms=latency_ms,
                output_length=output_length,
                error=error,
            )
        )

    def _convert_tool_calls(self, tool_calls: list[Any] | None) -> list[dict]:
        """
        Convert ToolCall objects to dict format.

        Args:
            tool_calls: List of ToolCall objects or dicts

        Returns:
            List of dicts
        """
        if not tool_calls:
            return []
        return [tc.to_dict() if hasattr(tc, "to_dict") else tc for tc in tool_calls]

    def record_raw_llm_call(self, raw_data: RawLLMCallData) -> None:
        """
        Record an LLM call from raw data (decoupled API).

        This method accepts a container with raw data objects, extracting
        and converting internally. The agent layer only needs to pass
        the raw objects without knowing how to extract values.

        Args:
            raw_data: Container with raw LLM call data
        """
        if not self.enabled or not self._current_iteration:
            return

        # Extract and convert internally
        model = raw_data.llm.model
        prompt_tokens = raw_data.usage.prompt_tokens
        completion_tokens = raw_data.usage.completion_tokens
        latency_ms = raw_data.latency_ms
        tool_calls_count = len(raw_data.tool_calls) if raw_data.tool_calls else 0

        # Convert ToolCall objects to dict internally
        tool_calls_dict = self._convert_tool_calls(raw_data.tool_calls)

        # Create metrics
        estimated_tokens = getattr(raw_data, "estimated_tokens", 0)
        calibration_factor = getattr(raw_data, "calibration_factor", 1.0)

        # Calculate deviation_pct
        deviation_pct = 0.0
        if estimated_tokens > 0:
            deviation_pct = abs(prompt_tokens - estimated_tokens) / estimated_tokens

        self._current_iteration.llm_call = LLMCallMetrics(
            timestamp=datetime.now(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            tool_calls_count=tool_calls_count,
            input_messages=raw_data.messages,
            output_text=raw_data.response_text,
            tool_calls=tool_calls_dict,
            tools_schema=raw_data.tools_schema or [],
            estimated_tokens=estimated_tokens,
            deviation_pct=deviation_pct,
        )

        # Increment LLM call count
        self._session_total_llm_calls += 1

        # Analyze token consumption
        self.token_analyzer.analyze_llm_call(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            input_messages=raw_data.messages,
            tool_calls=tool_calls_dict,
        )

        # v0.7.18: Record estimation audit
        if estimated_tokens > 0 and prompt_tokens > 0:
            self._estimation_audit.record(
                estimated=estimated_tokens,
                actual=prompt_tokens,
                calibration_factor=calibration_factor,
            )

    def record_raw_tool_execution(self, raw_data: RawToolExecutionData) -> None:
        """
        Record a tool execution from raw data (decoupled API).

        This method accepts a container with raw tool call and result objects,
        extracting internally. The agent layer only needs to pass the raw objects.

        Args:
            raw_data: Container with raw tool execution data
        """
        if not self.enabled or not self._current_iteration:
            return

        self._current_iteration.tool_executions.append(
            ToolExecutionMetrics(
                timestamp=datetime.now(),
                tool_name=raw_data.tool_call.name,
                arguments=raw_data.tool_call.arguments,
                success=raw_data.result.success,
                latency_ms=raw_data.latency_ms,
                output_length=(
                    len(raw_data.result.output) if raw_data.result.output else 0
                ),
                error=raw_data.result.error,
            )
        )

    def record_skipped_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        reason: str,
    ) -> None:
        """
        Record a skipped tool call with reason.

        This is called when a tool call is not executed due to various reasons:
        - routing_limit: Reached max tools limit
        - merged: Merged with another tool call
        - duplicate: Detected as duplicate call
        - budget_exceeded: Token budget exceeded

        Args:
            tool_name: The tool name that was skipped
            arguments: The arguments for the tool call
            reason: The reason why the tool call was skipped
        """
        if not self.enabled or not self._current_iteration:
            return

        self._current_iteration.skipped_tool_calls.append(
            SkippedToolCall(
                tool_name=tool_name,
                arguments=arguments,
                reason=reason,
            )
        )

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of the current run.

        Returns:
            Summary dictionary
        """
        if not self.run_metrics:
            return {}

        return {
            "session_id": self.run_metrics.session_id,
            "duration_ms": round(self.run_metrics.total_latency_ms, 2),
            "total_iterations": self.run_metrics.total_iterations,
            "total_tokens": self.run_metrics.total_tokens,
            "total_tool_calls": self.run_metrics.total_tool_calls,
            "successful_tool_calls": self.run_metrics.successful_tool_calls,
            "failed_tool_calls": self.run_metrics.failed_tool_calls,
        }

    def get_session_summary(self) -> dict[str, Any]:
        """
        Get accumulated session statistics (across all runs).

        Returns:
            Session summary dictionary
        """
        session_duration = (time.perf_counter() - self._session_start_time) * 1000
        return {
            "session_duration_ms": round(session_duration, 2),
            "total_tokens": self._session_total_tokens,
            "total_iterations": self._session_total_iterations,
            "total_llm_calls": self._session_total_llm_calls,
            "total_runs": self._run_counter,
            "total_tool_calls": self._session_total_tool_calls,
            "successful_tool_calls": self._session_successful_tool_calls,
            "failed_tool_calls": self._session_failed_tool_calls,
        }

    def get_last_iteration_tokens(self) -> dict[str, int]:
        """
        Get token counts from the last iteration.

        Returns:
            Dictionary with prompt_tokens, completion_tokens, total_tokens
            Returns empty dict if no iterations available.
        """
        if not self.run_metrics or not self.run_metrics.iterations:
            return {}

        last_iteration = self.run_metrics.iterations[-1]
        if not last_iteration.llm_call:
            return {}

        return {
            "prompt_tokens": last_iteration.llm_call.prompt_tokens,
            "completion_tokens": last_iteration.llm_call.completion_tokens,
            "total_tokens": last_iteration.llm_call.total_tokens,
        }

    def get_iteration_token_list(self) -> list[dict[str, int]]:
        """
        Get token counts for each iteration.

        Returns:
            List of dictionaries with iteration_number, prompt_tokens,
            completion_tokens, total_tokens
        """
        if not self.run_metrics:
            return []

        result = []
        for iteration in self.run_metrics.iterations:
            if iteration.llm_call:
                result.append(
                    {
                        "iteration_number": iteration.iteration_number,
                        "prompt_tokens": iteration.llm_call.prompt_tokens,
                        "completion_tokens": iteration.llm_call.completion_tokens,
                        "total_tokens": iteration.llm_call.total_tokens,
                    }
                )
        return result

    def get_full_report(self) -> dict[str, Any]:
        """
        Get the full report.

        Returns:
            Full report dictionary
        """
        if not self.run_metrics:
            return {}
        return self.run_metrics.to_dict()

    def get_detailed_usage(self) -> list[dict[str, Any]]:
        """
        Get detailed usage information across all runs.

        Returns:
            List of usage entries, one per iteration:
            {
                "id": 1,  # 行号
                "run_number": 1,  # 轮次
                "iteration_number": 1,  # 迭代
                "tool_tokens": 100,  # 工具定义 token
                "system_tokens": 50,  # 系统提示 token
                "skill_tokens": 30,  # 技能提示 token
                "message_tokens": 20,  # user + assistant + tool 结果 token
                "input_tokens": 200,  # prompt_tokens（准确值）
                "output_tool_tokens": 30,  # tool_calls 参数 token
                "output_text_tokens": 50,  # content 文本 token
                "total_tokens": 280,  # 总和
                # Raw data for CLI to format description
                "tool_names": ["shell_execute"],
                "input_messages": [...],
                "output_text": "...",
            }
        """
        result = []
        row_id = 0
        for run in self._run_history:
            run_num = run.run_number
            iter_count_in_run = 0
            for iteration in run.iterations:
                iter_num = iteration.iteration_number
                if iteration.llm_call:
                    row_id += 1
                    iter_count_in_run += 1
                    llm = iteration.llm_call

                    is_first_iteration = iter_count_in_run == 1

                    # 委托给 token_analyzer 进行细粒度分类
                    token_breakdown = self.token_analyzer.categorize_detailed(
                        input_messages=llm.input_messages,
                        prompt_tokens=llm.prompt_tokens,
                        completion_tokens=llm.completion_tokens,
                        tools_schema=llm.tools_schema,
                        tool_calls=llm.tool_calls,
                        output_text=llm.output_text,
                        is_first_iteration=is_first_iteration,
                    )

                    # 获取工具名称
                    tool_names = [t.tool_name for t in iteration.tool_executions]

                    # 获取跳过的工具调用
                    skipped_calls = [
                        {"tool_name": s.tool_name, "reason": s.reason}
                        for s in iteration.skipped_tool_calls
                    ]

                    result.append(
                        {
                            "id": row_id,
                            "run_number": run_num,
                            "iteration_number": iter_num,
                            "tool_tokens": token_breakdown["tool_tokens"],
                            "system_tokens": token_breakdown["system_tokens"],
                            "skill_tokens": token_breakdown["skill_tokens"],
                            "summary_tokens": token_breakdown["summary_tokens"],
                            "message_tokens": token_breakdown["message_tokens"],
                            "input_tokens": llm.prompt_tokens,
                            "output_tool_tokens": token_breakdown["output_tool_tokens"],
                            "output_text_tokens": token_breakdown["output_text_tokens"],
                            "total_tokens": llm.total_tokens,
                            # Raw data for CLI to format description
                            "tool_names": tool_names,
                            "input_messages": llm.input_messages,
                            "output_text": llm.output_text,
                            "skipped_tool_calls": skipped_calls,
                        }
                    )

        return result

    @staticmethod
    def _get_user_message_preview(input_messages: list[dict], max_len: int = 20) -> str:
        """
        Get a preview of the last user message from input messages.

        Args:
            input_messages: Input messages sent to LLM
            max_len: Maximum length of preview

        Returns:
            Preview string of user message, or empty string if not found
        """
        # Find the last user message
        for msg in reversed(input_messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    # Truncate and clean
                    preview = content.replace("\n", " ")[:max_len]
                    if len(content) > max_len:
                        preview += "..."
                    return preview
        return ""

    def get_base_ratio(self) -> float:
        """
        Get the base ratio for token estimation.

        Returns:
            Base ratio (prompt_tokens / total_chars) from first iteration,
            or 0.25 as default if not available.
        """
        return self._base_ratio if self._base_ratio > 0 else 0.25

    def get_estimation_audit_summary(self) -> dict:
        """Get estimation audit summary (v0.7.18).

        Returns:
            Dict with avg/max deviation, convergence info, etc.
        """
        return self._estimation_audit.get_summary()

    @property
    def estimation_audit(self) -> EstimationAudit:
        """Get the estimation audit instance (v0.7.18)."""
        return self._estimation_audit

    def get_base_chars(self) -> dict[str, int]:
        """
        Get the base character lengths for stable estimation.

        Returns:
            Dict with tool_chars, system_chars, skill_chars
        """
        return {
            "tool_chars": self._base_tool_chars,
            "system_chars": self._base_system_chars,
            "skill_chars": self._base_skill_chars,
        }

    @staticmethod
    def format_iteration_description(
        iter_num: int,
        tool_names: list[str],
        input_messages: list[dict],
        output_text: str,
        skipped_tool_calls: list[dict] | None = None,
    ) -> str:
        """
        Format description for an iteration (for CLI layer to use).

        Args:
            iter_num: Iteration number
            tool_names: List of tool names executed in this iteration
            input_messages: Input messages for this iteration
            output_text: Output text from LLM
            skipped_tool_calls: List of skipped tool calls with reasons

        Returns:
            Formatted description string
        """
        skipped_tool_calls = skipped_tool_calls or []

        if iter_num == 1:
            # First iteration: show user message
            user_msg = MetricsTracker._get_user_message_preview(input_messages)
            if user_msg:
                return f"[用户] {user_msg}"
            else:
                return "[用户] 发起请求"
        else:
            # Subsequent iterations: check skipped first, then tool calls, then output
            if skipped_tool_calls:
                # Show skipped tool calls with reason
                skipped_names = [s["tool_name"] for s in skipped_tool_calls]
                reasons = set(s["reason"] for s in skipped_tool_calls)
                reason_str = ", ".join(reasons)
                return f"[跳过] {', '.join(skipped_names)} ({reason_str})"
            elif tool_names:
                return f"[工具调用] {', '.join(tool_names)}"
            elif output_text:
                # No tool calls, has output text -> final answer
                preview = output_text.replace("\n", " ")[:20]
                if len(output_text) > 20:
                    preview += "..."
                return f"[回答] {preview}"
            else:
                return "[思考] 继续处理"

    def reset(self) -> None:
        """Reset the tracker."""
        self.run_metrics = None
        self._current_iteration = None
        self._iteration_start_time = 0.0
        self._run_start_time = 0.0
        self._base_ratio = 0.0  # 重置基准比例
        self._base_tool_chars = 0  # 重置基准字符长度
        self._base_system_chars = 0
        self._base_skill_chars = 0
        self._base_ratio_initialized = False
        self._base_ratio_iteration = 0
        self._estimation_audit.reset()
