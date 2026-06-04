"""
Token analyzer for categorizing token consumption.

Merges the former TokenAnalyzer (coarse) and MetricsTracker._categorize_tokens_v2 (detailed)
into a single class with two methods:
- analyze_llm_call(): coarse grain (system/tools/history/response) for quick reports
- categorize_detailed(): fine grain for budget management and usage tables
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenCategory(Enum):
    """Token 消耗分类"""

    SYSTEM = "system"
    TOOLS = "tools"
    HISTORY = "history"
    RESPONSE = "response"
    COMPRESSED = "compressed"


@dataclass
class TokenBreakdown:
    """Token 消耗明细"""

    category: TokenCategory
    tokens: int
    percentage: float
    details: dict[str, int] = field(default_factory=dict)


@dataclass
class ToolTokenUsage:
    """工具 Token 使用记录"""

    tool_name: str
    input_tokens: int
    output_tokens: int
    call_count: int


class TokenAnalyzer:
    """Token 分析器 - 粗粒度 + 细粒度 token 分类"""

    def __init__(self):
        # Coarse grain accumulators
        self._category_totals: dict[TokenCategory, int] = {
            TokenCategory.SYSTEM: 0,
            TokenCategory.TOOLS: 0,
            TokenCategory.HISTORY: 0,
            TokenCategory.RESPONSE: 0,
            TokenCategory.COMPRESSED: 0,
        }
        self._tool_token_usage: dict[str, ToolTokenUsage] = {}
        self._iteration_breakdowns: list[dict[str, int]] = []

        # Fine grain: base_ratio state (migrated from MetricsTracker._categorize_tokens_v2)
        self._base_ratio: float = 0.0
        self._base_tool_chars: int = 0
        self._base_system_chars: int = 0
        self._base_skill_chars: int = 0
        self._base_ratio_initialized: bool = False
        self._base_ratio_iteration: int = 0

    def reset_base_ratio(self) -> None:
        """Reset base_ratio state for a new run."""
        self._base_ratio = 0.0
        self._base_tool_chars = 0
        self._base_system_chars = 0
        self._base_skill_chars = 0
        self._base_ratio_initialized = False
        self._base_ratio_iteration = 0

    # ── Coarse grain API ──────────────────────────────────────────────

    def analyze_llm_call(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        input_messages: list[dict],
        tool_calls: list[dict] | None = None,
    ) -> None:
        """
        粗粒度 token 分类 - 累积统计。

        Args:
            prompt_tokens: 输入 Token 数（实际值）
            completion_tokens: 输出 Token 数（实际值）
            input_messages: 输入消息列表
            tool_calls: 工具调用列表
        """
        system_chars = 0
        tool_chars = 0
        history_chars = 0

        for msg in input_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            msg_chars = self._estimate_message_chars(msg)

            if role == "system":
                system_chars += msg_chars
            elif role == "tool":
                tool_chars += msg_chars
                tool_name = msg.get("name", "unknown")
                self._record_tool_output(tool_name, msg_chars)
            elif content and role != "tool":
                history_chars += msg_chars

        total_chars = system_chars + tool_chars + history_chars
        if total_chars > 0:
            system_tokens = int(prompt_tokens * system_chars / total_chars)
            tool_tokens = int(prompt_tokens * tool_chars / total_chars)
            history_tokens = prompt_tokens - system_tokens - tool_tokens
        else:
            system_tokens = 0
            tool_tokens = 0
            history_tokens = prompt_tokens

        self._category_totals[TokenCategory.SYSTEM] += system_tokens
        self._category_totals[TokenCategory.TOOLS] += tool_tokens
        self._category_totals[TokenCategory.HISTORY] += history_tokens
        self._category_totals[TokenCategory.RESPONSE] += completion_tokens

        self._iteration_breakdowns.append(
            {
                "system": system_tokens,
                "tools": tool_tokens,
                "history": history_tokens,
                "response": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            }
        )

        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.get("name", "unknown")
                args_chars = self._estimate_dict_chars(tc.get("arguments", {}))
                self._record_tool_input(tool_name, args_chars)

    def record_compression_savings(self, saved_tokens: int) -> None:
        self._category_totals[TokenCategory.COMPRESSED] += saved_tokens

    def get_breakdown(self) -> list[TokenBreakdown]:
        total = sum(
            v for k, v in self._category_totals.items() if k != TokenCategory.COMPRESSED
        )
        if total == 0:
            return []

        breakdowns = []
        for category, tokens in self._category_totals.items():
            if tokens > 0:
                percentage = (tokens / total * 100) if total > 0 else 0
                breakdowns.append(
                    TokenBreakdown(
                        category=category,
                        tokens=tokens,
                        percentage=percentage,
                        details=self._get_category_details(category),
                    )
                )
        breakdowns.sort(key=lambda x: x.tokens, reverse=True)
        return breakdowns

    def get_tool_ranking(self, limit: int = 10) -> list[ToolTokenUsage]:
        total_tool_chars = sum(
            t.input_tokens + t.output_tokens for t in self._tool_token_usage.values()
        )
        total_tool_tokens = self._category_totals.get(TokenCategory.TOOLS, 0)

        result = []
        for tool in self._tool_token_usage.values():
            if total_tool_chars > 0:
                tool_chars = tool.input_tokens + tool.output_tokens
                tool_tokens = int(total_tool_tokens * tool_chars / total_tool_chars)
                input_ratio = tool.input_tokens / tool_chars if tool_chars > 0 else 0.5
                input_tokens = int(tool_tokens * input_ratio)
                output_tokens = tool_tokens - input_tokens
            else:
                input_tokens = 0
                output_tokens = 0

            result.append(
                ToolTokenUsage(
                    tool_name=tool.tool_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    call_count=tool.call_count,
                )
            )
        result.sort(key=lambda x: x.input_tokens + x.output_tokens, reverse=True)
        return result[:limit]

    def get_iteration_breakdowns(self) -> list[dict[str, int]]:
        return self._iteration_breakdowns

    def get_summary(self) -> dict[str, Any]:
        breakdowns = self.get_breakdown()
        tool_ranking = self.get_tool_ranking(5)
        return {
            "categories": [
                {
                    "name": b.category.value,
                    "tokens": b.tokens,
                    "percentage": round(b.percentage, 1),
                }
                for b in breakdowns
            ],
            "top_tools": [
                {
                    "name": t.tool_name,
                    "input_tokens": t.input_tokens,
                    "output_tokens": t.output_tokens,
                    "total_tokens": t.input_tokens + t.output_tokens,
                    "call_count": t.call_count,
                }
                for t in tool_ranking
            ],
            "iteration_count": len(self._iteration_breakdowns),
            "total_tokens": sum(
                v
                for k, v in self._category_totals.items()
                if k != TokenCategory.COMPRESSED
            ),
            "compression_savings": self._category_totals[TokenCategory.COMPRESSED],
        }

    # ── Fine grain API (migrated from MetricsTracker._categorize_tokens_v2) ──

    def categorize_detailed(
        self,
        input_messages: list[dict],
        prompt_tokens: int,
        completion_tokens: int,
        tools_schema: list[dict],
        tool_calls: list[dict],
        output_text: str,
        is_first_iteration: bool = False,
    ) -> dict[str, int]:
        """
        细粒度 token 分类 - 用于预算管理和 usage 表。

        分类逻辑（v2：跳过首轮设置 base_ratio）：
        1. 首次迭代：保存固定部分字符长度，但不设置 base_ratio
        2. 第二次迭代：设置 base_ratio（更具代表性）
        3. 后续迭代：使用已保存的 base_ratio
        4. 消息部分 = prompt_tokens - 固定部分，确保总和准确
        """
        # === 输入部分分类 ===
        tool_chars = 0
        system_chars = 0
        skill_chars = 0
        summary_chars = 0
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
                if content.startswith("[历史摘要]"):
                    summary_chars += chars
                elif "## Skills" in content or "skill" in content.lower():
                    skill_chars += chars
                else:
                    system_chars += chars
            elif role == "tool":
                message_chars += chars
            else:
                message_chars += chars

        total_chars = (
            tool_chars + system_chars + skill_chars + summary_chars + message_chars
        )

        if total_chars > 0:
            current_ratio = prompt_tokens / total_chars

            if not self._base_ratio_initialized:
                if is_first_iteration:
                    self._base_tool_chars = tool_chars
                    self._base_system_chars = system_chars
                    self._base_skill_chars = skill_chars
                    self._base_ratio_iteration = 1
                    ratio = current_ratio
                else:
                    self._base_ratio = current_ratio
                    self._base_ratio_initialized = True
                    self._base_ratio_iteration = 2
                    ratio = self._base_ratio
            else:
                ratio = self._base_ratio

            tool_tokens = int(self._base_tool_chars * ratio)
            system_tokens = int(self._base_system_chars * ratio)
            skill_tokens = int(self._base_skill_chars * ratio)
            summary_tokens = int(summary_chars * ratio) if summary_chars > 0 else 0
            message_tokens = max(
                0,
                prompt_tokens
                - tool_tokens
                - system_tokens
                - skill_tokens
                - summary_tokens,
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
            tool_calls_json = json.dumps(tool_calls, ensure_ascii=False)
            tool_calls_chars = len(tool_calls_json)
            output_text_chars = len(output_text) if output_text else 0

            if output_text_chars < 50:
                output_tool_tokens = completion_tokens
            else:
                total_output_chars = tool_calls_chars + output_text_chars
                if total_output_chars > 0:
                    tool_ratio = tool_calls_chars / total_output_chars
                    output_tool_tokens = int(completion_tokens * tool_ratio)
                    output_text_tokens = completion_tokens - output_tool_tokens
        else:
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

    def get_base_ratio(self) -> float:
        return self._base_ratio if self._base_ratio > 0 else 0.25

    def get_base_chars(self) -> dict[str, int]:
        return {
            "tool_chars": self._base_tool_chars,
            "system_chars": self._base_system_chars,
            "skill_chars": self._base_skill_chars,
        }

    # ── Reset ─────────────────────────────────────────────────────────

    def reset(self) -> None:
        for category in self._category_totals:
            self._category_totals[category] = 0
        self._tool_token_usage.clear()
        self._iteration_breakdowns.clear()
        self.reset_base_ratio()

    # ── Internal helpers ───────────────────────────────────────────────

    def _estimate_message_chars(self, msg: dict) -> int:
        content = msg.get("content", "")
        if isinstance(content, str):
            return len(content)
        elif isinstance(content, list):
            total = 0
            for item in content:
                if isinstance(item, str):
                    total += len(item)
                elif isinstance(item, dict) and "text" in item:
                    total += len(item["text"])
            return total
        return 0

    def _estimate_dict_chars(self, d: dict) -> int:
        try:
            return len(json.dumps(d))
        except Exception:
            return 0

    def _record_tool_output(self, tool_name: str, chars: int) -> None:
        if tool_name not in self._tool_token_usage:
            self._tool_token_usage[tool_name] = ToolTokenUsage(
                tool_name=tool_name, input_tokens=0, output_tokens=0, call_count=0
            )
        self._tool_token_usage[tool_name].output_tokens += chars

    def _record_tool_input(self, tool_name: str, chars: int) -> None:
        if tool_name not in self._tool_token_usage:
            self._tool_token_usage[tool_name] = ToolTokenUsage(
                tool_name=tool_name, input_tokens=0, output_tokens=0, call_count=0
            )
        self._tool_token_usage[tool_name].input_tokens += chars
        self._tool_token_usage[tool_name].call_count += 1

    def _get_category_details(self, category: TokenCategory) -> dict[str, int]:
        if category == TokenCategory.TOOLS:
            return {
                t.tool_name: t.output_tokens for t in self._tool_token_usage.values()
            }
        return {}
