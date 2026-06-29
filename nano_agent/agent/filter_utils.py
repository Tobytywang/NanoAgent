"""Shared utilities for guard/filter/validator modules.

Extracts common patterns from sanitizer, output_guard, harmful_filter,
and result_validator to eliminate code duplication.
"""

from .events import EventEmitter
from .types import AgentEvent


def summarize_by_field(items: list, field: str) -> str:
    """Summarize a list of objects by counting occurrences of a field value.

    Args:
        items: List of objects to summarize
        field: Attribute name to count by

    Returns:
        Comma-separated "key: count" string, sorted by key
    """
    counts: dict[str, int] = {}
    for item in items:
        key = getattr(item, field)
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))


def emit_blocked_event(
    emitter: EventEmitter | None,
    event_type: AgentEvent,
    data: dict,
) -> None:
    """Emit a blocked event if an event emitter is available.

    Args:
        emitter: Event emitter instance (or None)
        event_type: AgentEvent enum value to emit
        data: Event data dict
    """
    if emitter:
        emitter.emit(event_type, data)
