"""
Provider-specific message/response normalizers.

Each provider's API has minor differences in message format and SSE streaming
behavior.  Normalizers encapsulate these differences so the core LLM client
does not need provider-specific branches.
"""


class MessageNormalizer:
    """Base normalizer — no-op for standard OpenAI-compatible providers."""

    def normalize_request_messages(self, messages: list[dict]) -> list[dict]:
        """Adjust outgoing messages before sending to the API.

        May modify messages in-place or return a new list.
        """
        return messages

    def normalize_stream_delta(
        self, delta: dict, partial_calls: dict[int, dict]
    ) -> None:
        """Adjust an incoming SSE delta during streaming.

        *delta* is the ``choices[0].delta`` dict from a single SSE event.
        *partial_calls* maps tool_call index to accumulated call state
        ``{idx: {"id": str, "name": str, "arguments_parts": list[str]}}``.
        Mutate *partial_calls* in-place as needed.
        """
        pass


class OpenAINormalizer(MessageNormalizer):
    """Standard OpenAI format — no adjustments needed."""

    pass


class DeepSeekNormalizer(MessageNormalizer):
    """DeepSeek V4 reasoning model.

    DeepSeek requires ``reasoning_content`` on any assistant message that
    carries ``tool_calls``.  Old or cross-model messages lack this field;
    inject an empty string to satisfy the check.
    """

    def normalize_request_messages(self, messages: list[dict]) -> list[dict]:
        for m in messages:
            if (
                m.get("role") == "assistant"
                and "tool_calls" in m
                and "reasoning_content" not in m
            ):
                m["reasoning_content"] = ""
        return messages


class XfyunNormalizer(MessageNormalizer):
    """讯飞星火 (iFlytek Spark).

    Their SSE delta format sends *all* fields on every event, resetting
    ``id`` and ``name`` to ``""`` on subsequent deltas for the same tool
    call index.  The standard accumulation logic treats any present key
    as a new value, so the correctly-set name from the first delta gets
    overwritten.

    Fix: skip id/name updates when the incoming value is empty.
    """

    def normalize_stream_delta(
        self, delta: dict, partial_calls: dict[int, dict]
    ) -> None:
        if "tool_calls" not in delta:
            return
        for tc_delta in delta["tool_calls"]:
            idx = tc_delta.get("index", 0)
            if idx not in partial_calls:
                continue  # not yet initialised — let the core code handle it
            # Only update when the new value is non-empty
            if tc_delta.get("id"):
                partial_calls[idx]["id"] = tc_delta["id"]
            func = tc_delta.get("function", {})
            if func.get("name"):
                partial_calls[idx]["name"] = func["name"]


# Map — matched against ``model.lower()``
NORMALIZER_MAP: list[tuple[str, MessageNormalizer]] = [
    ("deepseek", DeepSeekNormalizer()),
    ("astron", XfyunNormalizer()),
    ("spark", XfyunNormalizer()),
]


def select_normalizer(model: str) -> MessageNormalizer:
    """Pick the right normalizer for *model*, falling back to OpenAI."""
    lower = model.lower()
    for key, normalizer in NORMALIZER_MAP:
        if key in lower:
            return normalizer
    return OpenAINormalizer()
