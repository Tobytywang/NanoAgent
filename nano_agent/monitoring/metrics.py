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
    # 完整交互信息（用于 prompt 优化分析）
    prompt_messages: list[dict] = field(default_factory=list)  # 发送给 LLM 的完整 messages
    response_text: str = ""  # LLM 返回的完整文本
    tool_calls_detail: list[dict] = field(default_factory=list)  # 工具调用详情

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
            "prompt_messages": self.prompt_messages,
            "response_text": self.response_text,
            "tool_calls_detail": self.tool_calls_detail,
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
class IterationMetrics:
    """迭代指标"""

    iteration_number: int
    llm_call: LLMCallMetrics | None = None
    tool_executions: list[ToolExecutionMetrics] = field(default_factory=list)
    total_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iteration_number": self.iteration_number,
            "llm_call": self.llm_call.to_dict() if self.llm_call else None,
            "tool_executions": [t.to_dict() for t in self.tool_executions],
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
