"""
Monitoring tools for runtime statistics.
"""

import json
from ..base import BaseTool, ToolResult
from ...agent.types import RiskLevel


class GetStatsTool(BaseTool):
    """Get current monitoring statistics."""

    name = "get_stats"
    description = "Get current session statistics including token usage, latency, iterations, and tool calls. Use this to answer questions about performance or resource usage."
    risk_level = RiskLevel.SAFE  # Read-only operation

    def __init__(self, tracker=None, context_length: int = 8192):
        self._tracker = tracker
        self._context_length = context_length

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "detail": {
                    "type": "boolean",
                    "description": "Whether to include detailed iteration breakdown (default: false)",
                }
            },
        }

    def execute(self, detail: bool = False) -> ToolResult:
        if not self._tracker:
            return ToolResult(success=True, output="Monitoring not available.")

        # Use session-level accumulated statistics
        summary = self._tracker.get_session_summary()

        if not summary or summary.get("total_tokens", 0) == 0:
            return ToolResult(
                success=True,
                output="No statistics available yet. Run some queries first.",
            )

        # Calculate context usage
        total_tokens = summary.get("total_tokens", 0)
        usage_percent = (
            (total_tokens / self._context_length) * 100
            if self._context_length > 0
            else 0
        )

        if not detail:
            # Simple summary
            duration_sec = summary.get("session_duration_ms", 0) / 1000
            warning = ""
            if usage_percent >= 80:
                warning = " ⚠️ (接近上限!)"

            output = (
                f"📊 Session Statistics (before current query):\n"
                f"- Tokens: {total_tokens} (prompt + completion)\n"
                f"- Context Usage: {usage_percent:.1f}% ({total_tokens}/{self._context_length}){warning}\n"
                f"- Duration: {duration_sec:.2f} seconds\n"
                f"- LLM Calls: {summary.get('total_llm_calls', 0)}\n"
                f"- Tool Calls: {summary.get('total_tool_calls', 0)} "
                f"({summary.get('successful_tool_calls', 0)} success, "
                f"{summary.get('failed_tool_calls', 0)} failed)"
            )
        else:
            # Detailed report - include both session and current run
            session_summary = summary
            current_run = self._tracker.get_full_report()
            output = json.dumps(
                {
                    "session_summary": session_summary,
                    "current_run": current_run,
                    "context_length": self._context_length,
                    "context_usage_percent": round(usage_percent, 2),
                },
                indent=2,
                default=str,
            )

        return ToolResult(success=True, output=output)
