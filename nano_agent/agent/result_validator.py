"""
Result correctness validator - verifies agent output against reality.

Runs at the orchestrator boundary, after OutputGuard and HarmfulContentFilter
have processed the response. This validator performs lightweight checks to
detect common falsehoods in agent output:

- file_exists: Agent claims a file was created/modified → verify the path exists
- code_syntax: Agent claims code is correct → verify syntax (Python/JSON/YAML)
- command_success: Agent claims a command succeeded → verify exit code patterns

Default: disabled (opt-in). Validation is conservative — it only flags
clearly verifiable falsehoods, not ambiguous claims.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ..config.schema import ResultValidatorConfig
from .types import AgentEvent

if TYPE_CHECKING:
    from .events import EventEmitter

logger = logging.getLogger(__name__)

# Patterns that indicate the agent is claiming a file operation
_FILE_CLAIM_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?i)(?:created|wrote|saved|written|generated)\s+(?:file\s+)?[`'\"]?([^\s`'\"]+)"
    ),
    re.compile(
        r"(?i)(?:file\s+)(?:created|written|saved|generated)\s*[`:]\s*([^\s`'\"]+)"
    ),
    re.compile(r"(?i)(?:saved\s+to|written\s+to|output\s+to)\s+[`'\"]?([^\s`'\"]+)"),
    # Chinese patterns
    re.compile(r"(?:已保存到|已写入|已生成|已创建)\s*[`'\"]?([^\s`'\"]+)"),
]

# Patterns that indicate the agent is claiming code correctness
_CODE_CLAIM_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?i)(?:code|script|function|module|json|yaml|config)\s+(?:is|compiles|runs|works)\s+(?:correct|fine|ok|successfully|without\s+errors?|valid)"
    ),
    re.compile(
        r"(?i)(?:no\s+)?(?:syntax\s+)?errors?\s+(?:found|detected|in\s+(?:the\s+)?(?:code|json|yaml|config))"
    ),
    re.compile(
        r"(?i)(?:compiles?|runs?|executes?|valid(?:ates?)?)\s+(?:successfully|without\s+errors?|cleanly)"
    ),
    # Chinese
    re.compile(r"代码(?:正确|没有错误|运行正常)"),
    re.compile(r"语法(?:正确|没有错误|有效)"),
]

# Patterns for extracting code blocks from response
_CODE_BLOCK_RE = re.compile(r"```(\w+)?\s*\n(.*?)```", re.DOTALL)

# Exit code pattern for command success contradiction detection
_EXIT_CODE_RE = re.compile(
    r"(?:exit\s+code|return\s+code)\s*[:=]?\s*(\d+)", re.IGNORECASE
)

# Patterns that indicate the agent is claiming a command succeeded
_COMMAND_CLAIM_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?i)(?:command|cmd|script)\s+(?:executed|ran|completed|finished)\s+(?:successfully|without\s+errors?|with\s+exit\s+code\s+0)"
    ),
    re.compile(r"(?i)(?:execution|operation)\s+(?:completed|finished|succeeded)"),
    re.compile(r"(?i)exit\s+code\s*[:=]?\s*0"),
]


@dataclass
class ValidationCheck:
    """A single validation check result."""

    check_type: str  # "file_exists", "code_syntax", "command_success"
    claim: str  # What the agent claimed
    passed: bool  # Whether the claim verified
    detail: str  # Human-readable explanation
    severity: Literal["high", "medium", "low"] = "medium"


@dataclass
class ValidationResult:
    """Result of output validation."""

    original: str
    validated: str
    blocked: bool
    reason: str | None
    checks: list[ValidationCheck]
    failed_checks: list[ValidationCheck]
    actions_taken: list[str]


def summarize_validation_checks(checks: list[ValidationCheck]) -> str:
    """Build a human-readable summary of validation check counts by type."""
    type_counts: dict[str, int] = {}
    for c in checks:
        type_counts[c.check_type] = type_counts.get(c.check_type, 0) + 1
    return ", ".join(f"{t}: {n}" for t, n in sorted(type_counts.items()))


class ResultValidator:
    """
    Validates agent output against verifiable reality.

    Performs lightweight checks to catch common falsehoods:
    - file_exists: Verify claimed file paths exist
    - code_syntax: Verify claimed-correct code actually parses
    - command_success: Verify claimed success patterns

    When a check fails, the validator can:
    - block: Block the entire response (for high-severity failures)
    - warn: Append a warning to the response
    - annotate: Append verification notes without blocking
    """

    def __init__(
        self, config: ResultValidatorConfig, events: "EventEmitter | None" = None
    ):
        self._config = config
        self._events = events
        self._enabled_checks = set(config.checks)

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def validate(self, response_text: str) -> ValidationResult:
        """Validate agent output against verifiable claims."""
        checks: list[ValidationCheck] = []

        if "file_exists" in self._enabled_checks:
            checks.extend(self._check_file_claims(response_text))

        if "code_syntax" in self._enabled_checks:
            checks.extend(self._check_code_claims(response_text))

        if "command_success" in self._enabled_checks:
            checks.extend(self._check_command_claims(response_text))

        # Run custom validators
        for validator in self._config.custom_validators:
            try:
                result = validator(response_text)
                if result is not None:
                    checks.append(result)
            except Exception as e:
                logger.warning("Custom validator failed: %s", e)

        failed = [c for c in checks if not c.passed]

        if not checks:
            return ValidationResult(
                original=response_text,
                validated=response_text,
                blocked=False,
                reason=None,
                checks=checks,
                failed_checks=[],
                actions_taken=[],
            )

        # Determine action based on failures
        if not failed:
            validated = (
                self._annotate_passed(response_text, checks)
                if self._config.on_pass == "annotate"
                else response_text
            )
            return ValidationResult(
                original=response_text,
                validated=validated,
                blocked=False,
                reason=None,
                checks=checks,
                failed_checks=[],
                actions_taken=["validation_passed"],
            )

        # Some checks failed
        high_severity_fails = [c for c in failed if c.severity == "high"]

        if self._config.on_fail == "block" and high_severity_fails:
            summary = summarize_validation_checks(high_severity_fails)
            self._emit_blocked(response_text, failed, summary)
            return ValidationResult(
                original=response_text,
                validated="",
                blocked=True,
                reason=f"Validation failed: {summary}",
                checks=checks,
                failed_checks=failed,
                actions_taken=[f"validation_blocked: {summary}"],
            )

        if self._config.on_fail == "warn":
            warning = self._build_warning(failed)
            failed_summary = summarize_validation_checks(failed)
            return ValidationResult(
                original=response_text,
                validated=f"{response_text}\n\n{warning}",
                blocked=False,
                reason=f"Validation warnings: {failed_summary}",
                checks=checks,
                failed_checks=failed,
                actions_taken=[f"validation_warning: {failed_summary}"],
            )

        # Default: annotate
        annotation = self._build_annotation(failed)
        failed_summary = summarize_validation_checks(failed)
        return ValidationResult(
            original=response_text,
            validated=f"{response_text}\n\n{annotation}",
            blocked=False,
            reason=None,
            checks=checks,
            failed_checks=failed,
            actions_taken=[f"validation_annotated: {failed_summary}"],
        )

    def scan_tool_output(self, output: str) -> str:
        """Scan tool output for validation. Returns output unchanged (validation is for agent responses, not tool output)."""
        return output

    def _check_file_claims(self, text: str) -> list[ValidationCheck]:
        """Check if claimed file paths actually exist."""
        checks: list[ValidationCheck] = []
        seen_paths: set[str] = set()

        for pattern in _FILE_CLAIM_PATTERNS:
            for m in pattern.finditer(text):
                path_str = m.group(1).strip("`'\"")
                # Skip obviously non-path strings
                if len(path_str) < 2 or path_str in seen_paths:
                    continue
                # Skip URLs and inline content
                if path_str.startswith(("http://", "https://", "data:")):
                    continue
                seen_paths.add(path_str)

                path = Path(path_str)
                exists = path.exists()
                checks.append(
                    ValidationCheck(
                        check_type="file_exists",
                        claim=f"File created: {path_str}",
                        passed=exists,
                        detail=f"Path {'exists' if exists else 'does not exist'}: {path_str}",
                        severity="high",
                    )
                )

        return checks

    def _check_code_claims(self, text: str) -> list[ValidationCheck]:
        """Check if claimed-correct code actually has valid syntax."""
        # Quick pre-check: skip if no code blocks or no correctness claims
        if "```" not in text:
            return []

        has_correctness_claim = any(p.search(text) for p in _CODE_CLAIM_PATTERNS)
        if not has_correctness_claim:
            return []

        checks: list[ValidationCheck] = []

        for m in _CODE_BLOCK_RE.finditer(text):
            lang = (m.group(1) or "").lower()
            code = m.group(2).strip()
            if not code:
                continue

            if lang == "python":
                check = self._validate_python_syntax(code)
                if check:
                    checks.append(check)
            elif lang == "json":
                check = self._validate_json_syntax(code)
                if check:
                    checks.append(check)
            elif lang in ("yaml", "yml"):
                check = self._validate_yaml_syntax(code)
                if check:
                    checks.append(check)

        return checks

    def _validate_python_syntax(self, code: str) -> ValidationCheck | None:
        """Validate Python code syntax."""
        try:
            compile(code, "<agent_output>", "exec")
            return ValidationCheck(
                check_type="code_syntax",
                claim="Python code is correct",
                passed=True,
                detail="Python syntax is valid",
                severity="medium",
            )
        except SyntaxError as e:
            return ValidationCheck(
                check_type="code_syntax",
                claim="Python code is correct",
                passed=False,
                detail=f"SyntaxError: {e.msg} (line {e.lineno})",
                severity="medium",
            )

    def _validate_json_syntax(self, code: str) -> ValidationCheck | None:
        """Validate JSON syntax."""
        try:
            json.loads(code)
            return ValidationCheck(
                check_type="code_syntax",
                claim="JSON is correct",
                passed=True,
                detail="JSON syntax is valid",
                severity="medium",
            )
        except json.JSONDecodeError as e:
            return ValidationCheck(
                check_type="code_syntax",
                claim="JSON is correct",
                passed=False,
                detail=f"JSONDecodeError: {e.msg} (line {e.lineno}, col {e.colno})",
                severity="medium",
            )

    def _validate_yaml_syntax(self, code: str) -> ValidationCheck | None:
        """Validate YAML syntax (best-effort, requires pyyaml)."""
        try:
            import yaml

            yaml.safe_load(code)
            return ValidationCheck(
                check_type="code_syntax",
                claim="YAML is correct",
                passed=True,
                detail="YAML syntax is valid",
                severity="medium",
            )
        except ImportError:
            return None
        except Exception as e:
            return ValidationCheck(
                check_type="code_syntax",
                claim="YAML is correct",
                passed=False,
                detail=f"YAML error: {e}",
                severity="medium",
            )

    def _check_command_claims(self, text: str) -> list[ValidationCheck]:
        """Check command success claims.

        This is a soft check — we can't re-run commands, but we can
        detect contradictions (e.g., claiming success but showing
        non-zero exit code in the output).
        """
        has_claim = any(p.search(text) for p in _COMMAND_CLAIM_PATTERNS)
        if not has_claim:
            return []

        # Scan exit codes once for the entire text
        exit_codes = _EXIT_CODE_RE.findall(text)
        non_zero = [ec for ec in exit_codes if ec != "0"]

        if non_zero:
            return [
                ValidationCheck(
                    check_type="command_success",
                    claim="Command succeeded",
                    passed=False,
                    detail=f"Claimed success but found exit code(s): {', '.join(non_zero)}",
                    severity="high",
                )
            ]

        return [
            ValidationCheck(
                check_type="command_success",
                claim="Command succeeded",
                passed=True,
                detail="No contradictory exit codes found",
                severity="low",
            )
        ]

    def _annotate_passed(self, text: str, checks: list[ValidationCheck]) -> str:
        """Append a passed-validation note to the response."""
        passed_count = len(checks)
        types = summarize_validation_checks(checks)
        return f"{text}\n\n[Validation: {passed_count} check(s) passed ({types})]"

    def _build_warning(self, failed: list[ValidationCheck]) -> str:
        """Build a warning message for failed checks."""
        lines = ["[Validation Warning]"]
        for c in failed:
            lines.append(f"  - {c.claim}: {c.detail}")
        return "\n".join(lines)

    def _build_annotation(self, failed: list[ValidationCheck]) -> str:
        """Build an annotation for failed checks."""
        lines = ["[Validation Note]"]
        for c in failed:
            icon = "x" if c.severity == "high" else "!"
            lines.append(f"  [{icon}] {c.claim}: {c.detail}")
        return "\n".join(lines)

    def _emit_blocked(
        self, original: str, failed: list[ValidationCheck], summary: str
    ) -> None:
        """Emit events for blocked validation."""
        if self._events:
            self._events.emit(
                AgentEvent.VALIDATION_FAILED,
                {
                    "action": "blocked",
                    "reason": f"Validation failed: {summary}",
                    "original_length": len(original),
                    "failed_count": len(failed),
                    "failed_summary": summary,
                },
            )
            self._events.emit(
                AgentEvent.OUTPUT_BLOCKED,
                {
                    "reason": f"Validation failed: {summary}",
                    "original_length": len(original),
                    "failed_count": len(failed),
                    "filter_type": "result_validator",
                },
            )
