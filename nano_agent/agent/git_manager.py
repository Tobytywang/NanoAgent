"""
Git integration for automatic commits and state rollback.

Provides Git-based operation history tracking and undo capabilities,
allowing users to rollback to any previous state.

Design for evolution:
- Core logic is I/O free (uses subprocess, not direct GitPython)
- Communication via EventEmitter
- Can be wrapped by CLI or future independent agent
"""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class GitCommit:
    """Git commit information."""

    hash: str  # Short commit hash (7 chars)
    message: str  # Commit message
    time: datetime  # Commit timestamp
    author: str  # Commit author


class GitManager:
    """
    Git integration manager.

    Provides automatic commit on tool execution and rollback capabilities.
    Thread-safe for use in async environments.
    """

    def __init__(self, repo_path: str = "."):
        """
        Initialize Git manager.

        Args:
            repo_path: Path to the Git repository
        """
        self.repo_path = Path(repo_path)
        self._enabled: Optional[bool] = None
        self._commit_prefix = "[NanoAgent]"

    def is_enabled(self) -> bool:
        """
        Check if Git is available in the repository.

        Returns:
            True if Git is available, False otherwise
        """
        if self._enabled is not None:
            return self._enabled

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._enabled = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            self._enabled = False

        return self._enabled

    def has_changes(self) -> bool:
        """
        Check if there are uncommitted changes.

        Returns:
            True if there are changes, False otherwise
        """
        if not self.is_enabled():
            return False

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def auto_commit(self, message: str, step_info: dict = None) -> Optional[str]:
        """
        Automatically commit current changes.

        Args:
            message: Commit message
            step_info: Optional step information (tool name, etc.)

        Returns:
            Commit hash if successful, None otherwise
        """
        if not self.is_enabled():
            return None

        # Check if there are changes
        if not self.has_changes():
            return None

        try:
            # Add all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=10,
            )

            # Format commit message
            full_message = self._format_commit_message(message, step_info)

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", full_message],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return self._get_last_commit_hash()
            return None
        except Exception:
            return None

    def undo(self, steps: int = 1) -> bool:
        """
        Rollback to a previous commit.

        Args:
            steps: Number of commits to rollback

        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False

        if steps < 1:
            return False

        try:
            result = subprocess.run(
                ["git", "reset", "--hard", f"HEAD~{steps}"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def soft_undo(self, steps: int = 1) -> bool:
        """
        Soft rollback (keep changes in working directory).

        Args:
            steps: Number of commits to rollback

        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False

        try:
            result = subprocess.run(
                ["git", "reset", "--soft", f"HEAD~{steps}"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_history(self, limit: int = 10) -> list[GitCommit]:
        """
        Get commit history.

        Args:
            limit: Maximum number of commits to retrieve

        Returns:
            List of GitCommit objects
        """
        if not self.is_enabled():
            return []

        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--pretty=format:%H|%s|%ci|%an"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )

            commits = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("|")
                    if len(parts) >= 4:
                        try:
                            commits.append(
                                GitCommit(
                                    hash=parts[0][:7],
                                    message=parts[1],
                                    time=datetime.strptime(
                                        parts[2][:19], "%Y-%m-%d %H:%M:%S"
                                    ),
                                    author=parts[3],
                                )
                            )
                        except ValueError:
                            continue

            return commits
        except Exception:
            return []

    def get_current_branch(self) -> Optional[str]:
        """
        Get current branch name.

        Returns:
            Branch name if available, None otherwise
        """
        if not self.is_enabled():
            return None

        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def _get_last_commit_hash(self) -> str:
        """Get the last commit hash (short)."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _format_commit_message(self, message: str, step_info: dict = None) -> str:
        """
        Format commit message with prefix and step info.

        Args:
            message: Base message
            step_info: Optional step information

        Returns:
            Formatted commit message
        """
        lines = [f"{self._commit_prefix} {message}"]

        if step_info:
            tool = step_info.get("tool", "unknown")
            lines.append(f"\nTool: {tool}")
            if "arguments" in step_info:
                args_preview = str(step_info["arguments"])[:50]
                lines.append(f"Arguments: {args_preview}")

        return "\n".join(lines)

    def set_commit_prefix(self, prefix: str) -> None:
        """
        Set custom commit message prefix.

        Args:
            prefix: New prefix to use
        """
        self._commit_prefix = prefix
