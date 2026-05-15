"""
Report generator for exporting monitoring data.
"""

import json
import re
from datetime import datetime
from typing import Any

from .metrics import RunMetrics


def _remove_emoji(text: str) -> str:
    """
    Remove emoji and other high-codepoint Unicode characters.

    These characters (U+1F000 and above) may display as garbled text
    in some terminals or editors (e.g., vim shows them as @ symbols).

    Args:
        text: Input text to sanitize

    Returns:
        Text with emoji removed
    """
    # Remove characters in Supplementary Multilingual Planes (U+1F000+)
    # This includes emoji, symbols, and other extended characters
    return re.sub(r'[\U0001F000-\U000FFFFF]', '', text)


def _split_long_string(text: str, max_length: int = 200) -> list[str]:
    """
    Split a long string into multiple parts for better readability.

    Args:
        text: String to split
        max_length: Maximum length per part (default: 200)

    Returns:
        List of string parts
    """
    if len(text) <= max_length:
        return [text]

    parts = []
    i = 0
    while i < len(text):
        # Find a good break point
        end = min(i + max_length, len(text))

        # Try to break at a newline if possible
        if end < len(text):
            # Look for newline within last 50 chars of chunk
            newline_pos = text.rfind('\n', i, end)
            if newline_pos > i:
                end = newline_pos + 1
            else:
                # Try to break at a space
                space_pos = text.rfind(' ', i, end)
                if space_pos > i:
                    end = space_pos + 1

        parts.append(text[i:end])
        i = end

    return parts


def _sanitize_strings(obj: Any) -> Any:
    """
    Recursively sanitize all strings in a structure.

    Args:
        obj: Object to sanitize (dict, list, str, or other)

    Returns:
        Sanitized object with all strings cleaned of emoji
    """
    if isinstance(obj, dict):
        return {k: _sanitize_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_strings(v) for v in obj]
    elif isinstance(obj, str):
        return _remove_emoji(obj)
    else:
        return obj


def _format_data_for_readable_json(data: dict, max_string_length: int = 200) -> dict:
    """
    Format data structure for more readable JSON output.

    Long string values in prompt_messages are split into arrays of
    shorter strings, making the JSON easier to view in terminals/editors.

    Args:
        data: Original data dictionary
        max_string_length: Maximum string length before splitting

    Returns:
        Formatted data dictionary
    """
    result = {}

    for key, value in data.items():
        if key == 'iterations' and isinstance(value, list):
            # Process iterations to split long prompt_messages content
            result[key] = [
                _format_iteration(iteration, max_string_length)
                for iteration in value
            ]
        else:
            result[key] = value

    return result


def _format_iteration(iteration: dict, max_string_length: int) -> dict:
    """
    Format a single iteration for readable JSON.

    Args:
        iteration: Iteration data
        max_string_length: Maximum string length before splitting

    Returns:
        Formatted iteration dictionary
    """
    result = dict(iteration)

    if 'llm_call' in result and result['llm_call']:
        llm_call = result['llm_call']

        # Format prompt_messages
        if 'prompt_messages' in llm_call and llm_call['prompt_messages']:
            llm_call['prompt_messages'] = [
                _format_prompt_message(msg, max_string_length)
                for msg in llm_call['prompt_messages']
            ]

        # Format output_text if it's very long
        if 'output_text' in llm_call and isinstance(llm_call['output_text'], str):
            if len(llm_call['output_text']) > max_string_length:
                llm_call['output_text_parts'] = _split_long_string(
                    llm_call['output_text'], max_string_length
                )

    return result


def _format_prompt_message(msg: dict, max_string_length: int) -> dict:
    """
    Format a prompt message for readable JSON.

    Long 'content' values are split into 'content_parts' array.

    Args:
        msg: Message dictionary
        max_string_length: Maximum string length before splitting

    Returns:
        Formatted message dictionary
    """
    result = dict(msg)

    if 'content' in result and isinstance(result['content'], str):
        content = result['content']
        if len(content) > max_string_length:
            # Split into parts and store as array
            result['content_parts'] = _split_long_string(content, max_string_length)
            # Keep original content reference but mark as split
            result['content_length'] = len(content)
            # Remove the long content to avoid @ display issue
            del result['content']

    return result


