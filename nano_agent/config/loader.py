"""
配置文件加载器
"""

import yaml
from pathlib import Path
from typing import Any

from .schema import Config, LLMConfig, AgentConfig, MemoryConfig, ToolConfig, SkillsConfig


class ConfigLoader:
    """从 YAML 文件加载配置"""

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        """
        从 YAML 文件加载配置。

        Args:
            config_path: 配置文件路径。None 时返回默认配置。

        Returns:
            Config 对象
        """
        if config_path is None:
            return Config()

        path = Path(config_path)

        if not path.exists():
            return Config()  # 文件不存在时返回默认配置

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls._parse_config(data)

    @classmethod
    def _parse_config(cls, data: dict) -> Config:
        """解析配置字典"""
        return Config(
            llm=cls._parse_llm_config(data.get("llm", {})),
            agent=cls._parse_agent_config(data.get("agent", {})),
            memory=cls._parse_memory_config(data.get("memory", {})),
            tools=cls._parse_tool_config(data.get("tools", {})),
            skills=cls._parse_skills_config(data.get("skills", {}))
        )

    @classmethod
    def _parse_llm_config(cls, data: dict) -> LLMConfig:
        """解析 LLM 配置"""
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
        """解析 Agent 配置"""
        return AgentConfig(
            max_iterations=data.get("max_iterations", 10),
            verbose=data.get("verbose", True),
            system_prompt=data.get("system_prompt"),
            user_name=data.get("user_name", "User"),
            agent_name=data.get("agent_name", "Agent")
        )

    @classmethod
    def _parse_memory_config(cls, data: dict) -> MemoryConfig:
        """解析记忆配置"""
        return MemoryConfig(
            max_messages=data.get("max_messages", 50),
            type=data.get("type", "short_term"),
            storage_type=data.get("storage_type", "file"),
            storage_path=data.get("storage_path", ".nano_agent/memory"),
            session_id=data.get("session_id"),
            long_term_storage_path=data.get("long_term_storage_path", ".nano_agent/long_term_memory"),
            auto_extract=data.get("auto_extract", True)
        )

    @classmethod
    def _parse_tool_config(cls, data: dict) -> ToolConfig:
        """解析工具配置"""
        return ToolConfig(
            enabled=data.get("enabled", ["all"]),
            disabled=data.get("disabled", [])
        )

    @classmethod
    def _parse_skills_config(cls, data: dict) -> SkillsConfig:
        """解析技能配置"""
        return SkillsConfig(
            enabled=data.get("enabled", []),
            directory=data.get("directory", ".nano_agent/skills"),
            configs=data.get("configs", {})
        )

    @classmethod
    def save(cls, config: Config, config_path: str | Path) -> None:
        """
        保存配置到 YAML 文件。

        Args:
            config: 要保存的 Config 对象
            config_path: 保存路径
        """
        path = Path(config_path)

        # 确保父目录存在
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
                "user_name": config.agent.user_name,
                "agent_name": config.agent.agent_name,
                "system_prompt": config.agent.system_prompt
            },
            "memory": {
                "type": config.memory.type,
                "max_messages": config.memory.max_messages,
                "storage_type": config.memory.storage_type,
                "storage_path": config.memory.storage_path,
                "session_id": config.memory.session_id,
                "long_term_storage_path": config.memory.long_term_storage_path,
                "auto_extract": config.memory.auto_extract
            },
            "tools": {
                "enabled": config.tools.enabled,
                "disabled": config.tools.disabled
            }
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)