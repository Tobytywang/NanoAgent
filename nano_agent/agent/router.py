"""
查询复杂度路由模块

根据查询复杂度选择不同的处理路径:
1. 简单查询: 直接回答，无需工具
2. 中等查询: 使用少量工具迭代
3. 复杂查询: 完整的 ReAct 循环
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class QueryComplexity(Enum):
    """查询复杂度级别"""
    SIMPLE = "simple"       # 直接回答，无需工具
    MODERATE = "moderate"   # 使用少量工具
    COMPLEX = "complex"     # 完整 ReAct 循环


@dataclass
class QueryAnalysis:
    """查询分析结果"""
    complexity: QueryComplexity
    confidence: float  # 分析置信度
    reasoning: str     # 分析理由
    suggested_tools: list[str]  # 建议使用的工具
    can_answer_directly: bool   # 是否可以直接回答


@dataclass
class RouterConfig:
    """路由配置"""
    # 简单查询特征
    simple_patterns: tuple[str, ...] = (
        # 问候
        "你好", "hello", "hi", "嗨", "早上好", "下午好", "晚上好",
        # 感谢
        "谢谢", "thanks", "thank you", "感谢",
        # 身份询问
        "你是谁", "who are you", "你的名字", "what is your name",
        # 能力询问
        "你能做什么", "what can you do", "你有什么功能",
        # 确认
        "好的", "ok", "okay", "明白", "了解", "清楚了",
    )

    # 中等复杂度特征（需要工具但简单）
    moderate_patterns: tuple[str, ...] = (
        "查看", "显示", "读取", "read", "show", "list",
        "搜索", "查找", "find", "search",
        "检查", "check", "verify",
    )

    # 复杂查询特征
    complex_patterns: tuple[str, ...] = (
        "修改", "更新", "删除", "modify", "update", "delete",
        "实现", "创建", "implement", "create",
        "重构", "优化", "refactor", "optimize",
        "分析", "设计", "analyze", "design",
        "调试", "修复", "debug", "fix",
    )

    # 长度阈值
    short_query_max_length: int = 20
    long_query_min_length: int = 100

    # 工具建议
    file_tools: tuple[str, ...] = ("file_read", "file_write", "file_search")
    search_tools: tuple[str, ...] = ("file_search", "web_search")
    execute_tools: tuple[str, ...] = ("shell_execute", "python_execute")


class QueryRouter:
    """
    查询复杂度路由器

    分析用户查询，决定处理路径。

    Usage:
        router = QueryRouter()
        analysis = router.analyze("帮我查看 config.yaml 文件")

        if analysis.complexity == QueryComplexity.SIMPLE:
            return direct_answer(query)
        elif analysis.complexity == QueryComplexity.MODERATE:
            return quick_tool_call(analysis.suggested_tools)
        else:
            return full_react_loop()
    """

    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()

    def analyze(self, query: str) -> QueryAnalysis:
        """
        分析查询复杂度

        Args:
            query: 用户查询

        Returns:
            QueryAnalysis 包含复杂度和建议
        """
        import re
        query_lower = query.lower().strip()

        # 1. 检查简单模式（使用单词边界匹配）
        for pattern in self.config.simple_patterns:
            # 使用单词边界匹配，避免 "something" 匹配 "hi"
            if re.search(r'\b' + re.escape(pattern) + r'\b', query_lower):
                return QueryAnalysis(
                    complexity=QueryComplexity.SIMPLE,
                    confidence=0.9,
                    reasoning=f"匹配简单模式: {pattern}",
                    suggested_tools=[],
                    can_answer_directly=True,
                )

        # 2. 检查长度
        if len(query) < self.config.short_query_max_length:
            # 短查询可能是简单的，但需要更严格的检查
            # 只有明确的问候/感谢/确认才认为是简单查询
            simple_indicators = ["你好", "hello", "hi", "嗨", "谢谢", "thanks", "好的", "ok", "明白"]
            # 使用单词边界匹配
            for indicator in simple_indicators:
                if re.search(r'\b' + re.escape(indicator) + r'\b', query_lower):
                    return QueryAnalysis(
                        complexity=QueryComplexity.SIMPLE,
                        confidence=0.7,
                        reasoning=f"短查询，匹配简单指示词: {indicator}",
                        suggested_tools=[],
                        can_answer_directly=True,
                    )
            # 其他短查询默认为中等复杂度，让 LLM 决定
            return QueryAnalysis(
                complexity=QueryComplexity.MODERATE,
                confidence=0.5,
                reasoning="短查询，需要 LLM 判断",
                suggested_tools=[],
                can_answer_directly=False,
            )

        # 3. 检查复杂模式
        for pattern in self.config.complex_patterns:
            if pattern in query_lower:
                return QueryAnalysis(
                    complexity=QueryComplexity.COMPLEX,
                    confidence=0.8,
                    reasoning=f"匹配复杂模式: {pattern}",
                    suggested_tools=self._suggest_tools(query),
                    can_answer_directly=False,
                )

        # 4. 检查中等模式
        for pattern in self.config.moderate_patterns:
            if pattern in query_lower:
                return QueryAnalysis(
                    complexity=QueryComplexity.MODERATE,
                    confidence=0.7,
                    reasoning=f"匹配中等模式: {pattern}",
                    suggested_tools=self._suggest_tools(query),
                    can_answer_directly=False,
                )

        # 5. 长查询默认复杂
        if len(query) > self.config.long_query_min_length:
            return QueryAnalysis(
                complexity=QueryComplexity.COMPLEX,
                confidence=0.6,
                reasoning="长查询，可能需要多步处理",
                suggested_tools=self._suggest_tools(query),
                can_answer_directly=False,
            )

        # 6. 默认中等复杂度
        return QueryAnalysis(
            complexity=QueryComplexity.MODERATE,
            confidence=0.5,
            reasoning="无法确定复杂度，使用中等处理",
            suggested_tools=self._suggest_tools(query),
            can_answer_directly=False,
        )

    def _suggest_tools(self, query: str) -> list[str]:
        """
        根据查询内容建议工具

        Args:
            query: 用户查询

        Returns:
            建议的工具列表
        """
        suggested = []
        query_lower = query.lower()

        # 文件相关
        if any(w in query_lower for w in ["文件", "file", "读取", "read", "写入", "write"]):
            suggested.extend(self.config.file_tools)

        # 搜索相关
        if any(w in query_lower for w in ["搜索", "search", "查找", "find"]):
            suggested.extend(self.config.search_tools)

        # 执行相关
        if any(w in query_lower for w in ["执行", "execute", "运行", "run", "命令", "command"]):
            suggested.extend(self.config.execute_tools)

        return list(set(suggested))  # 去重

    def get_max_iterations(self, complexity: QueryComplexity) -> int:
        """
        根据复杂度获取最大迭代次数

        Args:
            complexity: 查询复杂度

        Returns:
            建议的最大迭代次数
        """
        iterations_map = {
            QueryComplexity.SIMPLE: 0,     # 不需要迭代
            QueryComplexity.MODERATE: 3,   # 少量迭代
            QueryComplexity.COMPLEX: 10,   # 完整迭代
        }
        return iterations_map[complexity]

    def should_skip_tools(self, complexity: QueryComplexity) -> bool:
        """
        是否应该跳过工具调用

        Args:
            complexity: 查询复杂度

        Returns:
            True 如果应该跳过工具
        """
        return complexity == QueryComplexity.SIMPLE


class RoutingDecision:
    """
    路由决策

    封装路由决策结果，供执行层使用。
    """

    def __init__(
        self,
        analysis: QueryAnalysis,
        max_iterations: int,
        skip_tools: bool,
        use_streaming: bool = False,
    ):
        self.analysis = analysis
        self.max_iterations = max_iterations
        self.skip_tools = skip_tools
        self.use_streaming = use_streaming

    @classmethod
    def from_analysis(cls, analysis: QueryAnalysis) -> "RoutingDecision":
        """
        从分析结果创建决策

        Args:
            analysis: 查询分析结果

        Returns:
            RoutingDecision 实例
        """
        router = QueryRouter()
        return cls(
            analysis=analysis,
            max_iterations=router.get_max_iterations(analysis.complexity),
            skip_tools=router.should_skip_tools(analysis.complexity),
        )

    def __repr__(self) -> str:
        return (
            f"RoutingDecision(complexity={self.analysis.complexity.value}, "
            f"max_iter={self.max_iterations}, skip_tools={self.skip_tools})"
        )
