"""
Tests for HarmfulContentFilter - harmful content filtering in agent output.
"""

import pytest

from nano_agent.agent.harmful_filter import (
    HarmfulContentFilter,
    HarmfulFilterResult,
    HarmfulMatch,
    summarize_harmful_matches,
    _HARMFUL_PATTERNS,
)
from nano_agent.agent.types import AgentEvent, TerminationReason
from nano_agent.agent.events import EventEmitter
from nano_agent.config.schema import HarmfulContentFilterConfig, Config
from nano_agent.tools.middleware import HarmfulContentMiddleware, MiddlewareContext
from nano_agent.tools.base import ToolResult

pytestmark = pytest.mark.unit


def _make_config(**overrides) -> HarmfulContentFilterConfig:
    """Create a HarmfulContentFilterConfig with defaults overridden."""
    defaults = {"enabled": True}
    defaults.update(overrides)
    return HarmfulContentFilterConfig(**defaults)


def _make_filter(**config_overrides) -> HarmfulContentFilter:
    """Create a HarmfulContentFilter with sensible defaults for testing."""
    return HarmfulContentFilter(_make_config(**config_overrides))


# === Config Tests ===


class TestHarmfulContentFilterConfig:
    def test_default_config_disabled(self):
        config = HarmfulContentFilterConfig()
        assert config.enabled is False

    def test_default_categories(self):
        config = HarmfulContentFilterConfig()
        assert config.categories == ["violence", "hate", "dangerous", "illegal"]

    def test_default_action_is_block(self):
        config = HarmfulContentFilterConfig()
        assert config.default_action == "block"

    def test_custom_config(self):
        config = HarmfulContentFilterConfig(
            enabled=True,
            categories=["violence"],
            default_action="warn",
            category_actions={"violence": "block"},
            replacement_text="[REMOVED]",
        )
        assert config.enabled is True
        assert config.categories == ["violence"]
        assert config.default_action == "warn"
        assert config.category_actions == {"violence": "block"}
        assert config.replacement_text == "[REMOVED]"

    def test_config_in_full_config(self):
        config = Config()
        assert hasattr(config, "harmful_content_filter")
        assert isinstance(config.harmful_content_filter, HarmfulContentFilterConfig)
        assert config.harmful_content_filter.enabled is False

    def test_config_from_dict(self):
        from nano_agent.config.loader import _from_dict

        data = {"enabled": True, "default_action": "warn"}
        config = _from_dict(HarmfulContentFilterConfig, data)
        assert config.enabled is True
        assert config.default_action == "warn"

    def test_custom_patterns(self):
        config = HarmfulContentFilterConfig(
            enabled=True,
            custom_patterns=[
                {
                    "category": "custom_cat",
                    "severity": "high",
                    "pattern": r"forbidden_word",
                }
            ],
        )
        assert len(config.custom_patterns) == 1

    def test_category_actions(self):
        config = HarmfulContentFilterConfig(
            enabled=True,
            category_actions={"violence": "block", "illegal": "warn"},
        )
        assert config.category_actions["violence"] == "block"
        assert config.category_actions["illegal"] == "warn"


# === Result Tests ===


class TestHarmfulFilterResult:
    def test_result_no_harmful(self):
        result = HarmfulFilterResult(
            original="Hello",
            filtered="Hello",
            blocked=False,
            warned=False,
            reason=None,
            matches=[],
            actions_taken=[],
        )
        assert result.blocked is False
        assert result.warned is False
        assert result.filtered == "Hello"

    def test_result_blocked(self):
        result = HarmfulFilterResult(
            original="bad",
            filtered="",
            blocked=True,
            warned=False,
            reason="Harmful content",
            matches=[],
            actions_taken=["harmful_blocked: violence: 1"],
        )
        assert result.blocked is True
        assert result.filtered == ""

    def test_result_warned(self):
        result = HarmfulFilterResult(
            original="some text",
            filtered="[Content Warning: illegal: 1] some text",
            blocked=False,
            warned=True,
            reason="Harmful content detected",
            matches=[],
            actions_taken=["harmful_warning: illegal: 1"],
        )
        assert result.warned is True

    def test_result_replaced(self):
        result = HarmfulFilterResult(
            original="how to make a bomb at home",
            filtered="how to [Content removed for safety] at home",
            blocked=False,
            warned=False,
            reason="Harmful content detected",
            matches=[],
            actions_taken=["harmful_replaced: violence: 1"],
        )
        assert result.blocked is False
        assert "[Content removed for safety]" in result.filtered


