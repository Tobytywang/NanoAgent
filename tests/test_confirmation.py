"""
Tests for v0.6.4 confirmation mechanism: RiskLevel, ConfirmationManager, and tool confirmation.
"""

import pytest
from unittest.mock import Mock, MagicMock
import threading
import time

from nano_agent.agent.types import RiskLevel, AgentEvent
from nano_agent.agent.confirmation import ConfirmationManager, ConfirmationConfig
from nano_agent.agent.subsystems import AgentSubsystems
from nano_agent.agent.events import EventEmitter
from nano_agent.tools.base import BaseTool, ToolResult


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output="Mock result")


class TestRiskLevel:
    """Tests for RiskLevel enumeration."""

    def test_risk_levels_exist(self):
        """Test that all risk levels are defined."""
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.MODERATE.value == "moderate"
        assert RiskLevel.DANGEROUS.value == "dangerous"

    def test_risk_level_comparison(self):
        """Test risk level comparison."""
        assert RiskLevel.SAFE != RiskLevel.DANGEROUS
        assert RiskLevel.MODERATE != RiskLevel.SAFE


class TestConfirmationConfig:
    """Tests for ConfirmationConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConfirmationConfig()
        assert config.enabled is True
        assert config.confirm_safe is False
        assert config.confirm_moderate is False
        assert config.confirm_dangerous is True
        assert config.whitelist == []

    def test_custom_config(self):
        """Test custom configuration."""
        config = ConfirmationConfig(
            enabled=False,
            confirm_safe=True,
            confirm_moderate=True,
            confirm_dangerous=False,
            whitelist=["test_tool"],
        )
        assert config.enabled is False
        assert config.confirm_safe is True
        assert config.confirm_moderate is True
        assert config.confirm_dangerous is False
        assert "test_tool" in config.whitelist


class TestConfirmationManager:
    """Tests for ConfirmationManager."""

    def test_needs_confirmation_disabled(self):
        """Test that confirmation is skipped when disabled."""
        config = ConfirmationConfig(enabled=False)
        manager = ConfirmationManager(config)

        tool = MockTool()
        tool.risk_level = RiskLevel.DANGEROUS

        assert manager.needs_confirmation(tool) is False

    def test_needs_confirmation_whitelist(self):
        """Test that whitelisted tools skip confirmation."""
        config = ConfirmationConfig(whitelist=["mock_tool"])
        manager = ConfirmationManager(config)

        tool = MockTool()
        tool.risk_level = RiskLevel.DANGEROUS

        assert manager.needs_confirmation(tool) is False

    def test_needs_confirmation_safe(self):
        """Test SAFE tool confirmation."""
        config = ConfirmationConfig(confirm_safe=False)
        manager = ConfirmationManager(config)

        tool = MockTool()
        tool.risk_level = RiskLevel.SAFE

        assert manager.needs_confirmation(tool) is False

        # Enable SAFE confirmation
        config.confirm_safe = True
        assert manager.needs_confirmation(tool) is True

    def test_needs_confirmation_moderate(self):
        """Test MODERATE tool confirmation."""
        config = ConfirmationConfig(confirm_moderate=False)
        manager = ConfirmationManager(config)

        tool = MockTool()
        tool.risk_level = RiskLevel.MODERATE

        assert manager.needs_confirmation(tool) is False

        # Enable MODERATE confirmation
        config.confirm_moderate = True
        assert manager.needs_confirmation(tool) is True

    def test_needs_confirmation_dangerous(self):
        """Test DANGEROUS tool confirmation."""
        config = ConfirmationConfig(confirm_dangerous=True)
        manager = ConfirmationManager(config)

        tool = MockTool()
        tool.risk_level = RiskLevel.DANGEROUS

        assert manager.needs_confirmation(tool) is True

        # Disable DANGEROUS confirmation
        config.confirm_dangerous = False
        assert manager.needs_confirmation(tool) is False

    def test_request_and_set_result(self):
        """Test confirmation request and result setting."""
        manager = ConfirmationManager()

        # Request confirmation
        manager.request_confirmation()
        assert manager.is_pending() is True
        assert manager.get_result() is None

        # Set result
        manager.set_result(True)
        assert manager.is_pending() is False
        assert manager.get_result() is True

    def test_wait_for_result(self):
        """Test waiting for confirmation result."""
        manager = ConfirmationManager()
        manager.request_confirmation()

        # Set result in another thread
        def set_result():
            time.sleep(0.1)
            manager.set_result(True)

        thread = threading.Thread(target=set_result)
        thread.start()

        # Wait for result
        result = manager.wait_for_result(timeout=1.0)
        assert result is True

        thread.join()

    def test_wait_for_result_timeout(self):
        """Test wait timeout."""
        manager = ConfirmationManager()
        manager.request_confirmation()

        # Wait without setting result
        result = manager.wait_for_result(timeout=0.1)
        assert result is None  # Timeout

    def test_reset(self):
        """Test reset functionality."""
        manager = ConfirmationManager()
        manager.request_confirmation()
        manager.set_result(True)

        manager.reset()
        assert manager.is_pending() is False
        assert manager.get_result() is None

    def test_whitelist_management(self):
        """Test whitelist add/remove."""
        manager = ConfirmationManager()

        manager.add_to_whitelist("tool1")
        assert "tool1" in manager.config.whitelist

        manager.add_to_whitelist("tool2")
        assert "tool2" in manager.config.whitelist

        manager.remove_from_whitelist("tool1")
        assert "tool1" not in manager.config.whitelist
        assert "tool2" in manager.config.whitelist

    def test_duplicate_whitelist_add(self):
        """Test that duplicate whitelist entries are ignored."""
        manager = ConfirmationManager()

        manager.add_to_whitelist("tool1")
        manager.add_to_whitelist("tool1")

        assert manager.config.whitelist.count("tool1") == 1


class TestToolRiskLevel:
    """Tests for tool risk level attribute."""

    def test_tool_default_risk_level(self):
        """Test that tools have default risk level."""
        tool = MockTool()
        # BaseTool.__init__ sets default to MODERATE
        assert tool.risk_level == RiskLevel.MODERATE

    def test_tool_custom_risk_level(self):
        """Test custom risk level on tool."""
        tool = MockTool()
        tool.risk_level = RiskLevel.DANGEROUS
        assert tool.risk_level == RiskLevel.DANGEROUS


class TestConfirmationEvent:
    """Tests for confirmation event emission."""

    def test_confirmation_event_emitted(self):
        """Test that CONFIRMATION_REQUIRED event is emitted."""
        from nano_agent.agent import ReActAgent

        # Create mock components
        llm = Mock()
        memory = Mock()
        memory.get_all = Mock(return_value=[])
        memory.add_user_message = Mock()
        memory.add_assistant_message = Mock()
        memory.add_tool_result = Mock()
        memory.set_system_prompt = Mock()

        tool_registry = Mock()
        tool = MockTool()
        tool.risk_level = RiskLevel.DANGEROUS
        tool_registry.get = Mock(return_value=tool)
        tool_registry.list_tools = Mock(return_value=["mock_tool"])
        tool_registry.get_all_schemas = Mock(return_value=[])

        events = EventEmitter()

        # Create agent with confirmation enabled
        config = ConfirmationConfig(confirm_dangerous=True)
        subsystems = AgentSubsystems.from_defaults()
        subsystems.confirmation = ConfirmationManager(config)
        agent = ReActAgent(
            llm=llm,
            memory=memory,
            tool_registry=tool_registry,
            subsystems=subsystems,
            events=events,
            verbose=False,
        )

        # Track events
        emitted = []
        events.on(AgentEvent.CONFIRMATION_REQUIRED, lambda e, d: emitted.append(d))

        # Request confirmation
        agent.confirmation.request_confirmation()
        events.emit(
            AgentEvent.CONFIRMATION_REQUIRED,
            {"tool": "mock_tool", "arguments": {}, "risk_level": "dangerous"},
        )

        assert len(emitted) == 1
        assert emitted[0]["tool"] == "mock_tool"
        assert emitted[0]["risk_level"] == "dangerous"

    def test_agent_confirm_tool_method(self):
        """Test agent's confirm_tool method."""
        from nano_agent.agent import ReActAgent

        llm = Mock()
        memory = Mock()
        memory.get_all = Mock(return_value=[])
        memory.add_user_message = Mock()
        memory.add_assistant_message = Mock()
        memory.add_tool_result = Mock()
        memory.set_system_prompt = Mock()

        tool_registry = Mock()
        tool_registry.list_tools = Mock(return_value=[])
        tool_registry.get_all_schemas = Mock(return_value=[])

        agent = ReActAgent(
            llm=llm, memory=memory, tool_registry=tool_registry, verbose=False
        )

        # Request confirmation
        agent.confirmation.request_confirmation()
        assert agent.confirmation.is_pending() is True

        # Confirm via method
        agent.confirm_tool(True)
        assert agent.confirmation.is_pending() is False
        assert agent.confirmation.get_result() is True

    def test_agent_add_tool_to_whitelist(self):
        """Test agent's whitelist method."""
        from nano_agent.agent import ReActAgent

        llm = Mock()
        memory = Mock()
        memory.get_all = Mock(return_value=[])
        memory.add_user_message = Mock()
        memory.add_assistant_message = Mock()
        memory.add_tool_result = Mock()
        memory.set_system_prompt = Mock()

        tool_registry = Mock()
        tool_registry.list_tools = Mock(return_value=[])
        tool_registry.get_all_schemas = Mock(return_value=[])

        agent = ReActAgent(
            llm=llm, memory=memory, tool_registry=tool_registry, verbose=False
        )

        agent.add_tool_to_whitelist("test_tool")
        assert "test_tool" in agent.confirmation.config.whitelist


class TestAgentEventConfirmation:
    """Tests for AgentEvent.CONFIRMATION_REQUIRED."""

    def test_confirmation_event_exists(self):
        """Test that CONFIRMATION_REQUIRED event is defined."""
        assert AgentEvent.CONFIRMATION_REQUIRED.value == "confirmation_required"

    def test_all_events_include_confirmation(self):
        """Test that all expected events are defined."""
        expected_events = [
            AgentEvent.RUN_START,
            AgentEvent.THINK_START,
            AgentEvent.TOOL_CALL,
            AgentEvent.TOOL_RESULT,
            AgentEvent.RUN_END,
            AgentEvent.CONFIRMATION_REQUIRED,
        ]
        assert len(expected_events) == 6
