"""
Configuration data structures.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

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

# Separator characters used in model versioning (e.g., "llama3.1", "gpt-4o-2024-08-06")
_MODEL_SEPARATORS = {".", "-", "_"}

# Conservative fallback — underestimating is safe (wastes some context),
# overestimating is dangerous (context overflow / API error)
CONSERVATIVE_CONTEXT_FALLBACK = 8192


def _model_prefix_matches(model_name: str, key: str) -> bool:
    """Check if model_name starts with key followed by a separator or end of string.

    This prevents 'llama3' from matching 'llama3.1' — the key 'llama3'
    must be followed by a separator char or the string must end there.
    """
    if not model_name.startswith(key):
        return False
    remainder = model_name[len(key) :]
    if not remainder:
        return True
    return remainder[0] in _MODEL_SEPARATORS


@dataclass
class LLMConfig:
    """LLM configuration."""

    provider: str = (
        "ollama"  # ollama, openai, deepseek, moonshot, openai_compatible, or any custom provider
    )
    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    timeout: int = 120
    temperature: float = 0.7
    context_length: int | None = None
    _llm_client: Any = field(default=None, repr=False)

    def set_llm_client(self, client: Any) -> None:
        """Set the LLM client instance for API-based context length queries."""
        self._llm_client = client  # Override context length (auto-detected if None)

    def get_context_length(self) -> int:
        """
        Get the context length for the current model.

        Four-layer fallback chain:
        1. User-configured override (context_length field)
        2. API query (via LLM client's query_context_length)
        3. Lookup table (exact match, then prefix match)
        4. Conservative fallback (8192)

        Returns:
            Context length in tokens
        """
        # Layer 1: User override
        if self.context_length is not None:
            return self.context_length

        # Layer 2: API query
        if self._llm_client is not None:
            try:
                result = self._llm_client.query_context_length()
                if result is not None:
                    return result
            except Exception:
                pass

        # Layer 3: Lookup table
        model_lower = self.model.lower()

        # Exact match
        if model_lower in MODEL_CONTEXT_LENGTHS:
            return MODEL_CONTEXT_LENGTHS[model_lower]

        # Prefix match (prevents llama3 from matching llama3.1)
        for key, length in MODEL_CONTEXT_LENGTHS.items():
            if _model_prefix_matches(model_lower, key):
                return length

        # Layer 4: Conservative fallback
        return CONSERVATIVE_CONTEXT_FALLBACK


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

    directories: list[str] = field(
        default_factory=list
    )  # Directories to scan for tools
    modules: list[str] = field(default_factory=list)  # Python modules to import
    files: list[str] = field(default_factory=list)  # Specific files to load


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
    pressure_threshold_low: float = 0.70  # 70% triggers light cleanup
    pressure_threshold_mid: float = 0.85  # 85% triggers summary mark
    pressure_threshold_high: float = 0.95  # 95% triggers model compression

    # Model context window size (auto-detected from LLM config if None)
    max_context_tokens: int | None = None

    # Compression configuration
    max_compress_failures: int = 3  # Circuit breaker threshold
    summary_max_tokens: int = 4000  # Max tokens for summary

    # Light cleanup configuration
    temp_message_age: int = 5  # Rounds before temp messages expire


@dataclass
class ConfirmationConfig:
    """Confirmation mechanism configuration."""

    enabled: bool = True
    confirm_safe: bool = False  # Require confirmation for SAFE tools
    confirm_moderate: bool = False  # Require confirmation for MODERATE tools
    confirm_dangerous: bool = True  # Require confirmation for DANGEROUS tools
    whitelist: list[str] = field(default_factory=list)  # Tools that bypass confirmation


@dataclass
class GitConfig:
    """Git integration configuration."""

    enabled: bool = True
    auto_commit: bool = True
    commit_mode: Literal["step", "round", "manual"] = "step"
    commit_prefix: str = "[NanoAgent]"  # Commit message prefix
    branch_prefix: str = "nano-"  # Working branch prefix (optional)


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
class AggressiveOutputConfig:
    """Aggressive output simplification configuration (v0.7.15)."""

    enabled: bool = False
    level: Literal["mild", "aggressive", "extreme"] = "mild"
    max_response_sentences: int = 0  # 0=unlimited; mild=3, aggressive=1, extreme=1
    strip_emoji: bool = True
    strip_markdown_tables: bool = True
    strip_markdown_lists: bool = False  # True for aggressive/extreme
    max_response_chars: int = 0  # 0=unlimited; extreme=200


@dataclass
class StandardizedOutputConfig:
    """Standardized tool output configuration (v0.7.15)."""

    enabled: bool = True
    detailed: bool = False  # True=full detail, False=compact


@dataclass
class ToolOffloadConfig:
    """Tool result offloading configuration (v0.7.17)."""

    enabled: bool = True
    size_threshold_tokens: int = 1000  # Offload when result exceeds this
    offload_dir: str = "/tmp/nano_agent_offload"
    auto_cleanup: bool = True
    summary_max_tokens: int = 200
    excluded_tools: list[str] = field(default_factory=lambda: ["memorize", "recall"])


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
    # v0.7.17: Multi-turn cache persistence
    persist: bool = False  # Persist cache to disk across sessions
    persist_dir: str = ".nano_agent/cache"  # Cache persistence directory
    warmup_on_restore: bool = True  # Warmup cache when restoring session
    mtime_invalidation: bool = True  # Invalidate cache on file modification


@dataclass
class CompressorConfig:
    """Message compression configuration."""

    enabled: bool = True
    threshold_tokens: int = 2000  # Compress when prompt_tokens > threshold
    keep_recent: int = 3  # Keep recent N rounds of conversation
    summary_max_tokens: int = 500  # Max tokens for summary


@dataclass
class SemanticCompressorConfig:
    """Semantic compression configuration (v0.7.19)."""

    enabled: bool = False
    similarity_threshold: float = 0.85
    min_messages_to_compress: int = 8
    provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    cache_embeddings: bool = True
    merge_tag: str = "[merged {n} similar]"


@dataclass
class ProjectFileConfig:
    """Project file handling configuration."""

    mode: Literal["full", "condensed", "reference"] = "condensed"
    # full: Send complete file every time
    # condensed: Send condensed version (first run only)
    # reference: Only send file name after first reference


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration for execution mode degradation."""

    enabled: bool = True
    max_response_tokens: int = 8000  # LLM single response token limit
    duplicate_trigger_count: int = 3  # Duplicate calls to trigger circuit break
    stall_trigger_count: int = 3  # Stall occurrences to trigger circuit break
    auto_reset_on_user_confirm: bool = True  # Reset to AUTO after user confirms


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
    initial_budget: int = (
        50000  # Initial token budget per session (increased from 20000)
    )

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

    # === Prejudgment Mechanism (v0.7.14) ===
    prejudgment_enabled: bool = False  # Enable LLM-based query prejudgment
    prejudgment_simple_prompt: str = ""  # Optional custom prompt for SIMPLE responses
    prejudgment_max_answer_tokens: int = 300  # Max tokens for SIMPLE direct answer

    # === Tool Result Processing ===
    tool_processor_enabled: bool = True  # Enable intelligent tool result processing
    tool_processor_max_output_tokens: int = 300  # Max tokens for processed tool output

    # === Duplicate Detection (v0.7.9) ===
    duplicate_threshold: int = 3  # Max identical calls before blocking
    duplicate_deep_equal: bool = False  # Use full JSON comparison instead of MD5[:8]

    # === Budget Wrap-Up (v0.7.9) ===
    budget_wrapup_enabled: bool = False  # Enable budget wrap-up round
    budget_wrapup_threshold: float = 0.1  # Trigger when remaining ratio <= threshold
    budget_wrapup_free_round: bool = True  # Wrap-up round doesn't consume budget
    budget_wrapup_max_tokens: int = 2000  # Max tokens for wrap-up LLM call

    # === Complexity Budget Profile (v0.7.16) ===
    complexity_budget_enabled: bool = True  # Adjust budget by query complexity
    complexity_budget_simple_ratio: float = 0.15  # 15% of full budget for SIMPLE
    complexity_budget_moderate_ratio: float = 0.5  # 50% of full budget for MODERATE
    complexity_budget_complex_ratio: float = 1.0  # 100% of full budget for COMPLEX

    # === Stall Detection (v0.7.16) ===
    stall_detection_enabled: bool = True  # Enable stall detection
    stall_patience: int = 3  # Consecutive similar iterations before stall
    stall_similarity_threshold: float = 0.7  # Signature similarity threshold
    stall_hint_injection: bool = True  # Inject redirect hint when stalled

    # === Calibration Configuration (v0.7.18) ===
    calibration_enabled: bool = True  # Enable dynamic calibration
    calibration_window: int = 5  # Number of calls for calibration
    min_calibration_samples: int = 3  # Minimum samples before calibration

    # === Estimation Audit (v0.7.18) ===
    estimation_audit_enabled: bool = True  # Enable estimation audit
    estimation_deviation_warning_threshold: float = 0.50  # Warn when deviation > 50%

    # === Circuit Breaker (v0.8.0) ===
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


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
        default_factory=lambda: [
            "core",
            "tools",
            "efficiency",
            "modification",
            "language",
        ]
    )

    # Enable prefix caching (Anthropic Prompt Caching, OpenAI Automatic Caching)
    enable_caching: bool = True


