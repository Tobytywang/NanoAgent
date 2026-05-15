"""
Tool result summarizer for token efficiency.

Provides intelligent summarization strategies per tool type:
- file_read: Extract key sections (imports, classes, functions)
- shell_execute: Filter meaningful output, extract errors
- file_search: Keep count and representative samples
"""

from dataclasses import dataclass, field
import re


@dataclass
class SummarizerConfig:
    """Summarizer configuration."""

    enabled: bool = True
    max_lines: int = 20  # Max lines to keep
    keep_first_lines: int = 5
    keep_last_lines: int = 5
    # Intelligent extraction settings
    extract_imports: bool = True  # Extract import statements
    extract_signatures: bool = True  # Extract class/function signatures
    extract_errors: bool = True  # Extract error messages
    file_search_count_only: bool = False  # Show only count for file searches


class ToolResultSummarizer:
    """Summarize tool results to reduce token consumption."""

    # Patterns for extracting key information
    IMPORT_PATTERN = re.compile(r"^(import |from .+ import)")
    CLASS_PATTERN = re.compile(r"^(class |async class )")
    FUNCTION_PATTERN = re.compile(r"^(def |async def )")
    ERROR_PATTERN = re.compile(r"(error|Error|ERROR|failed|Failed|FAILED|exception)")

    def __init__(self, config: SummarizerConfig | None = None):
        self.config = config or SummarizerConfig()

    def summarize(self, output: str, tool_name: str) -> str:
        """
        Summarize tool output based on tool type.

        Args:
            output: Original tool output
            tool_name: Name of the tool that generated the output

        Returns:
            Summarized output
        """
        if not self.config.enabled:
            return output

        if tool_name == "file_read":
            return self._summarize_file_read(output)
        elif tool_name == "shell_execute":
            return self._summarize_shell(output)
        elif tool_name == "file_search":
            return self._summarize_file_search(output)
        else:
            return self._summarize_generic(output)

    def _summarize_file_read(self, output: str) -> str:
        """
        Summarize file content - extract key structural elements.

        Strategy:
        1. Extract imports (understand dependencies)
        2. Extract class/function signatures (understand structure)
        3. Keep first/last lines as context
        """
        lines = output.split("\n")

        if len(lines) <= self.config.max_lines:
            return output

        key_lines = []
        skipped_sections = []

        # Extract imports
        if self.config.extract_imports:
            imports = []
            for line in lines:
                if self.IMPORT_PATTERN.match(line.strip()):
                    imports.append(line)
            if imports:
                key_lines.append("# Imports:")
                key_lines.extend(imports[:5])  # Limit imports
                if len(imports) > 5:
                    key_lines.append(f"# ... and {len(imports) - 5} more imports")
                skipped_sections.append(f"{len(imports)} imports")

        # Extract class/function signatures
        if self.config.extract_signatures:
            signatures = []
            for line in lines:
                stripped = line.strip()
                if self.CLASS_PATTERN.match(stripped) or self.FUNCTION_PATTERN.match(
                    stripped
                ):
                    signatures.append(line)
            if signatures:
                key_lines.append("\n# Structure:")
                key_lines.extend(signatures[:10])  # Limit signatures
                if len(signatures) > 10:
                    key_lines.append(f"# ... and {len(signatures) - 10} more definitions")
                skipped_sections.append(f"{len(signatures)} definitions")

        # Add first lines context
        key_lines.append("\n# First lines:")
        key_lines.extend(lines[: self.config.keep_first_lines])

        # Add skip indicator
        skipped = len(lines) - self.config.keep_first_lines - self.config.keep_last_lines
        key_lines.append(f"\n# ... [{skipped} lines skipped] ...")

        # Add last lines context
        key_lines.append("\n# Last lines:")
        key_lines.extend(lines[-self.config.keep_last_lines :])

        summary = "\n".join(key_lines)

        # Add extraction summary
        if skipped_sections:
            summary += f"\n\n[Extracted: {', '.join(skipped_sections)}]"

        return summary

    def _summarize_shell(self, output: str) -> str:
        """
        Summarize shell output - extract meaningful content.

        Strategy:
        1. Filter empty lines and common noise
        2. Extract error messages if present
        3. Keep meaningful output lines
        """
        lines = output.split("\n")

        # Filter noise and categorize
        meaningful = []
        error_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped or self._is_noise(stripped):
                continue

            # Check for errors
            if self.config.extract_errors and self.ERROR_PATTERN.search(stripped):
                error_lines.append(line)
            else:
                meaningful.append(line)

        # Build summary
        result_parts = []

        if error_lines:
            result_parts.append("# Errors:")
            result_parts.extend(error_lines[:10])  # Limit error lines

        if meaningful:
            result_parts.append("\n# Output:")
            # Limit output
            if len(meaningful) > self.config.max_lines:
                result_parts.extend(meaningful[: self.config.max_lines])
                result_parts.append(f"... [{len(meaningful) - self.config.max_lines} more lines]")
            else:
                result_parts.extend(meaningful)

        if not result_parts:
            return "[No meaningful output]"

        return "\n".join(result_parts)

    def _summarize_file_search(self, output: str) -> str:
        """
        Summarize file search results.

        Strategy:
        1. Count total matches
        2. Show representative sample (first few)
        3. Optionally show count only
        """
        # Count only mode
        if self.config.file_search_count_only:
            match = re.search(r"(\d+)", output)
            if match:
                count = int(match.group(1))
                return f"[{count} files found]"
            return output

        lines = output.split("\n")

        if len(lines) <= self.config.max_lines:
            return output

        # Show sample with count
        sample = lines[: self.config.keep_first_lines]
        remaining = len(lines) - self.config.keep_first_lines

        result = "\n".join(sample)
        result += f"\n... (+{remaining} more files)"

        return result

    def _summarize_generic(self, output: str) -> str:
        """Generic summarization - keep first/last with context."""
        lines = output.split("\n")

        if len(lines) <= self.config.max_lines:
            return output

        first = lines[: self.config.keep_first_lines]
        last = lines[-self.config.keep_last_lines :]
        skipped = len(lines) - self.config.keep_first_lines - self.config.keep_last_lines

        return (
            "\n".join(first)
            + f"\n... [{skipped} lines skipped] ...\n"
            + "\n".join(last)
        )

    def _is_noise(self, line: str) -> bool:
        """Check if a line is noise that can be filtered."""
        noise_patterns = [
            "total ",  # ls -la total line
            "drwx",  # directory listing prefix
            "Empty output",
            "No files found",
        ]
        return any(line.startswith(p) for p in noise_patterns)
