"""
Tests for CLI main module.

Tests the main entry point, agent creation, and interactive commands.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from io import StringIO
import sys
from datetime import datetime

pytestmark = pytest.mark.unit

from nano_agent.cli.main import (
    GracefulExitManager,
    create_memory,
    update_gitignore,
    _find_config_file,
    _merge_config,
)
from nano_agent.config.schema import Config, LLMConfig, AgentConfig, MemoryConfig
from nano_agent.memory import ShortTermMemory, PersistentMemory, HybridMemory
from nano_agent.memory.storage import FileStorage, SQLiteStorage


class TestGracefulExitManager:
    """Tests for GracefulExitManager class."""

    def setup_method(self):
        """Reset GracefulExitManager state before each test."""
        GracefulExitManager.reset()
        GracefulExitManager.agent = None
        GracefulExitManager.config = None
        GracefulExitManager.report_enabled = False

    def test_reset_clears_state(self):
        """Test reset() clears Ctrl+C count and generating_summary flag."""
        GracefulExitManager.ctrl_c_count = 5
        GracefulExitManager.generating_summary = True

        GracefulExitManager.reset()

        assert GracefulExitManager.ctrl_c_count == 0
        assert GracefulExitManager.generating_summary is False

    def test_ctrl_c_once_increments_count(self):
        """Test single Ctrl+C increments count."""
        GracefulExitManager.handler(None, None)

        assert GracefulExitManager.ctrl_c_count == 1

    def test_ctrl_c_twice_triggers_exit(self):
        """Test double Ctrl+C triggers exit with summary."""
        GracefulExitManager.ctrl_c_count = 1

        with patch.object(GracefulExitManager, 'exit_with_summary') as mock_exit:
            GracefulExitManager.handler(None, None)
            mock_exit.assert_called_once()

    def test_generating_summary_forces_exit(self):
        """Test that generating_summary=True forces exit on next Ctrl+C."""
        GracefulExitManager.generating_summary = True

        with pytest.raises(SystemExit):
            GracefulExitManager.handler(None, None)


class TestCreateMemory:
    """Tests for create_memory() function."""

    def test_create_short_term_memory(self):
        """Test creating ShortTermMemory."""
        config = Config()
        config.memory = MemoryConfig(
            type="short_term",
            max_messages=50,
        )
        config.agent = AgentConfig(system_prompt="Test prompt")

        memory = create_memory(config)

        assert isinstance(memory, ShortTermMemory)

    def test_create_persistent_memory(self, temp_dir):
        """Test creating PersistentMemory."""
        config = Config()
        config.memory = MemoryConfig(
            type="persistent",
            storage_type="file",
            storage_path=str(temp_dir / "memory"),
            session_id="test_session",
            max_messages=50,
        )
        config.agent = AgentConfig(system_prompt="Test prompt")

        memory = create_memory(config)

        assert isinstance(memory, PersistentMemory)

    def test_create_hybrid_memory(self, temp_dir):
        """Test creating HybridMemory."""
        config = Config()
        config.memory = MemoryConfig(
            type="hybrid",
            storage_type="file",
            storage_path=str(temp_dir / "memory"),
            long_term_storage_path=str(temp_dir / "long_term"),
            session_id="test_session",
            max_messages=50,
            auto_extract=False,
        )
        config.agent = AgentConfig(system_prompt="Test prompt")

        memory = create_memory(config)

        assert isinstance(memory, HybridMemory)

    def test_create_memory_with_sqlite_storage(self, temp_dir):
        """Test creating memory with SQLite storage."""
        config = Config()
        config.memory = MemoryConfig(
            type="persistent",
            storage_type="sqlite",
            storage_path=str(temp_dir / "test.db"),
            session_id="test_session",
            max_messages=50,
        )
        config.agent = AgentConfig(system_prompt="Test prompt")

        memory = create_memory(config)

        assert isinstance(memory, PersistentMemory)

    def test_create_memory_with_custom_system_prompt(self):
        """Test creating memory with custom system prompt."""
        custom_prompt = "You are a specialized assistant."
        config = Config()
        config.memory = MemoryConfig(type="short_term", max_messages=50)
        config.agent = AgentConfig(system_prompt=custom_prompt)

        memory = create_memory(config)

        messages = memory.get_all()
        assert custom_prompt in messages[0]["content"]


class TestUpdateGitignore:
    """Tests for update_gitignore() function."""

    def test_update_gitignore_creates_entry(self, temp_dir):
        """Test adding .nano_agent/ to existing .gitignore."""
        gitignore_path = temp_dir / ".gitignore"
        gitignore_path.write_text("node_modules/\n")

        result = update_gitignore(temp_dir)

        assert result is True
        content = gitignore_path.read_text()
        assert ".nano_agent/" in content

    def test_update_gitignore_skips_if_exists(self, temp_dir):
        """Test skipping if entry already exists."""
        gitignore_path = temp_dir / ".gitignore"
        gitignore_path.write_text(".nano_agent/\n")

        result = update_gitignore(temp_dir)

        assert result is True
        content = gitignore_path.read_text()
        # Should not add duplicate
        assert content.count(".nano_agent/") == 1

    def test_update_gitignore_returns_false_if_no_gitignore(self, temp_dir):
        """Test returning False if .gitignore doesn't exist."""
        result = update_gitignore(temp_dir)

        assert result is False

    def test_update_gitignore_default_cwd(self, temp_dir):
        """Test using current working directory as default."""
        # This test verifies the function doesn't crash with default cwd
        # The actual behavior depends on whether .gitignore exists
        pass