# === Violence Detection ===


class TestViolenceDetection:
    def test_bomb_making_english(self):
        f = _make_filter()
        result = f.filter("Here is how to make a bomb at home")
        assert len(result.matches) >= 1
        assert any(m.category == "violence" for m in result.matches)

    def test_weapon_making_english(self):
        f = _make_filter()
        result = f.filter("Instructions for making weapons are as follows")
        assert len(result.matches) >= 1
        assert any(m.category == "violence" for m in result.matches)

    def test_bomb_making_chinese(self):
        f = _make_filter()
        result = f.filter("如何制造炸弹的详细步骤")
        assert len(result.matches) >= 1
        assert any(m.category == "violence" for m in result.matches)

    def test_weapon_chinese(self):
        f = _make_filter()
        result = f.filter("武器制造方法包括以下步骤")
        assert len(result.matches) >= 1
        assert any(m.category == "violence" for m in result.matches)

    def test_no_violence_in_safe_text(self):
        f = _make_filter()
        result = f.filter("The history of World War II involves many countries")
        assert len(result.matches) == 0


# === Hate Detection ===


class TestHateDetection:
    def test_hate_speech_english(self):
        f = _make_filter()
        result = f.filter("hate speech should make us attack and destroy them")
        assert len(result.matches) >= 1
        assert any(m.category == "hate" for m in result.matches)

    def test_hate_speech_chinese(self):
        f = _make_filter()
        result = f.filter("种族歧视应该让我们攻击消灭他们")
        assert len(result.matches) >= 1
        assert any(m.category == "hate" for m in result.matches)

    def test_no_hate_in_discussion(self):
        f = _make_filter()
        result = f.filter("We should promote racial equality and understanding")
        assert len(result.matches) == 0


# === Dangerous Detection ===


class TestDangerousDetection:
    def test_suicide_methods_english(self):
        f = _make_filter()
        result = f.filter("Here are suicide methods that are painless")
        assert len(result.matches) >= 1
        assert any(m.category == "dangerous" for m in result.matches)

    def test_suicide_methods_chinese(self):
        f = _make_filter()
        result = f.filter("无痛自杀方法有哪些")
        assert len(result.matches) >= 1
        assert any(m.category == "dangerous" for m in result.matches)

    def test_drug_synthesis_english(self):
        f = _make_filter()
        result = f.filter("How to synthesize meth at home step by step")
        assert len(result.matches) >= 1
        assert any(m.category == "dangerous" for m in result.matches)

    def test_hacking_instructions_english(self):
        f = _make_filter()
        result = f.filter("How to hack into a server using exploits")
        assert len(result.matches) >= 1
        assert any(m.category == "dangerous" for m in result.matches)

    def test_no_dangerous_in_safe_text(self):
        f = _make_filter()
        result = f.filter("Please help me set up a secure server configuration")
        assert len(result.matches) == 0


# === Illegal Detection ===


class TestIllegalDetection:
    def test_money_laundering_english(self):
        f = _make_filter()
        result = f.filter("Money laundering methods for hiding cash proceeds")
        assert len(result.matches) >= 1
        assert any(m.category == "illegal" for m in result.matches)

    def test_forgery_instructions_english(self):
        f = _make_filter()
        result = f.filter("How to forge documents and IDs easily")
        assert len(result.matches) >= 1
        assert any(m.category == "illegal" for m in result.matches)

    def test_money_laundering_chinese(self):
        f = _make_filter()
        result = f.filter("洗钱方法有几种常见手段")
        assert len(result.matches) >= 1
        assert any(m.category == "illegal" for m in result.matches)

    def test_no_illegal_in_safe_text(self):
        f = _make_filter()
        result = f.filter("We need to comply with anti-money laundering regulations")
        assert len(result.matches) == 0


# === Blocking ===


class TestBlocking:
    def test_block_action_blocks_response(self):
        f = _make_filter(default_action="block")
        result = f.filter("How to make a bomb at home")
        assert result.blocked is True
        assert result.filtered == ""

    def test_block_emits_events(self):
        events = EventEmitter()
        detected = []
        blocked = []
        events.on(AgentEvent.HARMFUL_CONTENT_DETECTED, lambda e, d: detected.append(d))
        events.on(AgentEvent.OUTPUT_BLOCKED, lambda e, d: blocked.append(d))

        f = HarmfulContentFilter(_make_config(), events=events)
        f.filter("How to make a bomb at home")

        assert len(detected) == 1
        assert detected[0]["action"] == "blocked"
        assert len(blocked) == 1
        assert blocked[0]["filter_type"] == "harmful_content"

    def test_blocked_response_is_empty(self):
        f = _make_filter(default_action="block")
        result = f.filter("How to make a bomb")
        assert result.filtered == ""

    def test_block_reason_includes_categories(self):
        f = _make_filter(default_action="block")
        result = f.filter("How to make a bomb")
        assert "violence" in result.reason


