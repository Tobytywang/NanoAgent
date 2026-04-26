"""
Configuration file loader.
"""

import yaml
from pathlib import Path
from typing import Any

from .schema import Config, LLMConfig, AgentConfig, MemoryConfig, ToolConfig


class ConfigLoader:
    """Load configuration from YAML files."""

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to configuration file. If None, returns default config.

        Returns:
            Config object
        """
        if config_path is None:
            return Config()

        path = Path(config_path)

        if not path.exists():
            return Config()  # Return default config if file doesn't exist

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls._parse_config(data)

    @classmethod
    def _parse_config(cls, data: dict) -> Config:
        """Parse configuration dictionary."""
        return Config(
            llm=cls._parse_llm_config(data.get("llm", {})),
            agent=cls._parse_agent_config(data.get("agent", {})),
            memory=cls._parse_memory_config(data.get("memory", {})),
            tools=cls._parse_tool_config(data.get("tools", {}))
        )

    @classmethod
    def _parse_llm_config(cls, data: dict) -> LLMConfig:
        """Parse LLM configuration."""
        return LLMConfig(
            provider=data.get("provider", "ollama"),
            model=data.get("model", "llama3"),
            base_url=data.get("base_url", "http://localhost:11434"),
            api_key=data.get("api_key"),
            api_key_env=data.get("api_key_env", "OPENAI_API_KEY"),
            timeout=data.get("timeout", 120),
            temperature=data.get("temperature", 0.7)
        )

    @classmethod
    def _parse_agent_config(cls, data: dict) -> AgentConfig:
        """Parse agent configuration."""
        return AgentConfig(
            max_iterations=data.get("max_iterations", 10),
            verbose=data.get("verbose", True),
            system_prompt=data.get("system_prompt")
        )

    @classmethod
    def _parse_memory_config(cls, data: dict) -> MemoryConfig:
        """Parse memory configuration."""
        return MemoryConfig(
            max_messages=data.get("max_messages", 50),
            type=data.get("type", "short_term")
        )

    @classmethod
    def _parse_tool_config(cls, data: dict) -> ToolConfig:
        """Parse tool configuration."""
        return ToolConfig(
            enabled=data.get("enabled", ["all"]),
            disabled=data.get("disabled", [])
        )

    @classmethod
    def save(cls, config: Config, config_path: str | Path) -> None:
        """
        Save configuration to a YAML file.

        Args:
            config: Config object to save
            config_path: Path to save to
        """
        path = Path(config_path)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "llm": {
                "provider": config.llm.provider,
                "model": config.llm.model,
                "base_url": config.llm.base_url,
                "api_key": config.llm.api_key,
                "api_key_env": config.llm.api_key_env,
                "timeout": config.llm.timeout,
                "temperature": config.llm.temperature
            },
            "agent": {
                "max_iterations": config.agent.max_iterations,
                "verbose": config.agent.verbose,
                "system_prompt": config.agent.system_prompt
            },
            "memory": {
                "type": config.memory.type,
                "max_messages": config.memory.max_messages
            },
            "tools": {
                "enabled": config.tools.enabled,
                "disabled": config.tools.disabled
            }
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
