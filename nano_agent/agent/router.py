"""
Query complexity routing for token efficiency.

This module provides a QueryRouter class that classifies queries by complexity
and applies appropriate processing strategies.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class QueryComplexity(Enum):
    """Query complexity levels."""

    SIMPLE = "simple"  # Greetings, simple questions - direct answer
    MODERATE = "moderate"  # Single-step reasoning - max 1 tool call
    COMPLEX = "complex"  # Multi-step reasoning - full ReAct loop


@dataclass
class RoutingResult:
    """Result of query routing."""

    complexity: QueryComplexity
    reason: str
    suggested_max_tools: int  # -1 means unlimited
    suggested_budget_ratio: float = 1.0  # 0.0-1.0, ratio of full budget


class QueryRouter:
    """
    Query complexity router.

    Classifies queries by complexity and suggests processing strategies
    to optimize token consumption.
    """

    # Simple patterns that can be answered directly
    SIMPLE_PATTERNS = [
        # Greetings (support Chinese and English punctuation)
        r"^(你好|hello|hi|嗨|早上好|下午好|晚上好)[\s!.！？?]*$",
        # Thanks
        r"^(谢谢|thanks|thank you|感谢)[\s!.！？?]*$",
        # Simple identity questions
        r"^(你是谁|who are you|你的名字)[\s?？]*$",
        # Simple capability questions
        r"^(你能做什么|what can you do|你有什么功能)[\s?？]*$",
        # Confirmations
        r"^(好的|ok|okay|明白|了解|清楚了)[\s!.！？?]*$",
    ]

    # Very short non-Chinese inputs (English words only)
    SIMPLE_SHORT_PATTERN = r"^[a-zA-Z\s]{1,5}$"

    # Moderate patterns that need single tool call
    MODERATE_PATTERNS = [
        # Single file operations
        r"^(读取|查看|read|show|cat)\s+\S+$",
        r"^(搜索|查找|find|search)\s+\S+$",
        # Simple questions with specific target
        r"^(什么|what|哪个|which)\s+(是|is)\s+\S+$",
    ]

    # Complex patterns that need full loop
    COMPLEX_PATTERNS = [
        # Multi-step tasks
        r"(分析|analyze|实现|implement|重构|refactor|修复|fix)",
        r"(然后|then|接着|next|之后|after)",
        r"(所有|all|多个|multiple|批量|batch)",
        # Code-related tasks
        r"(代码|code|函数|function|类|class|模块|module)",
        # Debug tasks
        r"(错误|error|bug|问题|issue|调试|debug)",
    ]

    def __init__(
        self,
        enabled: bool = True,
        simple_direct: bool = True,
        moderate_single_tool: bool = True,
        custom_simple_patterns: list[str] | None = None,
        custom_moderate_patterns: list[str] | None = None,
        custom_complex_patterns: list[str] | None = None,
        simple_budget_ratio: float = 0.15,
        moderate_budget_ratio: float = 0.5,
        complex_budget_ratio: float = 1.0,
    ):
        """
        Initialize query router.

        Args:
            enabled: Whether routing is enabled
            simple_direct: Whether to answer simple queries directly
            moderate_single_tool: Whether to limit moderate queries to 1 tool
            custom_simple_patterns: Additional simple patterns
            custom_moderate_patterns: Additional moderate patterns
            custom_complex_patterns: Additional complex patterns
            simple_budget_ratio: Budget ratio for SIMPLE queries (default 0.15 = 15%)
            moderate_budget_ratio: Budget ratio for MODERATE queries (default 0.5 = 50%)
            complex_budget_ratio: Budget ratio for COMPLEX queries (default 1.0 = 100%)
        """
        self.enabled = enabled
        self.simple_direct = simple_direct
        self.moderate_single_tool = moderate_single_tool
        self.simple_budget_ratio = simple_budget_ratio
        self.moderate_budget_ratio = moderate_budget_ratio
        self.complex_budget_ratio = complex_budget_ratio

        # Compile patterns
        self._simple_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SIMPLE_PATTERNS
        ]
        self._simple_short_pattern = re.compile(
            self.SIMPLE_SHORT_PATTERN, re.IGNORECASE
        )
        self._moderate_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.MODERATE_PATTERNS
        ]
        self._complex_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.COMPLEX_PATTERNS
        ]

        # Add custom patterns
        if custom_simple_patterns:
            self._simple_patterns.extend(
                re.compile(p, re.IGNORECASE) for p in custom_simple_patterns
            )
        if custom_moderate_patterns:
            self._moderate_patterns.extend(
                re.compile(p, re.IGNORECASE) for p in custom_moderate_patterns
            )
        if custom_complex_patterns:
            self._complex_patterns.extend(
                re.compile(p, re.IGNORECASE) for p in custom_complex_patterns
            )

    def classify(self, query: str) -> RoutingResult:
        """
        Classify query complexity.

        Args:
            query: User's input query

        Returns:
            RoutingResult with complexity and suggested strategy
        """
        if not self.enabled:
            return RoutingResult(
                complexity=QueryComplexity.COMPLEX,
                reason="Routing disabled",
                suggested_max_tools=-1,
                suggested_budget_ratio=self.complex_budget_ratio,
            )

        query_stripped = query.strip()

        # Check simple patterns first
        if self.simple_direct:
            for pattern in self._simple_patterns:
                if pattern.search(query_stripped):
                    return RoutingResult(
                        complexity=QueryComplexity.SIMPLE,
                        reason=f"Matched simple pattern: {pattern.pattern}",
                        suggested_max_tools=0,
                        suggested_budget_ratio=self.simple_budget_ratio,
                    )

            # Check very short English-only inputs
            if self._simple_short_pattern.match(query_stripped):
                return RoutingResult(
                    complexity=QueryComplexity.SIMPLE,
                    reason=f"Matched short pattern: {self._simple_short_pattern.pattern}",
                    suggested_max_tools=0,
                    suggested_budget_ratio=self.simple_budget_ratio,
                )

        # Check complex patterns (prioritize over moderate)
        for pattern in self._complex_patterns:
            if pattern.search(query_stripped):
                return RoutingResult(
                    complexity=QueryComplexity.COMPLEX,
                    reason=f"Matched complex pattern: {pattern.pattern}",
                    suggested_max_tools=-1,
                    suggested_budget_ratio=self.complex_budget_ratio,
                )

        # Check moderate patterns
        if self.moderate_single_tool:
            for pattern in self._moderate_patterns:
                if pattern.search(query_stripped):
                    return RoutingResult(
                        complexity=QueryComplexity.MODERATE,
                        reason=f"Matched moderate pattern: {pattern.pattern}",
                        suggested_max_tools=1,
                        suggested_budget_ratio=self.moderate_budget_ratio,
                    )

        # Default to complex for unknown queries
        return RoutingResult(
            complexity=QueryComplexity.COMPLEX,
            reason="No specific pattern matched, defaulting to complex",
            suggested_max_tools=-1,
            suggested_budget_ratio=self.complex_budget_ratio,
        )

    def is_simple(self, query: str) -> bool:
        """
        Quick check if query is simple.

        Args:
            query: User's input query

        Returns:
            True if query is classified as simple
        """
        result = self.classify(query)
        return result.complexity == QueryComplexity.SIMPLE

    def get_max_tools(self, query: str) -> int:
        """
        Get suggested max tool calls for a query.

        Args:
            query: User's input query

        Returns:
            Max tool calls (-1 for unlimited)
        """
        result = self.classify(query)
        return result.suggested_max_tools

    @staticmethod
    def is_simple_greeting(query: str) -> bool:
        """Quick static check if query is a simple greeting.

        Args:
            query: User's input query

        Returns:
            True if query is a simple greeting/thanks/identity question
        """
        query_lower = query.lower().strip()

        # Keyword-based check (broader than regex patterns)
        if any(
            kw in query_lower
            for kw in [
                "你好",
                "hello",
                "hi",
                "嗨",
                "早上好",
                "下午好",
                "晚上好",
                "谢谢",
                "thanks",
                "thank you",
                "感谢",
                "你是谁",
                "who are you",
                "你的名字",
                "你能做什么",
                "what can you do",
                "好的",
                "ok",
                "okay",
                "明白",
                "了解",
                "清楚了",
            ]
        ):
            return True

        # Very short English-only inputs
        if re.match(r"^[a-zA-Z\s]{1,5}$", query_lower):
            return True

        return False

    @staticmethod
    def answer_simple(llm, user_input: str) -> str:
        """Generate a direct answer for simple queries without tool calls.

        Args:
            llm: LLM client instance
            user_input: User's input text

        Returns:
            Direct response string
        """
        input_lower = user_input.lower().strip()

        # Greetings
        if any(g in input_lower for g in ["你好", "hello", "hi", "嗨"]):
            return "你好！我是助手，有什么可以帮助你的？"
        # Thanks
        if any(t in input_lower for t in ["谢谢", "thanks", "thank you", "感谢"]):
            return "不客气！"
        # Identity
        if any(i in input_lower for i in ["你是谁", "who are you", "你的名字"]):
            return "我是一个 AI 助手，可以帮助你处理各种任务。"
        # Capabilities
        if any(c in input_lower for c in ["你能做什么", "what can you do"]):
            return "我可以帮你：查看文件、执行命令、搜索内容、管理记忆等。"
        # Confirmations
        if any(c in input_lower for c in ["好的", "ok", "okay", "明白"]):
            return "好的，请告诉我你需要什么帮助。"

        # Fallback: lightweight LLM call
        try:
            messages = [
                {
                    "role": "system",
                    "content": "Answer briefly and directly in the user's language.",
                },
                {"role": "user", "content": user_input},
            ]
            response, _, _ = llm.chat(messages=messages, tools=None, system_stable=None)
            return response
        except Exception:
            return "请继续说明你的需求。"
