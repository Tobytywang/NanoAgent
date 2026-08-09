"""
Tests for output system: TUI vs debug separation, three-level verbosity.

BUG-012 regression: [Estimation] warnings leaked in quiet mode because
WARNING category was QUIET-visible and debug telemetry was misclassified.
"""

import pytest

pytestmark = pytest.mark.unit

from nano_agent.output import OutputCategory, Verbosity, parse_verbosity
from nano_agent.output.manager import OutputManager


def _fresh_manager(verbosity: Verbosity = Verbosity.QUIET) -> OutputManager:
    return OutputManager(verbosity=verbosity)


class TestVerbosityLevels:
    """三级冗度过滤语义"""

    def test_quiet_only_tui_and_error(self):
        """quiet: 仅 TUI + ERROR 可见，其余全部隐藏"""
        m = _fresh_manager(Verbosity.QUIET)
        assert m._should_show(OutputCategory.TUI)
        assert m._should_show(OutputCategory.ERROR)
        assert not m._should_show(OutputCategory.WARNING)
        assert not m._should_show(OutputCategory.LIFECYCLE)
        assert not m._should_show(OutputCategory.TOOL)
        assert not m._should_show(OutputCategory.LLM)
        assert not m._should_show(OutputCategory.BUDGET)
        assert not m._should_show(OutputCategory.CONTEXT)
        assert not m._should_show(OutputCategory.PERF)

    def test_minimal_adds_warning_and_lifecycle(self):
        """minimal: + WARNING + LIFECYCLE，调试细节仍隐藏"""
        m = _fresh_manager(Verbosity.MINIMAL)
        assert m._should_show(OutputCategory.TUI)
        assert m._should_show(OutputCategory.ERROR)
        assert m._should_show(OutputCategory.WARNING)
        assert m._should_show(OutputCategory.LIFECYCLE)
        assert not m._should_show(OutputCategory.TOOL)
        assert not m._should_show(OutputCategory.LLM)
        assert not m._should_show(OutputCategory.BUDGET)

    def test_verbose_shows_all(self):
        """verbose: 全部类别可见"""
        m = _fresh_manager(Verbosity.VERBOSE)
        for category in OutputCategory:
            assert m._should_show(category), f"{category} 应在 verbose 可见"

    def test_module_overrides(self):
        """模块级覆写：仅覆盖指定模块，其余按全局"""
        m = _fresh_manager(Verbosity.QUIET)
        m.set_verbosity(Verbosity.VERBOSE, module="react")
        assert m._should_show(OutputCategory.TOOL, module="react")
        assert m._should_show(OutputCategory.LLM, module="react")
        assert not m._should_show(OutputCategory.TOOL, module="context")
        assert not m._should_show(OutputCategory.WARNING, module="context")
        m.reset_module("react")
        assert not m._should_show(OutputCategory.TOOL, module="react")

    def test_module_override_never_hides_error(self):
        """模块覆写不能隐藏 ERROR（用户必须知道出错）"""
        m = _fresh_manager(Verbosity.QUIET)
        m.set_verbosity(Verbosity.QUIET, module="react")
        assert m._should_show(OutputCategory.ERROR, module="react")


class TestParseVerbosity:
    """冗度字符串解析兼容"""

    def test_english_names(self):
        assert parse_verbosity("quiet") == Verbosity.QUIET
        assert parse_verbosity("minimal") == Verbosity.MINIMAL
        assert parse_verbosity("verbose") == Verbosity.VERBOSE

    def test_chinese_and_numeric(self):
        assert parse_verbosity("无") == Verbosity.QUIET
        assert parse_verbosity("少") == Verbosity.MINIMAL
        assert parse_verbosity("多") == Verbosity.VERBOSE
        assert parse_verbosity("0") == Verbosity.QUIET
        assert parse_verbosity("1") == Verbosity.MINIMAL
        assert parse_verbosity("2") == Verbosity.VERBOSE

    def test_case_insensitive(self):
        assert parse_verbosity("QUIET") == Verbosity.QUIET
        assert parse_verbosity("Minimal") == Verbosity.MINIMAL

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_verbosity("invalid")


class TestTUIAlwaysVisible:
    """TUI 层始终可见，不受冗度影响"""

    def test_tui_methods_work_at_all_levels(self, capsys):
        from nano_agent.output import get_output

        get_output().set_verbosity(Verbosity.QUIET)
        get_output().tui.info("TUI 消息")
        captured = capsys.readouterr()
        assert "TUI 消息" in captured.out

        get_output().set_verbosity(Verbosity.VERBOSE)
        get_output().tui.info("TUI 消息")
        captured = capsys.readouterr()
        assert "TUI 消息" in captured.out
