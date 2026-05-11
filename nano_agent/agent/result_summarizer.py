"""
Tool result summarizer for token efficiency.
"""

from dataclasses import dataclass


@dataclass
class SummarizerConfig:
    """Summarizer configuration."""
    enabled: bool = True
    max_lines: int = 20  # Max lines to keep
    keep_first_lines: int = 5
    keep_last_lines: int = 5


class ToolResultSummarizer:
    """Summarize tool results to reduce token consumption."""

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
        """Summarize file read output - keep key lines."""
        lines = output.split("\n")

        if len(lines) <= self.config.max_lines:
            return output

        # Keep first N lines (often contains headers/imports)
        first = lines[:self.config.keep_first_lines]
        # Keep last N lines (often contains conclusions/errors)
        last = lines[-self.config.keep_last_lines:]

        skipped = len(lines) - self.config.keep_first_lines - self.config.keep_last_lines

        result = "\n".join(first)
        result += f"\n... [{skipped} lines skipped] ...\n"
        result += "\n".join(last)

        return result

    def _summarize_shell(self, output: str) -> str:
        """Summarize shell output - filter empty/meaningless lines."""
        lines = output.split("\n")

        # Filter out empty lines and common noise
        meaningful = []
        for line in lines:
            stripped = line.strip()
            if stripped and not self._is_noise(stripped):
                meaningful.append(line)

        if len(meaningful) <= self.config.max_lines:
            return "\n".join(meaningful)

        # Truncate if still too long
        return "\n".join(meaningful[:self.config.max_lines]) + f"\n... [{len(meaningful) - self.config.max_lines} more lines]"

    def _summarize_file_search(self, output: str) -> str:
        """Summarize file search - keep file list."""
        lines = output.split("\n")

        if len(lines) <= self.config.max_lines:
            return output

        # Keep first N matches
        kept = lines[:self.config.max_lines]
        remaining = len(lines) - self.config.max_lines

        return "\n".join(kept) + f"\n... (+{remaining} more matches)"

    def _summarize_generic(self, output: str) -> str:
        """Generic summarization for other tools."""
        lines = output.split("\n")

        if len(lines) <= self.config.max_lines:
            return output

        # Keep first and last portions
        first = lines[:self.config.keep_first_lines]
        last = lines[-self.config.keep_last_lines:]
        skipped = len(lines) - self.config.keep_first_lines - self.config.keep_last_lines

        return "\n".join(first) + f"\n... [{skipped} lines skipped] ...\n" + "\n".join(last)

    def _is_noise(self, line: str) -> bool:
        """Check if a line is noise that can be filtered."""
        noise_patterns = [
            "total ",  # ls -la total line
            "drwx",    # directory listing prefix (keep files only)
        ]
        # Keep lines that don't start with noise patterns
        return any(line.startswith(p) for p in noise_patterns)
