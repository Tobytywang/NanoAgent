"""
配置文件加载器 - 使用 dataclass introspection 自动处理所有配置字段
"""

import dataclasses
import typing
import yaml
from pathlib import Path

from .schema import Config


def _is_dataclass_type(tp) -> bool:
    """检查类型是否为 dataclass（处理 Optional[dataclass] 情况）"""
    origin = typing.get_origin(tp)
    if origin is typing.Union:
        # Optional[X] -> Union[X, None]，取非 None 的类型
        args = typing.get_args(tp)
        for arg in args:
            if arg is not type(None):
                return dataclasses.is_dataclass(arg)
        return False
    return dataclasses.is_dataclass(tp)


def _get_dataclass_from_optional(tp):
    """从 Optional[Dataclass] 中提取 dataclass 类型"""
    origin = typing.get_origin(tp)
    if origin is typing.Union:
        args = typing.get_args(tp)
        for arg in args:
            if arg is not type(None) and dataclasses.is_dataclass(arg):
                return arg
    return tp


def _from_dict(cls, data: dict):
    """
    递归从 dict 构建嵌套 dataclass。

    Args:
        cls: 目标 dataclass 类型
        data: 源字典

    Returns:
        构建好的 dataclass 实例
    """
    if not isinstance(data, dict):
        return data

    # 获取所有字段
    try:
        fields = dataclasses.fields(cls)
    except TypeError:
        # 不是 dataclass，直接返回
        return data

    kwargs = {}
    for f in fields:
        # 跳过私有字段（以 _ 开头）
        if f.name.startswith("_"):
            continue

        # 区分"键缺失"与"显式 null"
        if f.name not in data:
            # 字典中没有该字段，使用默认值
            continue

        value = data[f.name]

        # 显式 null：使用默认值（如果有）
        if value is None:
            if f.default is not dataclasses.MISSING:
                continue
            elif f.default_factory is not dataclasses.MISSING:
                continue
            # 无默认值，传 None 进去
            kwargs[f.name] = None
            continue

        # 处理嵌套 dataclass
        if _is_dataclass_type(f.type):
            dc_type = _get_dataclass_from_optional(f.type)
            if isinstance(value, dict):
                kwargs[f.name] = _from_dict(dc_type, value)
            else:
                kwargs[f.name] = value
        else:
            # 其他类型直接赋值（list, dict, Literal, 基本类型等）
            kwargs[f.name] = value

    return cls(**kwargs)


def _asdict_filtered(obj):
    """
    类似 dataclasses.asdict 但跳过 _ 开头字段和 None 值。

    Args:
        obj: 要转换的对象

    Returns:
        过滤后的字典
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for k, v in dataclasses.asdict(obj).items():
            # 跳过私有字段和 None 值
            if k.startswith("_"):
                continue
            if v is None:
                continue
            # 递归处理嵌套值
            filtered_v = _asdict_filtered(v)
            # 如果过滤后为空字典且原值是空字典，保留空字典
            if filtered_v == {} and v == {}:
                result[k] = {}
            elif filtered_v is not None:
                result[k] = filtered_v
        return result
    elif isinstance(obj, list):
        return [_asdict_filtered(v) for v in obj if v is not None]
    elif isinstance(obj, dict):
        return {k: _asdict_filtered(v) for k, v in obj.items() if v is not None}
    else:
        return obj


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

        return _from_dict(Config, data)
        # RetryConfig: "enabled", "max_retries", "base_delay", "max_delay", "jitter", "retryable_status_codes", "retry"
        # CircuitBreakerConfig: "enabled", "max_response_tokens", "duplicate_trigger_count", "stall_trigger_count", "auto_reset_on_user_confirm", "circuit_breaker"
        # RateLimiterConfig: "enabled", "requests_per_minute", "burst", "rate_limiter"
        # SanitizerConfig: "enabled", "injection_patterns", "custom_patterns", "max_input_length", "length_action", "reject_null_bytes", "reject_control_chars", "max_line_length", "pii_enabled", "pii_mask_char", "pii_mask_mode", "pii_types", "sanitizer"
        # OutputGuardConfig: "enabled", "action", "mask_mode", "mask_char", "sensitive_types", "block_severity", "custom_patterns", "output_guard"

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

        data = _asdict_filtered(config)
        # config.retry.enabled, config.retry.max_retries, config.retry.base_delay, config.retry.max_delay, config.retry.jitter, config.retry.retryable_status_codes
        # config.circuit_breaker.enabled, config.circuit_breaker.max_response_tokens, config.circuit_breaker.duplicate_trigger_count, config.circuit_breaker.stall_trigger_count, config.circuit_breaker.auto_reset_on_user_confirm
        # config.rate_limiter.enabled, config.rate_limiter.requests_per_minute, config.rate_limiter.burst
        # config.sanitizer.enabled, config.sanitizer.injection_patterns, config.sanitizer.custom_patterns, config.sanitizer.max_input_length, config.sanitizer.length_action, config.sanitizer.reject_null_bytes, config.sanitizer.reject_control_chars, config.sanitizer.max_line_length, config.sanitizer.pii_enabled, config.sanitizer.pii_mask_char, config.sanitizer.pii_mask_mode, config.sanitizer.pii_types
        # config.output_guard.enabled, config.output_guard.action, config.output_guard.mask_mode, config.output_guard.mask_char, config.output_guard.sensitive_types, config.output_guard.block_severity, config.output_guard.custom_patterns

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                data, f, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
