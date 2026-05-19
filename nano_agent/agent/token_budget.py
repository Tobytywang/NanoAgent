"""
Token budget management for controlling token consumption.

This module provides a TokenBudget class that tracks remaining token budget
and triggers summarization when budget is exhausted.
"""

from dataclasses import dataclass


@dataclass
class TokenBudgetConfig:
    """Configuration for token budget management."""

    initial_budget: int = 2000  # Initial token budget
    warning_threshold: float = 0.2  # Warn when remaining < 20%
    force_summarize: bool = True  # Force summarize when exhausted


class TokenBudget:
    """
    Token budget tracker for controlling consumption.

    Tracks remaining budget and provides methods to check if
    summarization should be triggered.
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

    def consume(self, tokens: int) -> None:
        """
        Consume tokens from the budget.

        Args:
            tokens: Number of tokens consumed
        """
        self.remaining = max(0, self.remaining - tokens)
        self._total_consumed += tokens

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
                if self.initial_budget > 0 else 0
            ),
        }
