"""
Translation Skill Example

A Python skill that provides translation capabilities.
"""

from nano_agent.skills.base import BaseSkill
from nano_agent.tools.base import BaseTool, ToolResult


class TranslateTool(BaseTool):
    """Translation tool (demo - uses simple word replacement)"""

    name = "translate"
    description = "Translate text between languages (demo implementation)"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to translate"},
                "source_lang": {
                    "type": "string",
                    "description": "Source language code (e.g., 'en', 'zh')",
                },
                "target_lang": {
                    "type": "string",
                    "description": "Target language code (e.g., 'en', 'zh')",
                },
            },
            "required": ["text", "target_lang"],
        }

    def execute(
        self, text: str, target_lang: str, source_lang: str = "auto"
    ) -> ToolResult:
        """
        Translate text between languages.

        Note: This is a demo implementation. In production, you would
        integrate with a real translation API like Google Translate,
        DeepL, or a local model.
        """
        # Demo: Just return the text with a prefix
        # In production, call a real translation service
        result = f"[{target_lang.upper()}] {text}"
        return ToolResult(success=True, output=f"Translated to {target_lang}: {result}")


class Skill(BaseSkill):
    """Translation skill with custom tool"""

    name = "translation"
    description = "Translation skill for multi-language support"

    @property
    def system_prompt(self) -> str:
        return """
You are a translation assistant.

Your capabilities:
- Translate text between languages
- Detect source language automatically
- Preserve formatting and structure

Always use the translate tool for translation requests.
Provide the original text alongside translations when helpful.
"""

    @property
    def tools(self) -> list[BaseTool]:
        return [TranslateTool()]

    def setup(self, config: dict | None = None) -> None:
        """Initialize the translation skill"""
        self.config = config or {}
        # In production: initialize translation API client
        print(f"Translation skill initialized with config: {self.config}")

    def teardown(self) -> None:
        """Cleanup resources"""
        print("Translation skill torn down")