@dataclass
class RetryConfig:
    """LLM call retry configuration."""

    enabled: bool = True
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    retryable_status_codes: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )


@dataclass
class RateLimiterConfig:
    """LLM API rate limiter configuration."""

    enabled: bool = True
    requests_per_minute: int = 60
    burst: int = 10

    def __post_init__(self):
        if self.requests_per_minute <= 0:
            raise ValueError(
                f"requests_per_minute must be > 0, got {self.requests_per_minute}"
            )
        if self.burst <= 0:
            raise ValueError(f"burst must be > 0, got {self.burst}")


@dataclass
class SanitizerConfig:
    """Input sanitizer configuration."""

    enabled: bool = True
    injection_patterns: list[str] = field(
        default_factory=lambda: [
            # English patterns
            r"(?i)ignore\s+(previous|all|above|prior)\s*(instructions?|prompts?|directions?)?",
            r"(?i)disregard\s+(all|previous|above|prior)\s*(instructions?|prompts?|rules?)?",
            r"(?i)forget\s+(all|previous|above|prior)\s*(instructions?|rules?)?",
            r"(?i)you\s+are\s+now\s+",
            r"(?i)act\s+as\s+if\s+you\s+are\s+",
            r"(?i)pretend\s+(you\s+are|to\s+be)\s+",
            r"(?i)new\s+instructions?\s*:",
            r"(?i)system\s*:\s*",
            r"(?i)\[?DAN\]?|do\s+anything\s+now",
            r"(?i)jailbreak",
            r"(?i)bypass\s+(your|the|all)\s*(rules?|restrictions?|guidelines?)?",
            r"(?i)override\s+(your|the|all)\s*(rules?|restrictions?|guidelines?|instructions?)?",
            # Chinese patterns
            r"忽略(之前的?|所有的?|上面的?)(指令|提示|规则)",
            r"忘记(之前的?|所有的?)(指令|规则)",
            r"你现在是",
            r"假装你是",
            r"绕过(你的?|所有的?)(规则|限制)",
            r"无视(之前的?|所有的?|上面的?)(指令|规则)",
        ]
    )
    custom_patterns: list[str] = field(default_factory=list)
    max_input_length: int = 10000
    length_action: Literal["truncate", "reject"] = "truncate"
    reject_null_bytes: bool = True
    reject_control_chars: bool = True
    max_line_length: int = 5000

    # PII desensitization (v0.8.4)
    pii_enabled: bool = False
    pii_mask_char: str = "*"
    pii_mask_mode: Literal["partial", "full"] = "partial"
    pii_types: list[str] = field(
        default_factory=lambda: ["phone", "id_card", "email", "api_key"]
    )


