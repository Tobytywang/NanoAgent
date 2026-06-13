"""Standardized tool output format (v0.7.15)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputFormat(Enum):
    """Standardized output format types."""

    STRUCTURE = "structure"  # Key-value pairs (file_read structure info)
    LIST = "list"  # Item list (file_search, web_search)
    STATUS = "status"  # Status message (shell, python_execute)
    CONTENT = "content"  # Content with metadata (file_read body)
    ERROR = "error"  # Error message


@dataclass
class StandardToolOutput:
    """Structured tool output that can be rendered for LLM consumption."""

    format: OutputFormat
    data: dict[str, Any]
    summary: str = ""

    MAX_LIST_DISPLAY = 10

    def to_llm_message(self, detailed: bool = False) -> str:
        """Render as compact text for LLM consumption."""
        dispatch = {
            OutputFormat.STRUCTURE: self._format_structure,
            OutputFormat.LIST: self._format_list,
            OutputFormat.STATUS: self._format_status,
            OutputFormat.CONTENT: self._format_content,
            OutputFormat.ERROR: self._format_error,
        }
        formatter = dispatch.get(self.format, self._format_structure)
        return formatter(detailed)

    def _format_structure(self, detailed: bool = False) -> str:
        lines = []
        for key, value in self.data.items():
            if isinstance(value, list):
                items = ", ".join(str(v) for v in value)
                lines.append(f"{key}: [{items}]")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _format_list(self, detailed: bool = False) -> str:
        items = self.data.get("items", [])
        total = self.data.get("total", len(items))
        max_display = self.data.get("max_display", self.MAX_LIST_DISPLAY)

        if not items:
            return "No results found"

        lines = [f"Total: {total}"]

        if total <= max_display or detailed:
            for item in items[: max_display if not detailed else None]:
                if isinstance(item, dict):
                    parts = [str(v) for v in item.values() if v]
                    lines.append(" | ".join(parts))
                else:
                    lines.append(str(item))
        else:
            for item in items[:max_display]:
                if isinstance(item, dict):
                    parts = [str(v) for v in item.values() if v]
                    lines.append(" | ".join(parts))
                else:
                    lines.append(str(item))
            remaining = total - max_display
            if remaining > 0:
                lines.append(f"... +{remaining} more")

        return "\n".join(lines)

    def _format_status(self, detailed: bool = False) -> str:
        status = self.data.get("status", "unknown")
        exit_code = self.data.get("exit_code")

        if status == "success" or exit_code == 0:
            prefix = "[ok]"
        elif status == "error":
            prefix = f"[error:{exit_code}]"
        else:
            prefix = f"[{status}]"

        parts = [prefix]

        stdout = self.data.get("stdout", "")
        stderr = self.data.get("stderr", "")

        if stdout:
            output = stdout[:500] if not detailed else stdout
            parts.append(output)
        if stderr:
            err = stderr[:300] if not detailed else stderr
            parts.append(f"stderr: {err}")

        return " ".join(parts) if len(parts) > 1 else parts[0]

    def _format_content(self, detailed: bool = False) -> str:
        source = self.data.get("source", "")
        lines_total = self.data.get("lines_total", 0)
        lines_shown = self.data.get("lines_shown", 0)
        start_line = self.data.get("start_line", 1)
        content = self.data.get("content", "")

        if detailed:
            header_parts = [f"Source: {source}"]
            if lines_total:
                header_parts.append(f"Lines: {lines_total}")
            if start_line > 1 or lines_shown < lines_total:
                header_parts.append(
                    f"Showing: {start_line}-{start_line + lines_shown - 1}"
                )
            return "\n".join(header_parts) + "\n\n" + content

        # Compact: just content with minimal header
        header = f"[{source}"
        if lines_total:
            header += f":{lines_total}L"
        header += "]"
        return header + "\n" + content

    def _format_error(self, detailed: bool = False) -> str:
        error_type = self.data.get("error_type", "error")
        message = self.data.get("message", "Unknown error")
        return f"[{error_type}] {message}"

    def validate(self) -> list[str]:
        """Validate data dict against format-specific schema.

        Returns:
            List of validation error messages. Empty list means valid.
        """
        schema = FORMAT_SCHEMAS.get(self.format)
        if schema is None:
            return [f"Unknown format: {self.format}"]

        errors: list[str] = []

        for key in schema.required_keys:
            if key not in self.data:
                errors.append(f"Missing required key: {key}")

        for key, expected_type in schema.key_types.items():
            if key in self.data and self.data[key] is not None:
                if not _is_type_compatible(self.data[key], expected_type):
                    errors.append(
                        f"Key '{key}': expected {expected_type.__name__}, got {type(self.data[key]).__name__}"
                    )

        return errors


def _is_type_compatible(value: Any, expected_type: type) -> bool:
    """Check if value matches expected_type, accounting for Python's type hierarchy.

    Python's bool is a subclass of int, so isinstance(True, int) is True.
    We reject bool where int is expected, and allow int where float is expected.
    """
    if isinstance(value, bool):
        return expected_type is bool
    if isinstance(value, expected_type):
        return True
    return expected_type is float and isinstance(value, int)


@dataclass(frozen=True)
class FormatSchema:
    """Schema definition for a StandardToolOutput format."""

    required_keys: tuple[str, ...]
    optional_keys: tuple[str, ...]
    key_types: dict[str, type] = field(default_factory=dict)


FORMAT_SCHEMAS: dict[OutputFormat, FormatSchema] = {
    OutputFormat.STATUS: FormatSchema(
        required_keys=("status",),
        optional_keys=("exit_code", "stdout", "stderr", "output"),
        key_types={
            "status": str,
            "exit_code": int,
            "stdout": str,
            "stderr": str,
            "output": str,
        },
    ),
    OutputFormat.LIST: FormatSchema(
        required_keys=("items", "total"),
        optional_keys=("max_display",),
        key_types={"items": list, "total": int, "max_display": int},
    ),
    OutputFormat.CONTENT: FormatSchema(
        required_keys=("source", "content"),
        optional_keys=("lines_total", "lines_shown", "start_line"),
        key_types={
            "source": str,
            "content": str,
            "lines_total": int,
            "lines_shown": int,
            "start_line": int,
        },
    ),
    OutputFormat.STRUCTURE: FormatSchema(
        required_keys=(),
        optional_keys=(),
    ),
    OutputFormat.ERROR: FormatSchema(
        required_keys=(),
        optional_keys=("error_type", "message"),
        key_types={"error_type": str, "message": str},
    ),
}
