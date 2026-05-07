"""
Shell command execution tool with cross-platform support.
"""

import subprocess
import platform
from typing import Literal
from .base import BaseTool, ToolResult
from ..agent.types import RiskLevel


class ShellTool(BaseTool):
    """Tool for executing shell commands with cross-platform support."""

    name = "shell_execute"
    description = "Execute shell commands. Automatically adapts to the operating system (Windows/macOS/Linux)."
    risk_level = RiskLevel.DANGEROUS  # Can execute arbitrary commands

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30)",
                    "default": 30
                }
            },
            "required": ["command"]
        }

    def _get_platform(self) -> Literal["windows", "linux", "darwin"]:
        """Detect the current platform."""
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "darwin":
            return "darwin"
        else:
            return "linux"

    def execute(self, command: str, timeout: int = 30) -> ToolResult:
        """
        Execute a shell command.

        Args:
            command: Shell command to execute
            timeout: Execution timeout in seconds

        Returns:
            ToolResult with command output
        """
        try:
            current_platform = self._get_platform()

            # Choose shell based on platform
            if current_platform == "windows":
                # Windows: use PowerShell
                shell_args = ["powershell", "-Command", command]
            else:
                # Unix-like: use bash
                shell_args = ["/bin/bash", "-c", command]

            result = subprocess.run(
                shell_args,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Build output
            output_parts = []
            if result.stdout:
                output_parts.append(f"stdout:\n{result.stdout}")
            if result.stderr:
                output_parts.append(f"stderr:\n{result.stderr}")

            output = "\n".join(output_parts) or "Command completed (no output)"

            return ToolResult(
                success=result.returncode == 0,
                output=output,
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out ({timeout} seconds)"
            )
        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Shell not found: {e}"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
