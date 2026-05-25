"""Raw data containers for decoupled agent/monitoring communication."""

from dataclasses import dataclass
from typing import Any


@dataclass
class RawLLMCallData:
    """Container for raw LLM call data passed from agent to tracker.

    This decouples the agent layer from the monitoring layer by allowing
    the agent to pass raw data objects without knowing how to extract
    or convert them for tracking purposes.

    Attributes:
        llm: The LLM client instance (has .model attribute)
        messages: Raw messages list sent to LLM
        tools_schema: Raw tools schema sent to LLM (can be None)
        response_text: Raw response text from LLM
        tool_calls: Raw ToolCall objects (not converted to dict)
        usage: LLMUsage object with token counts
        latency_ms: Measured latency in milliseconds
    """

    llm: Any
    messages: list[dict]
    tools_schema: list[dict] | None
    response_text: str
    tool_calls: list[Any]
    usage: Any
    latency_ms: float


@dataclass
class RawToolExecutionData:
    """Container for raw tool execution data.

    This allows the agent to pass raw tool call and result objects
    without extracting individual fields.

    Attributes:
        tool_call: ToolCall object with name and arguments
        result: ToolResult object with success, output, error
        latency_ms: Measured latency in milliseconds
    """

    tool_call: Any
    result: Any
    latency_ms: float
