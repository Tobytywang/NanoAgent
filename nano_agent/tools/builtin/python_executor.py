"""
Python code executor tool.
"""

import subprocess
import sys
import tempfile
from ..base import BaseTool, ToolResult
from ..standard_output import StandardToolOutput, OutputFormat
from ...agent.types import RiskLevel


class PythonExecutorTool(BaseTool):
    """Tool for executing Python code."""

    name = "python_execute"
    description = "Execute Python code and return the result. Useful for calculations, data processing, and algorithm implementation."
    risk_level = RiskLevel.DANGEROUS  # Can execute arbitrary code
    can_offload = True
    has_builtin_timeout = True  # Uses subprocess.run(timeout=...)

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The Python code to execute"},
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30)",
                    "default": 30,
                },
            },
            "required": ["code"],
        }

    def execute(self, code: str, timeout: int = 30) -> ToolResult:
        """
        Execute Python code in a subprocess.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds

        Returns:
            ToolResult with execution output or error
        """
        try:
            # Execute in a separate process for isolation
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tempfile.gettempdir(),
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                standard_output = StandardToolOutput(
                    format=OutputFormat.STATUS,
                    data={
                        "status": "success",
                        "output": output[:500],
                    },
                    summary="Code executed successfully",
                )
                return ToolResult(
                    success=True,
                    output=output or "Code executed successfully (no output)",
                    metadata={"standard_output": standard_output},
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Execution error: {result.stderr.strip()}",
                )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Execution timed out ({timeout} seconds)",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
