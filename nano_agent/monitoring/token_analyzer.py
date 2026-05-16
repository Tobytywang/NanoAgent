"""
Token analyzer for categorizing token consumption.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenCategory(Enum):
    """Token 消耗分类"""
    SYSTEM = "system"        # 系统提示词（固定成本）
    TOOLS = "tools"          # 工具输出（可优化成本）
    HISTORY = "history"      # 历史消息（累积成本）
    RESPONSE = "response"    # LLM 响应（输出成本）
    COMPRESSED = "compressed" # 压缩节省（优化效果）


@dataclass
class TokenBreakdown:
    """Token 消耗明细"""
    category: TokenCategory
    tokens: int
    percentage: float
    details: dict[str, int] = field(default_factory=dict)  # 子分类详情


@dataclass
class ToolTokenUsage:
    """工具 Token 使用记录"""
    tool_name: str
    input_tokens: int   # 工具调用参数 Token
    output_tokens: int  # 工具输出 Token
    call_count: int     # 调用次数


class TokenAnalyzer:
    """Token 分析器 - 分析 Token 消耗来源"""

    def __init__(self):
        self._category_totals: dict[TokenCategory, int] = {
            TokenCategory.SYSTEM: 0,
            TokenCategory.TOOLS: 0,
            TokenCategory.HISTORY: 0,
            TokenCategory.RESPONSE: 0,
            TokenCategory.COMPRESSED: 0,
        }
        self._tool_token_usage: dict[str, ToolTokenUsage] = {}
        self._iteration_breakdowns: list[dict[str, int]] = []  # 各轮消耗

    def analyze_llm_call(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        input_messages: list[dict],
        tool_calls: list[dict] | None = None,
    ) -> None:
        """
        分析单次 LLM 调用的 Token 消耗。

        Args:
            prompt_tokens: 输入 Token 数（实际值）
            completion_tokens: 输出 Token 数（实际值）
            input_messages: 输入消息列表
            tool_calls: 工具调用列表
        """
        # 分类统计输入消息（使用估算值计算比例）
        system_chars = 0
        tool_chars = 0
        history_chars = 0

        for msg in input_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            # 估算字符数
            msg_chars = self._estimate_message_chars(msg)

            if role == "system":
                system_chars += msg_chars
            elif role == "tool":
                # 工具输出消息
                tool_chars += msg_chars
                # 记录工具消耗（按比例分配实际 token）
                tool_name = msg.get("name", "unknown")
                self._record_tool_output(tool_name, msg_chars)
            elif content and not role == "tool":
                # 用户或助手消息（历史对话）
                history_chars += msg_chars

        # 计算总字符数用于比例分配
        total_chars = system_chars + tool_chars + history_chars

        # 按比例分配实际的 prompt_tokens
        if total_chars > 0:
            system_tokens = int(prompt_tokens * system_chars / total_chars)
            tool_tokens = int(prompt_tokens * tool_chars / total_chars)
            history_tokens = prompt_tokens - system_tokens - tool_tokens  # 避免舍入误差
        else:
            system_tokens = 0
            tool_tokens = 0
            history_tokens = prompt_tokens

        # 更新分类统计
        self._category_totals[TokenCategory.SYSTEM] += system_tokens
        self._category_totals[TokenCategory.TOOLS] += tool_tokens
        self._category_totals[TokenCategory.HISTORY] += history_tokens
        self._category_totals[TokenCategory.RESPONSE] += completion_tokens

        # 记录本轮消耗
        self._iteration_breakdowns.append({
            "system": system_tokens,
            "tools": tool_tokens,
            "history": history_tokens,
            "response": completion_tokens,
            "total": prompt_tokens + completion_tokens,
        })

        # 记录工具调用参数（如果有）
        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.get("name", "unknown")
                # 估算工具调用参数字符数
                args_chars = self._estimate_dict_chars(tc.get("arguments", {}))
                self._record_tool_input(tool_name, args_chars)

    def record_compression_savings(self, saved_tokens: int) -> None:
        """
        记录压缩节省的 Token。

        Args:
            saved_tokens: 节省的 Token 数
        """
        self._category_totals[TokenCategory.COMPRESSED] += saved_tokens

    def get_breakdown(self) -> list[TokenBreakdown]:
        """
        获取 Token 消耗明细。

        Returns:
            TokenBreakdown 列表
        """
        # 计算总消耗（不含压缩节省）
        total = sum(
            v for k, v in self._category_totals.items()
            if k != TokenCategory.COMPRESSED
        )

        if total == 0:
            return []

        breakdowns = []
        for category, tokens in self._category_totals.items():
            if tokens > 0:
                percentage = (tokens / total * 100) if total > 0 else 0
                breakdowns.append(TokenBreakdown(
                    category=category,
                    tokens=tokens,
                    percentage=percentage,
                    details=self._get_category_details(category),
                ))

        # 按消耗量排序
        breakdowns.sort(key=lambda x: x.tokens, reverse=True)
        return breakdowns

    def get_tool_ranking(self, limit: int = 10) -> list[ToolTokenUsage]:
        """
        获取工具 Token 消耗排名。

        注意：工具的 input_tokens 和 output_tokens 实际存储的是字符数，
        这里按比例转换为实际的 token 数。

        Args:
            limit: 返回数量限制

        Returns:
            ToolTokenUsage 列表（按总消耗排序）
        """
        # 计算工具总字符数
        total_tool_chars = sum(
            t.input_tokens + t.output_tokens
            for t in self._tool_token_usage.values()
        )

        # 获取工具实际消耗的 token 数（TOOLS 分类）
        total_tool_tokens = self._category_totals.get(TokenCategory.TOOLS, 0)

        # 按比例分配 token
        result = []
        for tool in self._tool_token_usage.values():
            if total_tool_chars > 0:
                # 按字符比例分配 token
                tool_chars = tool.input_tokens + tool.output_tokens
                tool_tokens = int(total_tool_tokens * tool_chars / total_tool_chars)
                input_ratio = tool.input_tokens / tool_chars if tool_chars > 0 else 0.5
                input_tokens = int(tool_tokens * input_ratio)
                output_tokens = tool_tokens - input_tokens
            else:
                input_tokens = 0
                output_tokens = 0

            result.append(ToolTokenUsage(
                tool_name=tool.tool_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                call_count=tool.call_count,
            ))

        # 按总消耗排序
        result.sort(key=lambda x: x.input_tokens + x.output_tokens, reverse=True)
        return result[:limit]

    def get_iteration_breakdowns(self) -> list[dict[str, int]]:
        """
        获取各轮 Token 消耗详情。

        Returns:
            各轮消耗列表
        """
        return self._iteration_breakdowns

    def get_summary(self) -> dict[str, Any]:
        """
        获取 Token 分析摘要。

        Returns:
            摘要字典
        """
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
                v for k, v in self._category_totals.items()
                if k != TokenCategory.COMPRESSED
            ),
            "compression_savings": self._category_totals[TokenCategory.COMPRESSED],
        }

    def reset(self) -> None:
        """重置分析器"""
        for category in self._category_totals:
            self._category_totals[category] = 0
        self._tool_token_usage.clear()
        self._iteration_breakdowns.clear()

    def _estimate_message_chars(self, msg: dict) -> int:
        """
        估算单条消息的字符数。

        Args:
            msg: 消息字典

        Returns:
            字符数
        """
        content = msg.get("content", "")
        if isinstance(content, str):
            return len(content)
        elif isinstance(content, list):
            # 复杂内容（如多模态）
            total = 0
            for item in content:
                if isinstance(item, str):
                    total += len(item)
                elif isinstance(item, dict) and "text" in item:
                    total += len(item["text"])
            return total
        return 0

    def _estimate_dict_chars(self, d: dict) -> int:
        """
        估算字典内容的字符数。

        Args:
            d: 字典

        Returns:
            字符数
        """
        import json
        try:
            text = json.dumps(d)
            return len(text)
        except Exception:
            return 0

    def _record_tool_output(self, tool_name: str, chars: int) -> None:
        """
        记录工具输出字符数（用于后续按比例分配 token）。

        Args:
            tool_name: 工具名称
            chars: 字符数
        """
        if tool_name not in self._tool_token_usage:
            self._tool_token_usage[tool_name] = ToolTokenUsage(
                tool_name=tool_name,
                input_tokens=0,
                output_tokens=0,
                call_count=0,
            )
        # 暂存字符数，后续会在 get_tool_ranking 中转换
        self._tool_token_usage[tool_name].output_tokens += chars

    def _record_tool_input(self, tool_name: str, chars: int) -> None:
        """
        记录工具调用参数字符数。

        Args:
            tool_name: 工具名称
            chars: 字符数
        """
        if tool_name not in self._tool_token_usage:
            self._tool_token_usage[tool_name] = ToolTokenUsage(
                tool_name=tool_name,
                input_tokens=0,
                output_tokens=0,
                call_count=0,
            )
        # 暂存字符数
        self._tool_token_usage[tool_name].input_tokens += chars
        self._tool_token_usage[tool_name].call_count += 1

    def _get_category_details(self, category: TokenCategory) -> dict[str, int]:
        """
        获取分类的详细子项。

        Args:
            category: Token 分类

        Returns:
            子分类详情
        """
        if category == TokenCategory.TOOLS:
            # 返回各工具消耗
            return {
                t.tool_name: t.output_tokens
                for t in self._tool_token_usage.values()
            }
        return {}