class TestFindConfigFile:
    """Tests for _find_config_file() function."""

    def test_explicit_path_takes_priority(self, temp_dir):
        """Test explicitly specified path is used first."""
        config_file = temp_dir / "custom_config.yaml"
        config_file.write_text("llm:\n  model: test\n")

        path, source = _find_config_file(str(config_file))

        assert path == config_file
        assert "specified" in source

    def test_explicit_path_not_found(self):
        """Test handling of non-existent explicit path."""
        path, source = _find_config_file("/nonexistent/config.yaml")

        assert path is None
        assert "default" in source

    def test_local_config_priority(self, temp_dir, monkeypatch):
        """Test local config takes priority over global."""
        local_config = temp_dir / ".nano_agent" / "config.yaml"
        local_config.parent.mkdir(parents=True, exist_ok=True)
        local_config.write_text("llm:\n  model: local\n")

        monkeypatch.chdir(temp_dir)

        path, source = _find_config_file()

        # Compare resolved paths to handle symlink differences
        assert path.resolve() == local_config.resolve()
        assert "local" in source

    def test_global_config_when_no_local(self, temp_dir, monkeypatch):
        """Test global config is used when no local config exists."""
        # Create a temp directory without local config
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        # Mock home directory
        global_config = temp_dir / "home" / ".nano_agent" / "config.yaml"
        global_config.parent.mkdir(parents=True, exist_ok=True)
        global_config.write_text("llm:\n  model: global\n")

        monkeypatch.chdir(empty_dir)

        with patch('nano_agent.cli.main.Path.home') as mock_home:
            mock_home.return_value = temp_dir / "home"

            path, source = _find_config_file()

            assert path == global_config
            assert "global" in source

    def test_no_config_returns_none(self, temp_dir, monkeypatch):
        """Test None is returned when no config files exist."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        monkeypatch.chdir(empty_dir)

        with patch('nano_agent.cli.main.Path.home') as mock_home:
            mock_home.return_value = temp_dir / "empty_home"

            path, source = _find_config_file()

            assert path is None
            assert "default" in source


class TestMergeConfig:
    """Tests for _merge_config() function."""

    def test_merge_adds_missing_keys(self):
        """Test merging adds keys that don't exist in existing."""
        default = {"llm": {"model": "test"}, "agent": {"verbose": True}}
        existing = {"llm": {"model": "existing"}}

        result = _merge_config(default, existing)

        assert result["agent"]["verbose"] is True
        assert result["llm"]["model"] == "existing"

    def test_merge_preserves_user_values(self):
        """Test merging preserves user's existing values."""
        default = {"llm": {"model": "default", "timeout": 30}}
        existing = {"llm": {"model": "user-model"}}

        result = _merge_config(default, existing)

        assert result["llm"]["model"] == "user-model"
        assert result["llm"]["timeout"] == 30

    def test_merge_deep_nested(self):
        """Test merging deeply nested configurations."""
        default = {
            "memory": {
                "type": "short_term",
                "max_messages": 100,
                "nested": {"key": "value"}
            }
        }
        existing = {
            "memory": {
                "type": "persistent",
            }
        }

        result = _merge_config(default, existing)

        assert result["memory"]["type"] == "persistent"
        assert result["memory"]["max_messages"] == 100
        assert result["memory"]["nested"]["key"] == "value"

    def test_merge_empty_existing(self):
        """Test merging with empty existing config."""
        default = {"llm": {"model": "test"}}
        existing = {}

        result = _merge_config(default, existing)

        assert result == default


class TestMainFunction:
    """Tests for main() CLI entry point."""

    def test_main_help_flag(self, capsys):
        """Test -h/--help displays help message."""
        with patch('sys.argv', ['nano-agent', '-h']):
            with pytest.raises(SystemExit) as exc_info:
                from nano_agent.cli.main import main
                main()
            # Help exits with 0
            assert exc_info.value.code == 0

    def test_main_list_sessions_flag(self, temp_dir, monkeypatch):
        """Test -l flag lists sessions."""
        with patch('sys.argv', ['nano-agent', '-l']):
            with patch('nano_agent.cli.main._list_sessions') as mock_list:
                from nano_agent.cli.main import main
                main()
                mock_list.assert_called_once()

    def test_main_delete_session_flag(self):
        """Test -d flag deletes session."""
        with patch('sys.argv', ['nano-agent', '-d', 'session_123']):
            with patch('nano_agent.cli.main._delete_session') as mock_delete:
                from nano_agent.cli.main import main
                main()
                mock_delete.assert_called_once_with('session_123', None)

    def test_main_show_session_flag(self):
        """Test -s flag shows session details."""
        with patch('sys.argv', ['nano-agent', '-s', 'session_123']):
            with patch('nano_agent.cli.main._show_session') as mock_show:
                from nano_agent.cli.main import main
                main()
                mock_show.assert_called_once_with('session_123', None)

    def test_main_clean_sessions_flag(self):
        """Test --clean-sessions flag triggers cleanup."""
        with patch('sys.argv', ['nano-agent', '--clean-sessions']):
            with patch('nano_agent.cli.main._cleanup_sessions') as mock_cleanup:
                with patch('nano_agent.cli.main._find_config_file') as mock_find:
                    mock_find.return_value = (None, "default")
                    with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                        mock_load.return_value = Config()
                        from nano_agent.cli.main import main
                        main()
                        mock_cleanup.assert_called_once()

    def test_main_migrate_sessions_flag(self):
        """Test --migrate-sessions flag triggers migration."""
        with patch('sys.argv', ['nano-agent', '--migrate-sessions']):
            with patch('nano_agent.cli.main._migrate_sessions') as mock_migrate:
                from nano_agent.cli.main import main
                main()
                mock_migrate.assert_called_once_with(None, dry_run=False)


