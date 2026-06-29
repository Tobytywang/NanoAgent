"""
Token budget management for controlling token consumption.

This module provides a TokenBudget class that tracks remaining token budget
and triggers summarization when budget is exhausted.

Features:
- LLMUsage history tracking for calibration
- Dynamic budget adjustment based on actual usage patterns
- Calibration factor for more accurate budget estimation

NEW in v0.7.8:
- Multi-level warning thresholds (50%, 30%, 20%, 10%)
- Configurable warning modes (silent/console/event)
- Warning interval to prevent spam
- LLM-based summary generation option

NEW in v0.7.13:
- Corrected calibration formula: actual/estimated instead of budget burn rate
- Calibration data tracked separately from usage history
- record_calibration_data() for feeding actual vs estimated pairs
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from nano_agent.llm.base import LLMUsage


@dataclass
class CalibrationData:
    """Single calibration data point: estimated vs actual prompt_tokens."""

    estimated: int  # Estimated prompt_tokens from estimate_tokens()
    actual: int  # Actual prompt_tokens from LLM response


@dataclass
class TokenBudgetConfig:
    """Configuration for token budget management."""

    initial_budget: int = (
        50000  # Initial token budget (increased for multi-turn conversations)
    )

    # Multi-level warning thresholds (relative to initial budget)
    # Warnings issued when remaining ratio <= each threshold
    warning_thresholds: list[float] = field(
        default_factory=lambda: [0.5, 0.3, 0.2, 0.1]
    )
    # Warning behavior
    warning_mode: Literal["silent", "console", "event"] = "console"
    warning_interval: int = 1  # Minimum iterations between warnings (prevent spam)

    force_summarize: bool = True  # Force summarize when exhausted

    # LLM-based summary generation
    llm_summary_enabled: bool = True  # Use LLM to generate structured summary
    llm_summary_max_tokens: int = 500  # Max tokens for LLM summary

    # Calibration settings
    calibration_enabled: bool = True  # Enable dynamic calibration
    calibration_window: int = 5  # Number of calls to consider for calibration
    min_calibration_samples: int = 3  # Minimum samples before calibration

    # Wrap-up round settings (v0.7.9)
    wrapup_enabled: bool = False  # Enable budget wrap-up round
    wrapup_threshold: float = 0.1  # Trigger when remaining ratio <= threshold
    wrapup_free_round: bool = True  # Wrap-up round doesn't consume budget
    wrapup_max_tokens: int = 2000  # Max tokens for wrap-up LLM call

    @classmethod
    def from_smart_optimization(cls, config) -> "TokenBudgetConfig":
        """Create TokenBudgetConfig from SmartOptimizationConfig.

        This eliminates the need for manual field mapping that caused
        BUG-003 and BUG-005 (fields drifting between the two classes).
        """
        return cls(
            initial_budget=config.initial_budget,
            warning_thresholds=config.budget_warning_thresholds,
            warning_mode=config.budget_warning_mode,
            warning_interval=config.budget_warning_interval,
            force_summarize=config.budget_force_summarize,
            llm_summary_enabled=config.budget_llm_summary_enabled,
            llm_summary_max_tokens=config.budget_llm_summary_max_tokens,
            calibration_enabled=config.calibration_enabled,
            calibration_window=config.calibration_window,
            min_calibration_samples=config.min_calibration_samples,
            wrapup_enabled=config.budget_wrapup_enabled,
            wrapup_threshold=config.budget_wrapup_threshold,
            wrapup_free_round=config.budget_wrapup_free_round,
            wrapup_max_tokens=config.budget_wrapup_max_tokens,
        )


class TokenBudget:
    """
    Token budget tracker for controlling consumption.

    Tracks remaining budget and provides methods to check if
    summarization should be triggered.

    Supports dynamic calibration based on actual LLM usage patterns.

    NEW in v0.7.8:
    - Progressive warnings at multiple thresholds
    - Warning state tracking to prevent duplicate warnings
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
        self._calibration_data: list[CalibrationData] = []
        self._calibration_factor: float = 1.0

        # Warning state tracking (v0.7.8)
        self._last_warning_level: int = (
            -1
        )  # Track last warning level (0=50%, 1=30%, 2=20%, 3=10%)
        self._warnings_issued: int = 0  # Total warnings issued
        self._last_warning_iteration: int = 0  # Iteration counter for interval control

    def consume(self, tokens: int) -> None:
        """
        Consume tokens from the budget.

        Args:
            tokens: Number of tokens consumed
        """
        self.remaining = max(0, self.remaining - tokens)
        self._total_consumed += tokens

    def consume_usage(self, usage: "LLMUsage") -> None:
        """Record actual usage from an LLM call.

        Args:
            usage: LLMUsage object with actual token counts
        """
        self._usage_history.append(usage)

        # Keep only the last N entries
        if len(self._usage_history) > self.config.calibration_window:
            self._usage_history = self._usage_history[-self.config.calibration_window :]

        # Consume tokens
        self.consume(usage.total_tokens)

    def _update_calibration(self) -> None:
        """Update calibration factor based on actual vs estimated token ratios.

        v0.7.13: Corrected formula.
        Old: avg(total_tokens) / (initial_budget / 10) - measured budget burn rate.
        New: avg(actual / estimated) - measures estimation accuracy.
        """
        if not self.config.calibration_enabled:
            return

        if len(self._calibration_data) < self.config.min_calibration_samples:
            return

        # Compute average ratio: actual / estimated
        ratios = [d.actual / max(d.estimated, 1) for d in self._calibration_data]
        avg_ratio = sum(ratios) / len(ratios)

        # Clamp to [0.5, 2.0] to prevent extreme values
        self._calibration_factor = max(0.5, min(2.0, avg_ratio))

    def record_calibration_data(self, estimated: int, actual: int) -> None:
        """Record a calibration data point and trigger calibration update.

        Called from react.py _think() after each LLM call, comparing
        estimate_tokens() output with actual usage.prompt_tokens.

        Args:
            estimated: Token count from estimate_tokens()
            actual: Real prompt_tokens from LLM response
        """
        if not self.config.calibration_enabled:
            return

        self._calibration_data.append(
            CalibrationData(estimated=estimated, actual=actual)
        )

        # Keep only the most recent data within the window
        if len(self._calibration_data) > self.config.calibration_window:
            self._calibration_data = self._calibration_data[
                -self.config.calibration_window :
            ]

        # Trigger calibration update
        self._update_calibration()

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

    def check_warning(self, current_iteration: int) -> dict | None:
        """
        Check if a warning should be issued based on current budget.

        This is the main entry point for progressive warnings in v0.7.8.
        Unlike should_warn() which only checks a single threshold,
        this method tracks multiple warning levels and prevents duplicates.

        Args:
            current_iteration: Current iteration number for interval control

        Returns:
            Warning dict if warning should be issued, None otherwise.
            Dict contains: level, threshold, remaining_ratio, remaining_tokens,
                          initial_budget, message
        """
        if self.initial_budget == 0:
            return None

        ratio = self.remaining / self.initial_budget

        # Find appropriate warning level
        for level_idx, threshold in enumerate(self.config.warning_thresholds):
            if ratio <= threshold and level_idx > self._last_warning_level:
                # Check interval to prevent spam
                if (
                    current_iteration - self._last_warning_iteration
                    >= self.config.warning_interval
                ):
                    self._last_warning_level = level_idx
                    self._last_warning_iteration = current_iteration
                    self._warnings_issued += 1

                    return {
                        "level": level_idx,
                        "threshold": threshold,
                        "remaining_ratio": ratio,
                        "remaining_tokens": self.remaining,
                        "initial_budget": self.initial_budget,
                        "message": self._format_warning_message(level_idx, ratio),
                    }

        return None

    def _format_warning_message(self, level: int, ratio: float) -> str:
        """
        Format user-friendly warning message.

        Args:
            level: Warning level (0=50%, 1=30%, 2=20%, 3=10%)
            ratio: Current remaining ratio

        Returns:
            Formatted warning message
        """
        percentage = ratio * 100
        icons = ["⚠️", "⚡", "🔴", "🚨"]  # Progressive urgency
        icon = icons[min(level, len(icons) - 1)]

        messages = [
            f"{icon} Token budget at {percentage:.0f}% - consider simplifying request",
            f"{icon} Token budget at {percentage:.0f}% - approaching limit",
            f"{icon} Token budget at {percentage:.0f}% - will summarize soon",
            f"{icon} Token budget at {percentage:.0f}% - final warning before summarization",
        ]

        return messages[min(level, len(messages) - 1)]

    def should_warn(self) -> bool:
        """
        Check if budget is running low.

        DEPRECATED: Use check_warning() for progressive warnings.

        Returns:
            True if remaining budget is below warning threshold
        """
        if self.initial_budget == 0:
            return False
        # Use the last threshold for backward compatibility
        ratio = self.remaining / self.initial_budget
        return ratio <= self.config.warning_thresholds[-1]

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

    def should_wrapup(self) -> bool:
        """
        Check if budget wrap-up round should be triggered.

        Returns:
            True if remaining ratio is at or below wrapup threshold
        """
        if not self.config.wrapup_enabled or self.initial_budget == 0:
            return False
        return self.remaining / self.initial_budget <= self.config.wrapup_threshold

    def set_budget_ratio(self, ratio: float, base_budget: int) -> None:
        """Adjust budget based on complexity ratio.

        Resets budget to base_budget * ratio, clears consumption and
        warning state so the new query starts fresh.

        Args:
            ratio: Budget ratio (0.0-1.0) based on query complexity
            base_budget: Full budget amount to scale from
        """
        self.initial_budget = int(base_budget * max(ratio, 0.05))
        self.remaining = self.initial_budget
        self._total_consumed = 0
        self._last_warning_level = -1
        self._warnings_issued = 0
        self._last_warning_iteration = 0

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
        self._calibration_data = []
        self._calibration_factor = 1.0
        # Reset warning state (v0.7.8)
        self._last_warning_level = -1
        self._warnings_issued = 0
        self._last_warning_iteration = 0

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
            "calibration_samples": len(self._calibration_data),
            # Warning state (v0.7.8)
            "warnings_issued": self._warnings_issued,
            "last_warning_level": self._last_warning_level,
        }
