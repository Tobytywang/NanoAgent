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


class ReportGenerator:
    """Generate reports from monitoring data."""

    @staticmethod
    def to_json(metrics: RunMetrics, indent: int = 2, remove_emoji: bool = True) -> str:
        """
        Export metrics as JSON string.

        Args:
            metrics: RunMetrics object
            indent: JSON indentation
            remove_emoji: Whether to remove emoji characters (default: True)
                          Emoji may display as garbled text in some terminals/editors

        Returns:
            JSON string
        """
        data = metrics.to_dict()
        if remove_emoji:
            data = _sanitize_strings(data)
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
    def save_json(metrics: RunMetrics, path: str, remove_emoji: bool = True) -> None:
        """
        Save metrics to JSON file.

        Args:
            metrics: RunMetrics object
            path: File path
            remove_emoji: Whether to remove emoji characters (default: True)
        """
        with open(path, 'w', encoding='utf-8') as f:
            f.write(ReportGenerator.to_json(metrics, remove_emoji=remove_emoji))

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
    remove_emoji: bool = True
) -> str | None:
    """
    Export report in specified format.

    Args:
        metrics: RunMetrics object
        format: Output format ("json", "markdown", "summary")
        path: Optional file path to save
        remove_emoji: Whether to remove emoji characters from JSON output (default: True)

    Returns:
        Report string if path is None, else None
    """
    generator = ReportGenerator()

    if format == "json":
        content = generator.to_json(metrics, remove_emoji=remove_emoji)
        if path:
            generator.save_json(metrics, path, remove_emoji=remove_emoji)
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