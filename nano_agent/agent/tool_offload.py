"""
Tool result offloading for large outputs (v0.7.17).

When tool results exceed a token threshold, write the full result to a
temporary file and only add a summary + file reference to the conversation
context. LLM can read the full result on demand via file_read.
"""

import os
import uuid
import time
from dataclasses import dataclass, field
from pathlib import Path

from .result_summarizer import ToolResultSummarizer, SummarizerConfig
from .token_utils import estimate_text_tokens, calculate_max_chars
from ..config.schema import ToolOffloadConfig


@dataclass
class OffloadedResult:
    """Metadata for an offloaded tool result."""

    offload_id: str
    file_path: str
    tool_name: str
    original_size_tokens: int
    summary: str
    created_at: float = field(default_factory=time.time)
    accessed: bool = False


class ToolOffloadManager:
    """
    Manages offloading of large tool results to temporary files.

    Flow: tool executes -> check can_offload + size threshold -> offload
    if triggered -> store full result in file -> add summary + reference
    to context.
    """

    def __init__(self, config: ToolOffloadConfig):
        self.config = config
        self._offloaded: dict[str, OffloadedResult] = {}
        self._offload_dir: Path | None = None
        self._summarizer = ToolResultSummarizer(
            SummarizerConfig(max_summary_tokens=config.summary_max_tokens)
        )

    @property
    def offload_dir(self) -> Path:
        """Get or create the offload directory."""
        if self._offload_dir is None:
            self._offload_dir = Path(self.config.offload_dir)
            self._offload_dir.mkdir(parents=True, exist_ok=True)
        return self._offload_dir

    def should_offload(
        self,
        result_content: str,
        tool_name: str,
        tool_can_offload: bool,
    ) -> bool:
        """
        Determine if a tool result should be offloaded.

        Three-way check: enabled + can_offload + exceeds threshold.
        """
        if not self.config.enabled:
            return False

        if not tool_can_offload:
            return False

        if tool_name in self.config.excluded_tools:
            return False

        token_count = estimate_text_tokens(result_content)
        return token_count > self.config.size_threshold_tokens

    def offload(
        self,
        result_content: str,
        tool_name: str,
        tool_call_id: str,
    ) -> tuple[str, OffloadedResult]:
        """
        Offload a tool result to a temporary file.

        1. Generate summary via ToolResultSummarizer
        2. Enforce summary token budget via calculate_max_chars
        3. Write full result to temp file
        4. Return summary + file reference for context
        """
        offload_id = f"{tool_name}_{tool_call_id}_{uuid.uuid4().hex[:8]}"
        token_count = estimate_text_tokens(result_content)

        # Generate summary using ToolResultSummarizer
        summary = self._summarizer.summarize(result_content, tool_name)

        # Enforce summary token budget
        if self.config.summary_max_tokens > 0:
            max_chars = calculate_max_chars(summary, self.config.summary_max_tokens)
            if len(summary) > max_chars:
                summary = summary[:max_chars] + "\n... [摘要已截断]"

        # Write full result to file
        file_path = self.offload_dir / f"{offload_id}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(result_content)

        # Track metadata
        offloaded = OffloadedResult(
            offload_id=offload_id,
            file_path=str(file_path),
            tool_name=tool_name,
            original_size_tokens=token_count,
            summary=summary,
        )
        self._offloaded[offload_id] = offloaded

        # Build summary message for context
        summary_content = self._build_summary_message(offloaded)

        return summary_content, offloaded

    def _build_summary_message(self, offloaded: OffloadedResult) -> str:
        """Build the summary message to add to context."""
        return (
            f"[结果已卸载] {offloaded.tool_name} 返回约 "
            f"{offloaded.original_size_tokens} tokens\n"
            f"摘要: {offloaded.summary}\n"
            f'完整结果: file_read("{offloaded.file_path}")'
        )

    def get_offloaded(self, offload_id: str) -> OffloadedResult | None:
        """Get metadata for an offloaded result."""
        result = self._offloaded.get(offload_id)
        if result:
            result.accessed = True
        return result

    def get_by_path(self, file_path: str) -> OffloadedResult | None:
        """Get metadata by file path."""
        for offloaded in self._offloaded.values():
            if offloaded.file_path == file_path:
                offloaded.accessed = True
                return offloaded
        return None

    def cleanup(self) -> int:
        """
        Clean up all offloaded files.

        Returns:
            Number of files deleted
        """
        count = 0
        for offloaded in self._offloaded.values():
            try:
                Path(offloaded.file_path).unlink(missing_ok=True)
                count += 1
            except Exception:
                pass
        self._offloaded.clear()
        return count

    def get_stats(self) -> dict:
        """Get offloading statistics."""
        total_tokens = sum(o.original_size_tokens for o in self._offloaded.values())
        accessed = sum(1 for o in self._offloaded.values() if o.accessed)

        return {
            "offloaded_count": len(self._offloaded),
            "total_tokens_saved": total_tokens,
            "accessed_count": accessed,
            "unaccessed_count": len(self._offloaded) - accessed,
        }
