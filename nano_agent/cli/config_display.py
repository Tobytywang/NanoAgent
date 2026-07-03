"""
Data-driven config display renderer.

Uses dataclass introspection + declarative spec to render config,
eliminating the need to manually print each field.
"""

from dataclasses import fields as dataclass_fields
from typing import Any, Callable


def _fmt_bool(v: Any) -> str:
    return str(v)


def _fmt_enabled(v: Any) -> str:
    return "开启" if v else "关闭"


def _fmt_tokens(v: Any) -> str:
    return f"{v} tokens"


def _fmt_seconds(v: Any) -> str:
    return f"{v}s"


def _fmt_comma(v: Any) -> str:
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v) if v else "None"
    return str(v)


def _fmt_count(v: Any) -> str:
    return str(len(v))


def _fmt_int_comma(v: Any) -> str:
    return f"{v:,}"


# Type alias for formatter callback
Formatter = Callable[[Any], str]

# Type alias for condition callback
Condition = Callable[[Any], bool]


class FieldSpec:
    """Specification for rendering a single config field."""

    __slots__ = ("field_name", "label", "formatter", "condition", "indent")

    def __init__(
        self,
        field_name: str,
        label: str | None = None,
        formatter: Formatter | None = None,
        condition: Condition | None = None,
        indent: bool = False,
    ):
        self.field_name = field_name
        self.label = label or field_name
        self.formatter = formatter
        self.condition = condition
        self.indent = indent


class SectionSpec:
    """Specification for rendering a config section."""

    __slots__ = ("attr_name", "title", "fields", "has_guard", "condition")

    def __init__(
        self,
        attr_name: str,
        title: str,
        fields: list[FieldSpec] | None = None,
        has_guard: bool = False,
        condition: Condition | None = None,
    ):
        self.attr_name = attr_name
        self.title = title
        self.fields = fields
        self.has_guard = has_guard
        self.condition = condition


def _render_field(obj: Any, spec: FieldSpec, width: int = 20) -> str | None:
    """Render a single field. Returns None if condition not met."""
    value = getattr(obj, spec.field_name, None)
    if spec.condition and not spec.condition(obj):
        return None
    formatted = spec.formatter(value) if spec.formatter else str(value)
    prefix = "  " if spec.indent else ""
    return f"  {prefix}{spec.label:<{width}} {formatted}"


def _render_section(
    config: Any,
    section: SectionSpec,
    agent: Any = None,
    width: int = 20,
) -> list[str]:
    """Render a section. Returns list of output lines."""
    # Check section-level condition
    if section.condition and not section.condition(config):
        return []

    # Special agent-only sections (no config attr)
    if section.attr_name == "_agent_tools":
        if not agent:
            return []
        lines: list[str] = []
        lines.append(f"\n## {section.title}")
        tools = agent.tool_registry.list_tools()
        lines.append(f"  {'Total':<{width}} {len(tools)}")
        tools_display = ", ".join(tools[:10])
        if len(tools) > 10:
            tools_display += f"... (+{len(tools) - 10} more)"
        lines.append(f"  {'Tools:':<{width}} {tools_display}")
        return lines

    obj = getattr(config, section.attr_name, None)
    if obj is None:
        if section.has_guard:
            return []
        obj = getattr(config, section.attr_name.replace("_", "-"), None)
        if obj is None:
            return []

    lines: list[str] = []
    lines.append(f"\n## {section.title}")

    if section.fields is None:
        # Auto-enumerate all dataclass fields
        for f in dataclass_fields(obj):
            value = getattr(obj, f.name, None)
            formatted = str(value)
            lines.append(f"  {f.name:<{width}} {formatted}")
    else:
        for field_spec in section.fields:
            # Special agent-dependent fields
            if field_spec.field_name == "_agent_skill_loader":
                if agent and hasattr(agent, "skill_loader"):
                    skills = agent.skill_loader.list_loaded_skills()
                    val = ", ".join(skills) if skills else "None"
                    lines.append(f"  {field_spec.label:<{width}} {val}")
                continue
            if field_spec.field_name == "_agent_prompt_modules":
                if (
                    agent
                    and hasattr(agent, "_prompt_builder")
                    and agent._prompt_builder
                ):
                    names = agent._prompt_builder.get_stable_module_names()
                    val = ", ".join(names) if names else "None"
                    lines.append(f"  {field_spec.label:<{width}} {val}")
                continue
            if field_spec.field_name == "_context_length":
                val = f"{config.llm.get_context_length():,}"
                lines.append(f"  {field_spec.label:<{width}} {val}")
                continue

            rendered = _render_field(obj, field_spec, width)
            if rendered is not None:
                lines.append(rendered)

    return lines


