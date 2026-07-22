"""
CLI 控制台输出工具
"""

import sys
from typing import Literal
from ..utils.strings import safe_str


class Console:
    """控制台输出格式化"""

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

    @classmethod
    def _supports_color(cls) -> bool:
        """检查终端是否支持颜色"""
        # Windows 某些终端可能不支持 ANSI 颜色
        if sys.platform == "win32":
            # 检查 Windows Terminal 或其他现代终端
            return "WT_SESSION" in sys.environ or "TERM" in sys.environ
        return True

    @classmethod
    def _colorize(cls, text: str, color: str) -> str:
        """为文本添加颜色"""
        if not cls._supports_color():
            return text
        return f"{cls.COLORS.get(color, '')}{text}{cls.COLORS['reset']}"

    @classmethod
    def print(
        cls,
        message: str,
        style: Literal["info", "success", "warning", "error", "user", "agent"] = "info",
        end: str = "\n",
    ) -> None:
        """
        打印带样式的消息。

        Args:
            message: 要打印的消息
            style: 样式类型
            end: 行结束符
        """
        # 清理消息中的无效 Unicode 字符
        message = safe_str(message)
        style_map = {
            "info": ("cyan", ""),
            "success": ("green", ""),
            "warning": ("yellow", ""),
            "error": ("red", ""),
            "user": ("blue", "[User] "),
            "agent": ("green", "[Agent] "),
            "header": ("bold", ""),  # 加粗以提高浅色背景下的可见性
        }

        color, prefix = style_map.get(style, ("", ""))
        formatted = cls._colorize(f"{prefix}{message}", color)
        print(formatted, end=end)

    @classmethod
    def print_separator(cls, char: str = "-", length: int = 50) -> None:
        """打印分隔线"""
        print(char * length)

    @classmethod
    def print_header(cls, title: str) -> None:
        """打印标题"""
        cls.print_separator("=")
        cls.print(title, style="header")
        cls.print_separator("=")

    @classmethod
    def print_tool_call(cls, tool_name: str, arguments: dict, result: str) -> None:
        """打印工具调用及其结果"""
        args_str = safe_str(str(arguments))
        result_str = safe_str(result)
        cls.print(f"[Tool] {tool_name}({args_str})", style="info")
        preview = result_str[:100] + "..." if len(result_str) > 100 else result_str
        cls.print(f"  -> {preview}", style="success")

    @classmethod
    def print_title(cls, title: str) -> None:
        """标准标题块"""
        print()
        print("=" * 50)
        print(title)
        print("=" * 50)

    @classmethod
    def print_subtitle(cls, title: str) -> None:
        """标准小标题"""
        print(f"\n## {title}")

    @classmethod
    def print_end(cls) -> None:
        """标准结尾分隔线"""
        print("\n" + "=" * 50 + "\n")

    @classmethod
    def print_kv(
        cls, key: str, value: str, key_width: int = 12, indent: int = 0
    ) -> None:
        """对齐 key-value 行

        Args:
            key: 键名（可含冒号，如 "工具定义:"）
            value: 值字符串
            key_width: 键区域总显示宽度（含缩进）
            indent: 额外缩进空格数
        """
        prefix = " " * indent
        current_width = 0
        for char in key:
            if "一" <= char <= "鿿":
                current_width += 2
            else:
                current_width += 1
        padding = max(0, key_width - current_width - indent)
        print(f"{prefix}{key}{' ' * padding} {value}")

    @classmethod
    def print_progress_bar(cls, pct: float, width: int = 40) -> None:
        """标准进度条，用 █ 填充 + · 表示剩余"""
        filled = int(pct / 100 * width)
        bar = "█" * filled + "·" * (width - filled)
        print(f"  [{bar}] {pct:.1f}%")