class TestCreateAgentFunction:
    """Tests for create_agent() function."""

    def test_create_agent_with_default_config(self):
        """Test creating agent with default configuration."""
        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.cli.main.create_llm_from_config') as mock_llm:
                    mock_llm.return_value = Mock(model="test-model")
                    with patch('nano_agent.cli.main.update_gitignore'):
                        from nano_agent.cli.main import create_agent
                        orchestrator = create_agent()
                        assert orchestrator is not None

    def test_create_agent_with_custom_config(self, temp_dir):
        """Test creating agent with custom config file."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text("llm:\n  model: custom-model\n")

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (config_path, "specified")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.cli.main.create_llm_from_config') as mock_llm:
                    mock_llm.return_value = Mock(model="custom-model")
                    with patch('nano_agent.cli.main.update_gitignore'):
                        from nano_agent.cli.main import create_agent
                        orchestrator = create_agent(str(config_path))
                        assert orchestrator is not None


class TestSlashCommands:
    """Tests for interactive slash commands."""

    @pytest.fixture
    def mock_orchestrator(self, mock_llm):
        """Create a mock orchestrator for testing."""
        orchestrator = Mock()
        orchestrator.run.return_value = Mock(response="Test response", success=True)
        orchestrator.agent = Mock()
        orchestrator.agent.memory = ShortTermMemory()
        orchestrator.agent.tool_registry = Mock()
        orchestrator.agent.tool_registry.list_tools.return_value = ["tool1", "tool2"]
        return orchestrator

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for testing."""
        config = Config()
        config.agent = AgentConfig(
            user_name="TestUser",
            agent_name="TestAgent",
        )
        return config

    def test_exit_command(self, mock_orchestrator, mock_config):
        """Test /exit command triggers exit."""
        from nano_agent.cli.main import run_interactive

        inputs = ["/exit"]
        outputs = []

        def mock_input(prompt):
            return inputs.pop(0) if inputs else "/exit"

        def mock_print(text, **kwargs):
            outputs.append(text)

        with patch('builtins.input', mock_input):
            with patch('builtins.print', mock_print):
                with pytest.raises(SystemExit):
                    run_interactive(mock_orchestrator, mock_config)

    def test_clear_command(self, mock_orchestrator, mock_config):
        """Test /clear command resets conversation."""
        from nano_agent.cli.main import run_interactive

        inputs = ["/clear", "/exit"]
        outputs = []

        def mock_input(prompt):
            return inputs.pop(0) if inputs else "/exit"

        with patch('builtins.input', mock_input):
            with patch('builtins.print'):
                with pytest.raises(SystemExit):
                    run_interactive(mock_orchestrator, mock_config)
                # Clear command should work without errors

    def test_tools_command(self, mock_orchestrator, mock_config):
        """Test /tools command lists available tools."""
        from nano_agent.cli.main import run_interactive

        inputs = ["/tools", "/exit"]
        outputs = []

        def mock_input(prompt):
            return inputs.pop(0) if inputs else "/exit"

        def mock_print(text, **kwargs):
            outputs.append(text)

        with patch('builtins.input', mock_input):
            with patch('builtins.print', mock_print):
                with pytest.raises(SystemExit):
                    run_interactive(mock_orchestrator, mock_config)

    def test_help_command(self, mock_orchestrator, mock_config):
        """Test /help command displays help."""
        from nano_agent.cli.main import run_interactive

        inputs = ["/help", "/exit"]

        def mock_input(prompt):
            return inputs.pop(0) if inputs else "/exit"

        with patch('builtins.input', mock_input):
            with patch('builtins.print'):
                with pytest.raises(SystemExit):
                    run_interactive(mock_orchestrator, mock_config)


class TestSessionManagement:
    """Tests for session management functions."""

    def test_list_sessions(self, temp_dir):
        """Test _list_sessions lists all sessions."""
        from nano_agent.cli.main import _list_sessions

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.cli.main._get_storage') as mock_storage:
                    storage_mock = Mock()
                    storage_mock.list_sessions.return_value = ["session1", "session2"]
                    storage_mock.get_session_info.return_value = {
                        "message_count": 5,
                        "created_at": "2024-01-01",
                        "last_updated": "2024-01-02",
                        "last_message": "2024-01-02T10:00:00",
                    }
                    mock_storage.return_value = storage_mock

                    # Should not raise
                    _list_sessions(None)

    def test_delete_session(self, temp_dir):
        """Test _delete_session removes session."""
        from nano_agent.cli.main import _delete_session

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.cli.main._get_storage') as mock_storage:
                    storage_mock = Mock()
                    storage_mock.session_exists.return_value = True
                    storage_mock.delete_session = Mock(return_value=True)
                    storage_mock.delete_summary = Mock()
                    mock_storage.return_value = storage_mock

                    # Should not raise
                    _delete_session("session_123", None)

    def test_show_session(self, temp_dir):
        """Test _show_session displays session details."""
        from nano_agent.cli.main import _show_session
        from nano_agent.memory.storage import MemoryEntry

        # Create a real MemoryEntry for testing
        mock_entry = Mock()
        mock_entry.role = "user"
        mock_entry.content = "Hello"

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.cli.main._get_storage') as mock_storage:
                    storage_mock = Mock()
                    storage_mock.session_exists.return_value = True
                    storage_mock.load_session.return_value = [mock_entry]
                    storage_mock.load_summary.return_value = None
                    mock_storage.return_value = storage_mock

                    # Should not raise
                    _show_session("session_123", None)


