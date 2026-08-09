"""
OutputManager — 统一输出控制器。

职责：
- TUI 层：委托给 self.tui（始终可见）
- 调试层：按 OutputCategory + Verbosity 过滤，支持模块级覆写
"""

from .categories import (
    CATEGORY_MIN_VERBOSITY,
    OutputCategory,
    Verbosity,
    parse_verbosity,
)
from .tui import TUIOutput


class OutputManager:
    """统一输出控制器。"""

    def __init__(self, verbosity: Verbosity = Verbosity.QUIET, color: bool = True):
        self._verbosity = verbosity
        self._module_overrides: dict[str, Verbosity] = {}
        self.tui = TUIOutput(color=color)

    # ------------------------------------------------------------------
    # 冗度控制
    # ------------------------------------------------------------------

    @property
    def verbosity(self) -> Verbosity:
        return self._verbosity

    def set_verbosity(self, level: Verbosity, module: str | None = None) -> None:
        """设置冗度。module=None 时设置全局级别，否则设置模块覆写。"""
        if module is None:
            self._verbosity = level
        elif level is None:
            self._module_overrides.pop(module, None)
        else:
            self._module_overrides[module] = level

    def reset_module(self, module: str) -> None:
        """重置模块级覆写，回退到全局冗度。"""
        self._module_overrides.pop(module, None)

    @property
    def module_overrides(self) -> dict[str, Verbosity]:
        return dict(self._module_overrides)

    def _should_show(self, category: OutputCategory, module: str | None = None) -> bool:
        """判断给定类别 + 模块在当前冗度下是否应输出。"""
        min_level = CATEGORY_MIN_VERBOSITY.get(category, Verbosity.VERBOSE)
        if min_level == Verbosity.QUIET:
            return True
        if module is not None and module in self._module_overrides:
            return self._module_overrides[module] >= min_level
        return self._verbosity >= min_level

    # ------------------------------------------------------------------
    # 调试输出（按类别过滤，模块名为可选参数）
    # ------------------------------------------------------------------

    def lifecycle(self, message: str, module: str | None = None, **kwargs) -> None:
        """迭代进度、会话生命周期"""
        if self._should_show(OutputCategory.LIFECYCLE, module):
            print(message, **kwargs)

    def warning(self, message: str, module: str | None = None, **kwargs) -> None:
        """警告（始终输出，但可被模块覆写）"""
        if self._should_show(OutputCategory.WARNING, module):
            print(self.tui._colorize(message, "yellow"), **kwargs)

    def error(self, message: str, module: str | None = None, **kwargs) -> None:
        """错误（始终输出，但可被模块覆写）"""
        if self._should_show(OutputCategory.ERROR, module):
            print(self.tui._colorize(message, "red"), **kwargs)

    def tool(self, message: str, module: str | None = None, **kwargs) -> None:
        """工具调用详情"""
        if self._should_show(OutputCategory.TOOL, module):
            print(message, **kwargs)

    def llm(self, message: str, module: str | None = None, **kwargs) -> None:
        """LLM 思考、缓存、路由"""
        if self._should_show(OutputCategory.LLM, module):
            print(message, **kwargs)

    def budget(self, message: str, module: str | None = None, **kwargs) -> None:
        """Token 预算追踪"""
        if self._should_show(OutputCategory.BUDGET, module):
            print(message, **kwargs)

    def context(self, message: str, module: str | None = None, **kwargs) -> None:
        """上下文管理"""
        if self._should_show(OutputCategory.CONTEXT, module):
            print(message, **kwargs)

    def perf(self, message: str, module: str | None = None, **kwargs) -> None:
        """性能指标、重试延迟"""
        if self._should_show(OutputCategory.PERF, module):
            print(message, **kwargs)


def configure_from_dict(output_manager: OutputManager, config: dict) -> None:
    """从配置字典（OutputConfig dataclass 的 asdict 结果）配置 OutputManager。"""
    verbosity = config.get("verbosity", "quiet")
    try:
        level = parse_verbosity(str(verbosity))
    except ValueError:
        level = Verbosity.QUIET
    output_manager.set_verbosity(level)

    for module, v in (config.get("module_overrides") or {}).items():
        try:
            output_manager.set_verbosity(parse_verbosity(str(v)), module=module)
        except ValueError:
            continue

    color = config.get("color", True)
    if isinstance(color, bool):
        output_manager.tui.set_color(color)
