"""
Harmful content filter - intercepts harmful/dangerous content in agent output.

Runs at the orchestrator boundary, after OutputGuard has processed the response.
Where OutputGuard prevents information *leakage*, this filter prevents *harmful
content* from reaching the user — violence instructions, hate speech, dangerous
activities, illegal content, etc.

Default: disabled (opt-in). The definition of "harmful" varies by context,
so users must explicitly enable and configure categories.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from ..config.schema import HarmfulContentFilterConfig
from .sanitizer import remove_overlapping
from .types import AgentEvent

if TYPE_CHECKING:
    from .events import EventEmitter

logger = logging.getLogger(__name__)

# Default harmful content patterns per category.
# Patterns are deliberately conservative — they target explicit instructional
# phrases (e.g. "how to make a bomb", "step-by-step suicide") rather than
# mere discussion keywords, to avoid false positives.
_HARMFUL_PATTERNS: dict[str, dict] = {
    "violence": {
        "severity": "high",
        "patterns": [
            # English: explicit violence/threat instructions
            r"(?i)how\s+to\s+(?:make|build|create|manufacture)\s+(?:a\s+)?(?:bomb|explosive|weapon|gun|firearm)",
            r"(?i)instructions?\s+for\s+(?:making|building|creating)\s+(?:explosives|bombs|weapons)",
            r"(?i)step[- ]by[- ]step\s+(?:bomb|weapon|explosive|poison)\s+(?:making|creation|construction)",
            r"(?i)\bkill\s+(?:yourself|your\s+self|him|her|them|people)\s+(?:with|using|by)\b",
            r"(?i)\bcommit\s+(?:murder|assault|arson|violent\s+crime)\b",
            # Chinese
            r"如何制造(?:炸弹|武器|枪支|爆炸物)",
            r"如何制作(?:炸弹|武器|枪支|爆炸物)",
            r"炸弹制作步骤",
            r"武器制造方法",
            r"杀人(?:方法|手段|技巧)",
        ],
    },
    "hate": {
        "severity": "high",
        "patterns": [
            # English: hate speech with violent/discriminatory intent
            r"(?i)\bhate\s+(?:speech|group)\b.*\b(?:kill|attack|destroy|eliminate)\b",
            r"(?i)\b(?:superior|inferior)\s+race\b.*\b(?:should|must|deserve)\b",
            r"(?i)\b(?:ethnic|racial)\s+(?:purification|cleansing|extermination)\b",
            # Chinese
            r"种族(?:歧视|清洗|灭绝).*(?:攻击|消灭|杀死)",
            r"仇恨(?:言论|组织).*(?:攻击|消灭|杀死)",
        ],
    },
    "dangerous": {
        "severity": "high",
        "patterns": [
            # English: dangerous/self-harm/cyberattack instructions
            r"(?i)how\s+to\s+(?:commit|do)\s+suicide",
            r"(?i)suicide\s+(?:methods|instructions|guide|techniques)",
            r"(?i)self[- ]harm\s+(?:methods|instructions|techniques|guide)",
            r"(?i)how\s+to\s+(?:synthesize|make|create|manufacture)\s+(?:meth|fentanyl|drugs|cocaine|heroin)",
            r"(?i)step[- ]by[- ]step\s+(?:hack|cyberattack|malware|ransomware)\s+(?:guide|tutorial|instructions)",
            r"(?i)how\s+to\s+(?:hack|breach|exploit|intrude)\s+into\s+(?:a\s+)?(?:system|server|database|network|computer)",
            # Chinese
            r"自杀(?:方法|指南|步骤|手段)",
            r"自残(?:方法|指南|步骤|手段)",
            r"如何合成(?:毒品|冰毒|芬太尼|可卡因|海洛因)",
            r"毒品(?:制作|合成|制造)方法",
            r"黑客(?:攻击|入侵)步骤",
            r"入侵(?:系统|服务器|数据库|网络)方法",
        ],
    },
    "illegal": {
        "severity": "medium",
        "patterns": [
            # English: illegal activity instructions
            r"(?i)how\s+to\s+(?:launder|laundering)\s+money",
            r"(?i)(?:money\s+laundering|laundering)\s+(?:methods|strategies|guide|techniques)",
            r"(?i)tax\s+evasion\s+(?:methods|strategies|guide|techniques|instructions)",
            r"(?i)how\s+to\s+(?:forge|counterfeit)\s+(?:money|documents|IDs|currency|bills)",
            r"(?i)identity\s+theft\s+(?:guide|instructions|methods|techniques|tutorial)",
            # Chinese
            r"洗钱(?:方法|手段|技巧|指南)",
            r"逃税(?:方法|手段|技巧|指南)",
            r"如何(?:伪造|仿造)(?:货币|证件|文件|身份证)",
            r"身份(?:盗窃|冒用)方法",
        ],
    },
}


@dataclass
class HarmfulMatch:
    """A single harmful content occurrence found in text."""

    category: str
    start: int
    end: int
    original: str
    severity: Literal["high", "medium"]


@dataclass
class HarmfulFilterResult:
    """Result of harmful content filtering."""

    original: str
    filtered: str
    blocked: bool
    warned: bool
    reason: str | None
    matches: list[HarmfulMatch]
    actions_taken: list[str]


def summarize_harmful_matches(matches: list[HarmfulMatch]) -> str:
    """Build a human-readable summary of harmful match counts by category."""
    cat_counts: dict[str, int] = {}
    for m in matches:
        cat_counts[m.category] = cat_counts.get(m.category, 0) + 1
    return ", ".join(f"{c}: {n}" for c, n in sorted(cat_counts.items()))


class HarmfulContentFilter:
    """
    Filters harmful/dangerous content in agent output.

    Supports three actions per category:
    - block: Block the entire response
    - warn: Allow the response with a warning prefix
    - replace: Replace harmful segments with safe substitution text

    When any category's action is "block", the whole response is blocked
    regardless of other categories' actions (block takes precedence).
    """

    def __init__(
        self, config: HarmfulContentFilterConfig, events: "EventEmitter | None" = None
    ):
        self._config = config
        self._events = events

        # Compile enabled category patterns
        enabled_categories = set(config.categories)
        self._patterns: dict[str, list[tuple[re.Pattern, str]]] = {}
        for cat_name, cat_def in _HARMFUL_PATTERNS.items():
            if cat_name in enabled_categories:
                compiled = []
                for pattern_str in cat_def["patterns"]:
                    try:
                        compiled.append((re.compile(pattern_str), cat_def["severity"]))
                    except re.error:
                        logger.warning(
                            "Invalid harmful pattern for '%s': %s",
                            cat_name,
                            pattern_str,
                        )
                self._patterns[cat_name] = compiled

        # Compile custom patterns (merge into same dict)
        for entry in config.custom_patterns:
            cat_name = entry.get("category", "custom")
            severity = entry.get("severity", "medium")
            pattern = entry.get("pattern", "")
            if pattern:
                try:
                    compiled = re.compile(pattern)
                    if cat_name not in self._patterns:
                        self._patterns[cat_name] = []
                    self._patterns[cat_name].append((compiled, severity))
                except re.error:
                    logger.warning(
                        "Invalid custom harmful pattern '%s', ignored", pattern
                    )

        # Build category→action map
        self._category_actions: dict[str, str] = {}
        for cat_name in enabled_categories:
            self._category_actions[cat_name] = config.category_actions.get(
                cat_name, config.default_action
            )
        for entry in config.custom_patterns:
            cat_name = entry.get("category", "custom")
            self._category_actions[cat_name] = config.category_actions.get(
                cat_name, config.default_action
            )

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def filter(self, response_text: str) -> HarmfulFilterResult:
        """Check response for harmful content and apply configured action."""
        matches = self._find_all_matches(response_text)

        if not matches:
            return HarmfulFilterResult(
                original=response_text,
                filtered=response_text,
                blocked=False,
                warned=False,
                reason=None,
                matches=[],
                actions_taken=[],
            )

        # Determine actions — block takes precedence over warn/replace
        block_cats = {
            m.category
            for m in matches
            if self._category_actions.get(m.category, self._config.default_action)
            == "block"
        }
        warn_cats = {
            m.category
            for m in matches
            if self._category_actions.get(m.category, self._config.default_action)
            == "warn"
        }
        replace_cats = {
            m.category
            for m in matches
            if self._category_actions.get(m.category, self._config.default_action)
            == "replace"
        }

        if block_cats:
            categories_str = summarize_harmful_matches(
                [m for m in matches if m.category in block_cats]
            )
            self._emit_blocked(response_text, matches, categories_str)
            return HarmfulFilterResult(
                original=response_text,
                filtered="",
                blocked=True,
                warned=False,
                reason=f"Output contains harmful content: {categories_str}",
                matches=matches,
                actions_taken=[f"harmful_blocked: {categories_str}"],
            )

        result_text = response_text
        warned = False
        actions: list[str] = []

        if replace_cats:
            replace_matches = [m for m in matches if m.category in replace_cats]
            result_text = self._apply_replacement(result_text, replace_matches)
            categories_str = summarize_harmful_matches(replace_matches)
            actions.append(f"harmful_replaced: {categories_str}")

        if warn_cats:
            categories_str = summarize_harmful_matches(
                [m for m in matches if m.category in warn_cats]
            )
            warned = True
            actions.append(f"harmful_warning: {categories_str}")
            result_text = f"[Content Warning: {categories_str}] {result_text}"

        return HarmfulFilterResult(
            original=response_text,
            filtered=result_text,
            blocked=False,
            warned=warned,
            reason=(
                f"Harmful content detected: {summarize_harmful_matches(matches)}"
                if matches
                else None
            ),
            matches=matches,
            actions_taken=actions,
        )

    def scan_tool_output(self, output: str) -> str:
        """Scan tool output for harmful content. Returns output with replacements only."""
        matches = self._find_all_matches(output)
        if not matches:
            return output
        return self._apply_replacement(output, matches)

    def _find_all_matches(self, text: str) -> list[HarmfulMatch]:
        """Find all harmful content matches in text."""
        raw: list[tuple[int, int, str, str]] = []

        for cat_name, patterns in self._patterns.items():
            for pattern, severity in patterns:
                for m in pattern.finditer(text):
                    raw.append((m.start(), m.end(), cat_name, severity))

        if not raw:
            return []

        filtered_raw = remove_overlapping(raw)

        return [
            HarmfulMatch(
                category=cat_name,
                start=start,
                end=end,
                original=text[start:end],
                severity=severity,  # type: ignore
            )
            for start, end, cat_name, severity in filtered_raw
        ]

    def _apply_replacement(self, text: str, matches: list[HarmfulMatch]) -> str:
        """Replace harmful segments from end to avoid offset shift."""
        replacement = self._config.replacement_text
        for match in reversed(matches):
            text = text[: match.start] + replacement + text[match.end :]
        return text

    def _emit_blocked(
        self, original: str, matches: list[HarmfulMatch], categories: str
    ) -> None:
        """Emit events for blocked harmful content."""
        if self._events:
            self._events.emit(
                AgentEvent.HARMFUL_CONTENT_DETECTED,
                {
                    "action": "blocked",
                    "reason": f"Harmful content detected: {categories}",
                    "original_length": len(original),
                    "match_count": len(matches),
                    "match_categories": categories,
                },
            )
            self._events.emit(
                AgentEvent.OUTPUT_BLOCKED,
                {
                    "reason": f"Harmful content detected: {categories}",
                    "original_length": len(original),
                    "match_count": len(matches),
                    "match_categories": categories,
                    "filter_type": "harmful_content",
                },
            )
