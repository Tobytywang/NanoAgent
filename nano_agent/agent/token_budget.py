"""
Token budget management for controlling token consumption.

This module provides a TokenBudget class that tracks remaining token budget
and triggers summarization when budget is exhausted.

Features:
- LLMUsage history tracking for calibration
- Dynamic budget adjustment based on actual usage patterns
- Calibration factor for more accurate budget estimation
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nano_agent.llm.base import LLMUsage


@dataclass
class TokenBudgetConfig:
    """Configuration for token budget management."""

    initial_budget: int = 2000  # Initial token budget
    warning_threshold: float = 0.2  # Warn when remaining < 20%
    force_summarize: bool = True  # Force summarize when exhausted
    # Calibration settings
    calibration_enabled: bool = True  # Enable dynamic calibration
    calibration_window: int = 5  # Number of calls to consider for calibration
    min_calibration_samples: int = 3  # Minimum samples before calibration


class TokenBudget:
    """
    Token budget tracker for controlling consumption.

    Tracks remaining budget and provides methods to check if
    summarization should be triggered.

    Supports dynamic calibration based on actual LLM usage patterns.
    """

    def __init__(self, config: TokenBudgetConfig | None = None):
        """
        Initialize token budget.

        Args:
            config: Budget configuration
        """
        self.config = config or TokenBudgetConfig()
        self.initial_budget = self.config.initial_budget
        self.remaining = self.initial_budget
        self._total_consumed = 0

        # Calibration support
        self._usage_history: list["LLMUsage"] = []
        self._calibration_factor: float = 1.0

    def consume(self, tokens: int) -> None:
        """
        Consume tokens from the budget.

        Args:
            tokens: Number of tokens consumed
        """
        self.remaining = max(0, self.remaining - tokens)
        self._total_consumed += tokens

    def consume_usage(self, usage: "LLMUsage") -> None:
        """
        Consume tokens from LLMUsage and record for calibration.

        Args:
            usage: LLMUsage object from LLM response
        """
        # Record usage for calibration
        self._usage_history.append(usage)

        # Keep only the last N entries
        if len(self._usage_history) > self.config.calibration_window:
            self._usage_history = self._usage_history[-self.config.calibration_window :]

        # Consume tokens
        self.consume(usage.total_tokens)

        # Update calibration factor
        self._update_calibration()

    def _update_calibration(self) -> None:
        """Update calibration factor based on usage history."""
        if not self.config.calibration_enabled:
            return

        if len(self._usage_history) < self.config.min_calibration_samples:
            return

        # Calculate average actual tokens per call
        avg_actual = sum(u.total_tokens for u in self._usage_history) / len(
            self._usage_history
        )

        # Calculate calibration factor
        # If actual usage is higher than expected, factor > 1
        # If actual usage is lower than expected, factor < 1
        if self.initial_budget > 0:
            expected_per_call = self.initial_budget / 10  # Assume ~10 calls expected
            if expected_per_call > 0:
                self._calibration_factor = avg_actual / expected_per_call

    def get_calibration_factor(self) -> float:
        """
        Get the current calibration factor.

        Returns:
            Calibration factor (1.0 = no adjustment needed)
        """
        return self._calibration_factor

    def get_average_usage(self) -> float:
        """
        Get average token usage per call.

        Returns:
            Average tokens per call, or 0 if no history
        """
        if not self._usage_history:
            return 0.0
        return sum(u.total_tokens for u in self._usage_history) / len(
            self._usage_history
        )

    def get_usage_history(self) -> list["LLMUsage"]:
        """
        Get the usage history.

        Returns:
            List of LLMUsage objects
        """
        return self._usage_history.copy()

    def should_warn(self) -> bool:
        """
        Check if budget is running low.

        Returns:
            True if remaining budget is below warning threshold
        """
        if self.initial_budget == 0:
            return False
        ratio = self.remaining / self.initial_budget
        # Warn when ratio <= threshold (not <)
        return ratio <= self.config.warning_threshold

    def should_summarize(self) -> bool:
        """
        Check if summarization should be forced.

        Returns:
            True if budget is exhausted and force_summarize is enabled
        """
        if not self.config.force_summarize:
            return False
        return self.remaining <= 0

    def is_exhausted(self) -> bool:
        """
        Check if budget is exhausted.

        Returns:
            True if no budget remaining
        """
        return self.remaining <= 0

    def reset(self, new_budget: int | None = None) -> None:
        """
        Reset the budget.

        Args:
            new_budget: Optional new initial budget
        """
        if new_budget is not None:
            self.initial_budget = new_budget
        self.remaining = self.initial_budget
        self._total_consumed = 0
        self._usage_history = []
        self._calibration_factor = 1.0

    def get_status(self) -> dict:
        """
        Get current budget status.

        Returns:
            Dict with budget information
        """
        return {
            "initial": self.initial_budget,
            "remaining": self.remaining,
            "consumed": self._total_consumed,
            "percentage_remaining": (
                (self.remaining / self.initial_budget * 100)
                if self.initial_budget > 0
                else 0
            ),
            "calibration_factor": self._calibration_factor,
            "average_usage": self.get_average_usage(),
            "samples_collected": len(self._usage_history),
        }
