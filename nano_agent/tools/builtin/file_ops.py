"""
File operation tools.
"""

import os
from pathlib import Path
from typing import Literal
from ..base import BaseTool, ToolResult
from ..standard_output import StandardToolOutput, OutputFormat
from ...agent.types import RiskLevel


class FileReadTool(BaseTool):
    """Tool for reading file contents."""

    name = "file_read"
    description = "Read the contents of a file. Supports text files with optional line range selection."
    risk_level = RiskLevel.SAFE  # Read-only operation
    can_offload = True  # Large file contents can be offloaded

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-based), default is 1",
                    "default": 1,
                },
                "num_lines": {
                    "type": "integer",
                    "description": "Number of lines to read, 0 means all lines",
                    "default": 0,
                },
            },
            "required": ["file_path"],
        }

    def execute(
        self, file_path: str, start_line: int = 1, num_lines: int = 0
    ) -> ToolResult:
        """
        Read file contents.

        Args:
            file_path: Path to the file
            start_line: Starting line number (1-based)
            num_lines: Number of lines to read (0 = all)

        Returns:
            ToolResult with file contents
        """
        try:
            path = Path(file_path).expanduser().resolve()

            if not path.exists():
                return ToolResult(
                    success=False, output="", error=f"File does not exist: {path}"
                )

            if not path.is_file():
                return ToolResult(
                    success=False, output="", error=f"Path is not a file: {path}"
                )

            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Handle line range
            start_idx = max(0, start_line - 1)
            end_idx = start_idx + num_lines if num_lines > 0 else len(lines)
            selected_lines = lines[start_idx:end_idx]

            # Add line numbers
            result_lines = [
                f"{start_idx + i + 1:6d} | {line.rstrip()}"
                for i, line in enumerate(selected_lines)
            ]

            content = "\n".join(result_lines)
            raw_output = f"File: {path}\nTotal lines: {len(lines)}\n\n{content}"
            standard_output = StandardToolOutput(
                format=OutputFormat.CONTENT,
                data={
                    "source": str(path),
                    "lines_total": len(lines),
                    "lines_shown": len(selected_lines),
                    "start_line": start_idx + 1,
                    "content": content,
                },
                summary=f"{path}: {len(lines)} lines",
            )
            return ToolResult(
                success=True,
                output=raw_output,
                metadata={"standard_output": standard_output},
            )
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error="File is not a text file or uses unsupported encoding",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileWriteTool(BaseTool):
    """Tool for writing to files."""

    name = "file_write"
    description = "Write content to a file. Can overwrite or append."
    risk_level = RiskLevel.MODERATE  # Write operation

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file",
                },
                "content": {"type": "string", "description": "The content to write"},
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "description": "Write mode: 'write' (overwrite) or 'append'",
                    "default": "write",
                },
            },
            "required": ["file_path", "content"],
        }

    @property
    def supports_undo(self) -> bool:
        """FileWriteTool supports undo by restoring previous content."""
        return True

    def undo(self, undo_data: dict, context: dict) -> bool:
        """
        Undo file write by restoring previous content.

        Args:
            undo_data: Contains path and previous_content
            context: Execution context (not used for file operations)

        Returns:
            True if undo was successful
        """
        path_str = undo_data.get("path")
        previous_content = undo_data.get("previous_content")
        file_existed = undo_data.get("file_existed", True)

        if not path_str:
            return False

        try:
            path = Path(path_str)

            if not file_existed:
                # File didn't exist before, delete it
                if path.exists():
                    path.unlink()
                return True

            # Restore previous content
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(previous_content or "")
            return True
        except Exception:
            return False

    def execute(
        self, file_path: str, content: str, mode: Literal["write", "append"] = "write"
    ) -> ToolResult:
        """
        Write content to a file.

        Args:
            file_path: Path to the file
            content: Content to write
            mode: 'write' to overwrite, 'append' to add

        Returns:
            ToolResult indicating success or failure
        """
        try:
            path = Path(file_path).expanduser().resolve()

            # Read previous content for undo (only in write mode)
            previous_content = None
            file_existed = False
            if mode == "write":
                file_existed = path.exists()
                if file_existed:
                    with open(path, "r", encoding="utf-8") as f:
                        previous_content = f.read()

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            write_mode = "a" if mode == "append" else "w"
            with open(path, write_mode, encoding="utf-8") as f:
                f.write(content)

            action = "Appended to" if mode == "append" else "Wrote to"

            # Only provide undo_data for write mode (append is harder to undo)
            undo_data = None
            if mode == "write":
                undo_data = {
                    "path": str(path),
                    "previous_content": previous_content,
                    "file_existed": file_existed,
                }

            return ToolResult(
                success=True, output=f"{action} file: {path}", undo_data=undo_data
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileSearchTool(BaseTool):
    """Tool for searching files."""

    name = "file_search"
    description = "Search for files matching a pattern in a directory."
    risk_level = RiskLevel.SAFE  # Read-only operation
    can_offload = True  # Large search results can be offloaded

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "The directory to search in",
                },
                "pattern": {
                    "type": "string",
                    "description": "File name pattern (supports * and ? wildcards)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to search recursively",
                    "default": True,
                },
            },
            "required": ["directory", "pattern"],
        }

    def execute(
        self, directory: str, pattern: str, recursive: bool = True
    ) -> ToolResult:
        """
        Search for files matching a pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern (supports | separator for multiple patterns)
            recursive: Whether to search subdirectories

        Returns:
            ToolResult with matching files
        """
        try:
            base_path = Path(directory).expanduser().resolve()

            if not base_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Directory does not exist: {base_path}",
                )

            if not base_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path is not a directory: {base_path}",
                )

            # Support pipe separator for multiple patterns
            patterns = pattern.split("|") if "|" in pattern else [pattern]

            # Collect matches from all patterns
            all_matches = set()
            for p in patterns:
                p = p.strip()
                if p:
                    matches = base_path.rglob(p) if recursive else base_path.glob(p)
                    all_matches.update(matches)

            if not all_matches:
                return ToolResult(
                    success=True, output=f"No files matching '{pattern}' found"
                )

            # Sort and limit results
            sorted_matches = sorted(all_matches, key=lambda m: str(m))
            max_results = 100
            result_str = "\n".join(
                str(m.relative_to(base_path)) for m in sorted_matches[:max_results]
            )

            if len(sorted_matches) > max_results:
                result_str += (
                    f"\n... and {len(sorted_matches) - max_results} more results"
                )

            items = [
                {"path": str(m.relative_to(base_path))}
                for m in sorted_matches[:max_results]
            ]
            standard_output = StandardToolOutput(
                format=OutputFormat.LIST,
                data={
                    "items": items,
                    "total": len(sorted_matches),
                    "max_display": max_results,
                },
                summary=f"Found {len(sorted_matches)} files matching '{pattern}'",
            )
            return ToolResult(
                success=True,
                output=f"Found {len(sorted_matches)} matches:\n{result_str}",
                metadata={"standard_output": standard_output},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