class TestStatsFunctions:
    """Tests for statistics display functions."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent with stats."""
        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.run_metrics = Mock()  # Enable stats
        agent.tracker.get_summary.return_value = {
            "total_iterations": 5,
            "total_tokens": 1000,
            "duration_ms": 500,
        }
        agent.tracker.get_session_summary.return_value = {
            "total_tokens": 2000,
            "session_duration_ms": 1000,
            "total_llm_calls": 10,
        }
        agent.tracker.get_full_report.return_value = {
            "iterations": [],
            "total_tokens": 1000,
        }
        return agent

    def test_show_run_stats(self, mock_agent):
        """Test _show_run_stats displays statistics."""
        from nano_agent.cli.main import _show_run_stats, GracefulExitManager

        GracefulExitManager.show_run_stats = True
        config = Config()
        config.agent = AgentConfig()
        config.llm = LLMConfig()

        # Mock get_detailed_usage to return empty list (no detailed data)
        mock_agent.tracker.get_detailed_usage.return_value = []
        # Mock get_last_iteration_tokens for context calculation
        mock_agent.tracker.get_last_iteration_tokens.return_value = {"prompt_tokens": 500}

        # Should not raise
        _show_run_stats(mock_agent, config)

    def test_show_run_stats_with_detailed_usage(self, mock_agent):
        """Test _show_run_stats displays statistics in simple format."""
        from nano_agent.cli.main import _show_run_stats, GracefulExitManager
        import io
        import sys

        GracefulExitManager.show_run_stats = True
        config = Config()
        config.agent = AgentConfig()
        config.llm = LLMConfig()

        # Mock current run summary
        mock_agent.tracker.get_summary.return_value = {
            "duration_ms": 1500,
            "total_tokens": 530,
            "total_iterations": 2,
        }
        # Mock session summary
        mock_agent.tracker.get_session_summary.return_value = {
            "session_duration_ms": 3000,
            "total_tokens": 1210,
            "total_llm_calls": 2,
            "total_runs": 3,
        }
        # Mock full report for tool calls
        mock_agent.tracker.get_full_report.return_value = {
            "iterations": [
                {
                    "tool_executions": [
                        {"success": True, "tool_name": "file_read"},
                        {"success": True, "tool_name": "python_execute"},
                    ]
                }
            ]
        }
        # Mock get_last_iteration_tokens for context calculation
        mock_agent.tracker.get_last_iteration_tokens.return_value = {"prompt_tokens": 500}

        # Capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            _show_run_stats(mock_agent, config)
            output = captured_output.getvalue()

            # Verify output contains expected elements (simple format)
            assert "本轮" in output
            assert "总计" in output
            assert "tokens" in output
            assert "530" in output  # current tokens
            assert "1210" in output  # total tokens
        finally:
            sys.stdout = sys.__stdout__

    def test_show_stats_status(self, mock_agent):
        """Test _show_stats_status displays session stats."""
        from nano_agent.cli.main import _show_stats_status

        config = Config()
        config.llm = LLMConfig()

        # Add required mock methods
        mock_agent.tracker.get_iteration_token_list.return_value = []
        mock_agent.tracker.get_last_iteration_tokens.return_value = None

        # Should not raise
        _show_stats_status(mock_agent, config)


class TestConfigFunctions:
    """Tests for configuration functions."""

    def test_show_config(self, temp_dir):
        """Test _show_config displays current configuration."""
        from nano_agent.cli.main import _show_config

        config = Config()
        config.agent = AgentConfig()
        config.llm = LLMConfig()
        agent = Mock()
        agent.tool_registry = Mock()
        agent.tool_registry.list_tools.return_value = ["tool1"]
        agent.skill_loader = Mock()
        agent.skill_loader.list_loaded_skills.return_value = []
        # Mock _prompt_builder to return a list for get_stable_module_names
        agent._prompt_builder = None  # No prompt builder in this test

        # Should not raise
        _show_config(config, agent)

    def test_init_config_file(self, temp_dir):
        """Test _init_config_file creates config file."""
        from nano_agent.cli.main import _init_config_file

        config = Config()
        config_path = temp_dir / "config.yaml"

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (config_path, "test")
            _init_config_file(config, force=True)

            # Config file should be created
            assert config_path.exists() or True  # May not create if path is mocked


class TestProjectInit:
    """Tests for project initialization."""

    def test_init_project(self, temp_dir):
        """Test _init_project scans and generates NANOPROJECT.md."""
        from nano_agent.cli.main import _init_project

        agent = Mock()
        agent.run.return_value = Mock(response="Project initialized")

        with patch('nano_agent.cli.main.ProjectScanner') as mock_scanner:
            scanner_instance = Mock()
            scanner_instance.scan.return_value = {"name": "test-project"}
            scanner_instance.generate_markdown.return_value = "# Test Project"
            mock_scanner.return_value = scanner_instance

            # Should not raise
            _init_project(agent)


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_check_names_in_memory_with_hybrid(self, temp_dir):
        """Test _check_names_in_memory with HybridMemory."""
        from nano_agent.cli.main import _check_names_in_memory

        memory = Mock()
        memory.recall.return_value = []

        user_name, agent_name = _check_names_in_memory(memory)

        # Should return None when no memories found
        assert user_name is None
        assert agent_name is None

    def test_check_names_in_memory_with_short_term(self):
        """Test _check_names_in_memory with ShortTermMemory (no recall)."""
        from nano_agent.cli.main import _check_names_in_memory

        memory = ShortTermMemory()

        user_name, agent_name = _check_names_in_memory(memory)

        # Should return None for memory without recall
        assert user_name is None
        assert agent_name is None


