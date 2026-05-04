"""
Logging utilities for NanoAgent debugging and monitoring.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# Log levels
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR


class AgentLogger:
    """
    Configurable logger for NanoAgent.

    Supports multiple output targets:
    - Console (stdout/stderr)
    - File
    - Both
    """

    def __init__(
        self,
        name: str = "nano_agent",
        level: int = INFO,
        console: bool = True,
        file_path: str | None = None,
        format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ):
        """
        Initialize the logger.

        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            console: Whether to output to console
            file_path: Optional file path for logging
            format: Log message format
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers = []  # Clear existing handlers

        self.format = format
        self.formatter = logging.Formatter(format)

        # Add console handler
        if console:
            self._add_console_handler()

        # Add file handler
        if file_path:
            self._add_file_handler(file_path)

    def _add_console_handler(self) -> None:
        """Add console output handler."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(self.formatter)
        self.logger.addHandler(handler)

    def _add_file_handler(self, file_path: str) -> None:
        """Add file output handler."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        handler = logging.FileHandler(file_path, encoding="utf-8")
        handler.setFormatter(self.formatter)
        self.logger.addHandler(handler)

    def set_level(self, level: int) -> None:
        """
        Set log level.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
        """
        self.logger.setLevel(level)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)

    def log_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float
    ) -> None:
        """Log LLM call details."""
        self.debug(
            f"LLM Call: model={model}, "
            f"tokens={prompt_tokens}+{completion_tokens}, "
            f"latency={latency_ms:.2f}ms"
        )

    def log_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        success: bool,
        latency_ms: float
    ) -> None:
        """Log tool execution details."""
        status = "success" if success else "failed"
        self.debug(
            f"Tool Call: {tool_name}({arguments}) -> {status}, "
            f"latency={latency_ms:.2f}ms"
        )

    def log_iteration(
        self,
        iteration: int,
        max_iterations: int,
        has_tool_calls: bool
    ) -> None:
        """Log iteration progress."""
        self.debug(
            f"Iteration {iteration}/{max_iterations}, "
            f"tool_calls={has_tool_calls}"
        )

    def log_session(
        self,
        session_id: str,
        action: str
    ) -> None:
        """Log session action."""
        self.info(f"Session: {action} (id={session_id})")


# Global logger instance
_global_logger: AgentLogger | None = None


def get_logger(
    level: int = INFO,
    console: bool = True,
    file_path: str | None = None
) -> AgentLogger:
    """
    Get or create the global logger.

    Args:
        level: Log level
        console: Whether to output to console
        file_path: Optional file path

    Returns:
        AgentLogger instance
    """
    global _global_logger

    if _global_logger is None:
        _global_logger = AgentLogger(
            level=level,
            console=console,
            file_path=file_path
        )

    return _global_logger


def configure_logging(
    level: str = "INFO",
    console: bool = True,
    file_path: str | None = None
) -> AgentLogger:
    """
    Configure logging from string level.

    Args:
        level: Log level string ("DEBUG", "INFO", "WARNING", "ERROR")
        console: Whether to output to console
        file_path: Optional file path

    Returns:
        AgentLogger instance
    """
    level_map = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
    }

    int_level = level_map.get(level.upper(), INFO)
    return get_logger(level=int_level, console=console, file_path=file_path)