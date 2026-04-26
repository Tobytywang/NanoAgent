"""
File operation tools.
"""

import os
from pathlib import Path
from typing import Literal
from .base import BaseTool, ToolResult


class FileReadTool(BaseTool):
    """Tool for reading file contents."""

    name = "file_read"
    description = "Read the contents of a file. Supports text files with optional line range selection."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-based), default is 1",
                    "default": 1
                },
                "num_lines": {
                    "type": "integer",
                    "description": "Number of lines to read, 0 means all lines",
                    "default": 0
                }
            },
            "required": ["file_path"]
        }

    def execute(
        self,
        file_path: str,
        start_line: int = 1,
        num_lines: int = 0
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
                    success=False,
                    output="",
                    error=f"File does not exist: {path}"
                )

            if not path.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path is not a file: {path}"
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
            return ToolResult(
                success=True,
                output=f"File: {path}\nTotal lines: {len(lines)}\n\n{content}"
            )
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error="File is not a text file or uses unsupported encoding"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileWriteTool(BaseTool):
    """Tool for writing to files."""

    name = "file_write"
    description = "Write content to a file. Can overwrite or append."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                },
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "description": "Write mode: 'write' (overwrite) or 'append'",
                    "default": "write"
                }
            },
            "required": ["file_path", "content"]
        }

    def execute(
        self,
        file_path: str,
        content: str,
        mode: Literal["write", "append"] = "write"
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

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            write_mode = "a" if mode == "append" else "w"
            with open(path, write_mode, encoding="utf-8") as f:
                f.write(content)

            action = "Appended to" if mode == "append" else "Wrote to"
            return ToolResult(
                success=True,
                output=f"{action} file: {path}"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileSearchTool(BaseTool):
    """Tool for searching files."""

    name = "file_search"
    description = "Search for files matching a pattern in a directory."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "The directory to search in"
                },
                "pattern": {
                    "type": "string",
                    "description": "File name pattern (supports * and ? wildcards)"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to search recursively",
                    "default": True
                }
            },
            "required": ["directory", "pattern"]
        }

    def execute(
        self,
        directory: str,
        pattern: str,
        recursive: bool = True
    ) -> ToolResult:
        """
        Search for files matching a pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern
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
                    error=f"Directory does not exist: {base_path}"
                )

            if not base_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path is not a directory: {base_path}"
                )

            matches = list(
                base_path.rglob(pattern) if recursive else base_path.glob(pattern)
            )

            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No files matching '{pattern}' found"
                )

            # Limit results
            max_results = 100
            result_str = "\n".join(
                str(m.relative_to(base_path)) for m in matches[:max_results]
            )

            if len(matches) > max_results:
                result_str += f"\n... and {len(matches) - max_results} more results"

            return ToolResult(
                success=True,
                output=f"Found {len(matches)} matches:\n{result_str}"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
