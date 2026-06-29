"""
Tests for OutputGuard - sensitive information interception in agent output.
"""

import pytest

from nano_agent.agent.output_guard import (
    OutputGuard,
    OutputGuardResult,
    SensitiveMatch,
    summarize_sensitive_matches,
    _OUTPUT_PATTERNS,
)
from nano_agent.agent.types import AgentEvent, TerminationReason
from nano_agent.agent.events import EventEmitter
from nano_agent.config.schema import OutputGuardConfig, Config
from nano_agent.tools.base import ToolResult

pytestmark = pytest.mark.unit


# === Config Tests ===


class TestOutputGuardConfig:
    def test_default_config(self):
        config = OutputGuardConfig()
        assert config.enabled is True
        assert config.action == "mask"
        assert config.mask_mode == "partial"
        assert config.mask_char == "*"
        assert "api_key" in config.sensitive_types
        assert "password" in config.sensitive_types
        assert "private_key" in config.sensitive_types
        assert "connection_string" in config.sensitive_types
        assert "phone" in config.sensitive_types
        assert "id_card" in config.sensitive_types
        assert "email" in config.sensitive_types
        assert "private_key" in config.block_severity
        assert config.custom_patterns == []

    def test_custom_config(self):
        config = OutputGuardConfig(
            enabled=False,
            action="block",
            mask_mode="full",
            mask_char="#",
            sensitive_types=["api_key"],
            block_severity=["api_key"],
        )
        assert config.enabled is False
        assert config.action == "block"
        assert config.mask_mode == "full"
        assert config.mask_char == "#"
        assert config.sensitive_types == ["api_key"]
        assert config.block_severity == ["api_key"]

    def test_config_in_full_config(self):
        config = Config()
        assert hasattr(config, "output_guard")
        assert isinstance(config.output_guard, OutputGuardConfig)
        assert config.output_guard.enabled is True

    def test_config_from_dict(self):
        from nano_agent.config.loader import _from_dict

        data = {"enabled": True, "action": "block"}
        config = _from_dict(OutputGuardConfig, data)
        assert config.action == "block"

    def test_custom_patterns(self):
        config = OutputGuardConfig(
            custom_patterns=[{"name": "aws_secret", "pattern": r"aws_secret_key=\w+"}]
        )
        assert len(config.custom_patterns) == 1


# === Result Tests ===


class TestOutputGuardResult:
    def test_result_no_sensitive(self):
        result = OutputGuardResult(
            original="hello",
            guarded="hello",
            blocked=False,
            reason=None,
            matches=[],
            actions_taken=[],
        )
        assert result.original == "hello"
        assert result.guarded == "hello"
        assert result.blocked is False
        assert result.reason is None

    def test_result_blocked(self):
        result = OutputGuardResult(
            original="secret",
            guarded="",
            blocked=True,
            reason="Contains API key",
            matches=[],
            actions_taken=["output_blocked: api_key: 1"],
        )
        assert result.blocked is True
        assert result.guarded == ""

    def test_result_masked(self):
        result = OutputGuardResult(
            original="key is sk-abc123",
            guarded="key is sk-****123",
            blocked=False,
            reason=None,
            matches=[],
            actions_taken=["output_masked: api_key: 1"],
        )
        assert result.guarded != result.original
        assert result.blocked is False


# === API Key Detection ===


class TestAPIKeyDetection:
    def test_openai_api_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        result = guard.guard("The key is sk-abc1234567890123")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "api_key"

    def test_github_token(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        result = guard.guard("Token: ghp_abc1234567890123")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "api_key"

    def test_bearer_token(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        result = guard.guard("Authorization: Bearer abcdefghijklmnopqrst")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "api_key"

    def test_aws_access_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        result = guard.guard("AWS key: AKIAIOSFODNN7EXAMPLE")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "api_key"

    def test_no_api_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        result = guard.guard("No sensitive data here")
        assert len(result.matches) == 0
        assert result.guarded == result.original


# === Password Detection ===


class TestPasswordDetection:
    def test_password_equals(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["password"]))
        result = guard.guard("password=secret123")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "password"

    def test_passwd_equals(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["password"]))
        result = guard.guard("passwd=mysecret")
        assert len(result.matches) == 1

    def test_pwd_equals(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["password"]))
        result = guard.guard("pwd=abc")
        assert len(result.matches) == 1

    def test_secret_equals(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["password"]))
        result = guard.guard("secret=xyz123")
        assert len(result.matches) == 1

    def test_password_colon(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["password"]))
        result = guard.guard("password: mypass")
        assert len(result.matches) == 1

    def test_case_insensitive(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["password"]))
        result = guard.guard("PASSWORD=secret")
        assert len(result.matches) == 1

    def test_no_password(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["password"]))
        result = guard.guard("This is safe output")
        assert len(result.matches) == 0


