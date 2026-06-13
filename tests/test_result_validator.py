"""
Tests for ResultValidator (v0.8.7, v0.8.8).

Verifies result correctness validation for agent output,
including file existence checks, code syntax validation,
command success verification, and schema validation (v0.8.8).
"""

import json
import os
import tempfile

import pytest

from nano_agent.agent.result_validator import (
    ResultValidator,
    ValidationCheck,
    ValidationResult,
    summarize_validation_checks,
    _FILE_CLAIM_PATTERNS,
    _CODE_CLAIM_PATTERNS,
    _COMMAND_CLAIM_PATTERNS,
)
from nano_agent.config.schema import ResultValidatorConfig

pytestmark = pytest.mark.unit


# === Helper fixtures ===


def _make_config(**overrides) -> ResultValidatorConfig:
    defaults = {"enabled": True}
    defaults.update(overrides)
    return ResultValidatorConfig(**defaults)


def _make_validator(**config_overrides) -> ResultValidator:
    return ResultValidator(_make_config(**config_overrides))


# === ValidationCheck ===


class TestValidationCheck:
    def test_creation(self):
        check = ValidationCheck(
            check_type="file_exists",
            claim="File created: /tmp/test.txt",
            passed=True,
            detail="Path exists: /tmp/test.txt",
        )
        assert check.check_type == "file_exists"
        assert check.passed is True
        assert check.severity == "medium"  # default

    def test_severity_override(self):
        check = ValidationCheck(
            check_type="file_exists",
            claim="test",
            passed=False,
            detail="not found",
            severity="high",
        )
        assert check.severity == "high"


# === ValidationResult ===


class TestValidationResult:
    def test_no_checks(self):
        result = ValidationResult(
            original="hello",
            validated="hello",
            blocked=False,
            reason=None,
            checks=[],
            failed_checks=[],
            actions_taken=[],
        )
        assert not result.blocked
        assert result.failed_checks == []

    def test_with_failed_checks(self):
        failed = ValidationCheck("file_exists", "claim", False, "not found", "high")
        result = ValidationResult(
            original="text",
            validated="text\n\n[Validation Note]",
            blocked=False,
            reason=None,
            checks=[failed],
            failed_checks=[failed],
            actions_taken=["validation_annotated: file_exists: 1"],
        )
        assert len(result.failed_checks) == 1


# === summarize_validation_checks ===


class TestSummarizeValidationChecks:
    def test_empty(self):
        assert summarize_validation_checks([]) == ""

    def test_single_type(self):
        checks = [ValidationCheck("file_exists", "c", True, "d")]
        assert summarize_validation_checks(checks) == "file_exists: 1"

    def test_multiple_types(self):
        checks = [
            ValidationCheck("file_exists", "c1", True, "d1"),
            ValidationCheck("code_syntax", "c2", True, "d2"),
            ValidationCheck("file_exists", "c3", True, "d3"),
        ]
        result = summarize_validation_checks(checks)
        assert "code_syntax: 1" in result
        assert "file_exists: 2" in result


# === ResultValidator basics ===


class TestResultValidatorBasics:
    def test_disabled_by_default(self):
        config = ResultValidatorConfig()
        assert config.enabled is False

    def test_enabled_property(self):
        v = _make_validator(enabled=True)
        assert v.enabled is True

    def test_disabled_validator_returns_unchanged(self):
        config = ResultValidatorConfig(enabled=False)
        v = ResultValidator(config)
        assert not v.enabled

    def test_scan_tool_output_returns_unchanged(self):
        v = _make_validator()
        output = "some tool output"
        assert v.scan_tool_output(output) == output


# === File existence checks ===