# === Warning ===


class TestWarning:
    def test_warn_action_does_not_block(self):
        f = _make_filter(default_action="warn", categories=["illegal"])
        result = f.filter("Money laundering methods for hiding cash")
        assert result.blocked is False
        assert result.warned is True

    def test_warn_prepend_notice(self):
        f = _make_filter(default_action="warn", categories=["illegal"])
        result = f.filter("Money laundering methods for hiding cash")
        assert result.filtered.startswith("[Content Warning:")

    def test_warn_does_not_remove_text(self):
        f = _make_filter(default_action="warn", categories=["illegal"])
        original = "Money laundering methods for hiding cash"
        result = f.filter(original)
        assert original in result.filtered


# === Replacement ===


class TestReplacement:
    def test_replace_action_substitutes_text(self):
        f = _make_filter(default_action="replace", categories=["violence"])
        result = f.filter("How to make a bomb at home")
        assert result.blocked is False
        assert result.warned is False
        assert "[Content removed for safety]" in result.filtered

    def test_custom_replacement_text(self):
        f = _make_filter(
            default_action="replace",
            categories=["violence"],
            replacement_text="[FILTERED]",
        )
        result = f.filter("How to make a bomb at home")
        assert "[FILTERED]" in result.filtered

    def test_multiple_replacements(self):
        f = _make_filter(default_action="replace", categories=["violence", "dangerous"])
        result = f.filter("How to make a bomb and how to commit suicide methods")
        assert result.filtered.count("[Content removed for safety]") >= 1


# === Category Actions ===


class TestCategoryActions:
    def test_different_actions_per_category(self):
        f = _make_filter(
            category_actions={"violence": "block", "illegal": "warn"},
        )
        # Violence should block
        violence_result = f.filter("How to make a bomb")
        assert violence_result.blocked is True

        # Illegal should warn
        illegal_result = f.filter("Money laundering methods for hiding cash")
        assert illegal_result.warned is True

    def test_category_action_overrides_default(self):
        f = _make_filter(
            default_action="replace",
            category_actions={"violence": "block"},
        )
        result = f.filter("How to make a bomb")
        assert result.blocked is True

    def test_mixed_actions_block_takes_precedence(self):
        f = _make_filter(
            category_actions={"violence": "block", "illegal": "warn"},
        )
        # Text matching both violence and illegal should block
        result = f.filter("How to make a bomb and money laundering methods")
        assert result.blocked is True


# === Orchestrator Integration ===


