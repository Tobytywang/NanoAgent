"""
Confirmation mechanism for tool execution.

Provides risk-based confirmation for tool operations, allowing users
to approve or deny dangerous operations before execution.

Design for evolution:
- Core logic is I/O free
- Communication via EventEmitter
- Can be wrapped by CLI or future independent agent
"""

from typing import TYPE_CHECKING
import threading

from .types import RiskLevel
from ..config.schema import ConfirmationConfig

if TYPE_CHECKING:
    from ..tools.base import BaseTool


class ConfirmationManager:
    """
    Manages tool execution confirmations.

    Uses risk levels to determine which tools require user confirmation.
    Supports whitelist for tools that should bypass confirmation.

    Thread-safe for use in async environments.
    """

    def __init__(self, config: ConfirmationConfig | None = None):
        self.config = config or ConfirmationConfig()
        self._pending_confirmation: bool = False
        self._confirmation_result: bool | None = None
        self._lock = threading.Lock()
        self._event = threading.Event()

    def needs_confirmation(self, tool: "BaseTool") -> bool:
        """
        Determine if a tool requires confirmation.

        Args:
            tool: The tool to check

        Returns:
            True if confirmation is needed, False otherwise
        """
        if not self.config.enabled:
            return False

        # Whitelist bypasses confirmation
        if tool.name in self.config.whitelist:
            return False

        # Check by risk level
        level = tool.risk_level
        if level == RiskLevel.SAFE:
            return self.config.confirm_safe
        elif level == RiskLevel.MODERATE:
            return self.config.confirm_moderate
        elif level == RiskLevel.DANGEROUS:
            return self.config.confirm_dangerous

        # Unknown level defaults to requiring confirmation
        return True

    def request_confirmation(self) -> None:
        """
        Request confirmation from user.

        Sets the manager into pending state, waiting for external
        confirmation via set_result().
        """
        with self._lock:
            self._pending_confirmation = True
            self._confirmation_result = None
            self._event.clear()

    def set_result(self, confirmed: bool) -> None:
        """
        Set the confirmation result.

        Called by external handler (CLI, UI, etc.) after user interaction.

        Args:
            confirmed: Whether the user confirmed the operation
        """
        with self._lock:
            self._confirmation_result = confirmed
            self._pending_confirmation = False
            self._event.set()

    def get_result(self) -> bool | None:
        """
        Get the confirmation result.

        Returns:
            True if confirmed, False if denied, None if not yet set
        """
        with self._lock:
            return self._confirmation_result

    def is_pending(self) -> bool:
        """Check if waiting for confirmation."""
        with self._lock:
            return self._pending_confirmation

    def wait_for_result(self, timeout: float | None = None) -> bool | None:
        """
        Wait for confirmation result.

        Args:
            timeout: Maximum time to wait in seconds (None = infinite)

        Returns:
            Confirmation result, or None if timeout
        """
        if self._event.wait(timeout=timeout):
            return self.get_result()
        return None

    def reset(self) -> None:
        """Reset confirmation state."""
        with self._lock:
            self._pending_confirmation = False
            self._confirmation_result = None
            self._event.clear()

    def add_to_whitelist(self, tool_name: str) -> None:
        """
        Add a tool to the whitelist.

        Args:
            tool_name: Name of the tool to whitelist
        """
        if tool_name not in self.config.whitelist:
            self.config.whitelist.append(tool_name)

    def remove_from_whitelist(self, tool_name: str) -> None:
        """
        Remove a tool from the whitelist.

        Args:
            tool_name: Name of the tool to remove
        """
        if tool_name in self.config.whitelist:
            self.config.whitelist.remove(tool_name)