class TestFileExistsCheck:
    def test_file_exists_pass(self):
        """When agent claims a file exists and it does, check passes."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            path = f.name

        try:
            v = _make_validator()
            text = f"I have created file {path}"
            result = v.validate(text)
            file_checks = [c for c in result.checks if c.check_type == "file_exists"]
            assert len(file_checks) >= 1
            assert any(c.passed for c in file_checks)
        finally:
            os.unlink(path)

    def test_file_not_exists_fail(self):
        """When agent claims a file exists but it doesn't, check fails."""
        v = _make_validator()
        text = "I have created file /tmp/nonexistent_file_xyz_123.txt"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) >= 1
        assert any(not c.passed for c in file_checks)

    def test_no_file_claims_no_checks(self):
        """When no file claims are made, no file checks are generated."""
        v = _make_validator()
        text = "The answer is 42."
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) == 0

    def test_url_paths_ignored(self):
        """URLs should not be treated as file paths."""
        v = _make_validator()
        text = "Created file https://example.com/data.json"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) == 0

    def test_file_claim_pattern_wrote(self):
        """Pattern: 'wrote file X' should be detected."""
        v = _make_validator()
        text = "I wrote file /tmp/definitely_missing_abc.txt"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) >= 1

    def test_file_claim_pattern_saved_to(self):
        """Pattern: 'saved to X' should be detected."""
        v = _make_validator()
        text = "Results saved to /tmp/missing_output_456.log"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) >= 1

    def test_file_claim_pattern_written_to(self):
        """Pattern: 'written to X' should be detected."""
        v = _make_validator()
        text = "Output written to /tmp/missing_report_789.csv"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) >= 1

    def test_duplicate_paths_deduplicated(self):
        """Same path mentioned twice should produce only one check."""
        v = _make_validator()
        text = "Created /tmp/unique_test_dedup.txt. File /tmp/unique_test_dedup.txt is ready."
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        paths = [c.claim for c in file_checks]
        assert len(paths) == len(set(paths))  # no duplicates

    def test_file_exists_check_disabled(self):
        """When file_exists is not in checks, no file checks are made."""
        config = _make_config(checks=["code_syntax"])
        v = ResultValidator(config)
        text = "Created file /tmp/nonexistent_xyz.txt"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) == 0


# === Code syntax checks ===


class TestCodeSyntaxCheck:
    def test_valid_python_code_passes(self):
        """When agent claims code is correct and it is, check passes."""
        v = _make_validator()
        text = (
            "The code is correct and runs successfully:\n```python\nprint('hello')\n```"
        )
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) >= 1
        assert any(c.passed for c in code_checks)

    def test_invalid_python_code_fails(self):
        """When agent claims code is correct but it has syntax errors, check fails."""
        v = _make_validator()
        text = "The code compiles without errors:\n```python\ndef foo(\n  print('broken'\n```"
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) >= 1
        assert any(not c.passed for c in code_checks)

    def test_no_correctness_claim_no_check(self):
        """When code is shown but no correctness claim is made, no check."""
        v = _make_validator()
        text = "Here is the code:\n```python\nprint('hello')\n```"
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) == 0

    def test_valid_json_passes(self):
        """When agent claims JSON is correct and it is, check passes."""
        v = _make_validator()
        text = 'The JSON is correct:\n```json\n{"key": "value"}\n```'
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) >= 1
        assert any(c.passed for c in code_checks)

    def test_invalid_json_fails(self):
        """When agent claims JSON is correct but it's malformed, check fails."""
        v = _make_validator()
        text = "The JSON is correct:\n```json\n{key: value}\n```"
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) >= 1
        assert any(not c.passed for c in code_checks)

    def test_code_syntax_check_disabled(self):
        """When code_syntax is not in checks, no code checks are made."""
        config = _make_config(checks=["file_exists"])
        v = ResultValidator(config)
        text = "The code is correct:\n```python\nprint('hello')\n```"
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) == 0

    def test_syntax_error_detail_contains_line(self):
        """Syntax error detail should mention the line number."""
        v = _make_validator()
        text = "The code runs correctly:\n```python\ndef foo(\n```\n"
        result = v.validate(text)
        failed = [
            c for c in result.checks if c.check_type == "code_syntax" and not c.passed
        ]
        assert len(failed) >= 1
        assert "SyntaxError" in failed[0].detail

    def test_empty_code_block_ignored(self):
        """Empty code blocks should not produce checks."""
        v = _make_validator()
        text = "The code is correct:\n```python\n\n```"
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) == 0


# === Command success checks ===


