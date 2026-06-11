"""
Output guard - intercepts sensitive information in agent output.

Runs at the orchestrator boundary, after the agent produces a response
but before it is returned to the user. This is the output-side mirror
of InputSanitizer: where the sanitizer protects what goes *in*, the
output guard protects what comes *out*.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from ..config.schema import OutputGuardConfig, SanitizerConfig
from .sanitizer import PIIDesensitizer, remove_overlapping
from .types import AgentEvent

if TYPE_CHECKING:
    from .events import EventEmitter

logger = logging.getLogger(__name__)

# Output-specific patterns (not covered by PIIDesensitizer)
_OUTPUT_PATTERNS: dict[str, str] = {
    "password": r"(?i)(?:password|passwd|pwd|secret|token)\s*[:=]\s*\S+",
    "private_key": r"-----BEGIN\s+(?:RSA\s+|DSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----",
    "connection_string": r"(?i)(?:mysql|postgres|postgresql|mongodb|redis)://[^\s\"']+",
}


# Pre-compiled regex for masking (avoids re-compilation per _mask() call)
_PASSWORD_SEP_RE = re.compile(r"(?i)(password|passwd|pwd|secret|token)(\s*[:=]\s*)")
_CONNECTION_STRING_RE = re.compile(
    r"(?i)((?:mysql|postgres|postgresql|mongodb|redis)://[^:@]+)(:[^@]+)(@.*)"
)


@dataclass
class SensitiveMatch:
    sensitive_type: str
    start: int
    end: int
    original: str
    masked: str
    severity: Literal["mask", "block"]


@dataclass
class OutputGuardResult:
    original: str
    guarded: str
    blocked: bool
    reason: str | None
    matches: list[SensitiveMatch]
    actions_taken: list[str]


def summarize_sensitive_matches(matches: list[SensitiveMatch]) -> str:
    """Build a human-readable summary of sensitive match counts by type."""
    type_counts: dict[str, int] = {}
    for m in matches:
        type_counts[m.sensitive_type] = type_counts.get(m.sensitive_type, 0) + 1
    return ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items()))


class OutputGuard:
    """
    Scans agent output for sensitive information.

    Supports three actions:
    - mask: Mask sensitive data in-place (default)
    - block: Block the entire response if sensitive data is found
    - warn: Allow the response but log a warning
    """

    def __init__(self, config: OutputGuardConfig, events: "EventEmitter | None" = None):
        self._config = config
        self._events = events
        self._mask_char = config.mask_char
        self._mask_mode = config.mask_mode
        self._block_severity = set(config.block_severity)

        # Reuse PIIDesensitizer for PII pattern compilation and masking
        pii_types = set(config.sensitive_types) & set(PIIDesensitizer._PATTERNS.keys())
        pii_config = SanitizerConfig(
            pii_enabled=True,
            pii_mask_char=config.mask_char,
            pii_mask_mode=config.mask_mode,
            pii_types=sorted(pii_types),
        )
        self._pii_desensitizer = PIIDesensitizer(pii_config)
        self._pii_patterns = self._pii_desensitizer.compiled

        # Compile output-specific patterns
        output_types = set(config.sensitive_types) & set(_OUTPUT_PATTERNS.keys())
        self._output_patterns: dict[str, re.Pattern] = {
            name: re.compile(_OUTPUT_PATTERNS[name]) for name in output_types
        }

        # Compile custom patterns
        self._custom_patterns: dict[str, re.Pattern] = {}
        for entry in config.custom_patterns:
            name = entry.get("name", "custom")
            pattern = entry.get("pattern", "")
            if pattern:
                try:
                    self._custom_patterns[name] = re.compile(pattern)
                except re.error:
                    logger.warning(
                        "Invalid custom pattern '%s' for type '%s', ignored",
                        pattern,
                        name,
                    )

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def guard(self, response_text: str) -> OutputGuardResult:
        """Scan response for sensitive data and apply guard action."""
        matches = self._find_all_matches(response_text)

        if not matches:
            return OutputGuardResult(
                original=response_text,
                guarded=response_text,
                blocked=False,
                reason=None,
                matches=[],
                actions_taken=[],
            )

        # Block-severity matches always trigger blocking
        block_matches = [m for m in matches if m.severity == "block"]
        if block_matches or self._config.action == "block":
            blocked_matches = block_matches or matches
            types = summarize_sensitive_matches(blocked_matches)
            self._emit_blocked(response_text, blocked_matches, types)
            prefix = "high-severity " if block_matches else ""
            return OutputGuardResult(
                original=response_text,
                guarded="",
                blocked=True,
                reason=f"Output contains {prefix}sensitive data: {types}",
                matches=blocked_matches,
                actions_taken=[f"output_blocked: {types}"],
            )

        if self._config.action == "warn":
            types = summarize_sensitive_matches(matches)
            return OutputGuardResult(
                original=response_text,
                guarded=response_text,
                blocked=False,
                reason=f"Sensitive data detected: {types}",
                matches=matches,
                actions_taken=[f"output_warning: {types}"],
            )

        # Default: mask
        guarded_text = self._apply_masking(response_text, matches)
        types = summarize_sensitive_matches(matches)
        return OutputGuardResult(
            original=response_text,
            guarded=guarded_text,
            blocked=False,
            reason=None,
            matches=matches,
            actions_taken=[f"output_masked: {types}"],
        )

    def scan_tool_output(self, output: str) -> str:
        """Scan tool output for sensitive data and mask in-place."""
        matches = self._find_all_matches(output)
        if not matches:
            return output
        return self._apply_masking(output, matches)

    def _find_all_matches(self, text: str) -> list[SensitiveMatch]:
        """Find all sensitive data matches in text."""
        raw: list[tuple[int, int, str, str]] = []

        for pii_type, pattern in self._pii_patterns.items():
            for m in pattern.finditer(text):
                raw.append((m.start(), m.end(), pii_type, m.group()))

        for sensitive_type, pattern in self._output_patterns.items():
            for m in pattern.finditer(text):
                raw.append((m.start(), m.end(), sensitive_type, m.group()))

        for custom_type, pattern in self._custom_patterns.items():
            for m in pattern.finditer(text):
                raw.append((m.start(), m.end(), custom_type, m.group()))

        if not raw:
            return []

        filtered_raw = remove_overlapping(raw)

        matches: list[SensitiveMatch] = []
        for start, end, sensitive_type, original in filtered_raw:
            masked = self._mask(original, sensitive_type)
            severity: Literal["mask", "block"] = (
                "block" if sensitive_type in self._block_severity else "mask"
            )
            matches.append(
                SensitiveMatch(
                    sensitive_type=sensitive_type,
                    start=start,
                    end=end,
                    original=original,
                    masked=masked,
                    severity=severity,
                )
            )

        return matches

    def _apply_masking(self, text: str, matches: list[SensitiveMatch]) -> str:
        """Replace matches from end to avoid offset shift."""
        for match in reversed(matches):
            text = text[: match.start] + match.masked + text[match.end :]
        return text

    def _mask(self, value: str, sensitive_type: str) -> str:
        """Mask a single sensitive value based on type and mode."""
        if self._mask_mode == "full":
            return self._mask_char * len(value)

        n = len(value)
        if sensitive_type in ("phone", "id_card", "email", "api_key"):
            return self._pii_desensitizer._mask(value, sensitive_type)

        if sensitive_type == "password":
            sep_match = _PASSWORD_SEP_RE.match(value)
            if sep_match:
                return sep_match.group(1) + sep_match.group(2) + self._mask_char * 4
            return self._mask_char * n

        if sensitive_type == "private_key":
            return "[PRIVATE KEY REDACTED]"

        if sensitive_type == "connection_string":
            cs_match = _CONNECTION_STRING_RE.match(value)
            if cs_match:
                return cs_match.group(1) + ":****" + cs_match.group(3)
            return self._mask_char * n

        if n <= 4:
            return self._mask_char * n
        return value[:2] + self._mask_char * (n - 4) + value[-2:]

    def _emit_blocked(
        self, original: str, matches: list[SensitiveMatch], types: str
    ) -> None:
        """Emit OUTPUT_BLOCKED event if event emitter is available."""
        if self._events:
            self._events.emit(
                AgentEvent.OUTPUT_BLOCKED,
                {
                    "reason": f"Sensitive data detected: {types}",
                    "original_length": len(original),
                    "match_count": len(matches),
                    "match_types": types,
                },
            )