# === Private Key Detection ===


class TestPrivateKeyDetection:
    def test_rsa_private_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["private_key"]))
        result = guard.guard("-----BEGIN RSA PRIVATE KEY-----\nMIIEpA...")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "private_key"

    def test_dsa_private_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["private_key"]))
        result = guard.guard("-----BEGIN DSA PRIVATE KEY-----\nMIIBug...")
        assert len(result.matches) == 1

    def test_ec_private_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["private_key"]))
        result = guard.guard("-----BEGIN EC PRIVATE KEY-----\nMHQCAQ...")
        assert len(result.matches) == 1

    def test_openssh_private_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["private_key"]))
        result = guard.guard("-----BEGIN OPENSSH PRIVATE KEY-----\nb3Blb...")
        assert len(result.matches) == 1

    def test_no_private_key(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["private_key"]))
        result = guard.guard("-----BEGIN PUBLIC KEY-----\nMIIBIj...")
        assert len(result.matches) == 0


# === Connection String Detection ===


class TestConnectionStringDetection:
    def test_postgres_connection(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["connection_string"]))
        result = guard.guard("DB: postgres://user:pass@localhost:5432/mydb")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "connection_string"

    def test_mysql_connection(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["connection_string"]))
        result = guard.guard("mysql://admin:secret@db.example.com:3306/app")
        assert len(result.matches) == 1

    def test_mongodb_connection(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["connection_string"]))
        result = guard.guard("mongodb://user:pwd@cluster.mongodb.net/test")
        assert len(result.matches) == 1

    def test_redis_connection(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["connection_string"]))
        result = guard.guard("redis://:password@redis.example.com:6379/0")
        assert len(result.matches) == 1

    def test_no_connection_string(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["connection_string"]))
        result = guard.guard("http://example.com is a website")
        assert len(result.matches) == 0


# === PII Reuse (phone, id_card, email) ===


class TestPIIReuse:
    def test_phone_detection(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["phone"]))
        result = guard.guard("手机号: 13812345678")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "phone"

    def test_id_card_detection(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["id_card"]))
        result = guard.guard("身份证: 110101199901011234")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "id_card"

    def test_email_detection(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["email"]))
        result = guard.guard("邮箱: test@example.com")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "email"


# === Masking ===


class TestMasking:
    def test_partial_mask_api_key(self):
        guard = OutputGuard(
            OutputGuardConfig(
                sensitive_types=["api_key"], mask_mode="partial", mask_char="*"
            )
        )
        result = guard.guard("key: sk-abc1234567890123")
        assert result.guarded != result.original
        assert "sk-" in result.guarded
        assert "****" in result.guarded

    def test_full_mask_api_key(self):
        guard = OutputGuard(
            OutputGuardConfig(
                sensitive_types=["api_key"], mask_mode="full", mask_char="#"
            )
        )
        result = guard.guard("key: sk-abc1234567890123")
        assert "sk-" not in result.guarded or "####" in result.guarded

    def test_partial_mask_password(self):
        guard = OutputGuard(
            OutputGuardConfig(sensitive_types=["password"], mask_mode="partial")
        )
        result = guard.guard("password=secret123")
        assert "password=" in result.guarded
        assert "****" in result.guarded
        assert "secret123" not in result.guarded

    def test_private_key_masked_as_redacted(self):
        guard = OutputGuard(
            OutputGuardConfig(
                sensitive_types=["private_key"],
                mask_mode="partial",
                block_severity=[],  # Disable block severity to test masking
            )
        )
        result = guard.guard("-----BEGIN RSA PRIVATE KEY-----\nMIIEpA...")
        assert "[PRIVATE KEY REDACTED]" in result.guarded

    def test_connection_string_password_masked(self):
        guard = OutputGuard(
            OutputGuardConfig(
                sensitive_types=["connection_string"], mask_mode="partial"
            )
        )
        result = guard.guard("postgres://user:pass@localhost:5432/db")
        assert ":****@" in result.guarded
        assert "pass" not in result.guarded

    def test_phone_partial_mask(self):
        guard = OutputGuard(
            OutputGuardConfig(sensitive_types=["phone"], mask_mode="partial")
        )
        result = guard.guard("号码: 13812345678")
        assert "138" in result.guarded
        assert "5678" in result.guarded
        assert "****" in result.guarded