class TestCommandSuccessCheck:
    def test_claim_with_zero_exit_code_passes(self):
        """When agent claims success and exit code is 0, check passes."""
        v = _make_validator()
        text = "Command executed successfully. Exit code: 0"
        result = v.validate(text)
        cmd_checks = [c for c in result.checks if c.check_type == "command_success"]
        assert len(cmd_checks) >= 1
        assert any(c.passed for c in cmd_checks)

    def test_claim_with_nonzero_exit_code_fails(self):
        """When agent claims success but exit code is non-zero, check fails."""
        v = _make_validator()
        text = "Command executed successfully. Exit code: 1"
        result = v.validate(text)
        cmd_checks = [c for c in result.checks if c.check_type == "command_success"]
        assert len(cmd_checks) >= 1
        assert any(not c.passed for c in cmd_checks)

    def test_no_command_claim_no_check(self):
        """When no command success claim is made, no check."""
        v = _make_validator()
        text = "The files are in /tmp."
        result = v.validate(text)
        cmd_checks = [c for c in result.checks if c.check_type == "command_success"]
        assert len(cmd_checks) == 0

    def test_command_success_check_disabled(self):
        """When command_success is not in checks, no command checks are made."""
        config = _make_config(checks=["file_exists"])
        v = ResultValidator(config)
        text = "Command executed successfully. Exit code: 1"
        result = v.validate(text)
        cmd_checks = [c for c in result.checks if c.check_type == "command_success"]
        assert len(cmd_checks) == 0

    def test_multiple_nonzero_exit_codes(self):
        """Multiple non-zero exit codes should be reported."""
        v = _make_validator()
        text = "Command completed successfully. Exit code: 1, return code: 2"
        result = v.validate(text)
        cmd_checks = [
            c
            for c in result.checks
            if c.check_type == "command_success" and not c.passed
        ]
        assert len(cmd_checks) >= 1
        # Detail should mention the non-zero codes
        detail = cmd_checks[0].detail
        assert "1" in detail


# === on_fail action modes ===


class TestOnFailActions:
    def test_annotate_appends_note(self):
        """on_fail='annotate' appends a validation note to the response."""
        v = _make_validator(on_fail="annotate")
        text = "Created file /tmp/absolutely_missing_file_xyz.txt"
        result = v.validate(text)
        assert not result.blocked
        assert "[Validation Note]" in result.validated

    def test_warn_appends_warning(self):
        """on_fail='warn' appends a warning to the response."""
        v = _make_validator(on_fail="warn")
        text = "Created file /tmp/absolutely_missing_file_xyz.txt"
        result = v.validate(text)
        assert not result.blocked
        assert "[Validation Warning]" in result.validated

    def test_block_with_high_severity(self):
        """on_fail='block' blocks the response when high-severity check fails."""
        v = _make_validator(on_fail="block")
        text = "Created file /tmp/absolutely_missing_file_xyz.txt"
        result = v.validate(text)
        assert result.blocked
        assert result.validated == ""

    def test_block_without_high_severity_does_not_block(self):
        """on_fail='block' only blocks when there are high-severity failures."""
        # Create a response where only code_syntax (medium) fails but file_exists doesn't trigger
        v = _make_validator(on_fail="block", checks=["code_syntax"])
        text = "The code compiles successfully:\n```python\ndef foo(\n```"
        result = v.validate(text)
        # code_syntax failures are medium severity, so block should not trigger
        assert not result.blocked

    def test_annotate_is_default(self):
        """Default on_fail action is 'annotate'."""
        config = ResultValidatorConfig()
        assert config.on_fail == "annotate"


# === on_pass action modes ===


class TestOnPassActions:
    def test_silent_is_default(self):
        """Default on_pass action is 'silent'."""
        config = ResultValidatorConfig()
        assert config.on_pass == "silent"

    def test_silent_no_annotation(self):
        """on_pass='silent' doesn't modify the response when all checks pass."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            path = f.name

        try:
            v = _make_validator(on_pass="silent")
            text = f"Created file {path}"
            result = v.validate(text)
            assert result.validated == text  # no annotation added
        finally:
            os.unlink(path)

    def test_annotate_appends_pass_note(self):
        """on_pass='annotate' appends a passed-validation note."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            path = f.name

        try:
            v = _make_validator(on_pass="annotate")
            text = f"Created file {path}"
            result = v.validate(text)
            assert "[Validation:" in result.validated
            assert "passed" in result.validated
        finally:
            os.unlink(path)


