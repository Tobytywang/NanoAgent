"""
Estimation audit for tracking token estimation accuracy.

Tracks estimated vs actual token usage, detects calibration convergence,
and warns when deviation exceeds threshold.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EstimationAuditConfig:
    """Configuration for estimation audit."""

    enabled: bool = True
    deviation_warning_threshold: float = 0.50  # Warn when deviation > 50%
    audit_window: int = 20  # How many data points to keep
    min_samples_for_convergence: int = 5  # Min samples to assess convergence
    convergence_threshold: float = 0.10  # Deviation below this = converged


@dataclass
class EstimationDeviation:
    """Single estimation deviation record."""

    estimated: int
    actual: int
    deviation_pct: float  # abs(actual - estimated) / estimated * 100
    direction: str  # "over" (estimated > actual) or "under" (estimated < actual)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EstimationAuditResult:
    """Result from recording an estimation check."""

    deviation_pct: float
    is_warning: bool  # deviation_pct > warning_threshold
    direction: str
    calibration_factor: float


class EstimationAudit:
    """Tracks estimation vs actual token usage and provides observability."""

    def __init__(self, config: EstimationAuditConfig | None = None):
        self.config = config or EstimationAuditConfig()
        self._history: list[EstimationDeviation] = []
        self._warning_count: int = 0

    def record(
        self, estimated: int, actual: int, calibration_factor: float = 1.0
    ) -> EstimationAuditResult:
        """Record an estimation deviation and check thresholds.

        Args:
            estimated: Token count from estimate_tokens()
            actual: Real prompt_tokens from LLM response
            calibration_factor: Current calibration factor

        Returns:
            EstimationAuditResult with deviation info and warning status
        """
        if not self.config.enabled:
            return EstimationAuditResult(
                deviation_pct=0.0,
                is_warning=False,
                direction="unknown",
                calibration_factor=calibration_factor,
            )

        if estimated <= 0:
            return EstimationAuditResult(
                deviation_pct=0.0,
                is_warning=False,
                direction="unknown",
                calibration_factor=calibration_factor,
            )

        deviation_pct = abs(actual - estimated) / estimated
        direction = "over" if estimated > actual else "under"
        is_warning = deviation_pct > self.config.deviation_warning_threshold

        if is_warning:
            self._warning_count += 1

        self._history.append(
            EstimationDeviation(
                estimated=estimated,
                actual=actual,
                deviation_pct=deviation_pct,
                direction=direction,
            )
        )

        # Trim to window size
        if len(self._history) > self.config.audit_window:
            self._history = self._history[-self.config.audit_window :]

        return EstimationAuditResult(
            deviation_pct=deviation_pct,
            is_warning=is_warning,
            direction=direction,
            calibration_factor=calibration_factor,
        )

    def get_summary(self) -> dict:
        """Get audit summary for /stats display.

        Returns:
            Dict with avg/max deviation, over/under counts, convergence info
        """
        if not self._history:
            return {
                "total_checks": 0,
                "avg_deviation_pct": 0.0,
                "max_deviation_pct": 0.0,
                "over_count": 0,
                "under_count": 0,
                "over_pct": 0.0,
                "under_pct": 0.0,
                "warning_count": 0,
                "calibration_factor": 1.0,
                "is_converged": False,
            }

        deviations = [d.deviation_pct for d in self._history]
        over_count = sum(1 for d in self._history if d.direction == "over")
        under_count = sum(1 for d in self._history if d.direction == "under")
        total = len(self._history)

        # Get latest calibration factor from most recent result
        latest_cf = 1.0
        if self._history:
            # Infer from latest deviation
            latest = self._history[-1]
            if latest.estimated > 0:
                latest_cf = latest.actual / latest.estimated

        return {
            "total_checks": total,
            "avg_deviation_pct": sum(deviations) / total,
            "max_deviation_pct": max(deviations),
            "over_count": over_count,
            "under_count": under_count,
            "over_pct": over_count / total * 100,
            "under_pct": under_count / total * 100,
            "warning_count": self._warning_count,
            "calibration_factor": latest_cf,
            "is_converged": self.is_converged(),
        }

    def get_deviation_history(self) -> list[EstimationDeviation]:
        """Get deviation history."""
        return self._history.copy()

    def is_converged(self) -> bool:
        """Check if calibration has converged (recent deviations < threshold).

        Returns:
            True if the last N deviations are all below convergence_threshold
        """
        if len(self._history) < self.config.min_samples_for_convergence:
            return False

        recent = self._history[-self.config.min_samples_for_convergence :]
        return all(d.deviation_pct < self.config.convergence_threshold for d in recent)

    def reset(self) -> None:
        """Reset audit state."""
        self._history.clear()
        self._warning_count = 0
