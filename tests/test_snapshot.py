"""
Tests for global state snapshot (v0.8.14) and audit/rollback (v0.8.15).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from nano_agent.agent.snapshot import (
    Snapshot,
    SnapshotMetadata,
    SnapshotManager,
    AuditLogEntry,
)
from nano_agent.agent.events import EventEmitter
from nano_agent.agent.types import AgentEvent
from nano_agent.config.schema import SnapshotConfig

pytestmark = pytest.mark.unit


# === Fixtures ===


@pytest.fixture
def snapshot_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def snapshot_config(snapshot_dir):
    return SnapshotConfig(
        enabled=True,
        auto_snapshot=False,
        max_snapshots=5,
        snapshot_dir=str(snapshot_dir),
        audit_log_dir=str(snapshot_dir),
    )


@pytest.fixture
def snapshot_manager(snapshot_config):
    events = EventEmitter()
    return SnapshotManager(config=snapshot_config, events=events)


def _make_agent(round_counter=5, total_tokens=1000, session_id="sess_abc"):
    """Create a minimal mock agent with all subsystems."""
    from nano_agent.agent.subsystems import AgentSubsystems
    from nano_agent.agent.undo import UndoStack
    from nano_agent.monitoring import MetricsTracker

    memory = Mock()
    memory.get_all.return_value = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    memory._messages = list(memory.get_all.return_value)
    memory.system_prompt = "You are helpful."
    memory.stable_system_prompt = "stable part"

    agent = Mock()
    agent.memory = memory
    agent._round_counter = round_counter
    agent._session_id = session_id
    agent._total_tokens = total_tokens
    agent._routing_max_tools = -1
    agent._wrapup_issued = False
    agent._last_prompt_tokens = None
    agent._stable_system_prompt = "stable part"
    agent.skill_prompt = ""
    agent.verbose = True
    agent._undo_stack = UndoStack()
    agent._tool_call_records = []
    agent.tracker = MetricsTracker()
    agent.tracker._session_total_tokens = total_tokens

    # Subsystems
    subsystems = AgentSubsystems.from_defaults()
    agent._subsystems = subsystems
    agent.token_budget = subsystems.token_budget
    agent.cache = subsystems.cache
    agent.circuit_breaker = subsystems.circuit_breaker
    agent._setup_system_prompt = Mock()

    return agent


def _make_orchestrator(agent, session_id="orch_xyz"):
    from nano_agent.agent.orchestrator import AgentOrchestrator, SessionStats

    orchestrator = Mock(spec=AgentOrchestrator)
    orchestrator.agent = agent
    orchestrator.session_id = session_id
    orchestrator.stats = SessionStats(
        total_tokens=100, total_tool_calls=5, total_iterations=3
    )
    orchestrator.events = EventEmitter()
    return orchestrator


# === SnapshotMetadata tests ===


class TestSnapshotMetadata:
    def test_to_dict_from_dict_roundtrip(self):
        m = SnapshotMetadata(
            snapshot_id="snap_abc12345",
            name="test snapshot",
            created_at="2026-06-21T10:30:00",
            session_id="sess_abc",
            round_counter=3,
            message_count=10,
            total_tokens=5000,
        )
        d = m.to_dict()
        m2 = SnapshotMetadata.from_dict(d)
        assert m2.snapshot_id == m.snapshot_id
        assert m2.name == m.name
        assert m2.round_counter == m.round_counter
        assert m2.total_tokens == m.total_tokens
        assert m2.version == "0.8.15"

    def test_from_dict_missing_optional_fields(self):
        d = {
            "snapshot_id": "snap_abc",
            "created_at": "2026-01-01",
        }
        m = SnapshotMetadata.from_dict(d)
        assert m.name == ""
        assert m.round_counter == 0


# === Snapshot data structure tests ===


class TestSnapshot:
    def test_to_dict_from_dict_roundtrip(self):
        metadata = SnapshotMetadata(
            snapshot_id="snap_test",
            name="",
            created_at="2026-06-21T10:00:00",
            session_id="sess_1",
            round_counter=1,
            message_count=5,
            total_tokens=100,
        )
        snapshot = Snapshot(
            metadata=metadata,
            orchestrator={"session_id": "sess_1", "stats": {"total_tokens": 100}},
            execution={"_round_counter": 1, "_total_tokens": 100},
            undo_stack={"records": [], "current_round": ""},
            tool_call_records=[],
            memory={"type": "short_term", "messages": [], "system_prompt": "hi"},
            token_budget={"initial_budget": 50000, "remaining": 49000},
            cache={"entries": [], "access_order": []},
            circuit_breaker={"mode": "auto", "trigger_reason": None},
            duplicate_detector={"call_history": {}, "warning_issued": False},
            stall_detector={
                "iteration_signatures": [],
                "stall_count": 0,
                "hint_index": 0,
            },
            feedback_loop={},
            tracker={"session_total_tokens": 100},
        )
        d = snapshot.to_dict()
        s2 = Snapshot.from_dict(d)
        assert s2.metadata.snapshot_id == "snap_test"
        assert s2.orchestrator["session_id"] == "sess_1"
        assert s2.feedback_loop == {}

    def test_from_dict_extra_fields_ignored(self):
        d = {
            "metadata": {
                "snapshot_id": "snap_x",
                "created_at": "2026-01-01",
            },
            "orchestrator": {},
            "execution": {},
            "undo_stack": {},
            "tool_call_records": [],
            "memory": {},
            "token_budget": {},
            "cache": {},
            "circuit_breaker": {},
            "duplicate_detector": {},
            "stall_detector": {},
            "feedback_loop": {},
            "tracker": {},
            "future_field": "should be fine",
        }
        s = Snapshot.from_dict(d)
        assert s.metadata.snapshot_id == "snap_x"


# === SnapshotManager.save() tests ===


class TestSnapshotManagerSave:
    def test_save_creates_json_file(self, snapshot_manager, snapshot_dir):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch, name="test")
        path = snapshot_dir / f"{meta.snapshot_id}.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["metadata"]["snapshot_id"] == meta.snapshot_id

    def test_save_returns_metadata(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch, name="mymeta")
        assert isinstance(meta, SnapshotMetadata)
        assert meta.name == "mymeta"
        assert meta.snapshot_id.startswith("snap_")

    def test_save_with_empty_name(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)
        assert meta.name == ""

    def test_save_emits_event(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        emitted = []
        snapshot_manager._events.on(
            AgentEvent.SNAPSHOT_SAVED, lambda e, d: emitted.append(d)
        )
        snapshot_manager.save(agent, orch)
        assert len(emitted) == 1
        assert emitted[0]["snapshot_id"].startswith("snap_")

    def test_save_captures_all_sections(self, snapshot_manager, snapshot_dir):
        agent = _make_agent(round_counter=7, total_tokens=2000)
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)
        path = snapshot_dir / f"{meta.snapshot_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in [
            "metadata",
            "orchestrator",
            "execution",
            "undo_stack",
            "tool_call_records",
            "memory",
            "token_budget",
            "cache",
            "circuit_breaker",
            "duplicate_detector",
            "stall_detector",
            "feedback_loop",
            "tracker",
        ]:
            assert key in data, f"Missing section: {key}"

    def test_save_enforces_max_snapshots(self, snapshot_manager, snapshot_config):
        snapshot_config.max_snapshots = 2
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        ids = []
        for _ in range(4):
            meta = snapshot_manager.save(agent, orch)
            ids.append(meta.snapshot_id)
        snapshots = snapshot_manager.list_snapshots()
        assert len(snapshots) <= 2


# === SnapshotManager.restore() tests ===


class TestSnapshotManagerRestore:
    def test_restore_replaces_agent_fields(self, snapshot_manager):
        agent = _make_agent(round_counter=3, total_tokens=500)
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch, name="before")

        # Modify agent state
        agent._round_counter = 99
        agent._total_tokens = 99999

        # Restore
        assert snapshot_manager.restore(meta.snapshot_id, agent, orch)
        assert agent._round_counter == 3
        assert agent._total_tokens == 500

    def test_restore_replaces_orchestrator_fields(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        orch.session_id = "modified"
        orch.stats.total_tokens = 99999

        snapshot_manager.restore(meta.snapshot_id, agent, orch)
        assert orch.session_id == "orch_xyz"
        assert orch.stats.total_tokens == 100

    def test_restore_emits_event(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        emitted = []
        snapshot_manager._events.on(
            AgentEvent.SNAPSHOT_RESTORED, lambda e, d: emitted.append(d)
        )
        snapshot_manager.restore(meta.snapshot_id, agent, orch)
        assert len(emitted) == 1
        assert emitted[0]["snapshot_id"] == meta.snapshot_id

    def test_restore_nonexistent_returns_false(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        assert not snapshot_manager.restore("snap_nonexistent", agent, orch)

    def test_restore_memory_messages_correct(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        # Add more messages after save
        agent.memory._messages.append({"role": "user", "content": "After save"})
        assert len(agent.memory._messages) == 4

        snapshot_manager.restore(meta.snapshot_id, agent, orch)
        assert len(agent.memory._messages) == 3  # Original count

    def test_restore_calls_setup_system_prompt(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        snapshot_manager.restore(meta.snapshot_id, agent, orch)
        agent._setup_system_prompt.assert_called_once()


# === SnapshotManager.list_snapshots() tests ===


class TestSnapshotManagerList:
    def test_list_empty(self, snapshot_manager):
        assert snapshot_manager.list_snapshots() == []

    def test_list_returns_metadata(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        snapshot_manager.save(agent, orch, name="first")
        snapshot_manager.save(agent, orch, name="second")

        snapshots = snapshot_manager.list_snapshots()
        assert len(snapshots) == 2
        assert all(isinstance(s, SnapshotMetadata) for s in snapshots)

    def test_list_sorted_by_creation_time(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta1 = snapshot_manager.save(agent, orch, name="first")
        meta2 = snapshot_manager.save(agent, orch, name="second")

        snapshots = snapshot_manager.list_snapshots()
        assert snapshots[0].name == "second"  # Newest first


# === SnapshotManager.delete() tests ===


class TestSnapshotManagerDelete:
    def test_delete_removes_file(self, snapshot_manager, snapshot_dir):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)
        assert (snapshot_dir / f"{meta.snapshot_id}.json").exists()

        assert snapshot_manager.delete(meta.snapshot_id)
        assert not (snapshot_dir / f"{meta.snapshot_id}.json").exists()

    def test_delete_nonexistent_returns_false(self, snapshot_manager):
        assert not snapshot_manager.delete("snap_nonexistent")


# === Roundtrip integration tests ===


class TestSnapshotRoundtrip:
    def test_save_restore_roundtrip(self, snapshot_manager):
        agent = _make_agent(round_counter=10, total_tokens=3000)
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        # Modify state
        agent._round_counter = 0
        agent._total_tokens = 0
        agent._routing_max_tools = 5
        orch.stats.total_iterations = 0

        # Restore
        snapshot_manager.restore(meta.snapshot_id, agent, orch)

        assert agent._round_counter == 10
        assert agent._total_tokens == 3000
        assert agent._routing_max_tools == -1
        assert orch.stats.total_iterations == 3

    def test_save_restore_token_budget(self, snapshot_manager):
        agent = _make_agent()
        agent.token_budget.consume(5000)
        assert agent.token_budget.remaining < agent.token_budget.initial_budget

        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        # Modify budget
        agent.token_budget.remaining = 0
        agent.token_budget._total_consumed = 99999

        snapshot_manager.restore(meta.snapshot_id, agent, orch)
        assert agent.token_budget.remaining < agent.token_budget.initial_budget
        assert agent.token_budget.remaining > 0

    def test_save_restore_circuit_breaker(self, snapshot_manager):
        agent = _make_agent()
        from nano_agent.agent.types import ExecutionMode

        # Trigger circuit breaker
        agent.circuit_breaker._mode = ExecutionMode.SUPERVISED
        agent.circuit_breaker._trigger_reason = "test trigger"

        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        # Reset
        agent.circuit_breaker._mode = ExecutionMode.AUTO
        agent.circuit_breaker._trigger_reason = None

        snapshot_manager.restore(meta.snapshot_id, agent, orch)
        assert agent.circuit_breaker._mode == ExecutionMode.SUPERVISED
        assert agent.circuit_breaker._trigger_reason == "test trigger"


# === Auto-snapshot tests ===


class TestAutoSnapshot:
    def test_auto_snapshot_disabled_by_default(self, snapshot_manager):
        snapshot_manager._config.auto_snapshot = False
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        snapshot_manager.maybe_auto_snapshot(agent, orch)
        assert snapshot_manager.list_snapshots() == []

    def test_auto_snapshot_before_run(self, snapshot_manager):
        snapshot_manager._config.auto_snapshot = True
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        snapshot_manager.maybe_auto_snapshot(agent, orch)
        assert len(snapshot_manager.list_snapshots()) == 1
        assert snapshot_manager.list_snapshots()[0].name == "auto"


# === Config tests ===


class TestSnapshotConfig:
    def test_snapshot_config_defaults(self):
        config = SnapshotConfig()
        assert config.enabled is True
        assert config.auto_snapshot is False
        assert config.max_snapshots == 20
        assert config.snapshot_dir == ".nano_agent/snapshots"
        assert config.audit_log_enabled is True
        assert config.max_audit_entries == 500
        assert config.auto_rollback_enabled is False
        assert config.auto_rollback_threshold == 3
        assert config.auto_rollback_on_failure == "error"

    def test_snapshot_config_in_main_config(self):
        from nano_agent.config.schema import Config

        config = Config()
        assert hasattr(config, "snapshot")
        assert isinstance(config.snapshot, SnapshotConfig)


# === AuditLogEntry tests (v0.8.15) ===


class TestAuditLogEntry:
    def test_to_dict_from_dict_roundtrip(self):
        entry = AuditLogEntry(
            audit_id="audit_abc12345",
            operation="save",
            snapshot_id="snap_xyz",
            timestamp="2026-06-22T10:30:00",
            session_id="sess_1",
            trigger="manual",
            outcome="success",
            reason="User /snapshot save",
            round_counter=3,
            message_count=10,
        )
        d = entry.to_dict()
        e2 = AuditLogEntry.from_dict(d)
        assert e2.audit_id == entry.audit_id
        assert e2.operation == entry.operation
        assert e2.snapshot_id == entry.snapshot_id
        assert e2.trigger == entry.trigger
        assert e2.outcome == entry.outcome
        assert e2.reason == entry.reason
        assert e2.round_counter == entry.round_counter

    def test_from_dict_missing_optional_fields(self):
        d = {
            "audit_id": "audit_x",
            "operation": "restore",
            "timestamp": "2026-01-01",
        }
        e = AuditLogEntry.from_dict(d)
        assert e.snapshot_id == ""
        assert e.trigger == "manual"
        assert e.outcome == "success"
        assert e.reason == ""


# === Audit log tests (v0.8.15) ===


class TestSnapshotManagerAudit:
    def test_save_records_audit(self, snapshot_manager, snapshot_dir):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch, name="test")

        entries = snapshot_manager.list_audit_entries()
        assert len(entries) >= 1
        save_entry = [e for e in entries if e.operation == "save"][0]
        assert save_entry.snapshot_id == meta.snapshot_id
        assert save_entry.trigger == "manual"
        assert save_entry.outcome == "success"

    def test_restore_records_audit(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        agent._round_counter = 99
        snapshot_manager.restore(meta.snapshot_id, agent, orch)

        entries = snapshot_manager.list_audit_entries()
        restore_entries = [e for e in entries if e.operation == "restore"]
        assert len(restore_entries) >= 1

    def test_delete_records_audit(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)
        snapshot_manager.delete(meta.snapshot_id)

        entries = snapshot_manager.list_audit_entries()
        delete_entries = [e for e in entries if e.operation == "delete"]
        assert len(delete_entries) >= 1

    def test_audit_log_disabled(self, snapshot_dir):
        config = SnapshotConfig(
            enabled=True,
            audit_log_enabled=False,
            snapshot_dir=str(snapshot_dir),
        )
        manager = SnapshotManager(config=config)
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        manager.save(agent, orch)

        audit_path = snapshot_dir / "audit_log.jsonl"
        assert not audit_path.exists()

    def test_list_audit_entries_sorted_by_time(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        snapshot_manager.save(agent, orch, name="first")
        snapshot_manager.save(agent, orch, name="second")

        entries = snapshot_manager.list_audit_entries()
        # Newest first
        assert entries[0].timestamp >= entries[1].timestamp

    def test_list_audit_entries_empty(self):
        with tempfile.TemporaryDirectory() as d:
            config = SnapshotConfig(
                enabled=True,
                audit_log_enabled=True,
                snapshot_dir=d,
                audit_log_dir=d,
            )
            manager = SnapshotManager(config=config)
            assert manager.list_audit_entries() == []

    def test_save_emits_audit_event(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        emitted = []
        snapshot_manager._events.on(
            AgentEvent.AUDIT_LOG_ENTRY, lambda e, d: emitted.append(d)
        )
        snapshot_manager.save(agent, orch)
        assert len(emitted) >= 1
        assert emitted[0]["operation"] == "save"

    def test_delete_emits_snapshot_deleted_event(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        emitted = []
        snapshot_manager._events.on(
            AgentEvent.SNAPSHOT_DELETED, lambda e, d: emitted.append(d)
        )
        snapshot_manager.delete(meta.snapshot_id)
        assert len(emitted) == 1
        assert emitted[0]["snapshot_id"] == meta.snapshot_id


# === Rollback from audit tests (v0.8.15) ===


class TestSnapshotManagerRollbackFromAudit:
    def test_rollback_from_save_audit(self, snapshot_manager):
        agent = _make_agent(round_counter=5)
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        # Find the save audit entry
        entries = snapshot_manager.list_audit_entries()
        save_entry = [e for e in entries if e.operation == "save"][0]

        # Modify state
        agent._round_counter = 99

        # Rollback from audit
        assert snapshot_manager.rollback_from_audit(save_entry.audit_id, agent, orch)
        assert agent._round_counter == 5

    def test_rollback_from_nonexistent_audit(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        assert not snapshot_manager.rollback_from_audit(
            "audit_nonexistent", agent, orch
        )

    def test_rollback_from_delete_audit_fails(self, snapshot_manager):
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)
        snapshot_manager.delete(meta.snapshot_id)

        entries = snapshot_manager.list_audit_entries()
        delete_entry = [e for e in entries if e.operation == "delete"][0]

        assert not snapshot_manager.rollback_from_audit(
            delete_entry.audit_id, agent, orch
        )


# === Auto-rollback tests (v0.8.15) ===


from nano_agent.agent.consecutive_failure_detector import (
    ConsecutiveFailureResult,
)


class TestSnapshotManagerAutoRollback:
    def test_auto_rollback_restores_latest_snapshot(self, snapshot_dir):
        config = SnapshotConfig(
            enabled=True,
            auto_rollback_enabled=True,
            snapshot_dir=str(snapshot_dir),
        )
        manager = SnapshotManager(config=config, events=EventEmitter())
        agent = _make_agent(round_counter=5)
        orch = _make_orchestrator(agent)
        meta = manager.save(agent, orch)

        # Modify state
        agent._round_counter = 99

        failure_result = ConsecutiveFailureResult(
            triggered=True,
            consecutive_failures=3,
            last_tool_name="tool_a",
            last_error="error",
        )
        assert manager.attempt_auto_rollback(agent, orch, failure_result)
        assert agent._round_counter == 5

    def test_auto_rollback_no_snapshots(self, snapshot_dir):
        config = SnapshotConfig(
            enabled=True,
            auto_rollback_enabled=True,
            snapshot_dir=str(snapshot_dir),
        )
        manager = SnapshotManager(config=config, events=EventEmitter())
        agent = _make_agent()
        orch = _make_orchestrator(agent)

        failure_result = ConsecutiveFailureResult(
            triggered=True,
            consecutive_failures=3,
            last_tool_name="tool_a",
            last_error="error",
        )
        assert not manager.attempt_auto_rollback(agent, orch, failure_result)

    def test_auto_rollback_disabled(self, snapshot_dir):
        config = SnapshotConfig(
            enabled=True,
            auto_rollback_enabled=False,
            snapshot_dir=str(snapshot_dir),
        )
        manager = SnapshotManager(config=config, events=EventEmitter())
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        manager.save(agent, orch)

        failure_result = ConsecutiveFailureResult(
            triggered=True,
            consecutive_failures=3,
            last_tool_name="tool_a",
            last_error="error",
        )
        assert not manager.attempt_auto_rollback(agent, orch, failure_result)

    def test_auto_rollback_emits_events(self, snapshot_dir):
        config = SnapshotConfig(
            enabled=True,
            auto_rollback_enabled=True,
            snapshot_dir=str(snapshot_dir),
        )
        events = EventEmitter()
        manager = SnapshotManager(config=config, events=events)
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        manager.save(agent, orch)

        completed_events = []
        events.on(
            AgentEvent.AUTO_ROLLBACK_COMPLETED,
            lambda e, d: completed_events.append(d),
        )

        failure_result = ConsecutiveFailureResult(
            triggered=True,
            consecutive_failures=3,
            last_tool_name="tool_a",
            last_error="error",
        )
        manager.attempt_auto_rollback(agent, orch, failure_result)

        assert len(completed_events) == 1
        assert completed_events[0]["success"] is True

    def test_auto_rollback_records_audit(self, snapshot_dir):
        config = SnapshotConfig(
            enabled=True,
            auto_rollback_enabled=True,
            snapshot_dir=str(snapshot_dir),
        )
        manager = SnapshotManager(config=config, events=EventEmitter())
        agent = _make_agent()
        orch = _make_orchestrator(agent)
        manager.save(agent, orch)

        failure_result = ConsecutiveFailureResult(
            triggered=True,
            consecutive_failures=3,
            last_tool_name="tool_a",
            last_error="error",
        )
        manager.attempt_auto_rollback(agent, orch, failure_result)

        entries = manager.list_audit_entries()
        auto_entries = [e for e in entries if e.operation == "auto_rollback"]
        assert len(auto_entries) >= 1
        assert auto_entries[0].trigger == "auto_rollback"


# === Snapshot with CFD state tests (v0.8.15) ===


class TestSnapshotWithConsecutiveFailure:
    def test_snapshot_captures_cfd_state(self, snapshot_manager, snapshot_dir):
        agent = _make_agent()
        agent._subsystems.consecutive_failure_detector.record_tool_result(
            "tool_a", False, "err"
        )
        agent._subsystems.consecutive_failure_detector.record_tool_result(
            "tool_b", False, "err2"
        )
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        path = snapshot_dir / f"{meta.snapshot_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        cfd = data["consecutive_failure_detector"]
        assert cfd["consecutive_failures"] == 2
        assert cfd["last_failed_tool"] == "tool_b"

    def test_restore_applies_cfd_state(self, snapshot_manager):
        agent = _make_agent()
        agent._subsystems.consecutive_failure_detector.record_tool_result(
            "tool_a", False, "err"
        )
        orch = _make_orchestrator(agent)
        meta = snapshot_manager.save(agent, orch)

        # Reset CFD state
        agent._subsystems.consecutive_failure_detector.reset()
        assert agent._subsystems.consecutive_failure_detector._consecutive_failures == 0

        # Restore
        snapshot_manager.restore(meta.snapshot_id, agent, orch)
        assert agent._subsystems.consecutive_failure_detector._consecutive_failures == 1

    def test_from_dict_backward_compat_no_cfd(self):
        """v0.8.14 snapshots without CFD field should load with defaults."""
        d = {
            "metadata": {
                "snapshot_id": "snap_old",
                "created_at": "2026-01-01",
            },
            "orchestrator": {},
            "execution": {},
            "undo_stack": {},
            "tool_call_records": [],
            "memory": {},
            "token_budget": {},
            "cache": {},
            "circuit_breaker": {},
            "duplicate_detector": {},
            "stall_detector": {},
            "feedback_loop": {},
            "tracker": {},
        }
        s = Snapshot.from_dict(d)
        assert s.consecutive_failure_detector["consecutive_failures"] == 0