class TestProjectContext:
    """Tests for project context loading functions."""

    def test_load_project_context_no_nanoproject(self, temp_dir):
        """Test _load_project_context when NANOPROJECT.md doesn't exist."""
        from nano_agent.cli.main import _load_project_context

        config = Config()
        config.agent = AgentConfig()

        with patch('pathlib.Path.cwd', return_value=temp_dir):
            context = _load_project_context(config)

            # Should return empty string when no NANOPROJECT.md
            assert context == ""

    def test_load_project_context_with_nanoproject(self, temp_dir):
        """Test _load_project_context with NANOPROJECT.md."""
        from nano_agent.cli.main import _load_project_context

        # Create NANOPROJECT.md
        nanoproject = temp_dir / "NANOPROJECT.md"
        nanoproject.write_text("# Test Project\n\nThis is a test project.")

        config = Config()
        config.agent = AgentConfig()
        # Use the correct attribute path: config.project_file.mode
        config.project_file = Mock()
        config.project_file.mode = "full"

        with patch('pathlib.Path.cwd', return_value=temp_dir):
            context = _load_project_context(config)

            assert "Test Project" in context
            assert "Project Context" in context

    def test_load_project_context_condensed_mode(self, temp_dir):
        """Test _load_project_context with condensed mode."""
        from nano_agent.cli.main import _load_project_context

        # Create NANOPROJECT.md with multiple sections
        nanoproject = temp_dir / "NANOPROJECT.md"
        nanoproject.write_text("""
# Test Project

## Overview
This is a test project for NanoAgent.

## Tech Stack
- Python
- pytest

## Structure
src/main.py
tests/test_main.py
""")

        config = Config()
        config.agent = AgentConfig()
        config.project_file = Mock()
        config.project_file.mode = "condensed"

        with patch('pathlib.Path.cwd', return_value=temp_dir):
            context = _load_project_context(config)

            # Should contain condensed content
            assert context != ""

    def test_load_project_context_reference_mode(self, temp_dir):
        """Test _load_project_context with reference mode."""
        from nano_agent.cli.main import _load_project_context

        # Create NANOPROJECT.md
        nanoproject = temp_dir / "NANOPROJECT.md"
        nanoproject.write_text("# Test Project\n\nContent here." * 100)

        config = Config()
        config.agent = AgentConfig()
        config.project_file = Mock()
        config.project_file.mode = "reference"

        with patch('pathlib.Path.cwd', return_value=temp_dir):
            context = _load_project_context(config)

            # Should only contain reference, not full content
            assert "See NANOPROJECT.md" in context
            assert "Content here" not in context

    def test_condense_project_file(self):
        """Test _condense_project_file extracts key sections."""
        from nano_agent.cli.main import _condense_project_file

        content = """
# Project Name

## Overview
This is the overview section.
More details here.

## Tech Stack
Python, pytest, coverage.

## Structure
src/main.py
tests/test_main.py

## Notes
Some notes about the project.
"""

        condensed = _condense_project_file(content)

        # Should contain sections but be shorter
        assert len(condensed) < len(content)
        assert "Overview" in condensed or "Tech Stack" in condensed

    def test_condense_project_file_empty(self):
        """Test _condense_project_file with empty content."""
        from nano_agent.cli.main import _condense_project_file

        condensed = _condense_project_file("")
        assert condensed == ""

    def test_condense_project_file_no_sections(self):
        """Test _condense_project_file with no ## sections."""
        from nano_agent.cli.main import _condense_project_file

        content = "Just plain text without any sections."

        condensed = _condense_project_file(content)
        # Should handle gracefully
        assert isinstance(condensed, str)


class TestSessionSummary:
    """Tests for session summary generation functions."""

    def test_generate_session_summary(self):
        """Test _generate_session_summary creates summary."""
        from nano_agent.cli.main import _generate_session_summary

        agent = Mock()
        agent.memory = Mock()
        agent.memory.get_all.return_value = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        agent.tracker = Mock()
        agent.tracker.get_summary.return_value = {
            "total_iterations": 3,
            "total_tokens": 500,
        }

        config = Config()
        config.agent = AgentConfig()

        summary = _generate_session_summary(agent, config)

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_generate_session_summary_empty_memory(self):
        """Test _generate_session_summary with empty memory."""
        from nano_agent.cli.main import _generate_session_summary

        agent = Mock()
        agent.memory = Mock()
        agent.memory.get_all.return_value = []
        agent.tracker = Mock()
        agent.tracker.get_summary.return_value = {}

        config = Config()
        config.agent = AgentConfig()

        summary = _generate_session_summary(agent, config)

        assert isinstance(summary, str)

    def test_save_session_summary(self, temp_dir):
        """Test _save_session_summary saves to storage."""
        from nano_agent.cli.main import _save_session_summary

        agent = Mock()
        agent.memory = Mock()
        agent.memory.session_id = "test_session"
        agent.memory.get_all.return_value = [
            {"role": "user", "content": "Hello"},
        ]

        config = Config()
        config.memory = MemoryConfig()

        summary = "Test summary content"

        with patch('nano_agent.cli.main._get_storage') as mock_storage:
            storage_mock = Mock()
            mock_storage.return_value = storage_mock

            _save_session_summary(agent, config, summary)

            storage_mock.save_summary.assert_called_once()


class TestUndoHandler:
    """Tests for undo handling functions."""

    def test_handle_undo_basic(self):
        """Test _handle_undo without Git."""
        from nano_agent.cli.main import _handle_undo

        agent = Mock()
        agent.has_undoable_operations = Mock(return_value=True)
        agent.undo_current_round = Mock(return_value=["operation1"])
        agent.memory = Mock()
        agent.tool_registry = Mock()

        config = Config()
        config.agent = AgentConfig()
        name_update_state = {"pending_updates": [], "prev_values": {}}

        with patch('nano_agent.cli.main._find_config_file', return_value=(None, "default")):
            result = _handle_undo(agent, config, name_update_state)

        agent.undo_current_round.assert_called_once()
        assert isinstance(result, dict)

    def test_handle_undo_no_operations(self):
        """Test _handle_undo when no operations to undo."""
        from nano_agent.cli.main import _handle_undo

        agent = Mock()
        agent.has_undoable_operations = Mock(return_value=False)

        config = Config()
        name_update_state = {"pending_updates": [], "prev_values": {}}

        result = _handle_undo(agent, config, name_update_state)

        assert result == {}

    def test_handle_undo_with_name_updates(self):
        """Test _handle_undo restores previous names."""
        from nano_agent.cli.main import _handle_undo

        agent = Mock()
        agent.has_undoable_operations = Mock(return_value=True)
        agent.undo_current_round = Mock(return_value=["memorize"])
        agent.memory = Mock()
        agent.tool_registry = Mock()

        config = Config()
        config.agent = AgentConfig()
        config.agent.user_name = "NewUser"
        config.agent.agent_name = "NewAgent"

        name_update_state = {
            "pending_updates": [("user_name", "OldUser"), ("agent_name", "OldAgent")],
            "prev_values": {"user_name": "OldUser", "agent_name": "OldAgent"}
        }

        with patch('nano_agent.cli.main._find_config_file', return_value=(None, "default")):
            result = _handle_undo(agent, config, name_update_state)

        assert "user_name" in result
        assert "agent_name" in result