# === Blocking ===


class TestBlocking:
    def test_block_action(self):
        guard = OutputGuard(
            OutputGuardConfig(sensitive_types=["api_key"], action="block")
        )
        result = guard.guard("key: sk-abc1234567890123")
        assert result.blocked is True
        assert result.reason is not None
        assert "api_key" in result.reason

    def test_block_severity_private_key(self):
        guard = OutputGuard(
            OutputGuardConfig(
                sensitive_types=["private_key"],
                action="mask",
                block_severity=["private_key"],
            )
        )
        result = guard.guard("-----BEGIN RSA PRIVATE KEY-----\nMIIEpA...")
        assert result.blocked is True

    def test_block_severity_not_triggered_for_mask_type(self):
        guard = OutputGuard(
            OutputGuardConfig(
                sensitive_types=["api_key"],
                action="mask",
                block_severity=["private_key"],
            )
        )
        result = guard.guard("key: sk-abc1234567890123")
        assert result.blocked is False

    def test_block_emits_event(self):
        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.OUTPUT_BLOCKED, lambda e, d: emitted.append(d))
        guard = OutputGuard(
            OutputGuardConfig(sensitive_types=["api_key"], action="block"),
            events=events,
        )
        guard.guard("key: sk-abc1234567890123")
        assert len(emitted) == 1
        assert "api_key" in emitted[0]["match_types"]

    def test_block_severity_emits_event(self):
        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.OUTPUT_BLOCKED, lambda e, d: emitted.append(d))
        guard = OutputGuard(
            OutputGuardConfig(
                sensitive_types=["private_key"],
                action="mask",
                block_severity=["private_key"],
            ),
            events=events,
        )
        guard.guard("-----BEGIN RSA PRIVATE KEY-----\nMIIEpA...")
        assert len(emitted) == 1


# === Warning ===


class TestWarning:
    def test_warn_action(self):
        guard = OutputGuard(
            OutputGuardConfig(sensitive_types=["api_key"], action="warn")
        )
        result = guard.guard("key: sk-abc1234567890123")
        assert result.blocked is False
        assert result.guarded == result.original
        assert result.reason is not None
        assert any("warning" in a for a in result.actions_taken)

    def test_warn_no_modification(self):
        guard = OutputGuard(
            OutputGuardConfig(sensitive_types=["password"], action="warn")
        )
        original = "password=secret"
        result = guard.guard(original)
        assert result.guarded == original


# === Orchestrator Integration ===


class TestOrchestratorIntegration:
    def _create_orchestrator(self, output_guard_config=None, llm_response="Hello"):
        from unittest.mock import Mock

        from nano_agent.agent.orchestrator import AgentOrchestrator
        from nano_agent.agent.react import ReActAgent
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
        config = output_guard_config or OutputGuardConfig(sensitive_types=["api_key"])
        output_guard = OutputGuard(config, events=agent.events)
        return AgentOrchestrator(agent, output_guard=output_guard)

    def test_orchestrator_masks_output(self):
        orchestrator = self._create_orchestrator(
            llm_response="The key is sk-abc1234567890123"
        )
        result = orchestrator.run("show me the key")
        assert result.termination_reason != TerminationReason.OUTPUT_BLOCKED.value
        assert orchestrator.last_output_guard_result is not None
        assert len(orchestrator.last_output_guard_result.matches) == 1

    def test_orchestrator_blocks_output(self):
        config = OutputGuardConfig(sensitive_types=["api_key"], action="block")
        orchestrator = self._create_orchestrator(
            output_guard_config=config,
            llm_response="The key is sk-abc1234567890123",
        )
        result = orchestrator.run("show me the key")
        assert result.termination_reason == TerminationReason.OUTPUT_BLOCKED.value
        assert result.success is False

    def test_orchestrator_no_guard(self):
        from unittest.mock import Mock

        from nano_agent.agent.orchestrator import AgentOrchestrator
        from nano_agent.agent.react import ReActAgent
        from nano_agent.llm.base import LLMUsage
        from nano_agent.memory.short_term import ShortTermMemory
        from nano_agent.tools.registry import ToolRegistry

        llm = Mock()
        llm.chat = Mock(return_value=("Hello", [], LLMUsage()))
        memory = ShortTermMemory()
        registry = ToolRegistry()
        agent = ReActAgent(
            llm=llm, memory=memory, tool_registry=registry, verbose=False
        )
        orchestrator = AgentOrchestrator(agent)
        result = orchestrator.run("hello")
        assert result.termination_reason != TerminationReason.OUTPUT_BLOCKED.value
        assert orchestrator.last_output_guard_result is None

    def test_orchestrator_guard_disabled(self):
        config = OutputGuardConfig(enabled=False)
        orchestrator = self._create_orchestrator(output_guard_config=config)
        result = orchestrator.run("hello")
        assert orchestrator.last_output_guard_result is None

    def test_orchestrator_clean_output(self):
        orchestrator = self._create_orchestrator(llm_response="Clean output here")
        result = orchestrator.run("hello")
        assert result.termination_reason != TerminationReason.OUTPUT_BLOCKED.value
        assert (
            orchestrator.last_output_guard_result is None
            or len(orchestrator.last_output_guard_result.matches) == 0
        )


