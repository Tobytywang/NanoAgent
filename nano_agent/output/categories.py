"""
输出冗度与类别定义。

将输出分为两层：
- TUI 层：用户界面的组成部分，始终可见，不受冗度控制
- 调试层：开发者关心的运行时信息，按冗度级别过滤
"""

from enum import Enum, IntEnum


class Verbosity(IntEnum):
    """调试输出冗度级别"""

    QUIET = 0  # 仅 TUI
    MINIMAL = 1  # 关键调试信息（生命周期、警告、错误）
    VERBOSE = 2  # 全部调试信息


class OutputCategory(str, Enum):
    """输出类别，决定每条调试消息在哪个冗度级别可见"""

    TUI = "tui"  # 始终输出，不受冗度控制
    LIFECYCLE = "lifecycle"  # 迭代进度、会话开始/结束 → MINIMAL
    WARNING = "warning"  # 预算警告、重复调用、断路器 → 始终输出
    ERROR = "error"  # 错误信息 → 始终输出
    TOOL = "tool"  # 工具调用名称/参数/结果 → VERBOSE
    LLM = "llm"  # LLM 思考文本、缓存命中、路由决策 → VERBOSE
    BUDGET = "budget"  # Token 预算追踪、压缩信息 → VERBOSE
    CONTEXT = "context"  # 上下文管理 → VERBOSE
    PERF = "perf"  # 性能指标、重试延迟 → VERBOSE


# 各类别的最小可见冗度
# QUIET: 仅 TUI + ERROR（用户必须知道出错）
# MINIMAL: + WARNING（断路器/预算/重复调用等开发必要信息）+ LIFECYCLE
CATEGORY_MIN_VERBOSITY: dict[OutputCategory, Verbosity] = {
    OutputCategory.TUI: Verbosity.QUIET,
    OutputCategory.ERROR: Verbosity.QUIET,
    OutputCategory.WARNING: Verbosity.MINIMAL,
    OutputCategory.LIFECYCLE: Verbosity.MINIMAL,
    OutputCategory.TOOL: Verbosity.VERBOSE,
    OutputCategory.LLM: Verbosity.VERBOSE,
    OutputCategory.BUDGET: Verbosity.VERBOSE,
    OutputCategory.CONTEXT: Verbosity.VERBOSE,
    OutputCategory.PERF: Verbosity.VERBOSE,
}


def parse_verbosity(value: str) -> Verbosity:
    """解析冗度字符串，兼容英文/中文/数字形式。"""
    value = value.strip().lower()
    mapping = {
        "quiet": Verbosity.QUIET,
        "q": Verbosity.QUIET,
        "无": Verbosity.QUIET,
        "0": Verbosity.QUIET,
        "minimal": Verbosity.MINIMAL,
        "min": Verbosity.MINIMAL,
        "少": Verbosity.MINIMAL,
        "1": Verbosity.MINIMAL,
        "verbose": Verbosity.VERBOSE,
        "v": Verbosity.VERBOSE,
        "多": Verbosity.VERBOSE,
        "2": Verbosity.VERBOSE,
    }
    if value not in mapping:
        raise ValueError(f"无效的冗度级别: {value!r}，可选: quiet/minimal/verbose")
    return mapping[value]
