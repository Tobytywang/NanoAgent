"""
Token 预算管理模块

实现 Token 预算管理，支持:
1. 预算分配与追踪
2. 预算耗尽强制总结
3. 分阶段预算控制
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class BudgetAction(Enum):
    """预算耗尽时的行为"""
    FORCE_SUMMARY = "force_summary"  # 强制总结并返回
    TRUNCATE_CONTEXT = "truncate_context"  # 截断上下文
    WARN_CONTINUE = "warn_continue"  # 警告但继续


@dataclass
class TokenBudgetConfig:
    """Token 预算配置"""
    total_budget: int = 8000  # 总 token 预算
    system_prompt_ratio: float = 0.15  # 系统 prompt 占比
    context_ratio: float = 0.45  # 上下文占比
    response_ratio: float = 0.25  # 响应占比
    buffer_ratio: float = 0.15  # 缓冲占比

    # 预算耗尽行为
    exhausted_action: BudgetAction = BudgetAction.FORCE_SUMMARY

    # 强制总结阈值
    summary_threshold: float = 0.9  # 当使用达到 90% 时触发

    # 分阶段预算
    phase_budgets: dict[str, int] = field(default_factory=lambda: {
        "think": 500,  # 思考阶段
        "act": 1000,   # 执行阶段
        "observe": 500,  # 观察阶段
    })


class TokenBudget:
    """
    Token 预算管理器

    管理整个执行过程中的 token 分配和使用。

    Usage:
        budget = TokenBudget(config)

        # 检查预算
        if budget.can_proceed(estimated_tokens):
            result = llm.call(...)
            budget.consume(result.usage.total_tokens)

        # 检查是否需要强制总结
        if budget.should_force_summary():
            return budget.generate_summary()
    """

    def __init__(self, config: TokenBudgetConfig | None = None):
        self.config = config or TokenBudgetConfig()
        self._consumed = 0
        self._phase_consumed: dict[str, int] = {}
        self._current_phase: str | None = None

    @property
    def remaining(self) -> int:
        """剩余预算"""
        return max(0, self.config.total_budget - self._consumed)

    @property
    def usage_ratio(self) -> float:
        """使用比例"""
        return self._consumed / self.config.total_budget

    @property
    def is_exhausted(self) -> bool:
        """是否预算耗尽"""
        return self.usage_ratio >= 1.0

    @property
    def is_near_limit(self) -> bool:
        """是否接近限制"""
        return self.usage_ratio >= self.config.summary_threshold

    def can_proceed(self, estimated_tokens: int) -> bool:
        """
        检查是否可以继续执行

        Args:
            estimated_tokens: 预估需要的 token 数

        Returns:
            True 如果有足够预算
        """
        return self.remaining >= estimated_tokens

    def consume(self, tokens: int, phase: str | None = None) -> None:
        """
        消耗 token

        Args:
            tokens: 消耗的 token 数
            phase: 当前阶段（可选）
        """
        self._consumed += tokens

        if phase:
            self._phase_consumed[phase] = self._phase_consumed.get(phase, 0) + tokens

    def start_phase(self, phase: str) -> None:
        """
        开始新阶段

        Args:
            phase: 阶段名称
        """
        self._current_phase = phase

    def get_phase_budget(self, phase: str) -> int:
        """
        获取阶段预算

        Args:
            phase: 阶段名称

        Returns:
            该阶段的预算
        """
        return self.config.phase_budgets.get(phase, 0)

    def get_phase_usage(self, phase: str) -> int:
        """
        获取阶段使用量

        Args:
            phase: 阶段名称

        Returns:
            该阶段已使用的 token
        """
        return self._phase_consumed.get(phase, 0)

    def should_force_summary(self) -> bool:
        """
        是否应该强制总结

        Returns:
            True 如果应该强制总结
        """
        return (
            self.is_near_limit and
            self.config.exhausted_action == BudgetAction.FORCE_SUMMARY
        )

    def get_allocation(self) -> dict[str, int]:
        """
        获取预算分配

        Returns:
            各部分的预算分配
        """
        total = self.config.total_budget
        return {
            "system_prompt": int(total * self.config.system_prompt_ratio),
            "context": int(total * self.config.context_ratio),
            "response": int(total * self.config.response_ratio),
            "buffer": int(total * self.config.buffer_ratio),
        }

    def get_status(self) -> dict[str, Any]:
        """
        获取预算状态

        Returns:
            预算状态信息
        """
        return {
            "total_budget": self.config.total_budget,
            "consumed": self._consumed,
            "remaining": self.remaining,
            "usage_ratio": f"{self.usage_ratio:.1%}",
            "is_exhausted": self.is_exhausted,
            "is_near_limit": self.is_near_limit,
            "allocation": self.get_allocation(),
            "phase_usage": dict(self._phase_consumed),
        }

    def reset(self) -> None:
        """重置预算状态"""
        self._consumed = 0
        self._phase_consumed = {}
        self._current_phase = None


class BudgetAwareExecutor:
    """
    预算感知执行器

    在执行过程中自动管理预算，支持预算耗尽时的处理。
    """

    def __init__(
        self,
        budget: TokenBudget,
        on_exhausted: Optional[Callable] = None,
    ):
        """
        初始化执行器

        Args:
            budget: Token 预算管理器
            on_exhausted: 预算耗尽时的回调函数
        """
        self.budget = budget
        self.on_exhausted = on_exhausted

    def execute_with_budget(
        self,
        func: Callable,
        estimated_tokens: int,
        *args,
        **kwargs
    ) -> tuple[Any, bool]:
        """
        在预算限制下执行函数

        Args:
            func: 要执行的函数
            estimated_tokens: 预估 token 消耗
            *args, **kwargs: 函数参数

        Returns:
            (结果, 是否成功) 元组
        """
        # 检查预算
        if not self.budget.can_proceed(estimated_tokens):
            if self.on_exhausted:
                return self.on_exhausted(), False
            return None, False

        # 执行
        result = func(*args, **kwargs)

        # 更新预算（如果结果包含 usage 信息）
        if hasattr(result, 'usage') and hasattr(result.usage, 'total_tokens'):
            self.budget.consume(result.usage.total_tokens)

        return result, True
