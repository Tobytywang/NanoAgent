"""
TUI 输出层 — 始终可见的用户界面渲染。

该层输出的内容是"应用程序界面"的一部分（标题、状态、进度、
Agent 回复、确认对话框等），不归冗度管理，任何级别下都输出。
"""

import sys
from typing import Literal

from ..utils.strings import safe_str


class TUIOutput:
    """始终可见的 TUI 输出。"""

    # ANSI 颜色代码
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "magenta": "\033[95m",
    }

    def __init__(self, color: bool = True):
        self._color = color

    @property
    def color(self) -> bool:
        return self._color

    def set_color(self, enabled: bool) -> None:
        self._color = enabled

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _supports_color(self) -> bool:
        if not self._color:
            return False
        if sys.platform == "win32":
            return "WT_SESSION" in sys.environ or "TERM" in sys.environ
        return True

    def _colorize(self, text: str, color: str) -> str:
        if not self._supports_color():
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def _print(self, message: str = "", end: str = "\n") -> None:
        print(safe_str(message), end=end)

    # ------------------------------------------------------------------
    # 状态消息
    # ------------------------------------------------------------------

    def info(self, message: str) -> None:
        """信息消息（青色）"""
        self._print(self._colorize(message, "cyan"))

    def success(self, message: str) -> None:
        """成功消息（绿色）"""
        self._print(self._colorize(message, "green"))

    def warning(self, message: str) -> None:
        """警告消息（黄色）"""
        self._print(self._colorize(message, "yellow"))

    def error(self, message: str) -> None:
        """错误消息（红色）"""
        self._print(self._colorize(message, "red"))

    def header(self, message: str) -> None:
        """加粗标题文本"""
        self._print(self._colorize(message, "bold"))

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------

    def separator(self, char: str = "-", length: int = 50) -> None:
        """打印分隔线"""
        self._print(char * length)

    def title(self, title: str) -> None:
        """标准标题块：空行 + ==== + 标题 + ==== + 空行"""
        self._print("")
        self._print("=" * 50)
        self._print(title)
        self._print("=" * 50)

    def subtitle(self, title: str) -> None:
        """标准小标题"""
        self._print(f"\n## {title}")

    def end(self) -> None:
        """标准结尾分隔线"""
        self._print("\n" + "=" * 50 + "\n")

    def kv(self, key: str, value: str, key_width: int = 12, indent: int = 0) -> None:
        """对齐 key-value 行（CJK 感知宽度）"""
        prefix = " " * indent
        current_width = 0
        for char in key:
            if "一" <= char <= "鿿":
                current_width += 2
            else:
                current_width += 1
        padding = max(0, key_width - current_width - indent)
        self._print(f"{prefix}{key}{' ' * padding} {value}")

    def progress_bar(self, pct: float, width: int = 40) -> None:
        """标准进度条：█ 填充 + · 剩余"""
        filled = int(pct / 100 * width)
        bar = "█" * filled + "·" * (width - filled)
        self._print(f"  [{bar}] {pct:.1f}%")

    # ------------------------------------------------------------------
    # 交互（对话循环）
    # ------------------------------------------------------------------

    def user_prompt(self, user_display: str, cwd: str) -> None:
        """用户输入提示行"""
        self._print(f"\n[{user_display}] [{cwd}]:")

    def agent_header(self, agent_display: str) -> None:
        """Agent 回复前的头部"""
        self._print(f"\n[{agent_display}]:")

    def streaming_text(self, chunk: str, end: str = "") -> None:
        """流式输出文本片段（无换行，连续输出）"""
        self._print(chunk, end=end)

    def agent_response(self, response: str) -> None:
        """非交互模式下输出最终回复"""
        self._print(f"> {response}")

    def tool_confirmation(
        self, tool_name: str, risk_level: str, arguments: str, icon: str = "⚠"
    ) -> None:
        """工具执行确认对话框"""
        self._print(f"\n{icon} 确认执行工具: {tool_name}")
        self._print(f"   风险级别: {risk_level}")
        self._print(f"   参数: {arguments}")

    # ------------------------------------------------------------------
    # 工具执行展示
    # ------------------------------------------------------------------

    def tool_executing(self, tool_name: str, args_str: str) -> None:
        """工具开始执行"""
        self._print(self._colorize(f"  [Tool] {tool_name}({args_str})", "cyan"))

    def tool_result(self, status: str, preview: str) -> None:
        """工具执行结果"""
        self._print(
            self._colorize(f"  [Result: {status}] {preview}", "green"), end="\n"
        )
