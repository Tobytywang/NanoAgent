"""
Project scanner for generating NANOPROJECT.md.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


class ProjectScanner:
    """Scan project and generate summary."""

    # Directories to skip during scanning
    SKIP_DIRS = {
        ".git", ".svn", ".hg",
        "__pycache__", ".pytest_cache", ".mypy_cache",
        "node_modules", "venv", ".venv", "env",
        ".idea", ".vscode", ".nano_agent",
        "dist", "build", "*.egg-info",
    }

    # Files to include for project info
    INFO_FILES = {
        "README.md", "README.rst", "README.txt",
        "pyproject.toml", "setup.py", "requirements.txt",
        "package.json", "Cargo.toml", "go.mod",
        "Makefile", "Dockerfile", "docker-compose.yml",
    }

    def __init__(self, project_root: Path | None = None):
        """
        Initialize scanner.

        Args:
            project_root: Project root directory, defaults to cwd
        """
        self.project_root = project_root or Path.cwd()
        self.project_name = self.project_root.name

    def scan(self) -> dict[str, Any]:
        """
        Scan the project and collect information.

        Returns:
            Dictionary with project information
        """
        info = {
            "project_name": self.project_name,
            "scan_time": datetime.now().isoformat(),
            "structure": self._scan_structure(),
            "tech_stack": self._detect_tech_stack(),
            "git_info": self._get_git_info(),
            "documents": self._scan_documents(),
            "code_summary": self._scan_code(),
        }
        return info

    def _scan_structure(self) -> dict[str, Any]:
        """Scan project directory structure."""
        structure = {
            "directories": [],
            "files": [],
            "total_files": 0,
            "total_dirs": 0,
        }

        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden and excluded directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in self.SKIP_DIRS]

            rel_root = Path(root).relative_to(self.project_root)

            for d in dirs:
                structure["directories"].append(str(rel_root / d))
                structure["total_dirs"] += 1

            for f in files:
                if not f.startswith("."):
                    structure["files"].append(str(rel_root / f))
                    structure["total_files"] += 1

        # Limit to top directories
        structure["top_dirs"] = sorted(set(
            d.split("/")[0] for d in structure["directories"] if "/" in d or d
        ))[:20]

        return structure

    def _detect_tech_stack(self) -> list[str]:
        """Detect technology stack from config files."""
        tech = []

        # Python
        if (self.project_root / "pyproject.toml").exists():
            tech.append("Python (pyproject.toml)")
        elif (self.project_root / "setup.py").exists():
            tech.append("Python (setup.py)")
        elif (self.project_root / "requirements.txt").exists():
            tech.append("Python (requirements.txt)")

        # Node.js
        if (self.project_root / "package.json").exists():
            tech.append("Node.js")

        # Rust
        if (self.project_root / "Cargo.toml").exists():
            tech.append("Rust")

        # Go
        if (self.project_root / "go.mod").exists():
            tech.append("Go")

        # Docker
        if (self.project_root / "Dockerfile").exists():
            tech.append("Docker")

        # Make
        if (self.project_root / "Makefile").exists():
            tech.append("Make")

        return tech

    def _get_git_info(self) -> dict[str, Any]:
        """Get Git repository information."""
        git_info = {
            "is_git_repo": False,
            "branch": None,
            "recent_commits": [],
            "remote": None,
        }

        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            return git_info

        git_info["is_git_repo"] = True

        try:
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                git_info["branch"] = result.stdout.strip()

            # Get recent commits
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                git_info["recent_commits"] = [
                    line.strip() for line in result.stdout.strip().split("\n") if line.strip()
                ]

            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                git_info["remote"] = result.stdout.strip()

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return git_info

    def _scan_documents(self) -> dict[str, str]:
        """Scan documentation files."""
        docs = {}

        # README
        readme_path = self.project_root / "README.md"
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                # Extract first 500 chars as summary
                docs["readme_preview"] = content[:500] + "..." if len(content) > 500 else content
            except Exception:
                pass

        # docs directory
        docs_dir = self.project_root / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            docs["docs_files"] = [
                f.name for f in docs_dir.iterdir()
                if f.is_file() and f.suffix in [".md", ".rst", ".txt"]
            ]

        return docs

    def _scan_code(self) -> dict[str, Any]:
        """Scan code files for summary."""
        code_info = {
            "languages": {},
            "main_files": [],
            "entry_points": [],
        }

        # Language extensions
        lang_exts = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
        }

        # Entry point patterns
        entry_patterns = ["main.py", "app.py", "__main__.py", "index.js", "main.go"]

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in self.SKIP_DIRS]

            for f in files:
                ext = Path(f).suffix
                if ext in lang_exts:
                    lang = lang_exts[ext]
                    code_info["languages"][lang] = code_info["languages"].get(lang, 0) + 1

                if f in entry_patterns:
                    rel_path = Path(root).relative_to(self.project_root) / f
                    code_info["entry_points"].append(str(rel_path))

        return code_info

    def generate_markdown(self, info: dict[str, Any] | None = None) -> str:
        """
        Generate NANOPROJECT.md content.

        Args:
            info: Project info dict, if None will scan

        Returns:
            Markdown content
        """
        if info is None:
            info = self.scan()

        lines = [
            f"# {info['project_name']} - Project Summary",
            "",
            f"> Generated by NanoAgent on {info['scan_time'][:19]}",
            "",
            "---",
            "",
            "## Tech Stack",
            "",
        ]

        if info["tech_stack"]:
            for tech in info["tech_stack"]:
                lines.append(f"- {tech}")
        else:
            lines.append("_No detected technology stack_")

        lines.extend(["", "---", "", "## Project Structure", ""])

        structure = info["structure"]
        lines.append(f"- **Total files**: {structure['total_files']}")
        lines.append(f"- **Total directories**: {structure['total_dirs']}")

        if structure["top_dirs"]:
            lines.append("")
            lines.append("**Main directories**:")
            for d in structure["top_dirs"]:
                lines.append(f"- `{d}/`")

        # Git info
        git = info["git_info"]
        if git["is_git_repo"]:
            lines.extend(["", "---", "", "## Git Information", ""])
            if git["branch"]:
                lines.append(f"- **Branch**: `{git['branch']}`")
            if git["remote"]:
                lines.append(f"- **Remote**: {git['remote']}")

            if git["recent_commits"]:
                lines.append("")
                lines.append("**Recent commits**:")
                for commit in git["recent_commits"][:5]:
                    lines.append(f"  - {commit}")

        # Entry points
        if info["code_summary"]["entry_points"]:
            lines.extend(["", "---", "", "## Entry Points", ""])
            for ep in info["code_summary"]["entry_points"]:
                lines.append(f"- `{ep}`")

        # Documents
        docs = info["documents"]
        if docs.get("docs_files"):
            lines.extend(["", "---", "", "## Documentation", ""])
            for doc in docs["docs_files"]:
                lines.append(f"- `docs/{doc}`")

        # Code languages
        languages = info["code_summary"]["languages"]
        if languages:
            lines.extend(["", "---", "", "## Code Statistics", ""])
            for lang, count in sorted(languages.items(), key=lambda x: -x[1]):
                lines.append(f"- **{lang}**: {count} files")

        lines.extend(["", "---", "", "## Notes", "", "_Add your project notes here..._", ""])

        return "\n".join(lines)

    def save(self, path: Path | None = None, info: dict[str, Any] | None = None) -> Path:
        """
        Save NANOPROJECT.md to file.

        Args:
            path: Output path, defaults to project_root/NANOPROJECT.md
            info: Project info, if None will scan

        Returns:
            Path to saved file
        """
        if path is None:
            path = self.project_root / "NANOPROJECT.md"

        content = self.generate_markdown(info)
        path.write_text(content, encoding="utf-8")
        return path

    def is_new_project(self) -> bool:
        """
        Check if this is a new project (not yet scanned).

        Returns:
            True if NANOPROJECT.md or .nano_agent/ doesn't exist
        """
        nanoproject = self.project_root / "NANOPROJECT.md"
        nano_agent = self.project_root / ".nano_agent"

        return not (nanoproject.exists() and nano_agent.exists())
