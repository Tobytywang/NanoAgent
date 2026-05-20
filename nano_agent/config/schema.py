"""
Configuration data structures.
"""

from dataclasses import dataclass, field
from typing import Literal


# Default context lengths for common models (in tokens)
MODEL_CONTEXT_LENGTHS = {
    # OpenAI models
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
    # Claude models
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3.5-sonnet": 200000,
    # DeepSeek models
    "deepseek-chat": 64000,
    "deepseek-coder": 16000,
    # Moonshot models
    "moonshot-v1-8k": 8192,
    "moonshot-v1-32k": 32768,
    "moonshot-v1-128k": 131072,
    # Ollama models (common defaults)
    "llama3": 8192,
    "llama3.1": 131072,
    "llama3.2": 131072,
    "qwen2.5": 131072,
    "qwen3": 131072,
    "mistral": 32768,
    "mixtral": 32768,
    "codellama": 16384,
}


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: str = "ollama"  # ollama, openai, deepseek, moonshot, openai_compatible, or any custom provider
    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    timeout: int = 120
    temperature: float = 0.7
    context_length: int | None = None  # Override context length (auto-detected if None)

    def get_context_length(self) -> int:
        """
        Get the context length for the current model.

        Returns:
            Context length in tokens
        """
        # Use override if set
        if self.context_length is not None:
            return self.context_length

        # Try exact match
        model_lower = self.model.lower()
        if model_lower in MODEL_CONTEXT_LENGTHS:
            return MODEL_CONTEXT_LENGTHS[model_lower]

        # Try partial match (e.g., "gpt-4o-2024-08-06" -> "gpt-4o")
        for key, length in MODEL_CONTEXT_LENGTHS.items():
            if key in model_lower or model_lower.startswith(key):
                return length

        # Default fallback (128k for modern models)
        return 128000


@dataclass
class AgentConfig:
    """Agent configuration."""
    max_iterations: int = 10
    verbose: bool = True
    system_prompt: str | None = None
    user_name: str = "User"  # Display name for user
    agent_name: str = "Agent"  # Display name for agent


@dataclass
class MemoryConfig:
    """Memory configuration."""
    max_messages: int = 50
    type: Literal["short_term", "persistent", "hybrid"] = "short_term"
    # Storage options
    storage_type: Literal["file", "sqlite"] = "file"
    storage_path: str = ".nano_agent/memory"
    session_id: str | None = None  # Optional: resume specific session
    # Hybrid memory options
    long_term_storage_path: str = ".nano_agent/long_term_memory"
    auto_extract: bool = True  # Auto-extract important info to long-term memory
    # Session cleanup options
    clean_threshold: int = 3  # Message count threshold for auto-clean


@dataclass
class ToolConfig:
    """Tool configuration."""
    enabled: list[str] = field(default_factory=lambda: ["all"])
    disabled: list[str] = field(default_factory=list)


@dataclass
class PluginsConfig:
    """Plugin configuration for external tools."""
    directories: list[str] = field(default_factory=list)  # Directories to scan for tools
    modules: list[str] = field(default_factory=list)      # Python modules to import
    files: list[str] = field(default_factory=list)        # Specific files to load


@dataclass
class SkillsConfig:
    """Skills configuration."""
    enabled: list[str] = field(default_factory=list)  # 启用的技能包名称
    directory: str = ".nano_agent/skills"  # 技能包目录
    configs: dict = field(default_factory=dict)  # 各技能包的额外配置


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    console: bool = True
    file: str | None = None  # Optional log file path


@dataclass
class ContextConfig:
    """Context management configuration."""
    # Pressure thresholds (relative to model context window)
    pressure_threshold_low: float = 0.70    # 70% triggers light cleanup
    pressure_threshold_mid: float = 0.85    # 85% triggers summary mark
    pressure_threshold_high: float = 0.95   # 95% triggers model compression

    # Model context window size (auto-detected from LLM config if None)
    max_context_tokens: int | None = None

    # Compression configuration
    max_compress_failures: int = 3          # Circuit breaker threshold
    summary_max_tokens: int = 4000          # Max tokens for summary

    # Light cleanup configuration
    temp_message_age: int = 5               # Rounds before temp messages expire


@dataclass
class ConfirmationConfig:
    """Confirmation mechanism configuration."""
    enabled: bool = True
    confirm_safe: bool = False        # Require confirmation for SAFE tools
    confirm_moderate: bool = False    # Require confirmation for MODERATE tools
    confirm_dangerous: bool = True    # Require confirmation for DANGEROUS tools
    whitelist: list[str] = field(default_factory=list)  # Tools that bypass confirmation


@dataclass
class GitConfig:
    """Git integration configuration."""
    enabled: bool = True
    auto_commit: bool = True
    commit_mode: Literal["step", "round", "manual"] = "step"
    commit_prefix: str = "[NanoAgent]"  # Commit message prefix
    branch_prefix: str = "nano-"        # Working branch prefix (optional)


@dataclass
class OutputStyleConfig:
    """Output style configuration for token efficiency."""

    style: Literal["concise", "standard", "detailed"] = "standard"
    tool_output_max_tokens: int = 500  # Max tokens for tool output before truncation
    # Intelligent summarization settings
    smart_summarization: bool = True  # Use intelligent extraction
    extract_imports: bool = True  # Extract imports from file content
    extract_signatures: bool = True  # Extract class/function signatures
    extract_errors: bool = True  # Extract error messages from shell
    file_search_count_only: bool = False  # Show only count for file searches