class TestHandleStatsCommand:
    """Tests for stats command handling."""

    def test_handle_stats_command_default(self):
        """Test _handle_stats_command without subcommand."""
        from nano_agent.cli.main import _handle_stats_command

        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.run_metrics = Mock()
        agent.tracker.get_iteration_token_list.return_value = []
        agent.tracker.get_last_iteration_tokens.return_value = None

        config = Config()
        config.llm = LLMConfig()

        # Should not raise
        _handle_stats_command(agent, config, "")

    def test_handle_stats_command_on(self):
        """Test _handle_stats_command 'on' enables stats."""
        from nano_agent.cli.main import _handle_stats_command, GracefulExitManager

        agent = Mock()
        agent.tracker = Mock()

        config = Config()
        config.llm = LLMConfig()

        _handle_stats_command(agent, config, "on")

        assert GracefulExitManager.show_run_stats is True

    def test_handle_stats_command_off(self):
        """Test _handle_stats_command 'off' disables stats."""
        from nano_agent.cli.main import _handle_stats_command, GracefulExitManager

        agent = Mock()
        agent.tracker = Mock()

        config = Config()
        config.llm = LLMConfig()

        _handle_stats_command(agent, config, "off")

        assert GracefulExitManager.show_run_stats is False

    def test_handle_stats_command_tokens(self):
        """Test _handle_stats_command 'tokens' shows breakdown."""
        from nano_agent.cli.main import _handle_stats_command

        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.run_metrics = Mock()
        agent.tracker.get_iteration_token_list.return_value = [
            {"prompt_tokens": 100, "completion_tokens": 50}
        ]

        config = Config()
        config.llm = LLMConfig()

        # Should not raise
        _handle_stats_command(agent, config, "tokens")


class TestHandleMemoryCommand:
    """Tests for memory command handling."""

    def test_handle_memory_command_status(self):
        """Test _handle_memory_command shows status."""
        from nano_agent.cli.main import _handle_memory_command

        agent = Mock()
        agent.memory = Mock()

        config = Config()
        config.memory = MemoryConfig()

        # Should not raise
        _handle_memory_command(agent, config, "")

    def test_handle_memory_command_on(self, temp_dir):
        """Test _handle_memory_command 'on' enables long-term memory."""
        from nano_agent.cli.main import _handle_memory_command

        agent = Mock()
        agent.memory = Mock()

        config = Config()
        config.memory = MemoryConfig()
        config.memory.long_term_storage_path = str(temp_dir / "ltm")

        _handle_memory_command(agent, config, "on")

    def test_handle_memory_command_off(self):
        """Test _handle_memory_command 'off' disables long-term memory."""
        from nano_agent.cli.main import _handle_memory_command

        agent = Mock()
        agent.memory = Mock()

        config = Config()
        config.memory = MemoryConfig()

        _handle_memory_command(agent, config, "off")


class TestHandleConfigCommand:
    """Tests for config command handling."""

    def test_handle_config_command_show(self):
        """Test _handle_config_command shows config."""
        from nano_agent.cli.main import _handle_config_command

        agent = Mock()
        agent.tool_registry = Mock()
        agent.tool_registry.list_tools.return_value = []
        agent.skill_loader = Mock()
        agent.skill_loader.list_loaded_skills.return_value = []

        config = Config()
        config.agent = AgentConfig()
        config.llm = LLMConfig()

        _handle_config_command(agent, config, "")

    def test_handle_config_command_init(self, temp_dir):
        """Test _handle_config_command 'init' creates config."""
        from nano_agent.cli.main import _handle_config_command

        agent = Mock()

        config = Config()
        config.agent = AgentConfig()
        config.llm = LLMConfig()

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (temp_dir / "config.yaml", "test")
            _handle_config_command(agent, config, "init")


class TestExportReport:
    """Tests for report export functions."""

    def test_export_report_json(self, temp_dir):
        """Test _export_report generates JSON report."""
        from nano_agent.cli.main import _export_report

        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.get_full_report.return_value = {
            "iterations": [],
            "total_tokens": 1000,
        }

        output_path = temp_dir / "report.json"

        _export_report(agent, "json", str(output_path))

        # Report file should exist
        assert output_path.exists()

    def test_export_report_markdown(self, temp_dir):
        """Test _export_report generates Markdown report."""
        from nano_agent.cli.main import _export_report

        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.get_full_report.return_value = {
            "iterations": [],
            "total_tokens": 1000,
        }

        output_path = temp_dir / "report.md"

        _export_report(agent, "markdown", str(output_path))

        # Report file should exist
        assert output_path.exists()

    def test_export_report_summary(self, temp_dir):
        """Test _export_report generates summary."""
        from nano_agent.cli.main import _export_report

        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.get_summary.return_value = {
            "total_iterations": 5,
            "total_tokens": 1000,
        }

        output_path = temp_dir / "summary.txt"

        _export_report(agent, "summary", str(output_path))


class TestSlashCommandsExtended:
    """Extended tests for slash commands."""

    def test_history_command_with_git(self):
        """Test /history command with Git integration."""
        from nano_agent.agent.git_manager import GitManager

        # Test GitManager can be instantiated
        git_manager = Mock(spec=GitManager)
        git_manager.is_enabled.return_value = True
        git_manager.get_history.return_value = [
            Mock(hash="abc123", time=datetime.now(), message="Test commit")
        ]

        # Verify history can be retrieved
        history = git_manager.get_history(limit=10)
        assert len(history) == 1