# === No checks scenario ===


class TestNoChecksScenario:
    def test_no_claims_no_checks(self):
        """When no verifiable claims are made, no checks are generated."""
        v = _make_validator()
        text = "The weather is nice today."
        result = v.validate(text)
        assert len(result.checks) == 0
        assert result.validated == text
        assert not result.blocked

    def test_all_checks_pass_no_failure(self):
        """When all checks pass, failed_checks is empty."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test")
            path = f.name

        try:
            v = _make_validator()
            text = f"Created file {path}"
            result = v.validate(text)
            assert len(result.failed_checks) == 0
        finally:
            os.unlink(path)


# === Custom validators ===


class TestCustomValidators:
    def test_custom_validator_pass(self):
        """Custom validator that passes should add a passing check."""

        def my_validator(text):
            return ValidationCheck(
                check_type="custom",
                claim="Custom check",
                passed=True,
                detail="All good",
            )

        config = _make_config(custom_validators=[my_validator])
        v = ResultValidator(config)
        result = v.validate("any text")
        custom_checks = [c for c in result.checks if c.check_type == "custom"]
        assert len(custom_checks) == 1
        assert custom_checks[0].passed

    def test_custom_validator_fail(self):
        """Custom validator that fails should add a failing check."""

        def my_validator(text):
            return ValidationCheck(
                check_type="custom",
                claim="Custom check",
                passed=False,
                detail="Something wrong",
                severity="high",
            )

        config = _make_config(on_fail="block", custom_validators=[my_validator])
        v = ResultValidator(config)
        result = v.validate("any text")
        assert result.blocked

    def test_custom_validator_exception_handled(self):
        """Custom validator that raises should not crash validation."""

        def bad_validator(text):
            raise RuntimeError("oops")

        config = _make_config(custom_validators=[bad_validator])
        v = ResultValidator(config)
        result = v.validate("any text")
        # Should not crash, just skip the bad validator
        assert not result.blocked

    def test_custom_validator_returns_none_skipped(self):
        """Custom validator that returns None should be skipped."""

        def no_op_validator(text):
            return None

        config = _make_config(custom_validators=[no_op_validator])
        v = ResultValidator(config)
        result = v.validate("any text")
        assert len(result.checks) == 0


# === Event emission ===


class TestEventEmission:
    def test_blocked_emits_validation_failed_event(self):
        """When validation blocks, VALIDATION_FAILED event should be emitted."""
        from nano_agent.agent.events import EventEmitter
        from nano_agent.agent.types import AgentEvent

        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.VALIDATION_FAILED, lambda e, d: emitted.append(d))

        config = _make_config(on_fail="block")
        v = ResultValidator(config, events=events)
        v.validate("Created file /tmp/absolutely_missing_xyz.txt")

        assert len(emitted) >= 1
        assert "failed_count" in emitted[0]

    def test_blocked_emits_output_blocked_event(self):
        """When validation blocks, OUTPUT_BLOCKED event should also be emitted."""
        from nano_agent.agent.events import EventEmitter
        from nano_agent.agent.types import AgentEvent

        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.OUTPUT_BLOCKED, lambda e, d: emitted.append(d))

        config = _make_config(on_fail="block")
        v = ResultValidator(config, events=events)
        v.validate("Created file /tmp/absolutely_missing_xyz.txt")

        assert len(emitted) >= 1
        assert emitted[0]["filter_type"] == "result_validator"

    def test_no_events_when_not_blocked(self):
        """When validation doesn't block, no OUTPUT_BLOCKED event."""
        from nano_agent.agent.events import EventEmitter
        from nano_agent.agent.types import AgentEvent

        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.OUTPUT_BLOCKED, lambda e, d: emitted.append(d))

        config = _make_config(on_fail="annotate")
        v = ResultValidator(config, events=events)
        v.validate("Created file /tmp/absolutely_missing_xyz.txt")

        assert len(emitted) == 0


