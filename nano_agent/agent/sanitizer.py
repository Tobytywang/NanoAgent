"""
Input sanitizer - filters prompt injection patterns and validates input format.

Runs at the orchestrator boundary, before user input reaches the ReAct loop
or memory. This is a hard gate: injection patterns always reject; format
issues may truncate or reject depending on configuration.
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


@dataclass
class SanitizerResult:
    """Result of input sanitization."""

    original_input: str
    sanitized_input: str
    rejected: bool
    reason: str | None
    actions_taken: list[str]


class InputSanitizer:
    """
    Input sanitizer - filters prompt injection patterns and validates format.

    Processing order:
    1. Format validation (null bytes, control chars) -- may reject or clean
    2. Injection pattern matching -- always rejects on match
    3. Length validation -- truncates or rejects based on config
    """

    def __init__(self, config: SanitizerConfig, events: "EventEmitter | None" = None):
        self._config = config
        self._events = events
        self._compiled_patterns = [
            re.compile(p) for p in config.injection_patterns + config.custom_patterns
        ]

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def sanitize(self, user_input: str) -> SanitizerResult:
        """Sanitize user input through format, injection, and length checks."""
        actions: list[str] = []
        current_input = user_input

        current_input, fmt_rejected, fmt_reason = self._check_format(
            current_input, actions
        )
        if fmt_rejected:
            return self._reject(user_input, current_input, fmt_reason, actions)

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
