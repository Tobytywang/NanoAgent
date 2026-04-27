"""
Persistent memory implementation - conversation history with persistence.
"""

import uuid
from dataclasses import dataclass, field
from typing import Literal

from .base import BaseMemory
from .storage.base import BaseStorage, MemoryEntry


@dataclass
class PersistentMemory(BaseMemory):
    """Persistent memory: conversation history with file-based storage."""

    storage: BaseStorage
    session_id: str | None = None
    max_messages: int = 50
    system_prompt: str = "You are a helpful AI assistant."
    _messages: list = field(default_factory=list)
    _loaded: bool = False

    def __post_init__(self):
        """Initialize or load session."""
        if self.session_id is None:
            self.session_id = self._generate_session_id()
        self._load_or_init()

    def _generate_session_id(self) -> str:
        """Generate a unique session id."""
        return f"session_{uuid.uuid4().hex[:8]}"

    def _load_or_init(self) -> None:
        """Load existing session or initialize new one."""
        if self.storage.session_exists(self.session_id):
            entries = self.storage.load_session(self.session_id)
            # Prepend system message, then add loaded messages
            self._messages = [{"role": "system", "content": self.system_prompt}]
            self._messages.extend([self._entry_to_message(e) for e in entries])
            self._loaded = True
        else:
            self._messages = [{"role": "system", "content": self.system_prompt}]
            self._loaded = False

    def _entry_to_message(self, entry: MemoryEntry) -> dict:
        """Convert MemoryEntry to message dict."""
        msg = {"role": entry.role, "content": entry.content}
        if entry.metadata:
            # Add metadata fields like tool_calls, tool_call_id
            for key, value in entry.metadata.items():
                msg[key] = value
        return msg

    def _message_to_entry(self, message: dict) -> MemoryEntry:
        """Convert message dict to MemoryEntry."""
        role = message.get("role", "user")
        content = message.get("content", "")

        # Extract metadata (everything except role and content)
        metadata = {k: v for k, v in message.items() if k not in ["role", "content"]}

        return MemoryEntry.create(
            session_id=self.session_id,
            role=role,
            content=content,
            metadata=metadata if metadata else None
        )

    def add(self, message: dict) -> None:
        """Add a message to history and persist it."""
        self._messages.append(message)
        entry = self._message_to_entry(message)
        self.storage.save(entry)
        self._trim_if_needed()

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.add({"role": "user", "content": content})

    def add_assistant_message(
        self,
        content: str,
        tool_calls: list | None = None
    ) -> None:
        """Add an assistant message, optionally with tool calls."""
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.add(msg)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool execution result."""
        self.add({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })

    def get_all(self) -> list:
        """Get all messages."""
        return self._messages.copy()

    def clear(self) -> None:
        """Clear history (keep system message) and delete storage."""
        self._messages = [{"role": "system", "content": self.system_prompt}]
        self.storage.delete_session(self.session_id)
        self._loaded = False

    def get_context(self, max_messages: int | None = None) -> list:
        """Get context, optionally limited to max_messages."""
        if max_messages is None:
            return self.get_all()

        if len(self._messages) <= max_messages:
            return self.get_all()

        system_msg = self._messages[0]
        recent = self._messages[-(max_messages - 1):]
        return [system_msg] + recent

    def _trim_if_needed(self) -> None:
        """Trim old messages if exceeding limit (in memory only)."""
        if len(self._messages) > self.max_messages:
            system_msg = self._messages[0]
            recent = self._messages[-(self.max_messages - 1):]
            self._messages = [system_msg] + recent

    def set_system_prompt(self, prompt: str) -> None:
        """Set or update the system prompt."""
        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = prompt
        else:
            self._messages.insert(0, {"role": "system", "content": prompt})

    def new_session(self) -> str:
        """Start a new session."""
        self.session_id = self._generate_session_id()
        self._messages = [{"role": "system", "content": self.system_prompt}]
        self._loaded = False
        return self.session_id

    def load_session(self, session_id: str) -> bool:
        """
        Load an existing session.

        Args:
            session_id: The session to load

        Returns:
            True if session was loaded, False if not found
        """
        if self.storage.session_exists(session_id):
            self.session_id = session_id
            self._load_or_init()
            return True
        return False

    def list_sessions(self) -> list[str]:
        """List all available sessions."""
        return self.storage.list_sessions()

    def is_loaded(self) -> bool:
        """Check if this is a loaded session (vs new)."""
        return self._loaded

    def __len__(self) -> int:
        """Return number of messages."""
        return len(self._messages)
