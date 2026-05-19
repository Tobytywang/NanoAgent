"""
Intent detection for dynamic module activation.

Detects user intent from input to determine which prompt modules should be activated.
"""

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class IntentKeywords:
    """Keywords for intent detection."""

    # Git operations keywords (ClassVar to avoid mutable default issues)
    GIT_STATUS: ClassVar[list[str]] = [
        "提交", "commit", "push", "pull", "merge",
        "分支", "branch", "checkout", "rebase",
        "git", "clone", "fetch", "diff", "log",
        "stash", "reset", "tag", "blame"
    ]

    # Environment keywords (ClassVar to avoid mutable default issues)
    ENVIRONMENT: ClassVar[list[str]] = [
        "环境变量", "env", "配置文件", "config",
        ".env", "settings", "setting", "配置",
        "变量", "dotenv", "环境"
    ]


class IntentDetector:
    """Simple intent detector using keyword matching.

    Detects user intent from input text to determine which
    prompt modules (git_status, environment) should be activated.
    """

    def __init__(self, custom_keywords: dict[str, list[str]] | None = None):
        """Initialize intent detector.

        Args:
            custom_keywords: Optional custom keywords to override defaults
        """
        self.keywords = {
            "git_status": IntentKeywords.GIT_STATUS,
            "environment": IntentKeywords.ENVIRONMENT,
        }

        # Override with custom keywords if provided
        if custom_keywords:
            for intent, words in custom_keywords.items():
                if intent in self.keywords:
                    self.keywords[intent] = words
                else:
                    self.keywords[intent] = words

    def detect(self, user_input: str) -> set[str]:
        """Detect intents from user input.

        Args:
            user_input: User input text

        Returns:
            Set of detected intent names (e.g., {"git_status", "environment"})
        """
        detected = set()
        user_input_lower = user_input.lower()

        for intent, keywords in self.keywords.items():
            if any(kw.lower() in user_input_lower for kw in keywords):
                detected.add(intent)

        return detected

    def should_activate_module(self, module_name: str, user_input: str) -> bool:
        """Check if a specific module should be activated.

        Args:
            module_name: Module name to check (e.g., "git_status")
            user_input: User input text

        Returns:
            True if the module should be activated
        """
        detected = self.detect(user_input)
        return module_name in detected

    def add_keywords(self, intent: str, keywords: list[str]) -> None:
        """Add keywords for an intent.

        Args:
            intent: Intent name
            keywords: Keywords to add
        """
        if intent not in self.keywords:
            self.keywords[intent] = []
        self.keywords[intent].extend(keywords)

    def remove_keywords(self, intent: str, keywords: list[str]) -> None:
        """Remove keywords from an intent.

        Args:
            intent: Intent name
            keywords: Keywords to remove
        """
        if intent in self.keywords:
            self.keywords[intent] = [
                kw for kw in self.keywords[intent]
                if kw not in keywords
            ]

    def get_keywords(self, intent: str) -> list[str]:
        """Get keywords for an intent.

        Args:
            intent: Intent name

        Returns:
            List of keywords for the intent
        """
        return self.keywords.get(intent, [])