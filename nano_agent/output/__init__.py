"""
输出系统 — TUI 与调试打印分离。

- TUI 层：output.tui.* 始终可见
- 调试层：output.lifecycle/tool/llm/... 按冗度过滤
"""

from .categories import OutputCategory, Verbosity, parse_verbosity
from .manager import OutputManager
from .tui import TUIOutput

__all__ = [
    "OutputCategory",
    "OutputManager",
    "TUIOutput",
    "Verbosity",
    "parse_verbosity",
    "get_output",
    "configure_output",
]

_output: OutputManager | None = None


def get_output() -> OutputManager:
    """获取全局 OutputManager 单例（懒初始化）。"""
    global _output
    if _output is None:
        _output = OutputManager()
    return _output


def configure_output(
    verbosity: Verbosity | str = Verbosity.QUIET,
    module_overrides: dict[str, str] | None = None,
    color: bool = True,
) -> OutputManager:
    """创建并配置全局 OutputManager。"""
    global _output
    if isinstance(verbosity, str):
        verbosity = parse_verbosity(verbosity)
    manager = OutputManager(verbosity=verbosity, color=color)
    if isinstance(module_overrides, dict):
        for module, v in module_overrides.items():
            manager.set_verbosity(parse_verbosity(v), module=module)
    _output = manager
    return _output
