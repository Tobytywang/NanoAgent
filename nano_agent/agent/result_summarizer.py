"""
Tool result summarizer for token efficiency.

Provides intelligent summarization strategies per tool type:
- file_read: Extract key sections (imports, classes, functions)
- shell_execute: Filter meaningful output, extract errors
- file_search: Keep count and representative samples
- python_execute: Extract output and errors
- web_search: Summarize search results
"""

from dataclasses import dataclass, field
import re
from typing import Optional

from .token_utils import estimate_text_tokens, calculate_max_chars


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
    # v0.7.5 enhancements
    extract_docstrings: bool = True  # Extract docstrings
    extract_constants: bool = True  # Extract constants
    max_summary_tokens: int = 500  # Target max tokens in summary
    preserve_structure: bool = True  # Preserve code structure hints


class ToolResultSummarizer:
    """Summarize tool results to reduce token consumption."""

    # Patterns for extracting key information
    IMPORT_PATTERN = re.compile(r"^(import |from .+ import)")
    CLASS_PATTERN = re.compile(r"^(class |async class )")
    FUNCTION_PATTERN = re.compile(r"^(def |async def )")
    ERROR_PATTERN = re.compile(r"(error|Error|ERROR|failed|Failed|FAILED|exception)")
    DOCSTRING_PATTERN = re.compile(r'^("""|\'\'\')')
    CONSTANT_PATTERN = re.compile(r"^([A-Z_]+)\s*=")

    def __init__(self, config: Optional[SummarizerConfig] = None):
        self.config = config or SummarizerConfig()

    def summarize(
        self, output: str, tool_name: str, calibration_factor: float = 1.0
    ) -> str:
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
            result = self._summarize_file_read(output)
        elif tool_name == "shell_execute":
            result = self._summarize_shell(output)
        elif tool_name == "file_search":
            result = self._summarize_file_search(output)
        elif tool_name == "python_execute":
            result = self._summarize_python(output)
        elif tool_name == "web_search":
            result = self._summarize_web_search(output)
        else:
            result = self._summarize_generic(output)

        # v0.7.13: Enforce max_summary_tokens budget
        if self.config.max_summary_tokens > 0:
            max_chars = calculate_max_chars(
                result,
                self.config.max_summary_tokens,
                calibration_factor=calibration_factor,
            )
            if len(result) > max_chars:
                result = result[:max_chars] + "\n... [摘要已截断]"

        return result

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
                    key_lines.append(
                        f"# ... and {len(signatures) - 10} more definitions"
                    )
                skipped_sections.append(f"{len(signatures)} definitions")

        # Add first lines context
        key_lines.append("\n# First lines:")
        key_lines.extend(lines[: self.config.keep_first_lines])

        # Add skip indicator
        skipped = (
            len(lines) - self.config.keep_first_lines - self.config.keep_last_lines
        )
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
                result_parts.append(
                    f"... [{len(meaningful) - self.config.max_lines} more lines]"
                )
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
        skipped = (
            len(lines) - self.config.keep_first_lines - self.config.keep_last_lines
        )

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

    def _summarize_python(self, output: str) -> str:
        """
        Summarize Python execution output.

        Strategy:
        1. Extract stdout/stderr sections
        2. Show output with error highlighting
        3. Limit long outputs
        """
        lines = output.split("\n")

        # Categorize lines
        stdout_lines = []
        stderr_lines = []
        current_section = "stdout"

        for line in lines:
            if "STDERR:" in line or "Error:" in line:
                current_section = "stderr"
                stderr_lines.append(line)
            elif current_section == "stderr":
                stderr_lines.append(line)
            else:
                stdout_lines.append(line)

        result_parts = []

        # Add stdout
        if stdout_lines:
            meaningful_stdout = [
                l for l in stdout_lines if l.strip() and not self._is_noise(l.strip())
            ]
            if meaningful_stdout:
                result_parts.append("# Output:")
                if len(meaningful_stdout) > self.config.max_lines:
                    result_parts.extend(meaningful_stdout[: self.config.max_lines])
                    result_parts.append(
                        f"... [{len(meaningful_stdout) - self.config.max_lines} more lines]"
                    )
                else:
                    result_parts.extend(meaningful_stdout)

        # Add stderr
        if stderr_lines:
            result_parts.append("\n# Errors:")
            result_parts.extend(stderr_lines[:10])  # Limit error lines

        if not result_parts:
            return "[No output]"

        return "\n".join(result_parts)

    def _summarize_web_search(self, output: str) -> str:
        """
        Summarize web search results.

        Strategy:
        1. Extract titles and URLs
        2. Show top results with brief snippets
        3. Limit total results shown
        """
        lines = output.split("\n")

        if len(lines) <= 5:
            return output

        # Try to extract structured results
        results = []
        current_result = {}

        for line in lines:
            # Look for title patterns (v0.7.15: support 【title】 format)
            if (
                line.startswith("Title:")
                or line.startswith("# ")
                or line.startswith("【")
            ):
                if current_result:
                    results.append(current_result)
                title = line.replace("Title:", "").replace("# ", "").strip()
                if title.startswith("【") and title.endswith("】"):
                    title = title[1:-1]
                current_result = {"title": title}
            elif (
                line.startswith("URL:")
                or line.startswith("http")
                or line.startswith("来源:")
            ):
                current_result["url"] = (
                    line.replace("URL:", "").replace("来源:", "").strip()
                )
            elif line.startswith("Snippet:") or line.startswith("Description:"):
                snippet = (
                    line.replace("Snippet:", "").replace("Description:", "").strip()
                )
                current_result["snippet"] = (
                    snippet[:100] + "..." if len(snippet) > 100 else snippet
                )

        if current_result:
            results.append(current_result)

        # Build summary
        if results:
            result_parts = [f"# Found {len(results)} results\n"]

            for i, r in enumerate(results[:5], 1):  # Show top 5
                result_parts.append(f"{i}. {r.get('title', 'Unknown')}")
                if "url" in r:
                    result_parts.append(f"   URL: {r['url']}")
                if "snippet" in r:
                    result_parts.append(f"   {r['snippet']}")
                result_parts.append("")

            if len(results) > 5:
                result_parts.append(f"... and {len(results) - 5} more results")

            return "\n".join(result_parts)

        # Fallback to generic
        return self._summarize_generic(output)

    def _extract_docstrings(self, lines: list[str]) -> list[str]:
        """Extract docstrings from code lines."""
        docstrings = []
        in_docstring = False
        current_docstring = []
        docstring_start_line = -1

        for i, line in enumerate(lines):
            stripped = line.strip()

            if not in_docstring:
                # Check for docstring start
                if self.DOCSTRING_PATTERN.match(stripped):
                    in_docstring = True
                    current_docstring = [line]
                    docstring_start_line = i
                    # Check for single-line docstring
                    if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                        docstrings.append("\n".join(current_docstring))
                        in_docstring = False
                        current_docstring = []
            else:
                current_docstring.append(line)
                # Check for docstring end
                if '"""' in stripped or "'''" in stripped:
                    docstrings.append("\n".join(current_docstring))
                    in_docstring = False
                    current_docstring = []

        return docstrings

    def estimate_tokens(self, text: str, calibration_factor: float = 1.0) -> int:
        """
        Estimate token count for text.

        Uses the unified estimate_text_tokens() which supports Chinese/English mixed text.

        Args:
            text: Text to estimate
            calibration_factor: Calibration factor from TokenBudget (v0.7.18)

        Returns:
            Estimated token count
        """
        return estimate_text_tokens(text, calibration_factor=calibration_factor)
