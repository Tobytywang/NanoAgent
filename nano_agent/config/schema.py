"""
Configuration data structures.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: Literal["ollama"] = "ollama"
    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    temperature: float = 0.7


@dataclass
class AgentConfig:
    """Agent configuration."""
    max_iterations: int = 10
    verbose: bool = True
    system_prompt: str | None = None


@dataclass
class MemoryConfig:
    """Memory configuration."""
    max_messages: int = 50
    type: Literal["short_term"] = "short_term"


@dataclass
class ToolConfig:
    """Tool configuration."""
    enabled: list[str] = field(default_factory=lambda: ["all"])
    disabled: list[str] = field(default_factory=list)


@dataclass
class Config:
    """Main configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