# === Integration with Orchestrator pattern ===


class TestOrchestratorIntegration:
    def test_validator_result_stored(self):
        """Validator result should be stored as last_validator_result."""
        from nano_agent.agent.orchestrator import AgentOrchestrator
        from nano_agent.agent.types import ExecutionResult, TerminationReason

        config = _make_config(on_fail="annotate")
        v = ResultValidator(config)
        orch = AgentOrchestrator(
            agent=None,  # type: ignore
            config=None,
            validator=v,
        )
        assert orch.validator is v
        assert orch.last_validator_result is None

    def test_validator_not_set_when_none(self):
        """When validator is None, last_validator_result stays None."""
        from nano_agent.agent.orchestrator import AgentOrchestrator

        orch = AgentOrchestrator(agent=None, config=None)  # type: ignore
        assert orch.validator is None
        assert orch.last_validator_result is None


# === Pattern matching edge cases ===


class TestPatternEdgeCases:
    def test_short_path_ignored(self):
        """Paths shorter than 2 chars should be ignored."""
        v = _make_validator()
        text = "Created file x"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) == 0

    def test_data_url_ignored(self):
        """data: URLs should not be treated as file paths."""
        v = _make_validator()
        text = "Created file data:text/plain,hello"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) == 0

    def test_chinese_file_claim(self):
        """Chinese text with file claims should work."""
        v = _make_validator()
        text = "已保存到 /tmp/missing_chinese_file_测试.txt"
        result = v.validate(text)
        file_checks = [c for c in result.checks if c.check_type == "file_exists"]
        assert len(file_checks) >= 1

    def test_code_claim_with_function(self):
        """Code correctness claim mentioning 'function' should work."""
        v = _make_validator()
        text = (
            "The function is correct:\n```python\ndef add(a, b):\n    return a + b\n```"
        )
        result = v.validate(text)
        code_checks = [c for c in result.checks if c.check_type == "code_syntax"]
        assert len(code_checks) >= 1
        assert any(c.passed for c in code_checks)

    def test_command_claim_with_execution(self):
        """Command execution claim should be detected."""
        v = _make_validator()
        text = "Execution completed successfully"
        result = v.validate(text)
        cmd_checks = [c for c in result.checks if c.check_type == "command_success"]
        assert len(cmd_checks) >= 1


# === Schema Validation (v0.8.8) ===


