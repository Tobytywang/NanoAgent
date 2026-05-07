"""
Tests for v0.6.5 Git integration: GitManager and Git-based undo.
"""

import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from nano_agent.agent.git_manager import GitManager, GitCommit


class TestGitManagerInit:
    """Tests for GitManager initialization."""

    def test_init_default_path(self):
        """Test initialization with default path."""
        manager = GitManager()
        assert manager.repo_path == Path(".")

    def test_init_custom_path(self):
        """Test initialization with custom path."""
        manager = GitManager("/tmp/test")
        assert manager.repo_path == Path("/tmp/test")


class TestGitManagerEnabled:
    """Tests for Git availability detection."""

    def test_is_enabled_in_git_repo(self):
        """Test detection in a Git repository."""
        # This test runs in the current repo
        manager = GitManager()
        assert manager.is_enabled() is True

    def test_is_enabled_not_git_repo(self):
        """Test detection outside a Git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(tmpdir)
            assert manager.is_enabled() is False

    def test_is_enabled_caches_result(self):
        """Test that result is cached."""
        manager = GitManager()
        # First call
        result1 = manager.is_enabled()
        # Second call should use cached value
        result2 = manager.is_enabled()
        assert result1 == result2
        assert manager._enabled is not None


class TestGitManagerChanges:
    """Tests for change detection."""

    def test_has_changes_true(self):
        """Test detecting changes."""
        # In a repo with potential changes, this could be True or False
        manager = GitManager()
        if manager.is_enabled():
            # Just verify it doesn't crash
            result = manager.has_changes()
            assert isinstance(result, bool)

    def test_has_changes_not_git_repo(self):
        """Test change detection outside Git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(tmpdir)
            assert manager.has_changes() is False


class TestGitManagerCommit:
    """Tests for auto commit functionality."""

    def test_auto_commit_not_git_repo(self):
        """Test auto commit outside Git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(tmpdir)
            result = manager.auto_commit("Test message")
            assert result is None

    def test_auto_commit_no_changes(self):
        """Test auto commit with no changes."""
        manager = GitManager()
        if manager.is_enabled():
            # If no changes, should return None
            if not manager.has_changes():
                result = manager.auto_commit("Test message")
                assert result is None

    def test_auto_commit_with_step_info(self):
        """Test auto commit with step info."""
        manager = GitManager()
        if manager.is_enabled() and manager.has_changes():
            result = manager.auto_commit(
                "Test message",
                step_info={"tool": "test_tool"}
            )
            # Result could be commit hash or None
            if result:
                assert isinstance(result, str)


class TestGitManagerUndo:
    """Tests for Git undo functionality."""

    def test_undo_not_git_repo(self):
        """Test undo outside Git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(tmpdir)
            assert manager.undo(1) is False

    def test_undo_invalid_steps(self):
        """Test undo with invalid steps."""
        manager = GitManager()
        if manager.is_enabled():
            assert manager.undo(0) is False
            assert manager.undo(-1) is False

    def test_soft_undo_not_git_repo(self):
        """Test soft undo outside Git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(tmpdir)
            assert manager.soft_undo(1) is False


class TestGitManagerHistory:
    """Tests for Git history functionality."""

    def test_get_history_in_git_repo(self):
        """Test getting history in a Git repo."""
        manager = GitManager()
        if manager.is_enabled():
            history = manager.get_history(limit=5)
            assert isinstance(history, list)
            # This repo should have commits
            if history:
                commit = history[0]
                assert isinstance(commit, GitCommit)
                assert len(commit.hash) == 7
                assert commit.message
                assert commit.time
                assert commit.author

    def test_get_history_not_git_repo(self):
        """Test getting history outside Git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(tmpdir)
            history = manager.get_history()
            assert history == []

    def test_get_history_limit(self):
        """Test history limit."""
        manager = GitManager()
        if manager.is_enabled():
            history = manager.get_history(limit=3)
            assert len(history) <= 3


class TestGitManagerBranch:
    """Tests for branch functionality."""

    def test_get_current_branch_in_git_repo(self):
        """Test getting current branch."""
        manager = GitManager()
        if manager.is_enabled():
            branch = manager.get_current_branch()
            # Branch could be None in detached HEAD state
            if branch:
                assert isinstance(branch, str)

    def test_get_current_branch_not_git_repo(self):
        """Test getting branch outside Git repo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GitManager(tmpdir)
            assert manager.get_current_branch() is None


class TestGitManagerPrefix:
    """Tests for commit prefix."""

    def test_default_prefix(self):
        """Test default commit prefix."""
        manager = GitManager()
        assert manager._commit_prefix == "[NanoAgent]"

    def test_set_custom_prefix(self):
        """Test setting custom prefix."""
        manager = GitManager()
        manager.set_commit_prefix("[Custom]")
        assert manager._commit_prefix == "[Custom]"


class TestGitCommit:
    """Tests for GitCommit dataclass."""

    def test_git_commit_creation(self):
        """Test creating a GitCommit."""
        from datetime import datetime

        commit = GitCommit(
            hash="abc1234",
            message="Test commit",
            time=datetime(2026, 5, 7, 10, 30, 0),
            author="Test User"
        )

        assert commit.hash == "abc1234"
        assert commit.message == "Test commit"
        assert commit.author == "Test User"


class TestGitManagerFormatMessage:
    """Tests for commit message formatting."""

    def test_format_simple_message(self):
        """Test formatting simple message."""
        manager = GitManager()
        message = manager._format_commit_message("Test", None)
        assert message == "[NanoAgent] Test"

    def test_format_message_with_step_info(self):
        """Test formatting message with step info."""
        manager = GitManager()
        message = manager._format_commit_message(
            "Test",
            step_info={"tool": "file_write"}
        )
        assert "[NanoAgent] Test" in message
        assert "Tool: file_write" in message

    def test_format_message_with_arguments(self):
        """Test formatting message with arguments."""
        manager = GitManager()
        message = manager._format_commit_message(
            "Test",
            step_info={"tool": "shell_execute", "arguments": {"command": "ls"}}
        )
        assert "[NanoAgent] Test" in message
        assert "Tool: shell_execute" in message
        assert "Arguments:" in message


class TestGitManagerIntegration:
    """Integration tests for GitManager."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary Git repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmpdir, capture_output=True)

            # Create initial commit
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("initial")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmpdir, capture_output=True)

            yield tmpdir

    def test_full_workflow(self, temp_git_repo):
        """Test full Git workflow: commit, history, undo."""
        manager = GitManager(temp_git_repo)

        # Verify enabled
        assert manager.is_enabled() is True

        # Make a change and commit
        test_file = Path(temp_git_repo) / "test.txt"
        test_file.write_text("modified")

        commit_hash = manager.auto_commit("Modified file", step_info={"tool": "file_write"})
        assert commit_hash is not None

        # Check history
        history = manager.get_history(limit=2)
        assert len(history) >= 1
        assert "Modified file" in history[0].message

        # Undo
        assert manager.undo(1) is True

        # Verify file reverted
        assert test_file.read_text() == "initial"

    def test_round_mode_workflow(self, temp_git_repo):
        """Test round mode: multiple changes, single commit."""
        manager = GitManager(temp_git_repo)

        # Make multiple changes
        (Path(temp_git_repo) / "file1.txt").write_text("content1")
        (Path(temp_git_repo) / "file2.txt").write_text("content2")

        # Single commit for round
        commit_hash = manager.auto_commit("Round: file_write, file_write")
        assert commit_hash is not None

        # Check history
        history = manager.get_history(limit=1)
        assert "Round" in history[0].message
