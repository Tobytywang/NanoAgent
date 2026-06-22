"""
Tests for global state snapshot (v0.8.14).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from nano_agent.agent.snapshot import Snapshot, SnapshotMetadata, SnapshotManager
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
        assert m2.version == "0.8.14"

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

    def test_snapshot_config_in_main_config(self):
        from nano_agent.config.schema import Config

        config = Config()
        assert hasattr(config, "snapshot")
        assert isinstance(config.snapshot, SnapshotConfig)
