"""
Stall detection for the ReAct loop.

Detects when the agent is making iterations without meaningful progress
and injects redirect hints to encourage strategy changes.

Unlike DuplicateDetector (which catches exact repeated tool calls),
StallDetector catches "different tools, same result" patterns where
the agent is cycling through different approaches but not advancing.
"""

import hashlib
from dataclasses import dataclass, field


@dataclass
class StallConfig:
    """Configuration for stall detection."""

    enabled: bool = True
    patience: int = 3  # Consecutive similar iterations before stall
    similarity_threshold: float = 0.7  # How similar signatures must be
    hint_injection: bool = True  # Inject redirect hint when stalled


@dataclass
class StallResult:
    """Result of stall detection check."""

    is_stalled: bool
    stalled_iterations: int  # How many consecutive stalled iterations
    hint: str | None = None  # Redirect hint for the LLM


# Default redirect hints, cycled to avoid repetition
_STALL_HINTS = [
    "你之前的尝试没有明显进展，请尝试不同的方法或综合已有信息给出回答。",
    "你似乎在原地打转。请换一个完全不同的策略，或者基于已有信息直接总结回答。",
    "多次尝试未见成效。请停止使用工具，直接根据已知信息给出最佳回答。",
]


class StallDetector:
    """
    Detects stall patterns in the ReAct loop.

    A stall is when consecutive iterations produce similar results,
    indicating the agent is not making meaningful progress despite
    trying different approaches.

    Detection strategy:
    1. Build a "signature" for each iteration from tool names + result hashes
    2. Compare signatures of recent iterations
    3. If N consecutive iterations are too similar, declare a stall
    4. Inject a redirect hint to encourage the LLM to change strategy
    """

    def __init__(self, config: StallConfig | None = None):
        self.config = config or StallConfig()
        self._iteration_signatures: list[str] = []
        self._stall_count: int = 0
        self._hint_index: int = 0

    def record_iteration(
        self,
        tool_names: list[str],
        tool_results: list[str],
    ) -> None:
        """Record an iteration's signature for stall comparison.

        Args:
            tool_names: List of tool names called in this iteration
            tool_results: List of tool result outputs (as strings)
        """
        signature = self._make_signature(tool_names, tool_results)
        self._iteration_signatures.append(signature)

    def check_stall(self) -> StallResult:
        """Check if the agent is stalled (no meaningful progress).

        Returns:
            StallResult with stall status and optional redirect hint
        """
        if not self.config.enabled:
            return StallResult(is_stalled=False, stalled_iterations=0)

        if len(self._iteration_signatures) < 2:
            return StallResult(is_stalled=False, stalled_iterations=0)

        # Compare last N iterations
        patience = self.config.patience
        recent = self._iteration_signatures[-patience:]

        if len(recent) < patience:
            # Not enough iterations yet, but check what we have
            if self._are_similar(recent):
                self._stall_count += 1
                hint = self._generate_hint() if self.config.hint_injection else None
                return StallResult(
                    is_stalled=True,
                    stalled_iterations=self._stall_count,
                    hint=hint,
                )
            self._stall_count = 0
            return StallResult(is_stalled=False, stalled_iterations=0)

        if self._are_similar(recent):
            self._stall_count += 1
            hint = self._generate_hint() if self.config.hint_injection else None
            return StallResult(
                is_stalled=True,
                stalled_iterations=self._stall_count,
                hint=hint,
            )

        self._stall_count = 0
        return StallResult(is_stalled=False, stalled_iterations=0)

    def reset(self) -> None:
        """Reset stall detection state for a new query."""
        self._iteration_signatures = []
        self._stall_count = 0
        self._hint_index = 0

    def _make_signature(
        self,
        tool_names: list[str],
        tool_results: list[str],
    ) -> str:
        """Create a signature for iteration comparison.

        Combines tool names with a hash of each result's content.
        This captures both which tools were used and what they returned,
        without storing full result text.

        Args:
            tool_names: Tool names called
            tool_results: Tool result strings

        Returns:
            Signature string for comparison
        """
        parts = []
        for name, result in zip(tool_names, tool_results):
            # Hash the result to get a fixed-length fingerprint
            result_hash = hashlib.md5(result.encode()).hexdigest()[:8]
            # Include result length as a progress signal
            result_len = len(result)
            parts.append(f"{name}:{result_hash}:{result_len}")
        return "|".join(parts)

    def _are_similar(self, signatures: list[str]) -> bool:
        """Check if signatures are too similar (no progress).

        Uses pairwise Jaccard similarity on signature components.
        If all pairs exceed the similarity threshold, the iterations
        are considered stalled.

        Args:
            signatures: List of iteration signatures to compare

        Returns:
            True if all pairs are too similar
        """
        if len(signatures) < 2:
            return False

        threshold = self.config.similarity_threshold

        # Compare each pair of consecutive signatures
        for i in range(len(signatures) - 1):
            similarity = self._signature_similarity(signatures[i], signatures[i + 1])
            if similarity < threshold:
                return False

        return True

    @staticmethod
    def _signature_similarity(sig_a: str, sig_b: str) -> float:
        """Compute similarity between two iteration signatures.

        Uses Jaccard similarity on the set of signature components
        (tool:hash:length segments).

        Args:
            sig_a: First signature
            sig_b: Second signature

        Returns:
            Similarity score (0.0-1.0)
        """
        set_a = set(sig_a.split("|"))
        set_b = set(sig_b.split("|"))
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)

    def _generate_hint(self) -> str:
        """Generate a redirect hint, cycling through available hints.

        Returns:
            Redirect hint string
        """
        hint = _STALL_HINTS[self._hint_index % len(_STALL_HINTS)]
        self._hint_index += 1
        return hint