# fmt: off
SECTIONS: list[SectionSpec] = [
    SectionSpec("llm", "LLM 设置", [
        FieldSpec("provider", "Provider:"),
        FieldSpec("model", "Model:"),
        FieldSpec("base_url", "Base URL:"),
        FieldSpec("timeout", "Timeout:", _fmt_seconds),
        FieldSpec("temperature", "Temperature:"),
        FieldSpec("_context_length", "Context Length:"),
    ]),
    SectionSpec("agent", "Agent 设置", [
        FieldSpec("max_iterations", "Max Iterations:"),
        FieldSpec("verbose", "Verbose:"),
    ]),
    SectionSpec("memory", "记忆设置", [
        FieldSpec("type", "Type:"),
        FieldSpec("storage_type", "Storage Type:"),
        FieldSpec("storage_path", "Storage Path:"),
        FieldSpec("max_messages", "Max Messages:"),
        FieldSpec("clean_threshold", "Clean Threshold:"),
        FieldSpec("long_term_storage_path", "Long-term Path:", condition=lambda m: m.type == "hybrid"),
        FieldSpec("auto_extract", "Auto Extract:", condition=lambda m: m.type == "hybrid"),
    ]),
    SectionSpec("skills", "技能设置", [
        FieldSpec("directory", "Directory:"),
        FieldSpec("_agent_skill_loader", "Loaded Skills:"),
    ]),
    SectionSpec("plugins", "插件设置", [
        FieldSpec("directories", "Directories:", _fmt_comma),
        FieldSpec("modules", "Modules:", _fmt_comma),
    ]),
    SectionSpec("logging", "日志设置", [
        FieldSpec("level", "Level:"),
        FieldSpec("console", "Console:"),
        FieldSpec("file", "File:", lambda v: v or "None"),
    ]),
    SectionSpec("_agent_tools", "工具"),
    SectionSpec("output_style", "输出风格", [
        FieldSpec("style", "Style:"),
        FieldSpec("tool_output_max_tokens", "Max Tool Output:", _fmt_tokens),
    ]),
    SectionSpec("smart_optimization", "智能优化", [
        FieldSpec("confidence_enabled", "置信度早停:", _fmt_enabled),
        FieldSpec("budget_enabled", "Token 预算:", _fmt_enabled),
        FieldSpec("routing_enabled", "查询路由:", _fmt_enabled),
        FieldSpec("prejudgment_enabled", "预判机制:", _fmt_enabled),
        FieldSpec("prejudgment_max_answer_tokens", "最大回答 Token:", _fmt_tokens,
                  condition=lambda o: o.prejudgment_enabled, indent=True),
        FieldSpec("calibration_enabled", "校准:", _fmt_enabled),
        FieldSpec("estimation_audit_enabled", "估算审计:", _fmt_enabled),
    ]),
    SectionSpec("prompt", "Prompt 设置", [
        FieldSpec("source", "Source:"),
        FieldSpec("style", "Style:"),
        FieldSpec("token_budget", "Token Budget:", _fmt_tokens),
        FieldSpec("include_environment", "Include Environment:"),
        FieldSpec("include_git_status", "Include Git Status:"),
        FieldSpec("enable_caching", "Enable Caching:"),
        FieldSpec("_agent_prompt_modules", "Stable Modules:"),
    ]),
    SectionSpec("aggressive_output", "激进输出简化", [
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("level", "Level:", condition=lambda o: o.enabled),
        FieldSpec("max_response_sentences", "Max Sentences:",
                  formatter=lambda v: str(v) if v > 0 else "auto",
                  condition=lambda o: o.enabled),
        FieldSpec("strip_emoji", "Strip Emoji:", condition=lambda o: o.enabled),
        FieldSpec("strip_markdown_tables", "Strip Tables:", condition=lambda o: o.enabled),
        FieldSpec("strip_markdown_lists", "Strip Lists:", condition=lambda o: o.enabled),
    ]),
    SectionSpec("standardized_output", "标准化工具输出", [
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("detailed", "Detailed:"),
    ]),
    SectionSpec("offload", "工具结果卸载", [
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("size_threshold_tokens", "Size Threshold:", _fmt_tokens,
                  condition=lambda o: o.enabled),
        FieldSpec("offload_dir", "Offload Dir:", condition=lambda o: o.enabled),
        FieldSpec("auto_cleanup", "Auto Cleanup:", condition=lambda o: o.enabled),
        FieldSpec("summary_max_tokens", "Summary Max Tokens:", condition=lambda o: o.enabled),
        FieldSpec("excluded_tools", "Excluded Tools:", _fmt_comma,
                  condition=lambda o: o.enabled and o.excluded_tools),
    ]),
    SectionSpec("semantic_compressor", "语义压缩", has_guard=True, fields=[
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("similarity_threshold", "Similarity Threshold:",
                  condition=lambda o: o.enabled),
        FieldSpec("min_messages_to_compress", "Min Messages:",
                  condition=lambda o: o.enabled),
        FieldSpec("provider", "Provider:", condition=lambda o: o.enabled),
        FieldSpec("embedding_model", "Embedding Model:",
                  condition=lambda o: o.enabled),
        FieldSpec("cache_embeddings", "Cache Embeddings:",
                  condition=lambda o: o.enabled),
        FieldSpec("merge_tag", "Merge Tag:", condition=lambda o: o.enabled),
    ]),
    SectionSpec("retry", "重试策略", has_guard=True, fields=[
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("max_retries", "Max Retries:", condition=lambda o: o.enabled),
        FieldSpec("base_delay", "Base Delay:", _fmt_seconds, lambda o: o.enabled),
        FieldSpec("max_delay", "Max Delay:", _fmt_seconds, lambda o: o.enabled),
        FieldSpec("jitter", "Jitter:", condition=lambda o: o.enabled),
        FieldSpec("retryable_status_codes", "Retryable Status Codes:", _fmt_comma,
                  condition=lambda o: o.enabled),
    ]),
    SectionSpec("rate_limiter", "限流策略", has_guard=True, fields=[
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("requests_per_minute", "Requests Per Minute:",
                  condition=lambda o: o.enabled),
        FieldSpec("burst", "Burst:", condition=lambda o: o.enabled),
    ]),
    SectionSpec("sanitizer", "输入净化 (Input Sanitizer)", has_guard=True, fields=[
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("injection_patterns", "Injection Patterns:", _fmt_count,
                  condition=lambda o: o.enabled),
        FieldSpec("custom_patterns", "Custom Patterns:", _fmt_count,
                  condition=lambda o: o.enabled),
        FieldSpec("max_input_length", "Max Input Length:", condition=lambda o: o.enabled),
        FieldSpec("length_action", "Length Action:", condition=lambda o: o.enabled),
        FieldSpec("reject_null_bytes", "Reject Null Bytes:", condition=lambda o: o.enabled),
        FieldSpec("reject_control_chars", "Reject Control Chars:", condition=lambda o: o.enabled),
        FieldSpec("max_line_length", "Max Line Length:", condition=lambda o: o.enabled),
        FieldSpec("pii_enabled", "PII Desensitization:", condition=lambda o: o.enabled),
        FieldSpec("pii_mask_mode", "PII Mask Mode:",
                  condition=lambda o: o.enabled and o.pii_enabled),
        FieldSpec("pii_mask_char", "PII Mask Char:",
                  condition=lambda o: o.enabled and o.pii_enabled),
        FieldSpec("pii_types", "PII Types:", _fmt_comma,
                  condition=lambda o: o.enabled and o.pii_enabled),
    ]),
    SectionSpec("output_guard", "输出护栏 (Output Guard)", fields=[
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("action", "Action:", condition=lambda o: o.enabled),
        FieldSpec("mask_mode", "Mask Mode:", condition=lambda o: o.enabled),
        FieldSpec("mask_char", "Mask Char:", condition=lambda o: o.enabled),
        FieldSpec("sensitive_types", "Sensitive Types:", _fmt_comma,
                  condition=lambda o: o.enabled),
        FieldSpec("block_severity", "Block Severity:", _fmt_comma,
                  condition=lambda o: o.enabled),
        FieldSpec("custom_patterns", "Custom Patterns:", _fmt_count,
                  condition=lambda o: o.enabled),
    ]),
    SectionSpec("harmful_content_filter", "有害内容过滤 (Harmful Content Filter)",
                has_guard=True, fields=[
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("categories", "Categories:", _fmt_comma,
                  condition=lambda o: o.enabled),
        FieldSpec("default_action", "Default Action:", condition=lambda o: o.enabled),
        FieldSpec("category_actions", "Category Actions:", condition=lambda o: o.enabled and o.category_actions),
        FieldSpec("replacement_text", "Replacement Text:", condition=lambda o: o.enabled),
        FieldSpec("custom_patterns", "Custom Patterns:", _fmt_count,
                  condition=lambda o: o.enabled),
    ]),
    SectionSpec("result_validator", "结果验证 (Result Validator)", has_guard=True, fields=[
        FieldSpec("enabled", "Enabled:"),
        FieldSpec("checks", "Checks:", _fmt_comma, condition=lambda o: o.enabled),
        FieldSpec("on_fail", "On Fail:", condition=lambda o: o.enabled),
        FieldSpec("on_pass", "On Pass:", condition=lambda o: o.enabled),
        FieldSpec("custom_validators", "Custom Validators:", _fmt_count,
                  condition=lambda o: o.enabled),
    ]),
    SectionSpec("feedback_loop", "反馈闭环 (Feedback Loop)", has_guard=True, fields=[
        FieldSpec("deviation_feedback_enabled", "偏差信号回流:"),
        FieldSpec("deviation_feedback_threshold", "告警阈值:",
                  condition=lambda o: o.deviation_feedback_enabled),
        FieldSpec("deviation_feedback_cooldown", "冷却间隔:",
                  condition=lambda o: o.deviation_feedback_enabled),
        FieldSpec("deviation_feedback_hint_injection", "提示注入:",
                  condition=lambda o: o.deviation_feedback_enabled),
        FieldSpec("self_correction_enabled", "自纠正循环:"),
        FieldSpec("self_correction_max_attempts", "最大尝试次数:",
                  condition=lambda o: o.self_correction_enabled),
    ]),
    SectionSpec("tool_resource_limiter", "工具资源限制 (Tool Resource Limiter)",
                has_guard=True, fields=[
        FieldSpec("enabled", "启用:"),
        FieldSpec("timeout_enabled", "超时保护:", condition=lambda o: o.enabled),
        FieldSpec("default_timeout", "默认超时:",
                  formatter=lambda v: f"{v}秒",
                  condition=lambda o: o.enabled and o.timeout_enabled),
        FieldSpec("rate_limit_enabled", "频率限制:", condition=lambda o: o.enabled),
        FieldSpec("per_tool_calls_per_minute", "单工具限制:",
                  formatter=lambda v: f"{v}次/分钟",
                  condition=lambda o: o.enabled and o.rate_limit_enabled),
        FieldSpec("global_calls_per_minute", "全局限制:",
                  formatter=lambda v: f"{v}次/分钟",
                  condition=lambda o: o.enabled and o.rate_limit_enabled),
    ]),
    SectionSpec("memory_gc", "记忆衰减与回收 (Memory GC)", has_guard=True, fields=[
        FieldSpec("decay_enabled", "衰减启用:"),
        FieldSpec("decay_half_life_days", "衰减半衰期:",
                  formatter=lambda v: f"{v} 天",
                  condition=lambda o: o.decay_enabled),
        FieldSpec("dedup_merge_enabled", "去重合并:"),
        FieldSpec("dedup_merge_tag", "合并标签:",
                  condition=lambda o: o.dedup_merge_enabled),
        FieldSpec("gc_enabled", "GC 启用:"),
        FieldSpec("gc_threshold", "GC 阈值:", condition=lambda o: o.gc_enabled),
        FieldSpec("gc_min_age_days", "GC 最小年龄:",
                  formatter=lambda v: f"{v} 天",
                  condition=lambda o: o.gc_enabled),
        FieldSpec("eviction_enabled", "淘汰启用:"),
        FieldSpec("eviction_max_entries", "淘汰上限:",
                  formatter=lambda v: f"{v} 条",
                  condition=lambda o: o.eviction_enabled),
        FieldSpec("eviction_protected_categories", "保护类别:", _fmt_comma,
                  condition=lambda o: o.eviction_enabled),
        FieldSpec("eviction_mention_count_threshold", "提及保护阈值:",
                  formatter=lambda v: f">= {v} 次",
                  condition=lambda o: o.eviction_enabled),
    ]),
    SectionSpec("snapshot", "全局状态快照 (Snapshot)", has_guard=True, fields=[
        FieldSpec("enabled", "启用:"),
        FieldSpec("auto_snapshot", "自动存档:"),
        FieldSpec("max_snapshots", "最大存档数:"),
        FieldSpec("snapshot_dir", "存档目录:"),
        FieldSpec("audit_log_enabled", "审计日志:"),
        FieldSpec("max_audit_entries", "最大审计条数:"),
        FieldSpec("auto_rollback_enabled", "自动回滚:"),
        FieldSpec("auto_rollback_threshold", "回滚阈值:"),
        FieldSpec("auto_rollback_on_failure", "回滚后行为:"),
    ]),
]
# fmt: on


def render_config(config: Any, agent: Any = None) -> str:
    """Render full config display as a string."""
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 50)
    lines.append("📊 当前配置")
    lines.append("=" * 50)

    for section in SECTIONS:
        section_lines = _render_section(config, section, agent)
        lines.extend(section_lines)

    # Timeout overrides (nested dict, special rendering)
    trl = getattr(config, "tool_resource_limiter", None)
    if trl and trl.enabled and trl.timeout_enabled and trl.timeout_overrides:
        for tool_name, timeout in trl.timeout_overrides.items():
            lines.append(f"    {tool_name + ':':<18} {timeout}秒")

    lines.append("")
    lines.append("=" * 50)
    lines.append("")
    return "\n".join(lines)
