"""Aggressive output simplifier for LLM responses (v0.7.15)."""

import re
from typing import Optional

from nano_agent.config.schema import AggressiveOutputConfig


class OutputSimplifier:
    """Post-processes LLM responses to enforce output constraints."""

    EMOJI_PATTERN = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map
        "\U0001f1e0-\U0001f1ff"  # flags
        "\U00002702-\U000027b0"  # dingbats
        "\U000024c2-\U0001f251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "♀-♂"
        "☀-⭕"
        "‍"
        "⏏"
        "⏩"
        "⌚"
        "️"
        "〰"
        "]+",
        re.UNICODE,
    )

    TABLE_PATTERN = re.compile(r"(\|[^\n]+\|\n)+", re.MULTILINE)
    TABLE_SEPARATOR_PATTERN = re.compile(r"\|[-: ]+\|\n", re.MULTILINE)

    LIST_PATTERN = re.compile(r"^[•\-\*\d]+[.)\s].*$", re.MULTILINE)

    SENTENCE_ENDINGS = re.compile(r"[.!?。！？]+")

    def __init__(self, config: AggressiveOutputConfig):
        self.config = config

    def simplify(self, response: str) -> str:
        if not self.config.enabled or not response:
            return response

        text = response

        if self.config.strip_emoji:
            text = self.EMOJI_PATTERN.sub("", text)

        if self.config.strip_markdown_tables:
            text = self.TABLE_SEPARATOR_PATTERN.sub("", text)
            text = self.TABLE_PATTERN.sub("", text)

        if self.config.strip_markdown_lists:
            text = self.LIST_PATTERN.sub("", text)
            text = re.sub(r"\n{3,}", "\n\n", text)

        if self.config.max_response_sentences > 0:
            text = self._truncate_sentences(text, self.config.max_response_sentences)

        if (
            self.config.max_response_chars > 0
            and len(text) > self.config.max_response_chars
        ):
            text = text[: self.config.max_response_chars].rstrip()
            if not text.endswith((".", "。", "!", "！", "?", "？")):
                text += "..."

        return text.strip()

    def _truncate_sentences(self, text: str, max_sentences: int) -> str:
        sentences = self.SENTENCE_ENDINGS.split(text)
        sentences = [s for s in sentences if s.strip()]

        if len(sentences) <= max_sentences:
            return text

        kept = sentences[:max_sentences]
        result = ""
        pos = 0
        for i, sent in enumerate(sentences[:max_sentences]):
            idx = text.find(sent, pos)
            if idx == -1:
                result += sent
            else:
                end = idx + len(sent)
                while end < len(text) and text[end] in ".!?。！？":
                    end += 1
                result += text[pos:end]
                pos = end

        return result.strip()

    @classmethod
    def from_level(cls, level: str) -> "OutputSimplifier":
        """Factory: create simplifier from preset level."""
        level_configs = {
            "mild": AggressiveOutputConfig(
                enabled=True,
                level="mild",
                max_response_sentences=3,
                strip_emoji=True,
                strip_markdown_tables=True,
                strip_markdown_lists=False,
                max_response_chars=0,
            ),
            "aggressive": AggressiveOutputConfig(
                enabled=True,
                level="aggressive",
                max_response_sentences=1,
                strip_emoji=True,
                strip_markdown_tables=True,
                strip_markdown_lists=True,
                max_response_chars=0,
            ),
            "extreme": AggressiveOutputConfig(
                enabled=True,
                level="extreme",
                max_response_sentences=1,
                strip_emoji=True,
                strip_markdown_tables=True,
                strip_markdown_lists=True,
                max_response_chars=200,
            ),
        }
        config = level_configs.get(level, level_configs["mild"])
        return cls(config)
