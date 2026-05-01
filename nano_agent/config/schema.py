"""
Configuration data structures.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: Literal["ollama", "openai", "deepseek", "moonshot", "openai_compatible"] = "ollama"
    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
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
    type: Literal["short_term", "persistent", "hybrid"] = "short_term"
    # Persistent memory options
    storage_type: Literal["file"] = "file"
    storage_path: str = ".nano_agent/memory"
    session_id: str | None = None  # Optional: resume specific session
    # Hybrid memory options
    long_term_storage_path: str = ".nano_agent/long_term_memory"
    auto_extract: bool = True  # Auto-extract important info to long-term memory


@dataclass
class ToolConfig:
    """Tool configuration."""
    enabled: list[str] = field(default_factory=lambda: ["all"])
    disabled: list[str] = field(default_factory=list)


@dataclass
class SkillsConfig:
    """Skills configuration."""
    enabled: list[str] = field(default_factory=list)  # 启用的技能包名称
    directory: str = ".nano_agent/skills"  # 技能包目录
    configs: dict = field(default_factory=dict)  # 各技能包的额外配置


@dataclass
class Config:
    """Main configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