@dataclass
class ToolMergeConfig:
    """Tool merging configuration for token efficiency."""

    enabled: bool = True
    concise_only: bool = True  # Only merge in concise mode
    max_batch_size: int = 3  # Maximum operations to merge
    merge_tools: list[str] = field(
        default_factory=lambda: ["file_search", "shell_execute"]
    )


@dataclass
class CacheConfig:
    """Tool result caching configuration."""

    enabled: bool = True
    ttl_seconds: int = 300  # 5 minutes
    cacheable_tools: list[str] = field(
        default_factory=lambda: ["file_read", "file_search", "shell_execute"]
    )
    excluded_tools: list[str] = field(
        default_factory=lambda: ["file_write", "memorize", "forget"]
    )
    max_cache_size: int = 100  # Maximum number of cached results


@dataclass
class CompressorConfig:
    """Message compression configuration."""

    enabled: bool = True
    threshold_tokens: int = 2000  # Compress when prompt_tokens > threshold
    keep_recent: int = 3  # Keep recent N rounds of conversation
    summary_max_tokens: int = 500  # Max tokens for summary


@dataclass
class ProjectFileConfig:
    """Project file handling configuration."""

    mode: Literal["full", "condensed", "reference"] = "condensed"
    # full: Send complete file every time
    # condensed: Send condensed version (first run only)
    # reference: Only send file name after first reference


@dataclass
class SmartOptimizationConfig:
    """Smart optimization configuration for dynamic token efficiency.

    These features are designed to reduce token consumption by adapting
    to task complexity and confidence levels.
    """

    # === Confidence-based Early Stop ===
    confidence_enabled: bool = True  # Enable confidence-based early stopping
    confidence_threshold: float = 0.9  # Stop early when confidence >= threshold
    confidence_prompt_suffix: str = (
        "\n\nAfter your response, indicate your confidence level (0.0-1.0) "
        "and whether you have enough information to answer definitively. "
        "Format: [CONFIDENCE: X.XX] [CAN_ANSWER: yes/no]"
    )

    # === Token Budget Management ===
    budget_enabled: bool = True  # Enable token budget tracking
    initial_budget: int = 20000  # Initial token budget per session (increased from 2000)

    # Multi-level warning thresholds (v0.7.8)
    budget_warning_thresholds: list[float] = field(
        default_factory=lambda: [0.5, 0.3, 0.2, 0.1]
    )
    budget_warning_mode: Literal["silent", "console", "event"] = "console"
    budget_warning_interval: int = 1  # Minimum iterations between warnings

    budget_force_summarize: bool = True  # Force summarize when budget exhausted

    # LLM-based summary generation (v0.7.8)
    budget_llm_summary_enabled: bool = True  # Use LLM to generate structured summary
    budget_llm_summary_max_tokens: int = 500  # Max tokens for LLM summary

    # === Query Complexity Routing ===
    routing_enabled: bool = True  # Enable query complexity routing
    routing_simple_direct: bool = True  # Answer simple queries directly (no LLM call)
    routing_moderate_single_tool: bool = True  # Allow max 1 tool for moderate queries
    routing_complex_full_loop: bool = True  # Full ReAct loop for complex queries

    # === Tool Result Processing ===
    tool_processor_enabled: bool = True  # Enable intelligent tool result processing
    tool_processor_max_output_tokens: int = 300  # Max tokens for processed tool output


@dataclass
class PromptConfig:
    """Prompt configuration for modular prompt system.

    Supports:
    1. Configurable prompt via Excel or code
    2. Composable prompt modules
    3. Stable prefix for LLM API caching
    """

    # Configuration source: "default" uses built-in modules, "excel" loads from file
    source: Literal["default", "excel", "custom"] = "default"

    # Excel configuration path (used when source="excel")
    excel_path: str | None = None

    # Style preset: "concise", "standard", "detailed", or "custom"
    style: str = "standard"

    # Custom module list (used when style="custom")
    modules: list[str] = field(default_factory=list)

    # Token budget for prompt
    token_budget: int = 2000

    # Dynamic content options
    include_environment: bool = False
    include_git_status: bool = False

    # Stable modules for LLM API caching optimization
    # These modules are built once and cached, reducing API costs
    stable_modules: list[str] = field(
        default_factory=lambda: ["core", "tools", "efficiency", "modification", "language"]
    )

    # Enable prefix caching (Anthropic Prompt Caching, OpenAI Automatic Caching)
    enable_caching: bool = True


@dataclass
class Config:
    """Main configuration."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    confirmation: ConfirmationConfig = field(default_factory=ConfirmationConfig)
    git: GitConfig = field(default_factory=GitConfig)
    output_style: OutputStyleConfig = field(default_factory=OutputStyleConfig)
    tool_merge: ToolMergeConfig = field(default_factory=ToolMergeConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    compressor: CompressorConfig = field(default_factory=CompressorConfig)
    project_file: ProjectFileConfig = field(default_factory=ProjectFileConfig)
    smart_optimization: SmartOptimizationConfig = field(default_factory=SmartOptimizationConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