class TestSchemaValidation:
    """Tests for schema validation check type (v0.8.8)."""

    def test_valid_status_schema_passes(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"status": "success", "exit_code": 0, "stdout": "hello"},
        )
        assert sto.validate() == []

    def test_status_missing_required_key(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"exit_code": 0},
        )
        errors = sto.validate()
        assert len(errors) >= 1
        assert "status" in errors[0]

    def test_status_wrong_type(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"status": "success", "exit_code": "zero"},
        )
        errors = sto.validate()
        assert any("exit_code" in e for e in errors)

    def test_status_python_executor_variant(self):
        """PythonExecutor uses 'output' key instead of stdout/stderr."""
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"status": "success", "output": "42"},
        )
        assert sto.validate() == []

    def test_list_schema_valid(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.LIST,
            data={"items": [{"path": "a.py"}], "total": 1},
        )
        assert sto.validate() == []

    def test_list_missing_items(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.LIST,
            data={"total": 5},
        )
        errors = sto.validate()
        assert any("items" in e for e in errors)

    def test_list_wrong_type_total(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.LIST,
            data={"items": [], "total": "five"},
        )
        errors = sto.validate()
        assert any("total" in e for e in errors)

    def test_content_schema_valid(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.CONTENT,
            data={"source": "/tmp/test.py", "content": "print('hi')"},
        )
        assert sto.validate() == []

    def test_content_missing_source(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.CONTENT,
            data={"content": "print('hi')"},
        )
        errors = sto.validate()
        assert any("source" in e for e in errors)

    def test_content_missing_content(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.CONTENT,
            data={"source": "/tmp/test.py"},
        )
        errors = sto.validate()
        assert any("content" in e for e in errors)

    def test_structure_always_passes(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.STRUCTURE,
            data={"arbitrary": "data"},
        )
        assert sto.validate() == []

    def test_error_schema_always_passes(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.ERROR,
            data={"error_type": "ValueError", "message": "bad input"},
        )
        assert sto.validate() == []

    def test_error_schema_empty_data_passes(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.ERROR,
            data={},
        )
        assert sto.validate() == []

    def test_validate_tool_output_valid(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        v = _make_validator(checks=["schema"])
        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"status": "success"},
        )
        is_valid, errors = v.validate_tool_output(sto)
        assert is_valid
        assert errors == []

    def test_validate_tool_output_invalid(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        v = _make_validator(checks=["schema"])
        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"exit_code": 0},
        )
        is_valid, errors = v.validate_tool_output(sto)
        assert not is_valid
        assert len(errors) >= 1

    def test_validate_tool_output_disabled_when_schema_not_in_checks(self):
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        v = _make_validator(checks=["file_exists"])
        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={},
        )
        is_valid, errors = v.validate_tool_output(sto)
        assert is_valid

    def test_schema_check_not_in_validate_dispatch(self):
        """schema check is handled via validate_tool_output(), not validate()."""
        v = _make_validator(checks=["schema"])
        result = v.validate("Some response text")
        schema_checks = [c for c in result.checks if c.check_type == "schema"]
        assert len(schema_checks) == 0

    def test_validate_tool_output_emits_event(self):
        from nano_agent.agent.events import EventEmitter
        from nano_agent.agent.types import AgentEvent
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        events = EventEmitter()
        emitted = []
        events.on(AgentEvent.VALIDATION_FAILED, lambda e, d: emitted.append(d))

        config = _make_config(checks=["schema"])
        v = ResultValidator(config, events=events)

        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={},
        )
        v.validate_tool_output(sto)
        assert len(emitted) >= 1
        assert emitted[0]["format"] == "status"

    def test_bool_value_rejected_for_int_key(self):
        """bool is subclass of int but should not pass int type check."""
        from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

        sto = StandardToolOutput(
            format=OutputFormat.STATUS,
            data={"status": "success", "exit_code": True},
        )
        errors = sto.validate()
        assert any("exit_code" in e for e in errors)


class TestIsTypeCompatible:
    """Tests for _is_type_compatible helper (v0.8.8)."""

    def test_str_matches_str(self):
        from nano_agent.tools.standard_output import _is_type_compatible

        assert _is_type_compatible("hello", str)

    def test_int_matches_int(self):
        from nano_agent.tools.standard_output import _is_type_compatible

        assert _is_type_compatible(42, int)

    def test_bool_rejected_for_int(self):
        from nano_agent.tools.standard_output import _is_type_compatible

        assert not _is_type_compatible(True, int)

    def test_bool_accepted_for_bool(self):
        from nano_agent.tools.standard_output import _is_type_compatible

        assert _is_type_compatible(True, bool)

    def test_int_accepted_for_float(self):
        from nano_agent.tools.standard_output import _is_type_compatible

        assert _is_type_compatible(42, float)

    def test_str_rejected_for_int(self):
        from nano_agent.tools.standard_output import _is_type_compatible

        assert not _is_type_compatible("42", int)

    def test_list_matches_list(self):
        from nano_agent.tools.standard_output import _is_type_compatible

        assert _is_type_compatible([1, 2], list)


class TestFormatSchema:
    """Tests for FormatSchema dataclass (v0.8.8)."""

    def test_format_schemas_use_dataclass(self):
        from nano_agent.tools.standard_output import FORMAT_SCHEMAS, FormatSchema

        for fmt, schema in FORMAT_SCHEMAS.items():
            assert isinstance(schema, FormatSchema)

    def test_required_keys_are_tuple(self):
        from nano_agent.tools.standard_output import FORMAT_SCHEMAS

        for fmt, schema in FORMAT_SCHEMAS.items():
            assert isinstance(schema.required_keys, tuple)
