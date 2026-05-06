"""
Undo mechanism for tracking and reverting tool operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class UndoRecord:
    """Record of an undoable operation."""

    tool_name: str
    undo_data: dict
    timestamp: str
    round_id: str  # Identifies which conversation round this belongs to


class UndoStack:
    """
    Manages a stack of undoable operations organized by conversation rounds.

    Each round corresponds to one user message and its associated tool calls.
    Undo operations revert all changes made in the current round.
    """

    def __init__(self):
        self._records: list[UndoRecord] = []
        self._current_round: str = ""

    def start_round(self, round_id: str) -> None:
        """
        Start a new conversation round.

        Args:
            round_id: Unique identifier for this round
        """
        self._current_round = round_id

    def push(self, tool_name: str, undo_data: dict) -> None:
        """
        Record an undoable operation.

        Args:
            tool_name: Name of the tool that was executed
            undo_data: Data needed to undo this operation
        """
        if undo_data:
            self._records.append(UndoRecord(
                tool_name=tool_name,
                undo_data=undo_data,
                timestamp=datetime.now().isoformat(),
                round_id=self._current_round
            ))

    def get_round_records(self) -> list[UndoRecord]:
        """
        Get all records for the current round.

        Returns:
            List of UndoRecord for current round, in execution order
        """
        return [r for r in self._records if r.round_id == self._current_round]

    def has_round_records(self) -> bool:
        """Check if current round has any undoable operations."""
        return any(r.round_id == self._current_round for r in self._records)

    def clear_round(self) -> None:
        """Clear all records for the current round (after successful undo or round completion)."""
        self._records = [r for r in self._records if r.round_id != self._current_round]

    def remove_record(self, record: UndoRecord) -> None:
        """Remove a specific record after it has been undone."""
        if record in self._records:
            self._records.remove(record)

    def clear_all(self) -> None:
        """Clear all records."""
        self._records = []

    def count(self) -> int:
        """Return total number of records."""
        return len(self._records)

    def count_round(self) -> int:
        """Return number of records in current round."""
        return len(self.get_round_records())
