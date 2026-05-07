"""
配置数据结构
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


def _load_model_context_lengths() -> dict:
    """从 YAML 文件加载模型上下文长度配置"""
    config_path = Path(__file__).parent / "model_contexts.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# 模型上下文长度配置（从 YAML 文件加载）
MODEL_CONTEXT_LENGTHS = _load_model_context_lengths()


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "ollama"  # ollama, openai, deepseek, moonshot, openai_compatible 或自定义提供商
    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    timeout: int = 120
    temperature: float = 0.7
    context_length: int | None = None  # 覆盖上下文长度（None 时自动检测）

    def get_context_length(self) -> int:
        """
        获取当前模型的上下文长度。

        Returns:
            上下文长度（tokens）
        """
        # 使用覆盖值
        if self.context_length is not None:
            return self.context_length

        # 尝试精确匹配
        model_lower = self.model.lower()
        if model_lower in MODEL_CONTEXT_LENGTHS:
            return MODEL_CONTEXT_LENGTHS[model_lower]

        # 尝试部分匹配（如 "gpt-4o-2024-08-06" -> "gpt-4o"）
        for key, length in MODEL_CONTEXT_LENGTHS.items():
            if key in model_lower or model_lower.startswith(key):
                return length

        # 默认回退值（现代模型 128k）
        return 128000


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_iterations: int = 10
    verbose: bool = True
    system_prompt: str | None = None
    user_name: str = "User"  # 用户显示名称
    agent_name: str = "Agent"  # Agent 显示名称


@dataclass
class MemoryConfig:
    """记忆配置"""
    max_messages: int = 50
    type: Literal["short_term", "persistent", "hybrid"] = "short_term"
    # 存储选项
    storage_type: Literal["file", "sqlite"] = "file"
    storage_path: str = ".nano_agent/memory"
    session_id: str | None = None  # 可选：恢复特定会话
    # 混合记忆选项
    long_term_storage_path: str = ".nano_agent/long_term_memory"
    auto_extract: bool = True  # 自动提取重要信息到长期记忆
    # 会话清理选项
    clean_threshold: int = 3  # 自动清理的消息数阈值


@dataclass
class ToolConfig:
    """工具配置"""
    enabled: list[str] = field(default_factory=lambda: ["all"])
    disabled: list[str] = field(default_factory=list)


@dataclass
class PluginsConfig:
    """外部工具插件配置"""
    directories: list[str] = field(default_factory=list)  # 扫描工具的目录
    modules: list[str] = field(default_factory=list)      # 要导入的 Python 模块
    files: list[str] = field(default_factory=list)        # 要加载的特定文件


@dataclass
class SkillsConfig:
    """技能配置"""
    enabled: list[str] = field(default_factory=list)  # 启用的技能包名称
    directory: str = ".nano_agent/skills"  # 技能包目录
    configs: dict = field(default_factory=dict)  # 各技能包的额外配置


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    console: bool = True
    file: str | None = None  # 可选日志文件路径


@dataclass
class Config:
    """主配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)