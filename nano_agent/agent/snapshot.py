"""
Global state snapshot for one-click save/restore of agent state (v0.8.14).

Provides a "save/load game" mechanism: capture all serializable agent state
into a JSON file, and restore to any saved point on demand.

v0.8.15: Audit log + auto-rollback — audit log links operations to snapshots,
enabling rollback from audit entries; auto-rollback on consecutive failures.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import __version__
from .types import AgentEvent, ExecutionMode

if TYPE_CHECKING:
    from .events import EventEmitter
    from .react import ReActAgent
    from .orchestrator import AgentOrchestrator
    from ..config.schema import SnapshotConfig


@dataclass
class SnapshotMetadata:
    """Lightweight metadata for snapshot indexing (no full payload)."""

    snapshot_id: str
    name: str
    created_at: str
    session_id: str
    round_counter: int
    message_count: int
    total_tokens: int
    version: str = field(default_factory=lambda: __version__)

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "name": self.name,
            "created_at": self.created_at,
            "session_id": self.session_id,
            "round_counter": self.round_counter,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SnapshotMetadata":
        return cls(
            snapshot_id=data["snapshot_id"],
            name=data.get("name", ""),
            created_at=data["created_at"],
            session_id=data.get("session_id", ""),
            round_counter=data.get("round_counter", 0),
            message_count=data.get("message_count", 0),
            total_tokens=data.get("total_tokens", 0),
            version=data.get("version", __version__),
        )


@dataclass
class AuditLogEntry:
    """Append-only audit log entry for snapshot operations (v0.8.15)."""

    audit_id: str
    operation: str  # "save" | "restore" | "delete" | "auto_rollback"
    snapshot_id: str
    timestamp: str
    session_id: str
    trigger: str  # "manual" | "auto" | "auto_rollback" | "audit_rollback"
    outcome: str  # "success" | "failure"
    reason: str = ""
    round_counter: int = 0
    message_count: int = 0

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "operation": self.operation,
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "trigger": self.trigger,
            "outcome": self.outcome,
            "reason": self.reason,
            "round_counter": self.round_counter,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditLogEntry":
        return cls(
            audit_id=data["audit_id"],
            operation=data["operation"],
            snapshot_id=data.get("snapshot_id", ""),
            timestamp=data["timestamp"],
            session_id=data.get("session_id", ""),
            trigger=data.get("trigger", "manual"),
            outcome=data.get("outcome", "success"),
            reason=data.get("reason", ""),
            round_counter=data.get("round_counter", 0),
            message_count=data.get("message_count", 0),
        )


@dataclass
class Snapshot:
    """Complete serializable agent state."""

    metadata: SnapshotMetadata
    orchestrator: dict
    execution: dict
    undo_stack: dict
    tool_call_records: list
    memory: dict
    token_budget: dict
    cache: dict
    circuit_breaker: dict
    duplicate_detector: dict
    stall_detector: dict
    feedback_loop: dict
    tracker: dict
    consecutive_failure_detector: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "orchestrator": self.orchestrator,
            "execution": self.execution,
            "undo_stack": self.undo_stack,
            "tool_call_records": self.tool_call_records,
            "memory": self.memory,
            "token_budget": self.token_budget,
            "cache": self.cache,
            "circuit_breaker": self.circuit_breaker,
            "duplicate_detector": self.duplicate_detector,
            "stall_detector": self.stall_detector,
            "feedback_loop": self.feedback_loop,
            "tracker": self.tracker,
            "consecutive_failure_detector": self.consecutive_failure_detector,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        return cls(
            metadata=SnapshotMetadata.from_dict(data["metadata"]),
            orchestrator=data["orchestrator"],
            execution=data["execution"],
            undo_stack=data["undo_stack"],
            tool_call_records=data["tool_call_records"],
            memory=data["memory"],
            token_budget=data["token_budget"],
            cache=data["cache"],
            circuit_breaker=data["circuit_breaker"],
            duplicate_detector=data["duplicate_detector"],
            stall_detector=data["stall_detector"],
            feedback_loop=data.get("feedback_loop", {}),
            tracker=data["tracker"],
            consecutive_failure_detector=data.get(
                "consecutive_failure_detector",
                {
                    "consecutive_failures": 0,
                    "last_failed_tool": None,
                    "last_error": None,
                },
            ),
        )


class SnapshotManager:
    """Manages save/restore/list/delete of agent state snapshots."""

    def __init__(
        self,
        config: "SnapshotConfig | None" = None,
        events: "EventEmitter | None" = None,
    ):
        self._config = config or _default_config()
        self._events = events
        self._snapshot_dir = Path(self._config.snapshot_dir)

    # --- Core operations ---

    def save(
        self,
        agent: "ReActAgent",
        orchestrator: "AgentOrchestrator",
        name: str = "",
        trigger: str = "manual",
    ) -> SnapshotMetadata:
        """Capture current agent state and persist to disk."""
        snapshot = self._capture(agent, orchestrator, name)
        self._persist(snapshot)
        self._enforce_max_snapshots()

        if self._events:
            self._events.emit(
                AgentEvent.SNAPSHOT_SAVED,
                {
                    "snapshot_id": snapshot.metadata.snapshot_id,
                    "name": snapshot.metadata.name,
                    "round_counter": snapshot.metadata.round_counter,
                },
            )

        self._record_audit(
            operation="save",
            snapshot_id=snapshot.metadata.snapshot_id,
            session_id=orchestrator.session_id,
            trigger=trigger,
            outcome="success",
            reason=f"Snapshot saved: {name}" if name else "Snapshot saved",
            round_counter=agent._round_counter,
            message_count=len(agent.memory.get_all()),
        )

        return snapshot.metadata

    def restore(
        self,
        snapshot_id: str,
        agent: "ReActAgent",
        orchestrator: "AgentOrchestrator",
        trigger: str = "manual",
    ) -> bool:
        """Load snapshot from disk and apply to agent/orchestrator in-place."""
        snapshot = self._load(snapshot_id)
        if snapshot is None:
            return False

        try:
            self._apply(snapshot, agent, orchestrator)
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Failed to apply snapshot %s: %s", snapshot_id, e
            )
            self._record_audit(
                operation="restore",
                snapshot_id=snapshot_id,
                session_id=orchestrator.session_id,
                trigger=trigger,
                outcome="failure",
                reason=f"Restore failed: {e}",
                round_counter=agent._round_counter,
                message_count=len(agent.memory.get_all()),
            )
            return False

        if self._events:
            self._events.emit(
                AgentEvent.SNAPSHOT_RESTORED,
                {
                    "snapshot_id": snapshot_id,
                    "round_counter": snapshot.metadata.round_counter,
                },
            )

        self._record_audit(
            operation="restore",
            snapshot_id=snapshot_id,
            session_id=orchestrator.session_id,
            trigger=trigger,
            outcome="success",
            reason=f"Restored to snapshot: {snapshot_id}",
            round_counter=agent._round_counter,
            message_count=len(agent.memory.get_all()),
        )

        return True

    def list_snapshots(self) -> list[SnapshotMetadata]:
        """List all stored snapshots (metadata only)."""
        if not self._snapshot_dir.exists():
            return []

        results = []
        for path in self._snapshot_dir.glob("snap_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                metadata = SnapshotMetadata.from_dict(data["metadata"])
                results.append(metadata)
            except Exception:
                continue

        results.sort(key=lambda m: m.created_at, reverse=True)
        return results

    def delete(self, snapshot_id: str) -> bool:
        """Delete a snapshot by ID."""
        path = self._snapshot_path(snapshot_id)
        if path.exists():
            path.unlink()
            if self._events:
                self._events.emit(
                    AgentEvent.SNAPSHOT_DELETED,
                    {"snapshot_id": snapshot_id},
                )
            self._record_audit(
                operation="delete",
                snapshot_id=snapshot_id,
                session_id="",
                trigger="manual",
                outcome="success",
                reason=f"Snapshot deleted: {snapshot_id}",
            )
            return True
        return False

    def maybe_auto_snapshot(
        self, agent: "ReActAgent", orchestrator: "AgentOrchestrator"
    ) -> None:
        """Auto-save before each run() if configured."""
        if self._config.enabled and self._config.auto_snapshot:
            self.save(agent, orchestrator, name="auto", trigger="auto")

    # --- Capture helpers ---

    def _capture(
        self,
        agent: "ReActAgent",
        orchestrator: "AgentOrchestrator",
        name: str,
    ) -> Snapshot:
        snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        messages = agent.memory.get_all()
        msg_count = len(messages)

        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            name=name,
            created_at=now,
            session_id=orchestrator.session_id,
            round_counter=agent._round_counter,
            message_count=msg_count,
            total_tokens=agent._total_tokens,
        )

        return Snapshot(
            metadata=metadata,
            orchestrator=self._capture_orchestrator(orchestrator),
            execution=self._capture_execution(agent),
            undo_stack=self._capture_undo_stack(agent),
            tool_call_records=list(agent._tool_call_records),
            memory=self._capture_memory(agent, messages),
            token_budget=self._capture_token_budget(agent),
            cache=self._capture_cache(agent),
            circuit_breaker=self._capture_circuit_breaker(agent),
            duplicate_detector=self._capture_duplicate_detector(agent),
            stall_detector=self._capture_stall_detector(agent),
            feedback_loop=self._capture_feedback_loop(agent),
            tracker=self._capture_tracker(agent),
            consecutive_failure_detector=self._capture_consecutive_failure_detector(
                agent
            ),
        )

    def _capture_orchestrator(self, orchestrator: "AgentOrchestrator") -> dict:
        return {
            "session_id": orchestrator.session_id,
            "stats": {
                "total_tokens": orchestrator.stats.total_tokens,
                "total_tool_calls": orchestrator.stats.total_tool_calls,
                "total_iterations": orchestrator.stats.total_iterations,
            },
        }

    def _capture_execution(self, agent: "ReActAgent") -> dict:
        return {
            "_round_counter": agent._round_counter,
            "_session_id": agent._session_id,
            "_total_tokens": agent._total_tokens,
            "_routing_max_tools": agent._routing_max_tools,
            "_wrapup_issued": agent._wrapup_issued,
            "_last_prompt_tokens": agent._last_prompt_tokens,
            "_stable_system_prompt": agent._stable_system_prompt,
            "skill_prompt": agent.skill_prompt,
            "verbose": agent.verbose,
        }

    def _capture_undo_stack(self, agent: "ReActAgent") -> dict:
        records = []
        for r in agent._undo_stack._records:
            records.append(
                {
                    "tool_name": r.tool_name,
                    "undo_data": r.undo_data,
                    "timestamp": r.timestamp,
                    "round_id": r.round_id,
                }
            )
        return {
            "records": records,
            "current_round": agent._undo_stack._current_round,
        }

    def _capture_memory(self, agent: "ReActAgent", messages: list) -> dict:
        from ..memory.hybrid import HybridMemory
        from ..memory.short_term import ShortTermMemory
        from ..memory.persistent import PersistentMemory

        mem = agent.memory
        result: dict[str, Any] = {
            "messages": list(messages),
            "system_prompt": getattr(mem, "system_prompt", ""),
            "stable_system_prompt": getattr(mem, "stable_system_prompt", ""),
        }

        if isinstance(mem, HybridMemory):
            result["type"] = "hybrid"
            result["session_id"] = mem.session_id
            result["auto_extract"] = mem.auto_extract
            result["long_term_entries"] = [
                e.to_dict() for e in mem.long_term_memory.entries
            ]
        elif isinstance(mem, PersistentMemory):
            result["type"] = "persistent"
            result["session_id"] = getattr(mem, "session_id", "")
        elif isinstance(mem, ShortTermMemory):
            result["type"] = "short_term"
        else:
            result["type"] = "unknown"

        return result

    def _capture_token_budget(self, agent: "ReActAgent") -> dict:
        tb = agent.token_budget
        if tb is None:
            return {}
        return {
            "initial_budget": tb.initial_budget,
            "remaining": tb.remaining,
            "_total_consumed": tb._total_consumed,
            "_calibration_data": [
                {"estimated": d.estimated, "actual": d.actual}
                for d in tb._calibration_data
            ],
            "_calibration_factor": tb._calibration_factor,
            "_last_warning_level": tb._last_warning_level,
            "_warnings_issued": tb._warnings_issued,
            "_last_warning_iteration": tb._last_warning_iteration,
        }

    def _capture_cache(self, agent: "ReActAgent") -> dict:
        cache = agent.cache
        if cache is None:
            return {}
        entries = []
        for key, entry in cache._cache.items():
            entries.append(
                {
                    "key": key,
                    "tool_name": entry.tool_name,
                    "args_key": entry.args_key,
                    "result": entry.result,
                    "timestamp": entry.timestamp,
                    "token_count": entry.token_count,
                    "file_paths": list(entry.file_paths),
                    "file_mtimes": dict(entry.file_mtimes),
                    "is_offloaded": entry.is_offloaded,
                }
            )
        return {
            "entries": entries,
            "access_order": list(cache._access_order),
        }

    def _capture_circuit_breaker(self, agent: "ReActAgent") -> dict:
        cb = agent.circuit_breaker
        if cb is None:
            return {}
        return {
            "mode": cb._mode.value,
            "trigger_reason": cb._trigger_reason,
        }

    def _capture_duplicate_detector(self, agent: "ReActAgent") -> dict:
        dd = agent._subsystems.duplicate_detector
        return {
            "call_history": dict(dd._call_history),
            "warning_issued": dd.warning_issued,
        }

    def _capture_stall_detector(self, agent: "ReActAgent") -> dict:
        sd = agent._subsystems.stall_detector
        return {
            "iteration_signatures": list(sd._iteration_signatures),
            "stall_count": sd._stall_count,
            "hint_index": sd._hint_index,
        }

    def _capture_feedback_loop(self, agent: "ReActAgent") -> dict:
        fl = agent._subsystems.feedback_loop
        if fl is None:
            return {}
        return {
            "deviation_warning_count": fl._deviation_warning_count,
            "deviation_injections": fl._deviation_injections,
            "over_hint_index": fl._over_hint_index,
            "under_hint_index": fl._under_hint_index,
            "correction_attempts": fl._correction_attempts,
        }

    def _capture_tracker(self, agent: "ReActAgent") -> dict:
        tracker = agent.tracker
        return {
            "session_total_tokens": tracker._session_total_tokens,
            "session_total_iterations": tracker._session_total_iterations,
            "session_total_llm_calls": tracker._session_total_llm_calls,
            "session_total_tool_calls": tracker._session_total_tool_calls,
            "session_successful_tool_calls": tracker._session_successful_tool_calls,
            "session_failed_tool_calls": tracker._session_failed_tool_calls,
            "run_counter": tracker._run_counter,
        }

    def _capture_consecutive_failure_detector(self, agent: "ReActAgent") -> dict:
        cfd = agent._subsystems.consecutive_failure_detector
        return cfd.get_state()

    # --- Restore helpers ---

    def _apply(
        self,
        snapshot: Snapshot,
        agent: "ReActAgent",
        orchestrator: "AgentOrchestrator",
    ) -> None:
        self._apply_orchestrator(snapshot.orchestrator, orchestrator)
        self._apply_execution(snapshot.execution, agent)
        self._apply_undo_stack(snapshot.undo_stack, agent)
        agent._tool_call_records = list(snapshot.tool_call_records)
        self._apply_memory(snapshot.memory, agent)
        self._apply_token_budget(snapshot.token_budget, agent)
        self._apply_cache(snapshot.cache, agent)
        self._apply_circuit_breaker(snapshot.circuit_breaker, agent)
        self._apply_duplicate_detector(snapshot.duplicate_detector, agent)
        self._apply_stall_detector(snapshot.stall_detector, agent)
        self._apply_feedback_loop(snapshot.feedback_loop, agent)
        self._apply_tracker(snapshot.tracker, agent)
        self._apply_consecutive_failure_detector(
            snapshot.consecutive_failure_detector, agent
        )

        agent._setup_system_prompt()

    def _apply_orchestrator(
        self, data: dict, orchestrator: "AgentOrchestrator"
    ) -> None:
        orchestrator.session_id = data["session_id"]
        stats = data.get("stats", {})
        orchestrator.stats.total_tokens = stats.get("total_tokens", 0)
        orchestrator.stats.total_tool_calls = stats.get("total_tool_calls", 0)
        orchestrator.stats.total_iterations = stats.get("total_iterations", 0)

    def _apply_execution(self, data: dict, agent: "ReActAgent") -> None:
        agent._round_counter = data.get("_round_counter", 0)
        agent._session_id = data.get("_session_id", "")
        agent._total_tokens = data.get("_total_tokens", 0)
        agent._routing_max_tools = data.get("_routing_max_tools", -1)
        agent._wrapup_issued = data.get("_wrapup_issued", False)
        agent._last_prompt_tokens = data.get("_last_prompt_tokens")
        agent._stable_system_prompt = data.get("_stable_system_prompt", "")
        agent.skill_prompt = data.get("skill_prompt", "")
        agent.verbose = data.get("verbose", True)

    def _apply_undo_stack(self, data: dict, agent: "ReActAgent") -> None:
        from .undo import UndoRecord

        records = []
        for r_data in data.get("records", []):
            records.append(
                UndoRecord(
                    tool_name=r_data["tool_name"],
                    undo_data=r_data["undo_data"],
                    timestamp=r_data["timestamp"],
                    round_id=r_data["round_id"],
                )
            )
        agent._undo_stack._records = records
        agent._undo_stack._current_round = data.get("current_round", "")

    def _apply_memory(self, data: dict, agent: "ReActAgent") -> None:
        from ..memory.hybrid import HybridMemory
        from ..memory.long_term import LongTermEntry

        mem = agent.memory
        mem_type = data.get("type", "unknown")

        # Restore messages
        messages = data.get("messages", [])
        mem._messages = list(messages)

        # Restore system prompt fields
        if hasattr(mem, "system_prompt"):
            mem.system_prompt = data.get("system_prompt", mem.system_prompt)
        if hasattr(mem, "stable_system_prompt"):
            mem.stable_system_prompt = data.get("stable_system_prompt", "")

        # HybridMemory: restore long-term entries
        if mem_type == "hybrid" and isinstance(mem, HybridMemory):
            if "session_id" in data:
                mem.session_id = data["session_id"]
            ltm_data = data.get("long_term_entries", [])
            mem.long_term_memory.entries = [
                LongTermEntry.from_dict(e) for e in ltm_data
            ]
            mem.long_term_memory._save()

    def _apply_token_budget(self, data: dict, agent: "ReActAgent") -> None:
        from .token_budget import CalibrationData

        tb = agent.token_budget
        if tb is None or not data:
            return

        tb.initial_budget = data.get("initial_budget", tb.initial_budget)
        tb.remaining = data.get("remaining", tb.remaining)
        tb._total_consumed = data.get("_total_consumed", 0)

        cal_data = data.get("_calibration_data", [])
        tb._calibration_data = [
            CalibrationData(estimated=d["estimated"], actual=d["actual"])
            for d in cal_data
        ]
        tb._calibration_factor = data.get("_calibration_factor", 1.0)
        tb._last_warning_level = data.get("_last_warning_level", -1)
        tb._warnings_issued = data.get("_warnings_issued", 0)
        tb._last_warning_iteration = data.get("_last_warning_iteration", 0)

    def _apply_cache(self, data: dict, agent: "ReActAgent") -> None:
        from .cache import CacheEntry

        cache = agent.cache
        if cache is None or not data:
            return

        cache._cache = {}
        for entry_data in data.get("entries", []):
            entry = CacheEntry(
                tool_name=entry_data["tool_name"],
                args_key=entry_data["args_key"],
                result=entry_data["result"],
                timestamp=entry_data["timestamp"],
                token_count=entry_data["token_count"],
                file_paths=entry_data.get("file_paths", []),
                file_mtimes=entry_data.get("file_mtimes", {}),
                is_offloaded=entry_data.get("is_offloaded", False),
            )
            cache._cache[entry_data["key"]] = entry

        cache._access_order = list(data.get("access_order", []))

    def _apply_circuit_breaker(self, data: dict, agent: "ReActAgent") -> None:
        cb = agent.circuit_breaker
        if cb is None or not data:
            return
        cb._mode = ExecutionMode(data.get("mode", ExecutionMode.AUTO.value))
        cb._trigger_reason = data.get("trigger_reason")

    def _apply_duplicate_detector(self, data: dict, agent: "ReActAgent") -> None:
        dd = agent._subsystems.duplicate_detector
        dd._call_history = dict(data.get("call_history", {}))
        dd.warning_issued = data.get("warning_issued", False)

    def _apply_stall_detector(self, data: dict, agent: "ReActAgent") -> None:
        sd = agent._subsystems.stall_detector
        sd._iteration_signatures = list(data.get("iteration_signatures", []))
        sd._stall_count = data.get("stall_count", 0)
        sd._hint_index = data.get("hint_index", 0)

    def _apply_feedback_loop(self, data: dict, agent: "ReActAgent") -> None:
        fl = agent._subsystems.feedback_loop
        if fl is None or not data:
            return
        fl._deviation_warning_count = data.get("deviation_warning_count", 0)
        fl._deviation_injections = data.get("deviation_injections", 0)
        fl._over_hint_index = data.get("over_hint_index", 0)
        fl._under_hint_index = data.get("under_hint_index", 0)
        fl._correction_attempts = data.get("correction_attempts", 0)

    def _apply_tracker(self, data: dict, agent: "ReActAgent") -> None:
        tracker = agent.tracker
        tracker._session_total_tokens = data.get("session_total_tokens", 0)
        tracker._session_total_iterations = data.get("session_total_iterations", 0)
        tracker._session_total_llm_calls = data.get("session_total_llm_calls", 0)
        tracker._session_total_tool_calls = data.get("session_total_tool_calls", 0)
        tracker._session_successful_tool_calls = data.get(
            "session_successful_tool_calls", 0
        )
        tracker._session_failed_tool_calls = data.get("session_failed_tool_calls", 0)
        tracker._run_counter = data.get("run_counter", 0)

    def _apply_consecutive_failure_detector(
        self, data: dict, agent: "ReActAgent"
    ) -> None:
        if data:
            agent._subsystems.consecutive_failure_detector.set_state(data)

    # --- Audit & Rollback (v0.8.15) ---

    def _enforce_max_audit_entries(self) -> None:
        """Trim audit log if it exceeds max_audit_entries."""
        max_entries = self._config.max_audit_entries
        if max_entries <= 0:
            return

        path = self._audit_path()
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) <= max_entries:
            return

        # Keep the most recent entries
        kept = lines[-max_entries:]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(kept)

    def _record_audit(
        self,
        operation: str,
        snapshot_id: str,
        session_id: str,
        trigger: str,
        outcome: str,
        reason: str = "",
        round_counter: int = 0,
        message_count: int = 0,
    ) -> None:
        """Append an audit log entry to JSONL file."""
        if not self._config.audit_log_enabled:
            return

        entry = AuditLogEntry(
            audit_id=f"audit_{uuid.uuid4().hex[:8]}",
            operation=operation,
            snapshot_id=snapshot_id,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            trigger=trigger,
            outcome=outcome,
            reason=reason,
            round_counter=round_counter,
            message_count=message_count,
        )

        audit_path = self._audit_path()
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        entry_dict = entry.to_dict()
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_dict, ensure_ascii=False) + "\n")

        if self._events:
            self._events.emit(AgentEvent.AUDIT_LOG_ENTRY, entry_dict)

        self._enforce_max_audit_entries()

    def _audit_path(self) -> Path:
        return Path(self._config.audit_log_dir) / "audit_log.jsonl"

    def list_audit_entries(self, limit: int = 50) -> list[AuditLogEntry]:
        """Read audit log from disk, return most recent entries.

        Reads from the end of the JSONL file for efficiency, since entries
        are naturally appended in chronological order.
        """
        path = self._audit_path()
        if not path.exists():
            return []

        entries: list[AuditLogEntry] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(AuditLogEntry.from_dict(json.loads(line)))
                    except Exception:
                        continue

        # Entries are naturally in chronological order (oldest first);
        # reverse to get newest first, then trim.
        entries.reverse()
        return entries[:limit]

    def rollback_from_audit(
        self,
        audit_id: str,
        agent: "ReActAgent",
        orchestrator: "AgentOrchestrator",
    ) -> bool:
        """Find audit entry and restore the referenced snapshot."""
        entries = self.list_audit_entries(limit=200)
        target = None
        for entry in entries:
            if entry.audit_id == audit_id:
                target = entry
                break

        if target is None or not target.snapshot_id:
            return False

        # Only allow rollback from save/restore/auto_rollback entries
        if target.operation not in ("save", "restore", "auto_rollback"):
            return False

        success = self.restore(
            target.snapshot_id, agent, orchestrator, trigger="audit_rollback"
        )

        if success:
            self._record_audit(
                operation="restore",
                snapshot_id=target.snapshot_id,
                session_id=orchestrator.session_id,
                trigger="audit_rollback",
                outcome="success",
                reason=f"Rollback from audit entry: {audit_id}",
                round_counter=agent._round_counter,
                message_count=len(agent.memory.get_all()),
            )

        return success

    def attempt_auto_rollback(
        self,
        agent: "ReActAgent",
        orchestrator: "AgentOrchestrator",
        failure_result: Any,
    ) -> bool:
        """Auto-rollback to most recent snapshot on consecutive failures."""
        if not self._config.auto_rollback_enabled:
            return False

        snapshots = self.list_snapshots()
        if not snapshots:
            return False

        target = snapshots[0]  # Already sorted newest-first

        success = self.restore(
            target.snapshot_id, agent, orchestrator, trigger="auto_rollback"
        )

        self._record_audit(
            operation="auto_rollback",
            snapshot_id=target.snapshot_id,
            session_id=orchestrator.session_id,
            trigger="auto_rollback",
            outcome="success" if success else "failure",
            reason=(
                f"Consecutive failures: {failure_result.consecutive_failures}, "
                f"last tool: {failure_result.last_tool_name}"
            ),
            round_counter=agent._round_counter,
            message_count=len(agent.memory.get_all()),
        )

        if self._events:
            self._events.emit(
                AgentEvent.AUTO_ROLLBACK_COMPLETED,
                {"snapshot_id": target.snapshot_id, "success": success},
            )

        return success

    # --- Storage helpers ---

    def _snapshot_path(self, snapshot_id: str) -> Path:
        return self._snapshot_dir / f"{snapshot_id}.json"

    def _persist(self, snapshot: Snapshot) -> None:
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self._snapshot_path(snapshot.metadata.snapshot_id)
        path.write_text(
            json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load(self, snapshot_id: str) -> Snapshot | None:
        path = self._snapshot_path(snapshot_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Snapshot.from_dict(data)
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def _enforce_max_snapshots(self) -> None:
        snapshots = self.list_snapshots()
        while len(snapshots) > self._config.max_snapshots:
            oldest = snapshots[-1]
            self.delete(oldest.snapshot_id)
            snapshots.pop()


def _default_config():
    """Create default SnapshotConfig without importing schema at module level."""
    from ..config.schema import SnapshotConfig

    return SnapshotConfig()
