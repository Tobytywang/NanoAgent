"""
配置文件加载器
"""

import yaml
from pathlib import Path
from typing import Any

from .schema import (
    Config, LLMConfig, AgentConfig, MemoryConfig, ToolConfig, SkillsConfig,
    OutputStyleConfig, ToolMergeConfig, CacheConfig, CompressorConfig,
    ProjectFileConfig, SmartOptimizationConfig, AggressiveOutputConfig, StandardizedOutputConfig
)


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
            skills=cls._parse_skills_config(data.get("skills", {})),
            output_style=cls._parse_output_style_config(data.get("output_style", {})),
            tool_merge=cls._parse_tool_merge_config(data.get("tool_merge", {})),
            cache=cls._parse_cache_config(data.get("cache", {})),
            compressor=cls._parse_compressor_config(data.get("compressor", {})),
            project_file=cls._parse_project_file_config(data.get("project_file", {})),
            smart_optimization=cls._parse_smart_optimization_config(data.get("smart_optimization", {})),
            aggressive_output=cls._parse_aggressive_output_config(data.get("aggressive_output", {})),
            standardized_output=cls._parse_standardized_output_config(data.get("standardized_output", {})),
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
            auto_extract=data.get("auto_extract", True),
            clean_threshold=data.get("clean_threshold", 3)
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
    def _parse_output_style_config(cls, data: dict) -> OutputStyleConfig:
        """解析输出风格配置"""
        return OutputStyleConfig(
            style=data.get("style", "standard"),
            tool_output_max_tokens=data.get("tool_output_max_tokens", 500),
            smart_summarization=data.get("smart_summarization", True),
            extract_imports=data.get("extract_imports", True),
            extract_signatures=data.get("extract_signatures", True),
            extract_errors=data.get("extract_errors", True),
            file_search_count_only=data.get("file_search_count_only", False)
        )

    @classmethod
    def _parse_tool_merge_config(cls, data: dict) -> ToolMergeConfig:
        """解析工具合并配置"""
        return ToolMergeConfig(
            enabled=data.get("enabled", True),
            concise_only=data.get("concise_only", True),
            max_batch_size=data.get("max_batch_size", 3),
            merge_tools=data.get("merge_tools", ["file_search", "shell_execute"])
        )

    @classmethod
    def _parse_cache_config(cls, data: dict) -> CacheConfig:
        """解析缓存配置"""
        return CacheConfig(
            enabled=data.get("enabled", True),
            ttl_seconds=data.get("ttl_seconds", 300),
            cacheable_tools=data.get("cacheable_tools", ["file_read", "file_search", "shell_execute"]),
            excluded_tools=data.get("excluded_tools", ["file_write", "memorize", "forget"]),
            max_cache_size=data.get("max_cache_size", 100)
        )

    @classmethod
    def _parse_compressor_config(cls, data: dict) -> CompressorConfig:
        """解析压缩配置"""
        return CompressorConfig(
            enabled=data.get("enabled", True),
            threshold_tokens=data.get("threshold_tokens", 2000),
            keep_recent=data.get("keep_recent", 3),
            summary_max_tokens=data.get("summary_max_tokens", 500)
        )

    @classmethod
    def _parse_project_file_config(cls, data: dict) -> ProjectFileConfig:
        """解析项目文件配置"""
        return ProjectFileConfig(
            mode=data.get("mode", "condensed")
        )

    @classmethod
    def _parse_smart_optimization_config(cls, data: dict) -> SmartOptimizationConfig:
        """解析智能优化配置"""
        return SmartOptimizationConfig(
            confidence_enabled=data.get("confidence_enabled", True),
            confidence_threshold=data.get("confidence_threshold", 0.9),
            budget_enabled=data.get("budget_enabled", True),
            initial_budget=data.get("initial_budget", 50000),
            budget_warning_thresholds=data.get("budget_warning_thresholds", [0.5, 0.3, 0.2, 0.1]),
            budget_warning_mode=data.get("budget_warning_mode", "console"),
            budget_warning_interval=data.get("budget_warning_interval", 1),
            budget_force_summarize=data.get("budget_force_summarize", True),
            budget_llm_summary_enabled=data.get("budget_llm_summary_enabled", True),
            budget_llm_summary_max_tokens=data.get("budget_llm_summary_max_tokens", 500),
            routing_enabled=data.get("routing_enabled", True),
            routing_simple_direct=data.get("routing_simple_direct", True),
            routing_moderate_single_tool=data.get("routing_moderate_single_tool", True),
            routing_complex_full_loop=data.get("routing_complex_full_loop", True),
            prejudgment_enabled=data.get("prejudgment_enabled", False),
            prejudgment_simple_prompt=data.get("prejudgment_simple_prompt", ""),
            prejudgment_max_answer_tokens=data.get("prejudgment_max_answer_tokens", 300),
            tool_processor_enabled=data.get("tool_processor_enabled", True),
            tool_processor_max_output_tokens=data.get("tool_processor_max_output_tokens", 300),
            duplicate_threshold=data.get("duplicate_threshold", 3),
            duplicate_deep_equal=data.get("duplicate_deep_equal", False),
            budget_wrapup_enabled=data.get("budget_wrapup_enabled", False),
            budget_wrapup_threshold=data.get("budget_wrapup_threshold", 0.1),
            budget_wrapup_free_round=data.get("budget_wrapup_free_round", True),
            budget_wrapup_max_tokens=data.get("budget_wrapup_max_tokens", 2000),
            complexity_budget_enabled=data.get("complexity_budget_enabled", True),
            complexity_budget_simple_ratio=data.get("complexity_budget_simple_ratio", 0.15),
            complexity_budget_moderate_ratio=data.get("complexity_budget_moderate_ratio", 0.5),
            complexity_budget_complex_ratio=data.get("complexity_budget_complex_ratio", 1.0),
            stall_detection_enabled=data.get("stall_detection_enabled", True),
            stall_patience=data.get("stall_patience", 3),
            stall_similarity_threshold=data.get("stall_similarity_threshold", 0.7),
            stall_hint_injection=data.get("stall_hint_injection", True),
        )

    @classmethod
    def _parse_aggressive_output_config(cls, data: dict) -> AggressiveOutputConfig:
        """解析激进输出配置"""
        return AggressiveOutputConfig(
            enabled=data.get("enabled", False),
            level=data.get("level", "mild"),
            max_response_sentences=data.get("max_response_sentences", 0),
            strip_emoji=data.get("strip_emoji", True),
            strip_markdown_tables=data.get("strip_markdown_tables", True),
            strip_markdown_lists=data.get("strip_markdown_lists", False),
            max_response_chars=data.get("max_response_chars", 0),
        )

    @classmethod
    def _parse_standardized_output_config(cls, data: dict) -> StandardizedOutputConfig:
        """解析标准化输出配置"""
        return StandardizedOutputConfig(
            enabled=data.get("enabled", True),
            detailed=data.get("detailed", False),
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
                "auto_extract": config.memory.auto_extract,
                "clean_threshold": config.memory.clean_threshold
            },
            "tools": {
                "enabled": config.tools.enabled,
                "disabled": config.tools.disabled
            },
            "output_style": {
                "style": config.output_style.style,
                "tool_output_max_tokens": config.output_style.tool_output_max_tokens,
                "smart_summarization": config.output_style.smart_summarization,
                "extract_imports": config.output_style.extract_imports,
                "extract_signatures": config.output_style.extract_signatures,
                "extract_errors": config.output_style.extract_errors,
                "file_search_count_only": config.output_style.file_search_count_only
            },
            "tool_merge": {
                "enabled": config.tool_merge.enabled,
                "concise_only": config.tool_merge.concise_only,
                "max_batch_size": config.tool_merge.max_batch_size,
                "merge_tools": config.tool_merge.merge_tools
            },
            "cache": {
                "enabled": config.cache.enabled,
                "ttl_seconds": config.cache.ttl_seconds,
                "cacheable_tools": config.cache.cacheable_tools,
                "excluded_tools": config.cache.excluded_tools,
                "max_cache_size": config.cache.max_cache_size
            },
            "compressor": {
                "enabled": config.compressor.enabled,
                "threshold_tokens": config.compressor.threshold_tokens,
                "keep_recent": config.compressor.keep_recent,
                "summary_max_tokens": config.compressor.summary_max_tokens
            },
            "project_file": {
                "mode": config.project_file.mode
            },
            "smart_optimization": {
                "confidence_enabled": config.smart_optimization.confidence_enabled,
                "confidence_threshold": config.smart_optimization.confidence_threshold,
                "budget_enabled": config.smart_optimization.budget_enabled,
                "initial_budget": config.smart_optimization.initial_budget,
                "budget_warning_thresholds": config.smart_optimization.budget_warning_thresholds,
                "budget_warning_mode": config.smart_optimization.budget_warning_mode,
                "budget_warning_interval": config.smart_optimization.budget_warning_interval,
                "budget_force_summarize": config.smart_optimization.budget_force_summarize,
                "budget_llm_summary_enabled": config.smart_optimization.budget_llm_summary_enabled,
                "budget_llm_summary_max_tokens": config.smart_optimization.budget_llm_summary_max_tokens,
                "routing_enabled": config.smart_optimization.routing_enabled,
                "routing_simple_direct": config.smart_optimization.routing_simple_direct,
                "routing_moderate_single_tool": config.smart_optimization.routing_moderate_single_tool,
                "routing_complex_full_loop": config.smart_optimization.routing_complex_full_loop,
                "prejudgment_enabled": config.smart_optimization.prejudgment_enabled,
                "prejudgment_simple_prompt": config.smart_optimization.prejudgment_simple_prompt,
                "prejudgment_max_answer_tokens": config.smart_optimization.prejudgment_max_answer_tokens,
                "tool_processor_enabled": config.smart_optimization.tool_processor_enabled,
                "tool_processor_max_output_tokens": config.smart_optimization.tool_processor_max_output_tokens,
                "duplicate_threshold": config.smart_optimization.duplicate_threshold,
                "duplicate_deep_equal": config.smart_optimization.duplicate_deep_equal,
                "budget_wrapup_enabled": config.smart_optimization.budget_wrapup_enabled,
                "budget_wrapup_threshold": config.smart_optimization.budget_wrapup_threshold,
                "budget_wrapup_free_round": config.smart_optimization.budget_wrapup_free_round,
                "budget_wrapup_max_tokens": config.smart_optimization.budget_wrapup_max_tokens,
                "complexity_budget_enabled": config.smart_optimization.complexity_budget_enabled,
                "complexity_budget_simple_ratio": config.smart_optimization.complexity_budget_simple_ratio,
                "complexity_budget_moderate_ratio": config.smart_optimization.complexity_budget_moderate_ratio,
                "complexity_budget_complex_ratio": config.smart_optimization.complexity_budget_complex_ratio,
                "stall_detection_enabled": config.smart_optimization.stall_detection_enabled,
                "stall_patience": config.smart_optimization.stall_patience,
                "stall_similarity_threshold": config.smart_optimization.stall_similarity_threshold,
                "stall_hint_injection": config.smart_optimization.stall_hint_injection,
            },
            "aggressive_output": {
                "enabled": config.aggressive_output.enabled,
                "level": config.aggressive_output.level,
                "max_response_sentences": config.aggressive_output.max_response_sentences,
                "strip_emoji": config.aggressive_output.strip_emoji,
                "strip_markdown_tables": config.aggressive_output.strip_markdown_tables,
                "strip_markdown_lists": config.aggressive_output.strip_markdown_lists,
                "max_response_chars": config.aggressive_output.max_response_chars,
            },
            "standardized_output": {
                "enabled": config.standardized_output.enabled,
                "detailed": config.standardized_output.detailed,
            }
        }

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)