class ReportGenerator:
    """Generate reports from monitoring data."""

    @staticmethod
    def to_json(metrics: RunMetrics, indent: int = 2, remove_emoji: bool = True,
                max_string_length: int = 200) -> str:
        """
        Export metrics as JSON string.

        Args:
            metrics: RunMetrics object
            indent: JSON indentation
            remove_emoji: Whether to remove emoji characters (default: True)
                          Emoji may display as garbled text in some terminals/editors
            max_string_length: Maximum string length before splitting into parts (default: 200)
                               Set to 0 to disable splitting

        Returns:
            JSON string
        """
        data = metrics.to_dict()

        if remove_emoji:
            data = _sanitize_strings(data)

        if max_string_length > 0:
            data = _format_data_for_readable_json(data, max_string_length)

        return json.dumps(data, indent=indent, default=str, ensure_ascii=False)

    @staticmethod
    def to_markdown(metrics: RunMetrics) -> str:
        """
        Export metrics as Markdown string.

        Args:
            metrics: RunMetrics object

        Returns:
            Markdown string
        """
        data = metrics.to_dict()

        lines = [
            "# NanoAgent 运行报告",
            "",
            f"**Session ID**: {data.get('session_id', 'N/A')}",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## 概览",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总 Token | {data.get('total_tokens', 0)} |",
            f"| 总耗时 | {data.get('total_latency_ms', 0) / 1000:.2f}s |",
            f"| 迭代次数 | {len(data.get('iterations', []))} |",
            "",
            "---",
            "",
            "## 用户输入",
            "",
            f"> {data.get('user_input', 'N/A')}",
            "",
            "---",
            "",
            "## 最终回复",
            "",
            f"{data.get('final_response', 'N/A')[:500]}...",
            "",
            "---",
            "",
            "## 迭代详情",
            "",
        ]

        for iteration in data.get('iterations', []):
            lines.append(f"### 迭代 {iteration.get('iteration_number', '?')}")

            # LLM 调用
            if iteration.get('llm_call'):
                llm = iteration['llm_call']
                lines.extend([
                    "",
                    "**LLM 调用**:",
                    "",
                    f"- 模型: `{llm.get('model', 'N/A')}`",
                    f"- Token: {llm.get('prompt_tokens', 0)} (prompt) + {llm.get('completion_tokens', 0)} (completion) = {llm.get('total_tokens', 0)}",
                    f"- 耗时: {llm.get('latency_ms', 0):.2f}ms",
                    f"- 工具调用数: {llm.get('tool_calls_count', 0)}",
                    "",
                ])

                # Prompt Messages 详情
                if llm.get('prompt_messages'):
                    lines.append("#### 发送给 LLM 的 Messages")
                    lines.append("")
                    for i, msg in enumerate(llm['prompt_messages'], 1):
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        lines.append(f"**[{i}] {role}**:")
                        lines.append("```")
                        lines.append(content)
                        lines.append("```")
                        lines.append("")

                # Response 详情
                if llm.get('response_text'):
                    lines.append("#### LLM 返回的 Response")
                    lines.append("")
                    lines.append("```")
                    lines.append(llm['response_text'])
                    lines.append("```")
                    lines.append("")

                # Tool Calls 详情
                if llm.get('tool_calls_detail'):
                    lines.append("#### 工具调用详情")
                    lines.append("")
                    for tc in llm['tool_calls_detail']:
                        tc_name = tc.get('name', 'unknown')
                        tc_args = tc.get('arguments', {})
                        lines.append(f"- `{tc_name}`: `{tc_args}`")
                    lines.append("")

            # 工具执行
            if iteration.get('tool_executions'):
                lines.append("**工具执行**:")
                lines.append("")
                lines.append("| 工具 | 状态 | 耗时 |")
                lines.append("|------|------|------|")

                for tool in iteration['tool_executions']:
                    status = "✓" if tool.get('success') else "✗"
                    lines.append(
                        f"| `{tool.get('tool_name', '?')}` | {status} | {tool.get('latency_ms', 0):.2f}ms |"
                    )

                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def to_summary(metrics: RunMetrics) -> str:
        """
        Export metrics as a brief summary.

        Args:
            metrics: RunMetrics object

        Returns:
            Summary string
        """
        data = metrics.to_dict()

        total_tokens = data.get('total_tokens', 0)
        total_time = data.get('total_latency_ms', 0) / 1000
        iterations = len(data.get('iterations', []))

        # Count tool calls
        total_tools = 0
        success_tools = 0
        for iteration in data.get('iterations', []):
            for tool in iteration.get('tool_executions', []):
                total_tools += 1
                if tool.get('success'):
                    success_tools += 1

        return (
            f"📊 运行摘要\n"
            f"- Token: {total_tokens}\n"
            f"- 耗时: {total_time:.2f}s\n"
            f"- 迭代: {iterations}\n"
            f"- 工具调用: {success_tools}/{total_tools} 成功"
        )

    @staticmethod
    def save_json(metrics: RunMetrics, path: str, remove_emoji: bool = True,
                  max_string_length: int = 200) -> None:
        """
        Save metrics to JSON file.

        Args:
            metrics: RunMetrics object
            path: File path
            remove_emoji: Whether to remove emoji characters (default: True)
            max_string_length: Maximum string length before splitting (default: 200)
        """
        with open(path, 'w', encoding='utf-8') as f:
            f.write(ReportGenerator.to_json(metrics, remove_emoji=remove_emoji,
                                            max_string_length=max_string_length))

    @staticmethod
    def save_markdown(metrics: RunMetrics, path: str) -> None:
        """
        Save metrics to Markdown file.

        Args:
            metrics: RunMetrics object
            path: File path
        """
        with open(path, 'w', encoding='utf-8') as f:
            f.write(ReportGenerator.to_markdown(metrics))


def export_report(
    metrics: RunMetrics,
    format: str = "json",
    path: str | None = None,
    remove_emoji: bool = True,
    max_string_length: int = 200
) -> str | None:
    """
    Export report in specified format.

    Args:
        metrics: RunMetrics object
        format: Output format ("json", "markdown", "summary")
        path: Optional file path to save
        remove_emoji: Whether to remove emoji characters from JSON output (default: True)
        max_string_length: Maximum string length before splitting (default: 200)

    Returns:
        Report string if path is None, else None
    """
    generator = ReportGenerator()

    if format == "json":
        content = generator.to_json(metrics, remove_emoji=remove_emoji,
                                    max_string_length=max_string_length)
        if path:
            generator.save_json(metrics, path, remove_emoji=remove_emoji,
                               max_string_length=max_string_length)
        return content

    elif format == "markdown":
        content = generator.to_markdown(metrics)
        if path:
            generator.save_markdown(metrics, path)
        return content

    elif format == "summary":
        return generator.to_summary(metrics)

    else:
        raise ValueError(f"Unknown format: {format}")
