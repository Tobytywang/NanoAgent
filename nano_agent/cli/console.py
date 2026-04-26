"""
Console output utilities for CLI.
"""

import sys
from typing import Literal


class Console:
    """Console output formatting."""

    # ANSI color codes
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
    }

    @classmethod
    def _supports_color(cls) -> bool:
        """Check if terminal supports colors."""
        # Windows may not support ANSI colors in some terminals
        if sys.platform == "win32":
            # Check for Windows Terminal or other modern terminals
            return "WT_SESSION" in sys.environ or "TERM" in sys.environ
        return True

    @classmethod
    def _colorize(cls, text: str, color: str) -> str:
        """Add color to text."""
        if not cls._supports_color():
            return text
        return f"{cls.COLORS.get(color, '')}{text}{cls.COLORS['reset']}"

    @classmethod
    def print(
        cls,
        message: str,
        style: Literal["info", "success", "warning", "error", "user", "agent"] = "info",
        end: str = "\n"
    ) -> None:
        """
        Print a styled message.

        Args:
            message: The message to print
            style: Style type
            end: Line ending
        """
        style_map = {
            "info": ("cyan", ""),
            "success": ("green", ""),
            "warning": ("yellow", ""),
            "error": ("red", ""),
            "user": ("blue", "[User] "),
            "agent": ("green", "[Agent] "),
        }

        color, prefix = style_map.get(style, ("", ""))
        formatted = cls._colorize(f"{prefix}{message}", color)
        print(formatted, end=end)

    @classmethod
    def print_separator(cls, char: str = "-", length: int = 50) -> None:
        """Print a separator line."""
        print(char * length)

    @classmethod
    def print_header(cls, title: str) -> None:
        """Print a header."""
        cls.print_separator("=")
        cls.print(title, style="info")
        cls.print_separator("=")

    @classmethod
    def print_tool_call(cls, tool_name: str, arguments: dict, result: str) -> None:
        """Print a tool call and its result."""
        cls.print(f"[Tool] {tool_name}({arguments})", style="info")
        preview = result[:100] + "..." if len(result) > 100 else result
        cls.print(f"  -> {preview}", style="success")