@dataclass
class OutputGuardConfig:
    """Output guard configuration for sensitive information interception."""

    enabled: bool = True
    action: Literal["mask", "block", "warn"] = "mask"
    mask_char: str = "*"
    mask_mode: Literal["partial", "full"] = "partial"
    sensitive_types: list[str] = field(
        default_factory=lambda: [
            "api_key",
            "password",
            "private_key",
            "connection_string",
            "phone",
            "id_card",
            "email",
        ]
    )
    block_severity: list[str] = field(default_factory=lambda: ["private_key"])
    custom_patterns: list[dict] = field(default_factory=list)


@dataclass
class HarmfulContentFilterConfig:
    """Harmful content filter configuration for output safety checks."""

    enabled: bool = False
    categories: list[str] = field(
        default_factory=lambda: ["violence", "hate", "dangerous", "illegal"]
    )
    default_action: Literal["block", "warn", "replace"] = "block"
    category_actions: dict[str, str] = field(default_factory=dict)
    replacement_text: str = "[Content removed for safety]"
    custom_patterns: list[dict] = field(default_factory=list)


@dataclass
class ResultValidatorConfig:
    """Result correctness validator configuration for verifying agent output."""

    enabled: bool = False
    checks: list[str] = field(
        default_factory=lambda: [
            "file_exists",
            "code_syntax",
            "command_success",
            "schema",
        ]
    )
    on_fail: Literal["block", "warn", "annotate"] = "annotate"
    on_pass: Literal["silent", "annotate"] = "silent"
    custom_validators: list = field(default_factory=list)


