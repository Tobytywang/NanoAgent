"""
Input sanitizer - filters prompt injection patterns, validates input format,
and optionally desensitizes PII (Personally Identifiable Information).

Runs at the orchestrator boundary, before user input reaches the ReAct loop
or memory. This is a hard gate: injection patterns always reject; format
issues may truncate or reject depending on configuration; PII is masked
in-place so the agent never sees raw sensitive data.
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..config.schema import SanitizerConfig
from .types import AgentEvent

if TYPE_CHECKING:
    from .events import EventEmitter

# Pre-built translation table: maps control chars (0x00-0x1F except \t\n\r) to None
_CONTROL_CHAR_TABLE = str.maketrans(
    "", "", "".join(chr(i) for i in range(0x20) if chr(i) not in "\t\n\r")
)


def remove_overlapping(
    raw: list[tuple[int, int, str, str]],
) -> list[tuple[int, int, str, str]]:
    """Sort matches by position and remove overlaps, keeping longer spans."""
    sorted_raw = sorted(raw, key=lambda x: (x[0], -(x[1] - x[0])))
    filtered: list[tuple[int, int, str, str]] = []
    for item in sorted_raw:
        if not filtered or item[0] >= filtered[-1][1]:
            filtered.append(item)
        elif item[1] > filtered[-1][1] and (item[1] - item[0]) > (
            filtered[-1][1] - filtered[-1][0]
        ):
            filtered[-1] = item
    return filtered


@dataclass
class PIIMatch:
    """A single PII occurrence found in text."""

    pii_type: str
    start: int
    end: int
    original: str
    masked: str


def summarize_pii_matches(matches: list[PIIMatch]) -> str:
    """Build a human-readable summary of PII match counts by type."""
    from .filter_utils import summarize_by_field

    return summarize_by_field(matches, "pii_type")


class PIIDesensitizer:
    """
    PII desensitizer - detects and masks personally identifiable information.

    Supported PII types:
    - phone: Chinese mobile numbers (1xx-xxxx-xxxx)
    - id_card: Chinese national ID (18 digits with optional X)
    - email: Email addresses
    - api_key: Common API key / token patterns (Bearer, sk-, pk-, ghp_, etc.)
    """

    _PATTERNS: dict[str, str] = {
        "phone": r"1[3-9]\d{9}",
        "id_card": r"[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]",
        "email": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        "api_key": r"(?:Bearer\s+|sk-|pk-|ghp_|gho_|github_pat_|AKIA|AIza)[a-zA-Z0-9_\-]{16,}",
    }

    def __init__(self, config: SanitizerConfig):
        self._mask_char = config.pii_mask_char
        self._mask_mode = config.pii_mask_mode
        self._enabled_types = set(config.pii_types)
        self.compiled = {
            name: re.compile(pattern)
            for name, pattern in self._PATTERNS.items()
            if name in self._enabled_types
        }

    def desensitize(self, text: str) -> tuple[str, list[PIIMatch]]:
        """Find and mask PII in text. Returns (sanitized_text, matches)."""
        # Collect raw matches as (start, end, pii_type, original)
        raw: list[tuple[int, int, str, str]] = []
        for pii_type, pattern in self.compiled.items():
            for m in pattern.finditer(text):
                raw.append((m.start(), m.end(), pii_type, m.group()))

        if not raw:
            return text, []

        filtered_raw = remove_overlapping(raw)

        # Build PIIMatch objects only for surviving matches
        matches: list[PIIMatch] = []
        for start, end, pii_type, original in filtered_raw:
            masked = self._mask(original, pii_type)
            matches.append(
                PIIMatch(
                    pii_type=pii_type,
                    start=start,
                    end=end,
                    original=original,
                    masked=masked,
                )
            )

        # Replace from end to avoid offset shift
        for match in reversed(matches):
            text = text[: match.start] + match.masked + text[match.end :]

        return text, matches

    def _mask(self, value: str, pii_type: str) -> str:
        """Mask a single PII value based on mode."""
        if self._mask_mode == "full":
            return self._mask_char * len(value)

        # Partial masking: show head/tail, mask middle
        n = len(value)
        if pii_type == "phone":
            # 138****1234
            return value[:3] + self._mask_char * 4 + value[-4:]
        elif pii_type == "id_card":
            # 110***********1234
            return value[:3] + self._mask_char * (n - 7) + value[-4:]
        elif pii_type == "email":
            # u***@domain.com
            at = value.index("@")
            if at <= 1:
                return self._mask_char * at + value[at:]
            return value[0] + self._mask_char * (at - 1) + value[at:]
        elif pii_type == "api_key":
            # sk-****...****abcd
            if n <= 8:
                return self._mask_char * n
            prefix_len = min(3, n // 4)
            suffix_len = min(4, n // 4)
            return (
                value[:prefix_len]
                + self._mask_char * (n - prefix_len - suffix_len)
                + value[-suffix_len:]
            )
        else:
            # Generic: show first 2 and last 2 chars
            if n <= 4:
                return self._mask_char * n
            return value[:2] + self._mask_char * (n - 4) + value[-2:]


@dataclass
class SanitizerResult:
    """Result of input sanitization."""

    original_input: str
    sanitized_input: str
    rejected: bool
    reason: str | None
    actions_taken: list[str]
    pii_matches: list[PIIMatch] = field(default_factory=list)


class InputSanitizer:
    """
    Input sanitizer - filters prompt injection patterns, validates format,
    and optionally desensitizes PII.

    Processing order:
    1. Format validation (null bytes, control chars) -- may reject or clean
    2. PII desensitization (optional) -- masks sensitive data in-place
    3. Injection pattern matching -- always rejects on match
    4. Length validation -- truncates or rejects based on config
    """

    def __init__(self, config: SanitizerConfig, events: "EventEmitter | None" = None):
        self._config = config
        self._events = events
        self._compiled_patterns = [
            re.compile(p) for p in config.injection_patterns + config.custom_patterns
        ]
        self._pii_desensitizer: PIIDesensitizer | None = None
        if config.pii_enabled:
            self._pii_desensitizer = PIIDesensitizer(config)

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def sanitize(self, user_input: str) -> SanitizerResult:
        """Sanitize user input through format, PII, injection, and length checks."""
        actions: list[str] = []
        pii_matches: list[PIIMatch] = []
        current_input = user_input

        current_input, fmt_rejected, fmt_reason = self._check_format(
            current_input, actions
        )
        if fmt_rejected:
            return self._reject(user_input, current_input, fmt_reason, actions)

        # PII desensitization (before injection check so masked text is checked)
        if self._pii_desensitizer is not None:
            current_input, pii_matches = self._pii_desensitizer.desensitize(
                current_input
            )
            if pii_matches:
                actions.append(
                    f"pii_desensitized: {summarize_pii_matches(pii_matches)}"
                )

        is_injection, matched_pattern = self._check_injection(current_input)
        if is_injection:
            reason = f"Prompt injection pattern matched: {matched_pattern}"
            actions.append(reason)
            return self._reject(user_input, current_input, reason, actions)

        current_input, len_rejected, len_reason = self._check_length(
            current_input, actions
        )
        if len_rejected:
            return self._reject(user_input, current_input, len_reason, actions)

        return SanitizerResult(
            original_input=user_input,
            sanitized_input=current_input,
            rejected=False,
            reason=None,
            actions_taken=actions,
            pii_matches=pii_matches,
        )

    def _reject(
        self, original: str, sanitized: str, reason: str, actions: list[str]
    ) -> SanitizerResult:
        """Build a rejected result and emit event."""
        self._emit_rejection(original, reason)
        return SanitizerResult(
            original_input=original,
            sanitized_input=sanitized,
            rejected=True,
            reason=reason,
            actions_taken=actions,
            pii_matches=[],
        )

    def _check_format(
        self, user_input: str, actions: list[str]
    ) -> tuple[str, bool, str | None]:
        """Check for null bytes and control characters."""
        if self._config.reject_null_bytes and "\x00" in user_input:
            count = user_input.count("\x00")
            return user_input, True, f"Input contains {count} null byte(s)"

        if self._config.reject_control_chars:
            stripped = user_input.translate(_CONTROL_CHAR_TABLE)
            if len(stripped) < len(user_input):
                stripped_count = len(user_input) - len(stripped)
                actions.append(f"control_chars_stripped: {stripped_count} chars")
                return stripped, False, None

        return user_input, False, None

    def _check_injection(self, user_input: str) -> tuple[bool, str | None]:
        """Check for prompt injection patterns."""
        for pattern in self._compiled_patterns:
            match = pattern.search(user_input)
            if match:
                return True, match.group()
        return False, None

    def _check_length(
        self, user_input: str, actions: list[str]
    ) -> tuple[str, bool, str | None]:
        """Check and handle length limits."""
        if len(user_input) > self._config.max_input_length:
            if self._config.length_action == "reject":
                actions.append(
                    f"input_rejected: {len(user_input)} > {self._config.max_input_length} chars"
                )
                return (
                    user_input,
                    True,
                    f"Input too long: {len(user_input)} chars (max {self._config.max_input_length})",
                )
            else:
                original_len = len(user_input)
                user_input = user_input[: self._config.max_input_length]
                actions.append(
                    f"input_truncated: {original_len} -> {self._config.max_input_length} chars"
                )

        if self._config.max_line_length > 0:
            lines = user_input.split("\n")
            any_line_truncated = False
            for i, line in enumerate(lines):
                if len(line) > self._config.max_line_length:
                    lines[i] = line[: self._config.max_line_length] + "...[truncated]"
                    actions.append(
                        f"line_truncated: line {i + 1} ({len(line)} -> {self._config.max_line_length} chars)"
                    )
                    any_line_truncated = True
            if any_line_truncated:
                user_input = "\n".join(lines)

        return user_input, False, None

    def _emit_rejection(self, original_input: str, reason: str) -> None:
        """Emit INPUT_REJECTED event if event emitter is available."""
        if self._events:
            self._events.emit(
                AgentEvent.INPUT_REJECTED,
                {
                    "reason": reason,
                    "original_length": len(original_input),
                    "original_input_preview": original_input[:200],
                },
            )
