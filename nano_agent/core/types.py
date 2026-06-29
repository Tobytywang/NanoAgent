"""
Shared type definitions used across multiple packages.

Types that are referenced by both agent/ and tools/ live here
to avoid circular dependencies.
"""

from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    """Tool risk level for confirmation mechanism."""

    SAFE = "safe"  # Read-only, query operations
    MODERATE = "moderate"  # Write, create operations
    DANGEROUS = "dangerous"  # Delete, shell operations


# === Plan Types ===


@dataclass
class PlanPhase:
    """
    A phase in a plan.

    Represents a single implementation stage with its target version,
    description, and completion status.
    """

    version: str  # Target version number (e.g., "v0.7.0")
    description: str  # Phase description
    status: str = "pending"  # pending / in_progress / completed


@dataclass
class Plan:
    """
    Execution plan for complex tasks.

    Plans are persisted to .nano_agent/plans/ and can span multiple
    sessions. They support multi-round refinement before execution.
    """

    name: str  # Plan name (used as filename)
    task: str  # Original task description
    analysis: str  # LLM analysis of the task
    phases: list[PlanPhase]  # Implementation phases
    risks: list[str] = field(default_factory=list)  # Risks and constraints
    created_at: str = ""  # Creation timestamp
    status: str = "planning"  # planning / executing / completed

    def __post_init__(self):
        if not self.created_at:
            from datetime import datetime

            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