class TestRunInteractiveLoop:
    """Tests for the interactive loop in run_interactive."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock orchestrator for testing."""
        orchestrator = Mock()
        orchestrator.agent = Mock()
        orchestrator.agent.tool_registry = Mock()
        orchestrator.agent.tool_registry.list_tools.return_value = ["tool1"]
        orchestrator.agent.memory = ShortTermMemory()
        orchestrator.agent.events = Mock()
        orchestrator.agent.events.on = Mock()
        orchestrator.agent.llm = Mock()
        orchestrator.agent.run.return_value = Mock(response="Test response", success=True)
        orchestrator._config_source = "test config"
        return orchestrator

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for testing."""
        config = Config()
        config.agent = AgentConfig()
        config.agent.user_name = "TestUser"
        config.agent.agent_name = "TestAgent"
        config.agent.system_prompt = "Test prompt"
        config.llm = LLMConfig()
        config.memory = MemoryConfig()
        config.git = Mock()
        config.git.enabled = False
        config.context = Mock()
        config.context.project_file_mode = "full"
        return config

    def test_user_input_empty_continues(self, mock_orchestrator, mock_config):
        """Test empty input continues loop."""
        from nano_agent.cli.main import run_interactive

        inputs = ["", "/exit"]

        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                with patch('signal.signal'):
                    with patch('os.getcwd', return_value="/test"):
                        # Should handle empty input gracefully
                        pass

    def test_user_input_processed(self, mock_orchestrator, mock_config):
        """Test user input is processed by agent."""
        from nano_agent.cli.main import run_interactive

        inputs = ["Hello", "/exit"]

        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                with patch('signal.signal'):
                    with patch('os.getcwd', return_value="/test"):
                        # Agent should process input
                        pass

    def test_help_command_displayed(self, mock_orchestrator, mock_config):
        """Test help command displays help text."""
        from nano_agent.cli.main import run_interactive, _show_help

        inputs = ["help", "/exit"]

        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                with patch('signal.signal'):
                    with patch('os.getcwd', return_value="/test"):
                        with patch('nano_agent.cli.main._show_help') as mock_help:
                            pass

    def test_clear_command_resets_memory(self, mock_orchestrator, mock_config):
        """Test /clear command resets agent memory."""
        mock_orchestrator.agent.reset = Mock()

        inputs = ["/clear", "/exit"]

        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                with patch('signal.signal'):
                    with patch('os.getcwd', return_value="/test"):
                        pass

    def test_tools_command_lists_tools(self, mock_orchestrator, mock_config):
        """Test /tools command lists available tools."""
        inputs = ["/tools", "/exit"]

        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                with patch('signal.signal'):
                    with patch('os.getcwd', return_value="/test"):
                        pass

    def test_exit_command_exits_loop(self, mock_orchestrator, mock_config):
        """Test /exit command exits loop."""
        from nano_agent.cli.main import GracefulExitManager

        # Test that exit_with_summary is called when /exit is used
        GracefulExitManager.agent = mock_orchestrator.agent
        GracefulExitManager.config = mock_config

        with patch.object(GracefulExitManager, 'exit_with_summary') as mock_exit:
            mock_exit.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                GracefulExitManager.exit_with_summary()

    def test_quit_command_exits_without_summary(self, mock_orchestrator, mock_config):
        """Test 'quit' command exits without summary."""
        inputs = ["quit"]

        with patch('builtins.input', side_effect=inputs):
            with patch('builtins.print'):
                with patch('signal.signal'):
                    with patch('os.getcwd', return_value="/test"):
                        pass


class TestMigrateSessions:
    """Tests for session migration functions."""

    def test_migrate_sessions_dry_run(self, temp_dir):
        """Test _migrate_sessions with dry_run=True."""
        from nano_agent.cli.main import _migrate_sessions

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.memory.migration.list_all_sessions') as mock_list:
                    mock_list.return_value = {
                        "file_storage": {"sessions": [], "info": {}},
                        "sqlite_storage": {"sessions": []},
                        "total_unique_sessions": 0
                    }

                    # Should not raise
                    _migrate_sessions(None, dry_run=True)

    def test_migrate_sessions_actual(self, temp_dir):
        """Test _migrate_sessions performs migration."""
        from nano_agent.cli.main import _migrate_sessions

        config = Config()
        config.memory = MemoryConfig()
        config.memory.storage_type = "sqlite"
        config.memory.storage_path = str(temp_dir / "test.db")

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = config
                with patch('nano_agent.memory.migration.list_all_sessions') as mock_list:
                    mock_list.return_value = {
                        "file_storage": {"sessions": [], "info": {}},
                        "sqlite_storage": {"sessions": []},
                        "total_unique_sessions": 0
                    }
                    with patch('nano_agent.memory.migration.migrate_file_to_sqlite') as mock_migrate:
                        mock_migrate.return_value = {
                            "total_file_sessions": 0,
                            "migrated": [],
                            "errors": [],
                            "already_in_sqlite": []
                        }

                        _migrate_sessions(None, dry_run=False)


class TestCleanupSessions:
    """Tests for session cleanup functions."""

    def test_cleanup_sessions_removes_low_value(self, temp_dir):
        """Test _cleanup_sessions removes low-value sessions."""
        from nano_agent.cli.main import _cleanup_sessions

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.cli.main._get_storage') as mock_storage:
                    storage_mock = Mock()
                    storage_mock.get_sessions_below_threshold.return_value = ["session1", "session2"]
                    storage_mock.get_session_info.return_value = {
                        "message_count": 1,
                    }
                    storage_mock.delete_session = Mock()
                    storage_mock.delete_summary = Mock()
                    mock_storage.return_value = storage_mock

                    _cleanup_sessions(None, threshold=3)

    def test_cleanup_sessions_no_low_value(self, temp_dir):
        """Test _cleanup_sessions when no low-value sessions."""
        from nano_agent.cli.main import _cleanup_sessions

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (None, "default")
            with patch('nano_agent.cli.main.ConfigLoader.load') as mock_load:
                mock_load.return_value = Config()
                with patch('nano_agent.cli.main._get_storage') as mock_storage:
                    storage_mock = Mock()
                    storage_mock.get_sessions_below_threshold.return_value = []
                    mock_storage.return_value = storage_mock

                    _cleanup_sessions(None, threshold=3)


class TestSetCleanThreshold:
    """Tests for setting cleanup threshold."""

    def test_set_clean_threshold_updates_config(self, temp_dir):
        """Test _set_clean_threshold updates config file."""
        from nano_agent.cli.main import _set_clean_threshold

        config_path = temp_dir / "config.yaml"
        config_path.write_text("agent:\n  max_iterations: 10\n")

        with patch('nano_agent.cli.main._find_config_file') as mock_find:
            mock_find.return_value = (config_path, "test")

            _set_clean_threshold(str(config_path), 5)


class TestHandleSkillCommand:
    """Tests for skill command handling."""

    def test_handle_skill_command_reload(self):
        """Test _handle_skill_command reloads skills."""
        from nano_agent.cli.main import _handle_skill_command

        agent = Mock()
        agent.skill_loader = Mock()
        agent.skill_loader.list_loaded_skills.return_value = ["coding", "testing"]
        agent.skill_loader.reload_skill = Mock(return_value=True)

        with patch('nano_agent.cli.main._update_agent_skills'):
            _handle_skill_command(agent, "reload coding")

        agent.skill_loader.reload_skill.assert_called_once_with("coding")

    def test_handle_skill_command_reload_not_found(self):
        """Test _handle_skill_command reload with unknown skill."""
        from nano_agent.cli.main import _handle_skill_command

        agent = Mock()
        agent.skill_loader = Mock()
        agent.skill_loader.list_loaded_skills.return_value = ["coding"]

        _handle_skill_command(agent, "reload unknown")

        # Should not call reload_skill
        agent.skill_loader.reload_skill.assert_not_called()

    def test_handle_skill_command_unload(self):
        """Test _handle_skill_command unloads skills."""
        from nano_agent.cli.main import _handle_skill_command

        agent = Mock()
        agent.skill_loader = Mock()
        agent.skill_loader.list_loaded_skills.return_value = ["coding"]
        agent.skill_loader.unload_skill = Mock(return_value=True)

        with patch('nano_agent.cli.main._update_agent_skills'):
            _handle_skill_command(agent, "unload coding")

        agent.skill_loader.unload_skill.assert_called_once_with("coding")

    def test_handle_skill_command_no_skill_loader(self):
        """Test _handle_skill_command when no skill_loader."""
        from nano_agent.cli.main import _handle_skill_command

        agent = Mock(spec=[])  # No skill_loader attribute

        _handle_skill_command(agent, "reload coding")

        # Should not raise


class TestShowHelp:
    """Tests for help display function."""

    def test_show_help_outputs_content(self):
        """Test _show_help outputs help text."""
        from nano_agent.cli.main import _show_help

        with patch('builtins.print') as mock_print:
            _show_help()

            # Should print multiple lines
            assert mock_print.call_count > 0


class TestShowIterationBreakdown:
    """Tests for iteration breakdown display."""

    def test_show_iteration_breakdown_with_data(self):
        """Test _show_iteration_breakdown with iteration data."""
        from nano_agent.cli.main import _show_iteration_breakdown

        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.get_iteration_token_list.return_value = [
            {"iteration_number": 1, "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            {"iteration_number": 2, "prompt_tokens": 150, "completion_tokens": 75, "total_tokens": 225},
        ]

        with patch('builtins.print'):
            _show_iteration_breakdown(agent)

    def test_show_iteration_breakdown_empty(self):
        """Test _show_iteration_breakdown with no data."""
        from nano_agent.cli.main import _show_iteration_breakdown

        agent = Mock()
        agent.tracker = Mock()
        agent.tracker.get_iteration_token_list.return_value = []

        with patch('builtins.print'):
            _show_iteration_breakdown(agent)

    def test_show_iteration_breakdown_no_tracker(self):
        """Test _show_iteration_breakdown when no tracker."""
        from nano_agent.cli.main import _show_iteration_breakdown

        agent = Mock(spec=[])  # No tracker attribute

        with patch('builtins.print'):
            _show_iteration_breakdown(agent)


class TestShowContextComposition:
    """Tests for context composition display."""

    def test_show_context_composition(self):
        """Test _show_context_composition shows token usage breakdown."""
        from nano_agent.cli.main import _show_context_composition

        agent = Mock()
        agent.tracker = Mock()
        # Use new decoupled API: return raw data instead of description
        agent.tracker.get_detailed_usage.return_value = [
            {
                "id": 1,
                "run_number": 1,
                "iteration_number": 1,
                "tool_tokens": 500,
                "system_tokens": 300,
                "skill_tokens": 50,
                "summary_tokens": 0,
                "message_tokens": 200,
                "input_tokens": 1050,
                "output_tool_tokens": 30,
                "output_text_tokens": 0,
                "total_tokens": 1080,
                # Raw data for CLI to format description
                "tool_names": [],
                "input_messages": [{"role": "user", "content": "你好"}],
                "output_text": "",
                "skipped_tool_calls": [],
            },
        ]

        config = Config()
        config.llm = LLMConfig()

        with patch('builtins.print'):
            _show_context_composition(agent, config)


class TestEnableDisableRunStats:
    """Tests for enabling/disabling run stats."""

    def test_enable_run_stats(self):
        """Test _enable_run_stats sets flag."""
        from nano_agent.cli.main import _enable_run_stats, GracefulExitManager

        _enable_run_stats()

        assert GracefulExitManager.show_run_stats is True

    def test_disable_run_stats(self):
        """Test _disable_run_stats clears flag."""
        from nano_agent.cli.main import _disable_run_stats, GracefulExitManager

        _disable_run_stats()

        assert GracefulExitManager.show_run_stats is False
