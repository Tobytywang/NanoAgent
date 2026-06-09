"""LLM module - Language model clients."""

from typing import Literal

from .base import BaseLLM, LLMUsage
from .ollama import OllamaLLM
from .openai_compatible import OpenAICompatibleLLM
from .anthropic import AnthropicLLM
from .messages import (
    Message,
    ToolCall,
    AssistantMessage,
    ToolResultMessage,
    SystemMessage,
    UserMessage,
)
from .embedding import (
    BaseEmbeddingClient,
    OllamaEmbeddingClient,
    SentenceTransformersEmbeddingClient,
    OpenAIEmbeddingClient,
    EmbeddingConfig,
    create_embedding_client,
)
from .retry import with_retry, is_retryable_error, calculate_delay
from .rate_limiter import TokenBucketRateLimiter, with_rate_limit

# Provider type alias
ProviderType = Literal[
    "ollama", "openai", "deepseek", "moonshot", "openai_compatible", "anthropic"
]

# Provider-specific default configurations
PROVIDER_DEFAULTS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "MOONSHOT_API_KEY",
        "default_model": "moonshot-v1-8k",
    },
    "openai_compatible": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
    },
}


def create_llm(
    provider: ProviderType = "ollama",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    timeout: int = 120,
    temperature: float = 0.7,
    **kwargs,
) -> BaseLLM:
    """
    Factory function to create LLM clients.

    Args:
        provider: LLM provider type
        model: Model name
        base_url: API base URL (optional, uses provider default if not specified)
        api_key: API key directly provided (optional)
        api_key_env: Environment variable name for API key
        timeout: Request timeout in seconds
        temperature: Sampling temperature
        **kwargs: Additional provider-specific parameters

    Returns:
        Configured LLM client instance

    Raises:
        ValueError: If provider is not supported
    """
    if provider == "ollama":
        return OllamaLLM(
            model=model or "llama3",
            base_url=base_url or "http://localhost:11434",
            timeout=timeout,
            **kwargs,
        )

    # Anthropic provider (supports Prompt Caching)
    if provider == "anthropic":
        return AnthropicLLM(
            model=model or PROVIDER_DEFAULTS["anthropic"]["default_model"],
            api_key=api_key,
            api_key_env=api_key_env or PROVIDER_DEFAULTS["anthropic"]["api_key_env"],
            timeout=timeout,
            temperature=temperature,
            **kwargs,
        )

    # OpenAI-compatible providers
    if provider in PROVIDER_DEFAULTS:
        defaults = PROVIDER_DEFAULTS[provider]

        return OpenAICompatibleLLM(
            model=model or defaults["default_model"],
            base_url=base_url or defaults["base_url"],
            api_key=api_key,
            api_key_env=api_key_env or defaults["api_key_env"],
            timeout=timeout,
            temperature=temperature,
            **kwargs,
        )

    # Unknown provider - treat as OpenAI-compatible if base_url is provided
    if base_url:
        return OpenAICompatibleLLM(
            model=model or "default",
            base_url=base_url,
            api_key=api_key,
            api_key_env=api_key_env or "OPENAI_API_KEY",
            timeout=timeout,
            temperature=temperature,
            **kwargs,
        )

    raise ValueError(
        f"Unsupported provider: {provider}. Use 'openai_compatible' with base_url for custom providers."
    )


def create_llm_from_config(config) -> BaseLLM:
    """
    Create LLM client from LLMConfig object.

    Args:
        config: LLMConfig instance

    Returns:
        Configured LLM client instance
    """
    return create_llm(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        api_key_env=config.api_key_env,
        timeout=config.timeout,
        temperature=config.temperature,
    )


__all__ = [
    "BaseLLM",
    "LLMUsage",
    "OllamaLLM",
    "OpenAICompatibleLLM",
    "AnthropicLLM",
    "Message",
    "ToolCall",
    "AssistantMessage",
    "ToolResultMessage",
    "SystemMessage",
    "UserMessage",
    "create_llm",
    "create_llm_from_config",
    "ProviderType",
    "PROVIDER_DEFAULTS",
    # Embedding clients (v0.7.19)
    "BaseEmbeddingClient",
    "OllamaEmbeddingClient",
    "SentenceTransformersEmbeddingClient",
    "OpenAIEmbeddingClient",
    "EmbeddingConfig",
    "create_embedding_client",
    # Retry (v0.8.0)
    "with_retry",
    "is_retryable_error",
    "calculate_delay",
    # Rate limiter (v0.8.1)
    "TokenBucketRateLimiter",
    "with_rate_limit",
]
