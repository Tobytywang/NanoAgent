"""
Metrics data structures for runtime monitoring.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LLMCallMetrics:
    """LLM 调用指标"""

    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    tool_calls_count: int
    # 新增：输入输出信息
    input_messages: list[dict] = field(default_factory=list)
    output_text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    # 新增：工具定义 schema（用于 token 分类）
    tools_schema: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": round(self.latency_ms, 2),
            "tool_calls_count": self.tool_calls_count,
            "input_messages": self.input_messages,
            "output_text": self.output_text,
            "tool_calls": self.tool_calls,
            "tools_schema": self.tools_schema,
        }


@dataclass
class ToolExecutionMetrics:
    """工具执行指标"""

    timestamp: datetime
    tool_name: str
    arguments: dict[str, Any]
    success: bool
    latency_ms: float
    output_length: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "success": self.success,
            "latency_ms": round(self.latency_ms, 2),
            "output_length": self.output_length,
            "error": self.error,
        }


@dataclass
class SkippedToolCall:
    """跳过的工具调用记录"""

    tool_name: str
    arguments: dict[str, Any]
    reason: str  # "routing_limit" | "merged" | "duplicate" | "budget_exceeded"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "reason": self.reason,
        }


@dataclass
class IterationMetrics:
    """迭代指标"""

    iteration_number: int
    llm_call: LLMCallMetrics | None = None
    tool_executions: list[ToolExecutionMetrics] = field(default_factory=list)
    skipped_tool_calls: list[SkippedToolCall] = field(default_factory=list)
    total_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iteration_number": self.iteration_number,
            "llm_call": self.llm_call.to_dict() if self.llm_call else None,
            "tool_executions": [t.to_dict() for t in self.tool_executions],
            "skipped_tool_calls": [s.to_dict() for s in self.skipped_tool_calls],
            "total_latency_ms": round(self.total_latency_ms, 2),
        }


@dataclass
class RunMetrics:
    """完整运行指标"""

    session_id: str
    start_time: datetime
    end_time: datetime | None = None
    user_input: str = ""
    final_response: str = ""
    iterations: list[IterationMetrics] = field(default_factory=list)
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    run_number: int = 0  # 轮次编号 (全局递增)

    @property
    def total_iterations(self) -> int:
        """Total number of iterations."""
        return len(self.iterations)

    @property
    def total_tool_calls(self) -> int:
        """Total number of tool calls."""
        return sum(len(i.tool_executions) for i in self.iterations)

    @property
    def successful_tool_calls(self) -> int:
        """Number of successful tool calls."""
        return sum(
            1 for i in self.iterations for t in i.tool_executions if t.success
        )

    @property
    def failed_tool_calls(self) -> int:
        """Number of failed tool calls."""
        return self.total_tool_calls - self.successful_tool_calls

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "user_input": self.user_input,
            "final_response": self.final_response,
            "iterations": [i.to_dict() for i in self.iterations],
            "total_tokens": self.total_tokens,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "summary": {
                "total_iterations": self.total_iterations,
                "total_tool_calls": self.total_tool_calls,
                "successful_tool_calls": self.successful_tool_calls,
                "failed_tool_calls": self.failed_tool_calls,
            },
        }
