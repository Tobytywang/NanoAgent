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
)
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
        self._session_total_runs: int = 0  # 轮次计数（用户交互次数）
        self._session_total_llm_calls: int = 0  # LLM API 调用次数
        self._session_total_tool_calls: int = 0
        self._session_successful_tool_calls: int = 0
        self._session_failed_tool_calls: int = 0
        self._session_start_time: float = time.perf_counter()

        # 每轮次的 token 消耗记录
        self._run_token_history: list[int] = []  # 每轮的总 token 消耗

        # 每轮次的迭代详情记录
        # 格式: [{"run": 1, "iteration": 1, "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, ...]
        self._iteration_history: list[dict] = []

        # Token analyzer
        self.token_analyzer = TokenAnalyzer()

    def start_run(self, user_input: str) -> None:
        """
        Start tracking a new run.

        Args:
            user_input: The user's input text
        """
        if not self.enabled:
            return

        self.run_metrics = RunMetrics(
            session_id=f"run_{uuid.uuid4().hex[:8]}",
            start_time=datetime.now(),
            user_input=user_input,
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
        self.run_metrics.total_latency_ms = (time.perf_counter() - self._run_start_time) * 1000

        # Calculate total tokens for this run
        self.run_metrics.total_tokens = sum(
            i.llm_call.total_tokens
            for i in self.run_metrics.iterations
            if i.llm_call
        )

        # Accumulate session statistics
        self._session_total_tokens += self.run_metrics.total_tokens
        self._session_total_iterations += len(self.run_metrics.iterations)
        self._session_total_runs += 1  # 增加轮次计数
        self._run_token_history.append(self.run_metrics.total_tokens)  # 记录每轮的 token 消耗

        # 记录每轮的迭代详情
        run_number = self._session_total_runs
        for iteration in self.run_metrics.iterations:
            if iteration.llm_call:
                self._iteration_history.append({
                    "run": run_number,
                    "iteration": iteration.iteration_number,
                    "prompt_tokens": iteration.llm_call.prompt_tokens,
                    "completion_tokens": iteration.llm_call.completion_tokens,
                    "total_tokens": iteration.llm_call.total_tokens,
                })

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
            "total_runs": self._session_total_runs,
            "total_llm_calls": self._session_total_llm_calls,
            "total_tool_calls": self._session_total_tool_calls,
            "successful_tool_calls": self._session_successful_tool_calls,
            "failed_tool_calls": self._session_failed_tool_calls,
        }

    def get_run_count(self) -> int:
        """
        Get the total number of runs (rounds) in this session.

        Returns:
            Total run count
        """
        return self._session_total_runs

    def get_current_run_iterations(self) -> int:
        """
        Get the number of iterations in the current run.

        Returns:
            Iteration count in current run, 0 if no run active
        """
        if self.run_metrics:
            return len(self.run_metrics.iterations)
        return 0

    def get_run_token_history(self) -> list[int]:
        """
        Get token consumption for each run (round).

        Returns:
            List of total tokens for each completed run
        """
        return self._run_token_history.copy()

    def get_iteration_history(self) -> list[dict]:
        """
        Get iteration details for all runs.

        Returns:
            List of dictionaries with run, iteration, prompt_tokens,
            completion_tokens, total_tokens
        """
        return self._iteration_history.copy()

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
                result.append({
                    "iteration_number": iteration.iteration_number,
                    "prompt_tokens": iteration.llm_call.prompt_tokens,
                    "completion_tokens": iteration.llm_call.completion_tokens,
                    "total_tokens": iteration.llm_call.total_tokens,
                })
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

    def reset(self) -> None:
        """Reset the tracker."""
        self.run_metrics = None
        self._current_iteration = None
        self._iteration_start_time = 0.0
        self._run_start_time = 0.0