class TestOrchestratorIntegration:
    def _create_orchestrator(self, filter_config=None, llm_response="Hello"):
        from unittest.mock import Mock

        from nano_agent.agent.react import ReActAgent
        from nano_agent.agent.orchestrator import AgentOrchestrator
        from nano_agent.llm.base import LLMUsage
        from nano_agent.memory.short_term import ShortTermMemory
        from nano_agent.tools.registry import ToolRegistry

        llm = Mock()
        llm.chat = Mock(return_value=(llm_response, [], LLMUsage()))
        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(
            llm=llm, memory=memory, tool_registry=registry, verbose=False
        )

        if filter_config is None:
            filter_config = _make_config()

        harmful_filter = HarmfulContentFilter(filter_config, events=agent.events)
        return AgentOrchestrator(agent, harmful_filter=harmful_filter)

    def test_orchestrator_blocks_harmful_output(self):
        orch = self._create_orchestrator(llm_response="How to make a bomb at home")
        result = orch.run("tell me")
        assert result.success is False
        assert (
            result.termination_reason == TerminationReason.HARMFUL_CONTENT_BLOCKED.value
        )

    def test_orchestrator_warns_harmful_output(self):
        config = _make_config(
            default_action="warn",
            categories=["illegal"],
        )
        orch = self._create_orchestrator(
            filter_config=config,
            llm_response="Money laundering methods for hiding cash",
        )
        result = orch.run("tell me")
        assert result.success is True
        assert orch.last_harmful_filter_result is not None
        assert orch.last_harmful_filter_result.warned is True

    def test_orchestrator_replaces_harmful_output(self):
        config = _make_config(
            default_action="replace",
            categories=["violence"],
        )
        orch = self._create_orchestrator(
            filter_config=config,
            llm_response="How to make a bomb at home",
        )
        result = orch.run("tell me")
        assert result.success is True
        assert "[Content removed for safety]" in result.response

    def test_orchestrator_no_filter(self):
        orch = self._create_orchestrator(llm_response="Hello world")
        result = orch.run("hi")
        assert result.success is True
        assert orch.last_harmful_filter_result is not None
        assert len(orch.last_harmful_filter_result.matches) == 0

    def test_orchestrator_filter_disabled(self):
        config = HarmfulContentFilterConfig(enabled=False)
        orch = self._create_orchestrator(
            filter_config=config,
            llm_response="How to make a bomb",
        )
        result = orch.run("tell me")
        assert orch.last_harmful_filter_result is None

    def test_orchestrator_clean_output(self):
        orch = self._create_orchestrator(llm_response="The weather is nice today")
        result = orch.run("how is the weather")
        assert result.success is True
        assert result.response == "The weather is nice today"

    def test_orchestrator_filter_after_output_guard(self):
        """Verify harmful filter runs after output guard in the pipeline."""
        from unittest.mock import Mock

        from nano_agent.agent.react import ReActAgent
        from nano_agent.agent.orchestrator import AgentOrchestrator
        from nano_agent.agent.output_guard import OutputGuard
        from nano_agent.llm.base import LLMUsage
        from nano_agent.memory.short_term import ShortTermMemory
        from nano_agent.tools.registry import ToolRegistry
        from nano_agent.config.schema import OutputGuardConfig

        llm = Mock()
        llm.chat = Mock(
            return_value=("sk-abc123456789 how to make a bomb", [], LLMUsage())
        )
        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(
            llm=llm, memory=memory, tool_registry=registry, verbose=False
        )

        output_guard = OutputGuard(
            OutputGuardConfig(enabled=True, action="mask"), events=agent.events
        )
        harmful_filter = HarmfulContentFilter(_make_config(), events=agent.events)
        orch = AgentOrchestrator(
            agent,
            output_guard=output_guard,
            harmful_filter=harmful_filter,
        )
        result = orch.run("test")
        # OutputGuard should mask the API key, harmful filter should block the bomb text
        assert (
            result.termination_reason == TerminationReason.HARMFUL_CONTENT_BLOCKED.value
        )


# === Middleware Tests ===


class TestHarmfulContentMiddleware:
    def test_middleware_replaces_output(self):
        f = _make_filter(default_action="replace", categories=["violence"])
        middleware = HarmfulContentMiddleware(harmful_filter=f)
        ctx = MiddlewareContext(
            tool_name="test",
            arguments={},
            result=ToolResult(success=True, output="How to make a bomb"),
        )
        middleware.after(ctx)
        assert "[Content removed for safety]" in ctx.result.output

    def test_middleware_no_filter(self):
        middleware = HarmfulContentMiddleware(harmful_filter=None)
        original_output = "How to make a bomb"
        ctx = MiddlewareContext(
            tool_name="test",
            arguments={},
            result=ToolResult(success=True, output=original_output),
        )
        middleware.after(ctx)
        assert ctx.result.output == original_output

    def test_middleware_filter_disabled(self):
        f = HarmfulContentFilter(HarmfulContentFilterConfig(enabled=False))
        middleware = HarmfulContentMiddleware(harmful_filter=f)
        original_output = "How to make a bomb"
        ctx = MiddlewareContext(
            tool_name="test",
            arguments={},
            result=ToolResult(success=True, output=original_output),
        )
        middleware.after(ctx)
        assert ctx.result.output == original_output

    def test_middleware_no_harmful_data(self):
        f = _make_filter()
        middleware = HarmfulContentMiddleware(harmful_filter=f)
        original_output = "Hello world"
        ctx = MiddlewareContext(
            tool_name="test",
            arguments={},
            result=ToolResult(success=True, output=original_output),
        )
        middleware.after(ctx)
        assert ctx.result.output == original_output

    def test_middleware_failed_result_skipped(self):
        f = _make_filter()
        middleware = HarmfulContentMiddleware(harmful_filter=f)
        ctx = MiddlewareContext(
            tool_name="test",
            arguments={},
            result=ToolResult(success=False, output="Error occurred", error="bad"),
        )
        middleware.after(ctx)
        assert ctx.result.output == "Error occurred"

    def test_middleware_priority(self):
        from nano_agent.tools.middleware import SensitiveOutputMiddleware

        assert HarmfulContentMiddleware.priority == 99
        assert HarmfulContentMiddleware.priority < SensitiveOutputMiddleware.priority