@dataclass
class FeedbackLoopConfig:
    """Feedback loop configuration for deviation backflow and self-correction."""

    # #13 Deviation feedback (偏差信号回流)
    deviation_feedback_enabled: bool = True
    deviation_feedback_threshold: float = 0.50  # Inject hint when deviation > threshold
    deviation_feedback_cooldown: int = 3  # Inject once per N warnings
    deviation_feedback_hint_injection: bool = True  # Inject hint into LLM prompt

    # #14 Self-correction loop (自纠正循环)
    self_correction_enabled: bool = True
    self_correction_max_attempts: int = 2  # Max correction attempts (3 total runs)


@dataclass
class ToolResourceLimiterConfig:
    """Configuration for tool resource limiting (timeout + rate limiting)."""

    enabled: bool = True
    # Timeout
    timeout_enabled: bool = True
    default_timeout: int = 60  # Default timeout in seconds
    timeout_overrides: dict = field(
        default_factory=dict
    )  # tool_name -> timeout seconds
    # Rate limiting
    rate_limit_enabled: bool = True
    per_tool_calls_per_minute: int = 30  # Max calls per tool per minute
    global_calls_per_minute: int = 60  # Max total tool calls per minute

    def __post_init__(self):
        if self.default_timeout <= 0:
            raise ValueError("default_timeout must be positive")
        if self.per_tool_calls_per_minute <= 0:
            raise ValueError("per_tool_calls_per_minute must be positive")
        if self.global_calls_per_minute <= 0:
            raise ValueError("global_calls_per_minute must be positive")


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
    smart_optimization: SmartOptimizationConfig = field(
        default_factory=SmartOptimizationConfig
    )
    prompt: PromptConfig = field(default_factory=PromptConfig)
    aggressive_output: AggressiveOutputConfig = field(
        default_factory=AggressiveOutputConfig
    )
    standardized_output: StandardizedOutputConfig = field(
        default_factory=StandardizedOutputConfig
    )
    offload: ToolOffloadConfig = field(default_factory=ToolOffloadConfig)
    semantic_compressor: SemanticCompressorConfig = field(
        default_factory=SemanticCompressorConfig
    )
    retry: RetryConfig = field(default_factory=RetryConfig)
    rate_limiter: RateLimiterConfig = field(default_factory=RateLimiterConfig)
    sanitizer: SanitizerConfig = field(default_factory=SanitizerConfig)
    output_guard: OutputGuardConfig = field(default_factory=OutputGuardConfig)
    harmful_content_filter: HarmfulContentFilterConfig = field(
        default_factory=HarmfulContentFilterConfig
    )
    result_validator: ResultValidatorConfig = field(
        default_factory=ResultValidatorConfig
    )
    feedback_loop: FeedbackLoopConfig = field(default_factory=FeedbackLoopConfig)
    tool_resource_limiter: ToolResourceLimiterConfig = field(
        default_factory=ToolResourceLimiterConfig
    )
