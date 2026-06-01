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


class MetricsTracker:
    """运行时指标追踪器"""

    def __init__(self, enabled: bool = True):
        """
        Initialize the tracker.

        Args:
            enabled: Whether tracking is enabled
        """
        self.enabled = enabled
        self.run_metrics: RunMetrics | None = None
        self._current_iteration: IterationMetrics | None = None
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
        self._base_ratio: float = 0.0
        # 保存第一次迭代时的字符长度，确保后续迭代使用相同值
        self._base_tool_chars: int = 0
        self._base_system_chars: int = 0
        self._base_skill_chars: int = 0

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

        Args:
            model: The model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            latency_ms: Latency in milliseconds
            tool_calls_count: Number of tool calls in response
            input_messages: The input messages sent to LLM
            output_text: The output text from LLM
            tool_calls: The tool calls from LLM response
            tools_schema: The tool definitions schema sent to LLM
        """
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
        Record a tool execution (legacy method, accepts individual parameters).

        Args:
            tool_name: The tool name
            arguments: The tool arguments
            success: Whether execution succeeded
            latency_ms: Latency in milliseconds
            output_length: Length of output
            error: Error message if failed
        """
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
            for iteration in run.iterations:
                iter_num = iteration.iteration_number
                if iteration.llm_call:
                    row_id += 1
                    llm = iteration.llm_call

                    # 分析输入消息，分类 token 消耗
                    token_breakdown = self._categorize_tokens_v2(
                        llm.input_messages,
                        llm.prompt_tokens,
                        llm.completion_tokens,
                        llm.tools_schema,
                        llm.tool_calls,
                        llm.output_text,
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

    def _categorize_tokens_v2(
        self,
        input_messages: list[dict],
        prompt_tokens: int,
        completion_tokens: int,
        tools_schema: list[dict],
        tool_calls: list[dict],
        output_text: str,
    ) -> dict[str, int]:
        """
        Categorize token consumption by type for a single iteration.

        分类逻辑（改进版：固定部分使用基准比例，确保数值稳定）：
        1. 第一次迭代时计算基准比例 = prompt_tokens / 总字符长度
        2. 后续迭代使用基准比例计算固定部分（工具、系统、技能）
        3. 消息部分 = prompt_tokens - 固定部分，确保总和准确

        Args:
            input_messages: Input messages sent to LLM
            prompt_tokens: Total prompt tokens
            completion_tokens: Total completion tokens
            tools_schema: Tool definitions schema sent to LLM
            tool_calls: Tool calls from LLM response
            output_text: Output text from LLM

        Returns:
            Dict with tool_tokens, system_tokens, skill_tokens, summary_tokens, message_tokens,
                 output_tool_tokens, output_text_tokens
        """
        import json

        # === 输入部分分类 ===
        # 步骤1：准确计算各部分的字符长度
        tool_chars = 0
        system_chars = 0
        skill_chars = 0
        summary_chars = 0  # 新增：历史摘要
        message_chars = 0

        # 1. 工具定义字符长度（从 tools_schema）
        if tools_schema:
            tools_json = json.dumps(tools_schema, ensure_ascii=False)
            tool_chars = len(tools_json)

        # 2. 分析 messages 中各角色的字符长度
        for msg in input_messages:
            role = msg.get("role", "")
            content = msg.get("content", "") or ""
            chars = len(content)

            if role == "system":
                # 检查是否是历史摘要（compressor 生成的）
                if content.startswith("[历史摘要]"):
                    summary_chars += chars
                # 检查是否包含 skill 相关内容
                elif "## Skills" in content or "skill" in content.lower():
                    skill_chars += chars
                else:
                    system_chars += chars
            elif role == "tool":
                # 工具结果属于消息列
                message_chars += chars
            else:
                # user, assistant 等属于消息列
                message_chars += chars

        # 步骤2：计算总字符长度
        total_chars = (
            tool_chars + system_chars + skill_chars + summary_chars + message_chars
        )

        if total_chars > 0:
            # 步骤3：第一次迭代时计算并保存基准比例和字符长度
            if self._base_ratio == 0:
                self._base_ratio = prompt_tokens / total_chars
                self._base_tool_chars = tool_chars
                self._base_system_chars = system_chars
                self._base_skill_chars = skill_chars

            # 步骤4：使用保存的基准值计算固定部分（确保数值稳定）
            tool_tokens = int(self._base_tool_chars * self._base_ratio)
            system_tokens = int(self._base_system_chars * self._base_ratio)
            skill_tokens = int(self._base_skill_chars * self._base_ratio)

            # 摘要部分：按当前字符长度计算（摘要会变化，不使用基准值）
            summary_tokens = (
                int(summary_chars * self._base_ratio) if summary_chars > 0 else 0
            )

            # 步骤5：消息部分用减法，确保总和等于 prompt_tokens
            message_tokens = (
                prompt_tokens
                - tool_tokens
                - system_tokens
                - skill_tokens
                - summary_tokens
            )
        else:
            tool_tokens = 0
            system_tokens = 0
            skill_tokens = 0
            summary_tokens = 0
            message_tokens = prompt_tokens

        # === 输出部分分类 ===
        output_tool_tokens = 0
        output_text_tokens = 0

        if tool_calls:
            # 有 tool_calls
            # 计算 tool_calls 的字符长度
            tool_calls_json = json.dumps(tool_calls, ensure_ascii=False)
            tool_calls_chars = len(tool_calls_json)
            output_text_chars = len(output_text) if output_text else 0

            # 简化估算：如果 content 极短（<50字符），全部归为 tool_calls
            if output_text_chars < 50:
                output_tool_tokens = completion_tokens
                output_text_tokens = 0
            else:
                # 按比例分配
                total_output_chars = tool_calls_chars + output_text_chars
                if total_output_chars > 0:
                    tool_ratio = tool_calls_chars / total_output_chars
                    output_tool_tokens = int(completion_tokens * tool_ratio)
                    output_text_tokens = completion_tokens - output_tool_tokens
        else:
            # 无 tool_calls，全部是文本回复
            output_tool_tokens = 0
            output_text_tokens = completion_tokens

        return {
            "tool_tokens": tool_tokens,
            "system_tokens": system_tokens,
            "skill_tokens": skill_tokens,
            "summary_tokens": summary_tokens,
            "message_tokens": message_tokens,
            "output_tool_tokens": output_tool_tokens,
            "output_text_tokens": output_text_tokens,
        }

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