# === Custom Patterns ===


class TestCustomPatterns:
    def test_custom_pattern_matches(self):
        f = _make_filter(
            categories=[],
            custom_patterns=[
                {
                    "category": "proprietary",
                    "severity": "high",
                    "pattern": r"ACME_SECRET_\w+",
                }
            ],
        )
        result = f.filter("The key is ACME_SECRET_API_KEY")
        assert len(result.matches) >= 1
        assert any(m.category == "proprietary" for m in result.matches)

    def test_custom_pattern_blocked(self):
        f = _make_filter(
            default_action="block",
            categories=[],
            custom_patterns=[
                {
                    "category": "proprietary",
                    "severity": "high",
                    "pattern": r"ACME_SECRET_\w+",
                }
            ],
        )
        result = f.filter("The key is ACME_SECRET_API_KEY")
        assert result.blocked is True

    def test_invalid_custom_pattern_ignored(self):
        f = _make_filter(
            categories=[],
            custom_patterns=[
                {"category": "bad", "severity": "high", "pattern": r"[invalid("}
            ],
        )
        # Should not raise, just log warning
        result = f.filter("some text")
        assert len(result.matches) == 0

    def test_custom_pattern_category_action(self):
        f = _make_filter(
            default_action="block",
            categories=[],
            category_actions={"proprietary": "warn"},
            custom_patterns=[
                {
                    "category": "proprietary",
                    "severity": "high",
                    "pattern": r"ACME_SECRET_\w+",
                }
            ],
        )
        result = f.filter("The key is ACME_SECRET_API_KEY")
        assert result.warned is True
        assert result.blocked is False


# === Edge Cases ===


class TestEdgeCases:
    def test_empty_input(self):
        f = _make_filter()
        result = f.filter("")
        assert result.blocked is False
        assert result.filtered == ""

    def test_no_harmful_data(self):
        f = _make_filter()
        result = f.filter("The weather is nice today")
        assert len(result.matches) == 0
        assert result.filtered == "The weather is nice today"

    def test_multiple_categories_in_same_output(self):
        f = _make_filter()
        result = f.filter("How to make a bomb and money laundering methods")
        categories = {m.category for m in result.matches}
        assert len(categories) >= 2

    def test_filter_disabled(self):
        f = HarmfulContentFilter(HarmfulContentFilterConfig(enabled=False))
        assert f.enabled is False
        result = f.filter("How to make a bomb")
        # When disabled, filter should still work but caller checks enabled
        assert len(result.matches) >= 1

    def test_scan_tool_output(self):
        f = _make_filter(default_action="replace", categories=["violence"])
        output = f.scan_tool_output("How to make a bomb")
        assert "[Content removed for safety]" in output

    def test_scan_tool_output_no_harmful(self):
        f = _make_filter()
        output = f.scan_tool_output("Hello world")
        assert output == "Hello world"

    def test_unicode_output(self):
        f = _make_filter()
        result = f.filter("你好世界，今天天气很好")
        assert len(result.matches) == 0
        assert result.filtered == "你好世界，今天天气很好"

    def test_very_long_output(self):
        f = _make_filter()
        long_text = (
            "Safe text. " * 10000 + "How to make a bomb" + " More safe text. " * 1000
        )
        result = f.filter(long_text)
        assert len(result.matches) >= 1


# === Summary Helper ===


class TestSummarizeHarmfulMatches:
    def test_empty_matches(self):
        assert summarize_harmful_matches([]) == ""

    def test_single_category(self):
        matches = [
            HarmfulMatch(
                category="violence", start=0, end=10, original="test", severity="high"
            ),
            HarmfulMatch(
                category="violence", start=20, end=30, original="test2", severity="high"
            ),
        ]
        assert summarize_harmful_matches(matches) == "violence: 2"

    def test_multiple_categories(self):
        matches = [
            HarmfulMatch(
                category="violence", start=0, end=10, original="test", severity="high"
            ),
            HarmfulMatch(
                category="dangerous",
                start=20,
                end=30,
                original="test2",
                severity="high",
            ),
        ]
        summary = summarize_harmful_matches(matches)
        assert "dangerous: 1" in summary
        assert "violence: 1" in summary
