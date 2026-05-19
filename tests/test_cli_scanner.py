"""
Tests for CLI scanner module.

Tests the project scanning functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

pytestmark = pytest.mark.unit

from nano_agent.cli.scanner import ProjectScanner


class TestProjectScanner:
    """Tests for ProjectScanner class."""

    def test_initialization_default_path(self):
        """Test scanner initializes with current directory."""
        with patch('nano_agent.cli.scanner.Path.cwd') as mock_cwd:
            mock_cwd.return_value = Path("/test/project")

            scanner = ProjectScanner()

            assert scanner.project_root == Path("/test/project")

    def test_initialization_custom_path(self, temp_dir):
        """Test scanner initializes with custom path."""
        scanner = ProjectScanner(project_root=temp_dir)

        assert scanner.project_root == temp_dir

    def test_scan_returns_complete_info(self, temp_dir):
        """Test scan() returns all expected fields."""
        scanner = ProjectScanner(project_root=temp_dir)

        info = scanner.scan()

        assert "project_name" in info
        assert "scan_time" in info
        assert "structure" in info
        assert "tech_stack" in info
        assert "git_info" in info
        assert "documents" in info
        assert "code_summary" in info

    def test_scan_structure(self, temp_dir):
        """Test _scan_structure returns correct structure."""
        # Create some directories and files
        (temp_dir / "src").mkdir()
        (temp_dir / "tests").mkdir()
        (temp_dir / "src" / "main.py").write_text("# main")
        (temp_dir / "README.md").write_text("# Test Project")

        scanner = ProjectScanner(project_root=temp_dir)

        structure = scanner._scan_structure()

        assert "directories" in structure
        assert "files" in structure
        assert "total_files" in structure
        assert "total_dirs" in structure
        assert structure["total_files"] >= 2
        assert structure["total_dirs"] >= 2

    def test_scan_structure_skips_hidden_dirs(self, temp_dir):
        """Test _scan_structure skips hidden directories."""
        # Create hidden directory
        (temp_dir / ".hidden").mkdir()
        (temp_dir / ".hidden" / "file.txt").write_text("hidden")

        scanner = ProjectScanner(project_root=temp_dir)

        structure = scanner._scan_structure()

        # Hidden directory should not be in the list
        assert not any(".hidden" in d for d in structure["directories"])

    def test_scan_structure_skips_excluded_dirs(self, temp_dir):
        """Test _scan_structure skips configured directories."""
        # Create excluded directory
        (temp_dir / "node_modules").mkdir()
        (temp_dir / "node_modules" / "package.js").write_text("// package")

        scanner = ProjectScanner(project_root=temp_dir)

        structure = scanner._scan_structure()

        # node_modules should not be in the list
        assert not any("node_modules" in d for d in structure["directories"])

    def test_detect_tech_stack_python(self, temp_dir):
        """Test _detect_tech_stack detects Python project."""
        (temp_dir / "pyproject.toml").write_text("[project]\nname = 'test'")

        scanner = ProjectScanner(project_root=temp_dir)

        tech = scanner._detect_tech_stack()

        assert "Python (pyproject.toml)" in tech

    def test_detect_tech_stack_nodejs(self, temp_dir):
        """Test _detect_tech_stack detects Node.js project."""
        (temp_dir / "package.json").write_text('{"name": "test"}')

        scanner = ProjectScanner(project_root=temp_dir)

        tech = scanner._detect_tech_stack()

        assert "Node.js" in tech

    def test_detect_tech_stack_rust(self, temp_dir):
        """Test _detect_tech_stack detects Rust project."""
        (temp_dir / "Cargo.toml").write_text('[package]\nname = "test"')

        scanner = ProjectScanner(project_root=temp_dir)

        tech = scanner._detect_tech_stack()

        assert "Rust" in tech

    def test_detect_tech_stack_go(self, temp_dir):
        """Test _detect_tech_stack detects Go project."""
        (temp_dir / "go.mod").write_text("module test")

        scanner = ProjectScanner(project_root=temp_dir)

        tech = scanner._detect_tech_stack()

        assert "Go" in tech

    def test_detect_tech_stack_docker(self, temp_dir):
        """Test _detect_tech_stack detects Docker."""
        (temp_dir / "Dockerfile").write_text("FROM python:3.10")

        scanner = ProjectScanner(project_root=temp_dir)

        tech = scanner._detect_tech_stack()

        assert "Docker" in tech

    def test_detect_tech_stack_multiple(self, temp_dir):
        """Test _detect_tech_stack detects multiple technologies."""
        (temp_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        (temp_dir / "Dockerfile").write_text("FROM python:3.10")

        scanner = ProjectScanner(project_root=temp_dir)

        tech = scanner._detect_tech_stack()

        assert "Python (pyproject.toml)" in tech
        assert "Docker" in tech

    def test_get_git_info_in_repo(self, temp_dir):
        """Test _get_git_info in a git repository."""
        scanner = ProjectScanner(project_root=temp_dir)

        # Mock git directory
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch('subprocess.run') as mock_run:
            # Mock successful git commands
            mock_run.return_value = Mock(
                returncode=0,
                stdout="main\n"
            )

            git_info = scanner._get_git_info()

            assert git_info["is_git_repo"] is True

    def test_get_git_info_not_in_repo(self, temp_dir):
        """Test _get_git_info outside git repository."""
        scanner = ProjectScanner(project_root=temp_dir)

        git_info = scanner._get_git_info()

        assert git_info["is_git_repo"] is False
        assert git_info["branch"] is None

    def test_get_git_info_handles_timeout(self, temp_dir):
        """Test _get_git_info handles git command timeout."""
        scanner = ProjectScanner(project_root=temp_dir)

        # Mock git directory
        git_dir = temp_dir / ".git"
        git_dir.mkdir()

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

            git_info = scanner._get_git_info()

            assert git_info["is_git_repo"] is True
            assert git_info["branch"] is None

    def test_scan_documents_reads_readme(self, temp_dir):
        """Test _scan_documents reads README.md."""
        readme = temp_dir / "README.md"
        readme.write_text("# Test Project\n\nThis is a test project.")

        scanner = ProjectScanner(project_root=temp_dir)

        docs = scanner._scan_documents()

        assert "readme_preview" in docs
        assert "Test Project" in docs["readme_preview"]

    def test_scan_documents_handles_missing_readme(self, temp_dir):
        """Test _scan_documents handles missing README."""
        scanner = ProjectScanner(project_root=temp_dir)

        docs = scanner._scan_documents()

        # Should not crash, may have empty or no readme_preview
        assert isinstance(docs, dict)

    def test_scan_documents_finds_docs_dir(self, temp_dir):
        """Test _scan_documents finds docs directory."""
        docs_dir = temp_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "api.md").write_text("# API")
        (docs_dir / "guide.md").write_text("# Guide")

        scanner = ProjectScanner(project_root=temp_dir)

        docs = scanner._scan_documents()

        assert "docs_files" in docs
        assert "api.md" in docs["docs_files"]
        assert "guide.md" in docs["docs_files"]

    def test_scan_code_counts_languages(self, temp_dir):
        """Test _scan_code counts files per language."""
        (temp_dir / "main.py").write_text("# main")
        (temp_dir / "utils.py").write_text("# utils")
        (temp_dir / "app.js").write_text("// app")

        scanner = ProjectScanner(project_root=temp_dir)

        code_info = scanner._scan_code()

        assert code_info["languages"].get("Python", 0) >= 2
        assert code_info["languages"].get("JavaScript", 0) >= 1

    def test_scan_code_finds_entry_points(self, temp_dir):
        """Test _scan_code identifies entry point files."""
        (temp_dir / "main.py").write_text("# main")

        scanner = ProjectScanner(project_root=temp_dir)

        code_info = scanner._scan_code()

        assert "main.py" in code_info["entry_points"]

    def test_generate_markdown_creates_valid_output(self, temp_dir):
        """Test generate_markdown creates valid markdown."""
        scanner = ProjectScanner(project_root=temp_dir)

        info = scanner.scan()
        markdown = scanner.generate_markdown(info)

        assert "# " in markdown
        assert "## Tech Stack" in markdown
        assert "## Project Structure" in markdown

    def test_generate_markdown_includes_all_sections(self, temp_dir):
        """Test generate_markdown includes all expected sections."""
        (temp_dir / "pyproject.toml").write_text("[project]\nname = 'test'")
        (temp_dir / "README.md").write_text("# Test")

        scanner = ProjectScanner(project_root=temp_dir)

        markdown = scanner.generate_markdown()

        assert "## Tech Stack" in markdown
        assert "## Project Structure" in markdown
        assert "## Notes" in markdown

    def test_save_creates_file(self, temp_dir):
        """Test save() creates NANOPROJECT.md file."""
        scanner = ProjectScanner(project_root=temp_dir)

        output_path = scanner.save()

        assert output_path.exists()
        assert output_path.name == "NANOPROJECT.md"

    def test_save_custom_path(self, temp_dir):
        """Test save() with custom output path."""
        scanner = ProjectScanner(project_root=temp_dir)
        custom_path = temp_dir / "custom_output.md"

        scanner.save(path=custom_path)

        assert custom_path.exists()

    def test_is_new_project_true(self, temp_dir):
        """Test is_new_project() returns True for new projects."""
        scanner = ProjectScanner(project_root=temp_dir)

        result = scanner.is_new_project()

        assert result is True

    def test_is_new_project_false(self, temp_dir):
        """Test is_new_project() returns False for existing projects."""
        # Create NANOPROJECT.md and .nano_agent/
        (temp_dir / "NANOPROJECT.md").write_text("# Project")
        nano_dir = temp_dir / ".nano_agent"
        nano_dir.mkdir()

        scanner = ProjectScanner(project_root=temp_dir)

        result = scanner.is_new_project()

        assert result is False


class TestProjectScannerIntegration:
    """Integration tests for ProjectScanner."""

    @pytest.mark.integration
    def test_scan_real_project(self):
        """Test scanning actual NanoAgent project."""
        # Use the current project directory
        project_root = Path(__file__).parent.parent

        scanner = ProjectScanner(project_root=project_root)
        info = scanner.scan()

        assert info["project_name"] is not None
        assert len(info["tech_stack"]) > 0
        assert "Python" in str(info["tech_stack"])

    @pytest.mark.integration
    def test_generate_markdown_real_project(self):
        """Test generating markdown for actual project."""
        project_root = Path(__file__).parent.parent

        scanner = ProjectScanner(project_root=project_root)
        markdown = scanner.generate_markdown()

        assert "# " in markdown
        assert "Python" in markdown