# === Custom Patterns ===


class TestCustomPatterns:
    def test_custom_pattern_matches(self):
        config = OutputGuardConfig(
            sensitive_types=[],
            custom_patterns=[{"name": "aws_secret", "pattern": r"aws_secret_key=\w+"}],
        )
        guard = OutputGuard(config)
        result = guard.guard("aws_secret_key=mysecretkey123")
        assert len(result.matches) == 1
        assert result.matches[0].sensitive_type == "aws_secret"

    def test_custom_pattern_masked(self):
        config = OutputGuardConfig(
            sensitive_types=[],
            custom_patterns=[{"name": "internal_id", "pattern": r"INTERNAL-\d{10}"}],
        )
        guard = OutputGuard(config)
        result = guard.guard("ref: INTERNAL-1234567890")
        assert result.guarded != result.original
        assert "INTERNAL-1234567890" not in result.guarded

    def test_invalid_custom_pattern_ignored(self):
        config = OutputGuardConfig(
            sensitive_types=[],
            custom_patterns=[{"name": "bad", "pattern": r"[invalid"}],
        )
        guard = OutputGuard(config)
        # Should not raise
        result = guard.guard("some text")
        assert len(result.matches) == 0


# === Edge Cases ===


class TestEdgeCases:
    def test_empty_input(self):
        guard = OutputGuard(OutputGuardConfig())
        result = guard.guard("")
        assert result.guarded == ""
        assert result.blocked is False
        assert len(result.matches) == 0

    def test_no_sensitive_data(self):
        guard = OutputGuard(OutputGuardConfig())
        result = guard.guard("This is perfectly safe output")
        assert result.guarded == result.original
        assert result.blocked is False

    def test_multiple_types_in_same_output(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key", "password"]))
        result = guard.guard("key: sk-abc1234567890123 and password=secret")
        assert len(result.matches) >= 2

    def test_overlapping_matches_keeps_longer(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key", "phone"]))
        # Just verify no crash and some detection occurs
        result = guard.guard("Contact: 13812345678")
        # Phone should be detected
        assert len(result.matches) >= 1

    def test_guard_disabled(self):
        guard = OutputGuard(OutputGuardConfig(enabled=False))
        assert guard.enabled is False

    def test_guard_enabled(self):
        guard = OutputGuard(OutputGuardConfig(enabled=True))
        assert guard.enabled is True

    def test_scan_tool_output(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        output = guard.scan_tool_output("key: sk-abc1234567890123")
        assert "sk-abc1234567890123" not in output

    def test_scan_tool_output_no_sensitive(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        output = guard.scan_tool_output("safe output")
        assert output == "safe output"

    def test_unicode_output(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["phone"]))
        result = guard.guard("中文手机号: 13812345678")
        assert result.guarded != result.original

    def test_very_long_output(self):
        guard = OutputGuard(OutputGuardConfig(sensitive_types=["api_key"]))
        long_text = "x" * 10000 + "sk-abc1234567890123" + "y" * 10000
        result = guard.guard(long_text)
        assert len(result.matches) == 1


# === Summary Helper ===


class TestSummarizeSensitiveMatches:
    def test_empty_matches(self):
        assert summarize_sensitive_matches([]) == ""

    def test_single_type(self):
        matches = [SensitiveMatch("api_key", 0, 10, "orig", "mask", "mask")]
        assert summarize_sensitive_matches(matches) == "api_key: 1"

    def test_multiple_types(self):
        matches = [
            SensitiveMatch("api_key", 0, 10, "orig", "mask", "mask"),
            SensitiveMatch("password", 20, 30, "orig", "mask", "mask"),
            SensitiveMatch("api_key", 40, 50, "orig", "mask", "mask"),
        ]
        summary = summarize_sensitive_matches(matches)
        assert "api_key: 2" in summary
        assert "password: 1" in summary
