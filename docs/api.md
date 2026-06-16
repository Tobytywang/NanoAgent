# NanoAgent API 文档

本文档提供 NanoAgent 框架的完整 API 参考。

## 目录

- [快速开始](#快速开始)
- [核心模块](#核心模块)
  - [Agent](#agent)
  - [LLM](#llm)
  - [Memory](#memory)
  - [Tools](#tools)
  - [Monitoring](#monitoring)
  - [Config](#config)
- [CLI 使用](#cli-使用)
- [相关文档](#相关文档)

---

## 快速开始

### 安装

```bash
pip install nano-agent
```

### 基本使用

```python
from nano_agent import create_agent

# 创建 Agent
agent = create_agent("config.yaml")

# 运行
response = agent.run("你好，请帮我列出当前目录的文件")
print(response)
```

---

## Agent

Agent 是 NanoAgent 的核心组件，实现 ReAct (Reasoning + Acting) 模式。

### ReActAgent

```python
from nano_agent.agent.react import ReActAgent
from nano_agent.llm import create_llm
from nano_agent.memory import ShortTermMemory
from nano_agent.tools.base import ToolRegistry
from nano_agent.tools.builtin import register_builtin_tools
```

#### 构造函数

```python
ReActAgent(
    llm,                    # LLM 客户端实例
    memory,                 # Memory 实例
    tool_registry,          # ToolRegistry 实例
    max_iterations: int = 10,    # 最大推理轮数
    verbose: bool = True,        # 是否显示详细过程
    skill_prompt: str = "",      # 技能包额外提示
    tracker = None               # MetricsTracker 实例
)
```

#### 方法

##### `run(user_input: str) -> str`

运行 Agent 处理用户输入。

```python
response = agent.run("帮我创建一个 hello.txt 文件")
```

##### `reset()`

重置 Agent 状态，清空对话历史。

```python
agent.reset()
```

##### `add_tool(tool)`

动态添加工具。

```python
from nano_agent.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的工具"
    # ...

agent.add_tool(MyTool())
```

### ContextManager

上下文压力检测与三层压缩管理器。

```python
from nano_agent.agent.context import ContextManager, ContextConfig

config = ContextConfig(
    max_context_tokens=None,       # 最大上下文 token（None 时从 LLM 配置获取）
    pressure_threshold_low=0.70,   # 轻量清理阈值
    pressure_threshold_mid=0.85,   # 摘要标记阈值
    pressure_threshold_high=0.95,  # 模型压缩阈值
)

cm = ContextManager(memory=memory, llm=llm, config=config)
```

#### `check_and_compress(max_context_tokens=None, last_prompt_tokens=None, calibration_factor=1.0) -> bool`

检查上下文压力并执行压缩。

```python
# 使用估算 token（首次迭代）
cm.check_and_compress()

# 使用上次 LLM 调用的真实 prompt_tokens（v0.7.12）
cm.check_and_compress(last_prompt_tokens=3500)
```

**参数**:
- `max_context_tokens`: 覆盖最大上下文 token 数
- `last_prompt_tokens`: 上次 LLM 调用返回的真实 `usage.prompt_tokens`。提供时直接用于压力计算，避免 `estimate_tokens()` 偏差
- `calibration_factor`: 估算校准系数（v0.7.13）。当 `last_prompt_tokens` 未提供时，`estimate_tokens()` 的结果会乘以此系数，默认 1.0

### SemanticCompressor

v0.7.19 语义压缩。通过 embedding 向量计算余弦相似度，合并长对话中语义重复的历史消息。

```python
from nano_agent.agent import SemanticCompressor, SemanticCompressorConfig

config = SemanticCompressorConfig(
    enabled=False,              # 默认关闭，需 embedding 服务
    similarity_threshold=0.85,  # 相似度阈值
    min_messages_to_compress=8, # 最少消息数触发
    provider="ollama",          # ollama / sentence-transformers / openai
    embedding_model="nomic-embed-text",
    cache_embeddings=True,      # 缓存 embedding 向量
    merge_tag="[merged {n} similar]",
)

compressor = SemanticCompressor(config)
compressor.compress(messages)  # 返回压缩后的消息列表
```

> **注意**: 语义压缩同时支持 dict 和对象类型的消息。embedding 失败不会立即禁用，连续 3 次失败后才将 `_available` 设为 `False`。
)

compressor = SemanticCompressor(config, llm_config=llm_config)

# 检查是否需要压缩
if compressor.should_compress(messages):
    result = compressor.compress(messages)
    # 相似消息被合并，保留最早 + merge_tag

# 统计信息
stats = compressor.get_stats()
# {"compression_count": 1, "messages_merged": 3, "cache_hits": 5, "errors": 0}
```

**压缩流程**:
1. 分离 system 消息（不参与合并）
2. 计算非 system 消息的 embedding（缓存优先）
3. 同 role 内 pairwise 计算余弦相似度
4. 相似度 > threshold 的消息归组
5. 每组保留最早消息，追加 merge_tag，丢弃其余

**Embedding 提供者**:
- `ollama`: 本地 Ollama 服务，使用 `/api/embed` 端点
- `sentence-transformers`: 纯 Python 库，无需外部服务（可选依赖）
- `openai`: OpenAI Embedding API

**配置** (SemanticCompressorConfig):
- `enabled: bool = False` — 默认关闭
- `similarity_threshold: float = 0.85` — 相似度阈值
- `min_messages_to_compress: int = 8` — 最少消息数触发
- `provider: str = "ollama"` — Embedding 提供者
- `embedding_model: str = "nomic-embed-text"` — Embedding 模型
- `base_url: str = "http://localhost:11434"` — Ollama/OpenAI 兼容 API 地址
- `api_key: str | None = None` — API 密钥（OpenAI）
- `cache_embeddings: bool = True` — 缓存 embedding 向量
- `merge_tag: str = "[merged {n} similar]"` — 合并标签模板

### MessageCompressor

消息压缩器，将旧消息摘要为一条系统消息。

```python
from nano_agent.agent.compressor import MessageCompressor, CompressorConfig

config = CompressorConfig(
    enabled=True,                # 是否启用压缩
    threshold_tokens=2000,       # 压缩触发阈值
    keep_recent=3,               # 保留最近 N 轮对话
    summary_max_tokens=500,      # 摘要最大 token 数
)

comp = MessageCompressor(config=config)
```

#### `should_compress(messages, last_prompt_tokens=None, calibration_factor=1.0) -> bool`

判断是否需要压缩。

**参数**:
- `messages`: 消息列表
- `last_prompt_tokens`: 上次 LLM 调用的真实 `usage.prompt_tokens`（v0.7.12）。提供时直接与阈值比较
- `calibration_factor`: 估算校准系数（v0.7.13）。当 `last_prompt_tokens` 未提供时，校准后的估算值与阈值比较

#### `compress(messages, last_prompt_tokens=None, calibration_factor=1.0) -> list`

压缩旧消息，返回压缩后的消息列表。

**参数**:
- `messages`: 消息列表
- `last_prompt_tokens`: 透传给 `should_compress()`
- `calibration_factor`: 透传给 `should_compress()`

### Token 估算工具（token_utils）

```python
from nano_agent.agent.token_utils import estimate_tokens, estimate_text_tokens, calculate_max_chars
```

#### `estimate_tokens(messages, calibration_factor=1.0) -> int`

估算消息列表的 token 数。支持中英混合文本。

**参数**:
- `messages`: 消息列表，每个元素为 `{"role": ..., "content": ...}` 字典
- `calibration_factor`: 估算校准系数（v0.7.13），乘以估算结果，默认 1.0

**估算规则**:
- 英文：~4 字符 = 1 token
- 中文：~1.5 字符 = 1 token
- 每条消息额外 4 token 开销

#### `estimate_text_tokens(text, calibration_factor=1.0) -> int`

估算单个文本字符串的 token 数。支持中英混合文本。

**参数**:
- `text`: 待估算的文本
- `calibration_factor`: 估算校准系数（v0.7.13），乘以估算结果，默认 1.0

#### `calculate_max_chars(text, max_tokens) -> int`

给定 token 预算，反算最多能保留的字符数。使用二分查找，支持中英混合文本（v0.7.13）。

**参数**:
- `text`: 待截断的文本
- `max_tokens`: token 预算上限

**返回**: 最多能保留的字符数

### Token 预算管理（token_budget）

```python
from nano_agent.agent.token_budget import TokenBudget, TokenBudgetConfig, CalibrationData
```

#### `CalibrationData`

校准数据点（v0.7.13）。

```python
@dataclass
class CalibrationData:
    estimated: int  # 估算的 prompt_tokens
    actual: int     # 实际的 prompt_tokens
```

#### `TokenBudget.record_calibration_data(estimated, actual)`

记录校准数据点并触发校准更新（v0.7.13）。由 `react.py._think()` 在每次 LLM 调用后调用。

**参数**:
- `estimated`: `estimate_tokens()` 的估算值
- `actual`: LLM 返回的 `usage.prompt_tokens`

#### `TokenBudget.get_calibration_factor() -> float`

获取当前校准系数。校准系数 = `avg(actual / estimated)`，clamp 到 [0.5, 2.0]。需 ≥3 个采样点才更新。

### QueryPrejudgment

v0.7.14 预判机制。在 ReAct 循环前用极简提示词（~50 tokens）判断查询复杂度，简单问题直接回答，节省 ~90% token。

```python
from nano_agent.agent import QueryPrejudgment, PrejudgmentResult

prejudgment = QueryPrejudgment(
    llm=llm,                      # LLM 实例
    simple_prompt="",             # 可选自定义 SIMPLE 回答提示词
    max_answer_tokens=300,        # SIMPLE 回答最大 token 数
)

result = prejudgment.prejudge("Python 的 GIL 是什么")
# result.complexity → QueryComplexity.SIMPLE
# result.answer → "GIL 是全局解释器锁..."
# result.prejudgment_tokens → 50
```

**触发条件**: 仅当 QueryRouter 返回默认 COMPLEX（reason 含 "defaulting to complex"）时触发。正则匹配到的 SIMPLE/MODERATE/COMPLEX 不触发。

**配置** (SmartOptimizationConfig):
- `prejudgment_enabled: bool = False` — 默认关闭
- `prejudgment_simple_prompt: str = ""` — 自定义 SIMPLE 回答提示词
- `prejudgment_max_answer_tokens: int = 300` — SIMPLE 回答最大 token 数

### AggressiveOutputConfig & OutputSimplifier

v0.7.15 激进输出精简。约束 LLM 回答长度，减少冗余格式（emoji、表格、列表）。

```python
from nano_agent.config.schema import AggressiveOutputConfig
from nano_agent.agent import OutputSimplifier

# 配置
config = AggressiveOutputConfig(
    enabled=True,
    level="mild",              # mild / aggressive / extreme
    max_response_sentences=3,  # 0=不限
    strip_emoji=True,
    strip_markdown_tables=True,
    strip_markdown_lists=False,
    max_response_chars=0,      # 0=不限
)

# 使用
simplifier = OutputSimplifier(config)
short = simplifier.simplify("Hello 🎉 world! This is a long response...")
# → "Hello world! This is a long response..."

# 工厂方法
simplifier = OutputSimplifier.from_level("aggressive")  # 1 句话，无格式
simplifier = OutputSimplifier.from_level("extreme")     # <200 字符
```

**三级预设**:
| Level | 句数 | 表格 | 列表 | Emoji | 字符限制 |
|-------|------|------|------|-------|---------|
| mild | 3 | 删除 | 保留 | 删除 | 无 |
| aggressive | 1 | 删除 | 删除 | 删除 | 无 |
| extreme | 1 | 删除 | 删除 | 删除 | 200 |

### StandardToolOutput & OutputFormat

v0.7.15 工具输出标准化。工具返回结构化数据，减少 LLM 解析负担。

```python
from nano_agent.tools.standard_output import StandardToolOutput, OutputFormat

# 创建标准化输出
sto = StandardToolOutput(
    format=OutputFormat.LIST,
    data={"items": [{"path": "a.py"}, {"path": "b.py"}], "total": 2},
    summary="2 files",
)

# 转换为 LLM 消息
message = sto.to_llm_message(detailed=False)
# → "a.py\nb.py\nTotal: 2"
```

**OutputFormat 枚举**:
- `STRUCTURE` — 键值对结构（file_read 结构信息）
- `LIST` — 列表（file_search, web_search）
- `STATUS` — 状态消息（shell, python_execute）
- `CONTENT` — 带元数据的内容（file_read 正文）
- `ERROR` — 错误信息

**配置** (StandardizedOutputConfig):
- `enabled: bool = True` — 默认启用
- `detailed: bool = False` — 紧凑模式（默认）或详细模式

**Schema 验证** (v0.8.8):
```python
# 验证 data 是否符合格式 schema
errors = sto.validate()  # → [] (空列表表示通过)

# 格式不匹配的示例
bad_sto = StandardToolOutput(format=OutputFormat.STATUS, data={"exit_code": 0})
bad_sto.validate()  # → ["Missing required key: status"]
```

`FORMAT_SCHEMAS` 定义了每个 `OutputFormat` 的 `required_keys`、`optional_keys`、`key_types`。

### StallDetector & StallConfig

v0.7.16 停滞检测。检测 Agent 在 ReAct 循环中连续迭代无进展，注入转向提示让 LLM 换策略。

```python
from nano_agent.agent.stall_detector import StallDetector, StallConfig, StallResult

# 配置
config = StallConfig(
    enabled=True,
    patience=3,                 # 连续 N 次无进展触发
    similarity_threshold=0.7,   # 签名相似度阈值
    hint_injection=True,        # 注入转向提示
)

# 使用
detector = StallDetector(config)
detector.record_iteration(["file_read"], ["result content"])
detector.record_iteration(["file_read"], ["result content"])
result = detector.check_stall()
# result.is_stalled → True
# result.stalled_iterations → 1
# result.hint → "你之前的尝试没有明显进展..."

# 重置（新查询前）
detector.reset()
```

**StallConfig 字段**:
- `enabled: bool = True` — 启用停滞检测
- `patience: int = 3` — 连续相似迭代次数阈值
- `similarity_threshold: float = 0.7` — 签名相似度阈值（Jaccard）
- `hint_injection: bool = True` — 检测到停滞时注入转向提示

**StallResult 字段**:
- `is_stalled: bool` — 是否停滞
- `stalled_iterations: int` — 连续停滞迭代次数
- `hint: str | None` — 转向提示文本

**进展度量**: 每次迭代生成签名（工具名 + 结果 MD5[:8] + 结果长度），通过 Jaccard 相似度比较相邻迭代。

**与 DuplicateDetector 的区别**: DuplicateDetector 检测完全相同的重复工具调用；StallDetector 检测"不同工具但原地打转"的模式。

### RetryConfig

v0.8.0 LLM 调用重试配置。429/500/网络错误自动指数退避重试。

- `enabled: bool = True` — 启用重试
- `max_retries: int = 3` — 最大重试次数
- `base_delay: float = 1.0` — 基础延迟（秒）
- `max_delay: float = 60.0` — 最大延迟上限（秒）
- `jitter: bool = True` — 添加随机抖动防止雷群效应
- `retryable_status_codes: list[int] = [429, 500, 502, 503, 504]` — 可重试的 HTTP 状态码

**重试逻辑**: 放在 `BaseLLM.chat()` 层，子类实现 `_chat_impl()`，`chat()` 自动包裹重试。Anthropic SDK 设 `max_retries=0` 避免双重重试。`chat_stream()` 本期不重试。

### RateLimiterConfig

v0.8.1 LLM API 速率限制配置。基于令牌桶算法，在请求发出前主动控制调用频率，防止触发 API 限流。

- `enabled: bool = True` — 启用速率限制
- `requests_per_minute: int = 60` — 每分钟允许的最大请求数
- `burst: int = 10` — 令牌桶容量，允许短时间内的突发请求数

**限流逻辑**: 放在 `BaseLLM.chat()` 层，在重试机制之前执行。调用链为 `chat() → rate_limiter.acquire() → with_retry(_chat_impl)`。令牌桶以 `requests_per_minute / 60` 的速率填充令牌，桶容量为 `burst`。桶满时新令牌被丢弃；桶空时请求阻塞等待直到获取令牌。`chat_stream()` 本期不限流。

> **注意**: `requests_per_minute` 必须 > 0，`burst` 必须 > 0，负值或零会抛出 `ValueError`。

### CircuitBreakerConfig & CircuitBreaker

v0.8.0 熔断器配置。检测异常 LLM 行为（响应过大、重复调用、停滞），从 AUTO 降级到 SUPERVISED 模式。

- `enabled: bool = True` — 启用熔断器
- `max_response_tokens: int = 8000` — LLM 单次响应 token 上限
- `duplicate_trigger_count: int = 3` — 重复调用触发次数阈值
- `stall_trigger_count: int = 3` — 停滞触发次数阈值
- `auto_reset_on_user_confirm: bool = True` — 用户确认后自动恢复 AUTO

**熔断逻辑**: 三种触发条件检测后，降级为 SUPERVISED 模式，所有工具调用强制走 `ConfirmationManager` 确认流程。`/auto` 命令手动恢复 AUTO。

```python
from nano_agent.agent.circuit_breaker import CircuitBreaker
from nano_agent.config.schema import CircuitBreakerConfig

cb = CircuitBreaker(CircuitBreakerConfig())
cb.check_llm_response(completion_tokens)  # 检查 LLM 响应大小
cb.check_duplicate(duplicate_result)      # 检查重复调用（传入 DuplicateCheckResult）
cb.check_stall(stall_result)              # 检查停滞
cb.mode  # ExecutionMode.AUTO / SUPERVISED
cb.reset()  # 重置为 AUTO，同时发射 CIRCUIT_BREAKER 事件
```

> **注意**: `max_retries` 必须 >= 0，负值会抛出 `ValueError`。

### SanitizerConfig & InputSanitizer

v0.8.3 输入净化器。在编排层（orchestrator）边界过滤 prompt injection 模式并验证输入格式，是 ReAct 循环前的硬门控。

- `enabled: bool = True` — 启用输入净化
- `injection_patterns: list[str]` — 注入检测正则列表（默认 18 条，覆盖常见 prompt injection 模式）
- `custom_patterns: list[str] = []` — 用户自定义注入检测正则
- `max_input_length: int = 10000` — 输入最大字符长度
- `length_action: str = "truncate"` — 超长处理方式：`"truncate"` 截断 / `"reject"` 拒绝
- `reject_null_bytes: bool = True` — 拒绝含 null 字节的输入
- `reject_control_chars: bool = True` — 剥离控制字符（保留换行/制表符）

**处理顺序**: format check（null bytes reject, control chars strip） → PII desensitization（optional mask） → injection check（regex match, always reject） → length check（truncate or reject）。格式检查先于注入检查，防止通过编码绕过注入检测。

**PII 脱敏** (v0.8.4): 在注入检查前，可选地检测并遮蔽 PII（个人身份信息），确保 Agent 不接触原始敏感数据。

- `pii_enabled: bool = False` — 启用 PII 脱敏（默认关闭）
- `pii_mask_char: str = "*"` — 遮蔽字符
- `pii_mask_mode: Literal["partial", "full"] = "partial"` — 遮蔽模式：`"partial"` 保留首尾（如 138****1234），`"full"` 全遮蔽
- `pii_types: list[str] = ["phone", "id_card", "email", "api_key"]` — 启用的 PII 检测类型

**支持的 PII 类型**:

| 类型 | 正则匹配 | Partial 示例 |
|------|---------|-------------|
| `phone` | 中国手机号 `1[3-9]\d{9}` | `138****1234` |
| `id_card` | 中国身份证 18 位 | `110***********1234` |
| `email` | 邮箱地址 | `u***@domain.com` |
| `api_key` | Bearer/sk-/pk-/ghp_/AKIA/AIza 等前缀 | `sk-****...****abcd` |

**重叠处理**: 当多个 PII 正则匹配重叠时（如手机号匹配在身份证号内部），保留更长的匹配。

```python
from nano_agent.agent.sanitizer import InputSanitizer, PIIDesensitizer, PIIMatch
from nano_agent.config.schema import SanitizerConfig

config = SanitizerConfig(
    enabled=True,
    pii_enabled=True,
    pii_mask_mode="partial",
    pii_types=["phone", "id_card", "email", "api_key"],
)

sanitizer = InputSanitizer(config)
result = sanitizer.sanitize("我的手机号是13812345678，邮箱是test@example.com")
# result.sanitized_input → "我的手机号是138****5678，邮箱是t***@example.com"
# result.pii_matches → [PIIMatch(pii_type="phone", ...), PIIMatch(pii_type="email", ...)]
# result.actions_taken → ["pii_desensitized: phone: 1, email: 1"]
```

**净化逻辑**: 放在 `AgentOrchestrator` 层，在 ReAct 循环之前执行。输入被拒绝时返回 `TerminationReason.INPUT_REJECTED`，触发 `AgentEvent.INPUT_REJECTED` 事件。

```python
from nano_agent.agent.sanitizer import InputSanitizer
from nano_agent.config.schema import SanitizerConfig

config = SanitizerConfig(
    enabled=True,
    max_input_length=10000,
    length_action="truncate",     # "truncate" 或 "reject"
    reject_null_bytes=True,
    reject_control_chars=True,
)

sanitizer = InputSanitizer(config)
result = sanitizer.sanitize(user_input)
# result.is_valid → True / False
# result.sanitized_input → 净化后的输入（可能截断）
# result.rejection_reason → 拒绝原因（None 如果通过）
# result.was_truncated → 是否被截断
```

### OutputGuardConfig & OutputGuard

v0.8.5 输出护栏。在编排层（orchestrator）边界扫描 Agent 响应中的敏感信息，是 ReAct 循环后的硬门控——输入净化器保护"进来"的数据，输出护栏保护"出去"的数据。

- `enabled: bool = True` — 启用输出护栏
- `action: Literal["mask", "block", "warn"] = "mask"` — 拦截动作：`"mask"` 遮蔽敏感数据（默认），`"block"` 整个响应被拦截，`"warn"` 允许但记录警告
- `mask_mode: Literal["partial", "full"] = "partial"` — 遮蔽模式
- `mask_char: str = "*"` — 遮蔽字符
- `sensitive_types: list[str]` — 启用的敏感类型（默认全部启用）
- `block_severity: list[str] = ["private_key"]` — 强制触发 block 的类型（即使 action 为 mask）
- `custom_patterns: list[dict] = []` — 用户自定义检测模式 `[{"name": "type", "pattern": "regex"}]`

**支持的敏感类型**:

| 类型 | 说明 | Partial 遮蔽示例 |
|------|------|-----------------|
| `api_key` | Bearer/sk-/pk-/ghp_/AKIA 等前缀 | `sk-****abcd` |
| `password` | password/passwd/pwd/secret/token 赋值 | `password=****` |
| `private_key` | PEM 私钥头 | `[PRIVATE KEY REDACTED]` |
| `connection_string` | 数据库连接串 | `postgres://user:****@host` |
| `phone` | 中国手机号（复用 PII 检测） | `138****1234` |
| `id_card` | 中国身份证（复用 PII 检测） | `110***********1234` |
| `email` | 邮箱地址（复用 PII 检测） | `u***@domain.com` |

**处理逻辑**: 放在 `AgentOrchestrator` 层，在 Agent 产生响应后、返回用户前执行。输出被拦截时返回 `TerminationReason.OUTPUT_BLOCKED`，触发 `AgentEvent.OUTPUT_BLOCKED` 事件。

```python
from nano_agent.agent.output_guard import OutputGuard, OutputGuardResult, SensitiveMatch
from nano_agent.config.schema import OutputGuardConfig

config = OutputGuardConfig(
    enabled=True,
    action="mask",
    sensitive_types=["api_key", "password", "private_key", "connection_string"],
    block_severity=["private_key"],
)

guard = OutputGuard(config)
result = guard.guard("The database is at postgres://admin:secret@db.example.com:5432/app")
# result.guarded → "The database is at postgres://admin:****@db.example.com:5432/app"
# result.blocked → False
# result.matches → [SensitiveMatch(sensitive_type="connection_string", ...)]
# result.actions_taken → ["output_masked: connection_string: 1"]
```

**block_severity**: `private_key` 默认在 block_severity 中，即使 action 为 mask，检测到私钥也会拦截整个响应。这防止了私钥的部分泄露（因为 PEM 格式跨多行，单行遮蔽不够安全）。

### HarmfulContentFilterConfig & HarmfulContentFilter

v0.8.6 有害内容过滤器。在编排层（orchestrator）边界扫描 Agent 响应中的有害/危险内容，是输出护栏之后的第二道防线——OutputGuard 防止信息*泄露*，HarmfulContentFilter 防止*有害内容*触达用户。默认关闭（opt-in），用户需显式启用并配置检测类别。

- `enabled: bool = False` — 启用有害内容过滤（默认关闭）
- `categories: list[str] = ["violence", "hate", "dangerous", "illegal"]` — 启用的检测类别
- `default_action: Literal["block", "warn", "replace"] = "block"` — 默认处理动作：`"block"` 拦截整个响应，`"warn"` 添加警告前缀，`"replace"` 替换有害片段
- `category_actions: dict[str, str] = {}` — 按类别覆盖动作（如 `{"illegal": "warn"}`）
- `replacement_text: str = "[Content removed for safety]"` — replace 动作的替换文本
- `custom_patterns: list[dict] = []` — 用户自定义有害内容模式 `[{"category": "custom", "severity": "medium", "pattern": "regex"}]`

**支持的检测类别**:

| 类别 | 严重度 | 说明 | 覆盖内容 |
|------|--------|------|---------|
| `violence` | high | 暴力内容 | 制造武器/爆炸物指示、杀人方法、暴力犯罪教唆 |
| `hate` | high | 仇恨言论 | 仇恨言论+攻击意图、种族歧视+暴力、种族清洗 |
| `dangerous` | high | 危险内容 | 自杀/自残方法、毒品合成、黑客攻击/入侵教程 |
| `illegal` | medium | 违法内容 | 洗钱方法、逃税方法、伪造货币/证件、身份盗窃 |

**处理逻辑**: 放在 `AgentOrchestrator` 层，在 OutputGuard 之后执行。当任何类别的动作为 block 时，整个响应被拦截（block 优先于 warn/replace）。输出被拦截时返回 `TerminationReason.HARMFUL_CONTENT_BLOCKED`，触发 `AgentEvent.HARMFUL_CONTENT_DETECTED` 和 `AgentEvent.OUTPUT_BLOCKED` 事件。

**优先级规则**: block > replace > warn。当多个类别同时命中且动作为 block 时，整个响应被拦截；当只有 warn/replace 类别命中时，先执行 replace 再添加 warn 前缀。

```python
from nano_agent.agent.harmful_filter import HarmfulContentFilter, HarmfulMatch, HarmfulFilterResult, summarize_harmful_matches
from nano_agent.config.schema import HarmfulContentFilterConfig

config = HarmfulContentFilterConfig(
    enabled=True,
    categories=["violence", "hate", "dangerous", "illegal"],
    default_action="block",
    category_actions={"illegal": "warn"},  # illegal 仅警告
    replacement_text="[Content removed for safety]",
)

harmful_filter = HarmfulContentFilter(config)
result = harmful_filter.filter("Here is how to make a bomb: ...")
# result.blocked → True
# result.filtered → ""
# result.reason → "Output contains harmful content: violence: 1"
# result.matches → [HarmfulMatch(category="violence", start=11, end=..., original="how to make a bomb", severity="high")]
# result.actions_taken → ["harmful_blocked: violence: 1"]
```

**HarmfulMatch 数据类**:
- `category: str` — 匹配的有害类别
- `start: int` — 匹配起始位置
- `end: int` — 匹配结束位置
- `original: str` — 匹配的原始文本
- `severity: Literal["high", "medium"]` — 严重度

**HarmfulFilterResult 数据类**:
- `original: str` — 原始文本
- `filtered: str` — 过滤后文本（blocked 时为空字符串）
- `blocked: bool` — 是否被拦截
- `warned: bool` — 是否添加警告前缀
- `reason: str | None` — 拦截/警告原因
- `matches: list[HarmfulMatch]` — 所有匹配项
- `actions_taken: list[str]` — 执行的动作列表

**summarize_harmful_matches(matches)**: 生成人类可读的匹配汇总，格式如 `"violence: 2, hate: 1"`。

**scan_tool_output(output)**: 扫描工具输出中的有害内容，仅执行替换（不拦截）。用于 `HarmfulContentMiddleware`（priority=99），在工具执行边界扫描输出，防止有害内容通过工具结果进入上下文。

```python
# 工具输出扫描（仅替换，不拦截）
filtered_output = harmful_filter.scan_tool_output("Step-by-step hacking guide: ...")
# → "Step-by-step [Content removed for safety]: ..."
```

**自定义模式**: 通过 `custom_patterns` 添加领域特定的有害内容检测模式：

```python
config = HarmfulContentFilterConfig(
    enabled=True,
    categories=["violence", "dangerous"],
    custom_patterns=[
        {"category": "corporate", "severity": "medium", "pattern": r"(?i)insider\s+trading\s+(?:tips|guide|methods)"},
    ],
)
```

### HarmfulContentMiddleware

v0.8.6 有害内容中间件。在工具执行边界（after phase）扫描工具输出中的有害内容，与 HarmfulContentFilter 配合使用。

- **priority**: 99（低于 SensitiveOutputMiddleware 的 100，确保敏感信息先被处理）
- **行为**: 调用 `HarmfulContentFilter.scan_tool_output()` 对工具输出执行替换，不拦截
- **激活条件**: 需传入 `HarmfulContentFilter` 实例且 `harmful_filter.enabled` 为 True

### ResultValidatorConfig & ResultValidator

v0.8.7 结果正确性验证器。在编排层（orchestrator）管线的 OutputGuard 和 HarmfulContentFilter 之后执行，验证 Agent 输出中的声明是否与实际结果一致。默认关闭（opt-in），用户需显式启用。

- `enabled: bool = False` — 是否启用结果正确性验证（默认关闭）
- `checks: list[str] = ["file_exists", "code_syntax", "command_success"]` — 启用的验证检查类型
- `on_fail: Literal["block", "warn", "annotate"] = "annotate"` — 检查失败时的动作：`"block"` 拦截响应（仅 high-severity），`"warn"` 添加警告前缀，`"annotate"` 在响应中添加验证标注
- `on_pass: Literal["silent", "annotate"] = "silent"` — 所有检查通过时的动作：`"silent"` 无额外输出，`"annotate"` 添加通过标注
- `custom_validators: list = []` — 自定义验证器函数列表

**验证检查类型**:

| check_type | severity | 说明 |
|------------|----------|------|
| `file_exists` | high | Agent 声称创建了文件 → 验证路径是否存在 |
| `code_syntax` | medium | Agent 声称代码正确 → 验证 Python/JSON/YAML 语法 |
| `command_success` | high/low | Agent 声称命令成功 → 检查是否有矛盾的非零退出码 |
| `schema` | medium | StandardToolOutput.data 不符合格式 schema → 回退原始输出 |

**处理逻辑**: 在 Orchestrator 管线中 OutputGuard 和 HarmfulContentFilter 之后执行。block 动作仅对 high-severity 失败生效。输出被拦截时返回 `TerminationReason.VALIDATION_FAILED`，触发 `AgentEvent.VALIDATION_FAILED` 和 `AgentEvent.OUTPUT_BLOCKED` 事件。

```python
from nano_agent.agent.result_validator import ResultValidator, ValidationCheck, ValidationResult, summarize_validation_checks
from nano_agent.config.schema import ResultValidatorConfig

config = ResultValidatorConfig(
    enabled=True,
    checks=["file_exists", "code_syntax", "command_success", "schema"],
    on_fail="annotate",   # 失败时添加验证标注
    on_pass="silent",     # 通过时无额外输出
)

validator = ResultValidator(config)
result = validator.validate("I've created the file output.txt for you.", tool_results=tool_results)
# result.blocked → False
# result.checks → [ValidationCheck(check_type="file_exists", claim="output.txt", passed=True, ...)]
# result.failed_checks → []
# result.actions_taken → []
```

**ValidationCheck 数据类**:
- `check_type: str` — 检查类型（`"file_exists"` / `"code_syntax"` / `"command_success"` / `"schema"`）
- `claim: str` — Agent 的声明内容
- `passed: bool` — 是否通过验证
- `detail: str` — 验证详情
- `severity: Literal["high", "medium", "low"]` — 严重度

**ValidationResult 数据类**:
- `original: str` — 原始输出文本
- `validated: str` — 验证后的输出文本（blocked 时为空字符串）
- `blocked: bool` — 是否被拦截
- `reason: str | None` — 拦截原因
- `checks: list[ValidationCheck]` — 所有检查项
- `failed_checks: list[ValidationCheck]` — 未通过的检查项
- `actions_taken: list[str]` — 执行的动作列表

**summarize_validation_checks(checks)**: 生成人类可读的检查汇总，格式如 `"file_exists: 2 passed, code_syntax: 1 failed"`。

### FeedbackLoop & FeedbackLoopConfig

v0.8.9 反馈闭环：偏差信号回流 (#13) + 自纠正循环 (#14)。

```python
from nano_agent.agent.feedback_loop import FeedbackLoop, DeviationFeedbackResult, SelfCorrectionResult
from nano_agent.config.schema import FeedbackLoopConfig

config = FeedbackLoopConfig(
    deviation_feedback_enabled=True,   # 偏差信号回流
    deviation_feedback_threshold=0.50, # 触发阈值
    deviation_feedback_cooldown=3,     # 冷却间隔
    self_correction_enabled=True,      # 自纠正循环
    self_correction_max_attempts=2,    # 最大尝试次数
)

fl = FeedbackLoop(config, events=agent.events)

# #13: 检查偏差并注入提示
result = fl.check_deviation(audit_result)
if result.should_inject and result.hint:
    memory.add_user_message(f"[System] {result.hint}")

# #14: 判断是否应重试
if fl.should_retry(validator_result):
    feedback = fl.build_correction_feedback(validator_result)
    fl.record_correction_attempt()
```

**FeedbackLoop 核心方法**：
- `check_deviation(audit_result)` → `DeviationFeedbackResult` — 检查偏差是否需要注入提示
- `should_retry(validator_result)` → `bool` — 判断是否应自纠正重试
- `build_correction_feedback(validator_result)` → `str` — 构建结构化反馈消息
- `record_correction_attempt()` → `SelfCorrectionResult` — 记录纠正尝试
- `reset()` — 重置状态（新 run 前调用）

**DeviationFeedbackResult 数据类**：
- `should_inject: bool` — 是否应注入提示
- `hint: str | None` — 提示文本
- `deviation_pct: float` — 当前偏差
- `direction: str` — "over"（高估）或 "under"（低估）

**SelfCorrectionResult 数据类**：
- `attempted: bool` — 是否已尝试纠正
- `attempt_number: int` — 当前尝试编号
- `remaining_attempts: int` — 剩余尝试次数

### ExecutionMode

v0.8.0 执行模式枚举，由熔断器控制。

- `AUTO = "auto"` — 全自动执行
- `SUPERVISED = "supervised"` — 每个工具调用需用户确认

### ToolOffloadManager & OffloadedResult

v0.7.17 工具结果卸载。大结果写入临时文件，仅注入摘要到上下文。

```python
from nano_agent.agent.tool_offload import ToolOffloadManager, OffloadedResult
from nano_agent.config.schema import ToolOffloadConfig

config = ToolOffloadConfig(
    enabled=True,
    size_threshold_tokens=1000,  # 超过 1000 tokens 触发卸载
    offload_dir="/tmp/nano_agent_offload",
    auto_cleanup=True,
    summary_max_tokens=200,
)

manager = ToolOffloadManager(config)

# 检查是否应卸载
if manager.should_offload(large_content, "file_read", tool_can_offload=True):
    summary, offloaded = manager.offload(large_content, "file_read", "call_123")
    # summary: "[结果已卸载] file_read 返回约 5000 tokens\n摘要: ...\n完整结果: file_read(\"/tmp/xxx\")"
    # offloaded.file_path: 临时文件路径
```

**OffloadedResult 字段**:
- `offload_id: str` — 卸载 ID
- `file_path: str` — 临时文件路径
- `tool_name: str` — 工具名称
- `original_size_tokens: int` — 原始大小
- `summary: str` — 摘要内容
- `accessed: bool` — 是否被访问

### ToolResultCache & CacheEntry

v0.7.17 多轮缓存。跨轮次复用工具结果，支持磁盘持久化和 mtime 失效。

```python
from nano_agent.agent.cache import ToolResultCache, CacheEntry
from nano_agent.config.schema import CacheConfig

config = CacheConfig(
    enabled=True,
    ttl_seconds=300,
    persist=True,              # 持久化到磁盘
    persist_dir=".nano_agent/cache",
    warmup_on_restore=True,    # 会话恢复时预热
    mtime_invalidation=True,   # 文件修改时失效
)

cache = ToolResultCache(config)

# 缓存结果
cache.set_cached_result("file_read", {"file_path": "/test.py"}, "file content")

# 获取缓存（自动检查 TTL 和 mtime）
result = cache.get_cached_result("file_read", {"file_path": "/test.py"})

# 持久化到磁盘
cache.persist_to_disk()

# 从磁盘预热
cache.warmup_from_disk()
```

**CacheEntry 字段**:
- `tool_name: str` — 工具名称
- `result: str` — 缓存内容（字符串）
- `timestamp: float` — 缓存时间
- `token_count: int` — Token 数量
- `file_paths: list[str]` — 相关文件路径
- `file_mtimes: dict[str, float]` — 文件修改时间
- `is_offloaded: bool` — 是否为卸载摘要

### RoutingResult.suggested_budget_ratio

v0.7.16 复杂度预算 Profile。QueryRouter 分类结果现在包含预算比例建议。

```python
from nano_agent.agent.router import QueryRouter, RoutingResult

router = QueryRouter(
    simple_budget_ratio=0.15,   # SIMPLE → 15% 预算
    moderate_budget_ratio=0.5,  # MODERATE → 50% 预算
    complex_budget_ratio=1.0,   # COMPLEX → 100% 预算
)

result = router.classify("你好")
# result.suggested_budget_ratio → 0.15
# result.suggested_max_tools → 0
```

**TokenBudget.set_budget_ratio()**: 根据复杂度比例调整预算。

```python
from nano_agent.agent.token_budget import TokenBudget, TokenBudgetConfig

budget = TokenBudget(TokenBudgetConfig(initial_budget=100000))
budget.set_budget_ratio(0.15, 100000)
# budget.initial_budget → 15000
# budget.remaining → 15000
```

### AgentEvent 枚举

```python
from nano_agent.agent.types import AgentEvent

class AgentEvent(Enum):
    RUN_START = "run_start"
    THINK_START = "think_start"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RUN_END = "run_end"
    CONFIRMATION_REQUIRED = "confirmation_required"
    BUDGET_WRAPUP = "budget_wrapup"
    DUPLICATE_BLOCKED = "duplicate_blocked"
    STALL_DETECTED = "stall_detected"          # v0.7.16
    INPUT_REJECTED = "input_rejected"          # v0.8.3
    OUTPUT_BLOCKED = "output_blocked"          # v0.8.5
    HARMFUL_CONTENT_DETECTED = "harmful_content_detected"  # v0.8.6
    VALIDATION_FAILED = "validation_failed"              # v0.8.7
```

### TerminationReason 枚举

```python
from nano_agent.agent.types import TerminationReason

class TerminationReason(str, Enum):
    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    BUDGET_EXHAUSTED = "budget_exhausted"
    BUDGET_WRAP_UP = "budget_wrap_up"
    STALL_DETECTED = "stall_detected"          # v0.7.16
    CONFIDENCE_EARLY_STOP = "confidence_early_stop"
    CONFIDENCE_VERIFIED = "confidence_verified"
    ROUTING_LIMIT = "routing_limit"
    DUPLICATE_BLOCKED = "duplicate_blocked"
    PREJUDGMENT_SIMPLE = "prejudgment_simple"
    INPUT_REJECTED = "input_rejected"              # v0.8.3
    OUTPUT_BLOCKED = "output_blocked"              # v0.8.5
    HARMFUL_CONTENT_BLOCKED = "harmful_content_blocked"  # v0.8.6
    VALIDATION_FAILED = "validation_failed"              # v0.8.7
```

**配置** (SmartOptimizationConfig):

复杂度预算 Profile (v0.7.16):
- `complexity_budget_enabled: bool = True` — 按复杂度调整预算
- `complexity_budget_simple_ratio: float = 0.15` — SIMPLE 预算比例
- `complexity_budget_moderate_ratio: float = 0.5` — MODERATE 预算比例
- `complexity_budget_complex_ratio: float = 1.0` — COMPLEX 预算比例

Stall Detection (v0.7.16):
- `stall_detection_enabled: bool = True` — 启用停滞检测
- `stall_patience: int = 3` — 连续相似迭代次数阈值
- `stall_similarity_threshold: float = 0.7` — 签名相似度阈值
- `stall_hint_injection: bool = True` — 检测到停滞时注入转向提示

Calibration & Estimation Audit (v0.7.18):
- `calibration_enabled: bool = True` — 启用校准
- `calibration_window: int = 5` — 校准窗口（最近 N 次调用）
- `min_calibration_samples: int = 3` — 最少采样数
- `estimation_audit_enabled: bool = True` — 启用估算审计
- `estimation_deviation_warning_threshold: float = 0.50` — 偏差告警阈值

Retry (v0.8.0):
- `retry.enabled: bool = True` — 启用 LLM 调用重试
- `retry.max_retries: int = 3` — 最大重试次数
- `retry.base_delay: float = 1.0` — 基础延迟（秒）
- `retry.max_delay: float = 60.0` — 最大延迟（秒）
- `retry.jitter: bool = True` — 随机抖动
- `retry.retryable_status_codes: list[int] = [429, 500, 502, 503, 504]` — 可重试状态码

Rate Limiter (v0.8.1):
- `rate_limiter.enabled: bool = True` — 启用速率限制
- `rate_limiter.requests_per_minute: int = 60` — 每分钟最大请求数
- `rate_limiter.burst: int = 10` — 令牌桶容量（允许突发请求数）

**CircuitBreaker (smart_optimization.circuit_breaker)**

- `smart_optimization.circuit_breaker.enabled: bool = True` — 启用熔断器
- `smart_optimization.circuit_breaker.max_response_tokens: int = 8000` — LLM 单次响应上限
- `smart_optimization.circuit_breaker.duplicate_trigger_count: int = 3` — 重复调用触发次数
- `smart_optimization.circuit_breaker.stall_trigger_count: int = 3` — 停滞触发次数
- `smart_optimization.circuit_breaker.auto_reset_on_user_confirm: bool = True` — 确认后恢复 AUTO

**Sanitizer (sanitizer)**

- `sanitizer.enabled: bool = True` — 启用输入净化
- `sanitizer.injection_patterns: list[str]` — 注入检测正则列表（默认 18 条）
- `sanitizer.custom_patterns: list[str] = []` — 自定义注入检测正则
- `sanitizer.max_input_length: int = 10000` — 输入最大字符长度
- `sanitizer.length_action: str = "truncate"` — 超长处理方式（`"truncate"` / `"reject"`）
- `sanitizer.reject_null_bytes: bool = True` — 拒绝含 null 字节的输入
- `sanitizer.reject_control_chars: bool = True` — 剥离控制字符
- `sanitizer.pii_enabled: bool = False` — 启用 PII 脱敏
- `sanitizer.pii_mask_mode: str = "partial"` — 遮蔽模式（`"partial"` / `"full"`）
- `sanitizer.pii_mask_char: str = "*"` — 遮蔽字符
- `sanitizer.pii_types: list[str] = ["phone", "id_card", "email", "api_key"]` — 启用的 PII 类型

**Harmful Content Filter (harmful_content_filter)**

- `harmful_content_filter.enabled: bool = False` — 启用有害内容过滤（默认关闭）
- `harmful_content_filter.categories: list[str] = ["violence", "hate", "dangerous", "illegal"]` — 启用的检测类别
- `harmful_content_filter.default_action: str = "block"` — 默认处理动作（`"block"` / `"warn"` / `"replace"`）
- `harmful_content_filter.category_actions: dict[str, str] = {}` — 按类别覆盖动作（如 `{"illegal": "warn"}`）
- `harmful_content_filter.replacement_text: str = "[Content removed for safety]"` — replace 动作的替换文本
- `harmful_content_filter.custom_patterns: list[dict] = []` — 用户自定义有害内容模式 `[{"category": "...", "severity": "...", "pattern": "..."}]`

**Result Validator (result_validator)**

- `result_validator.enabled: bool = False` — 启用结果正确性验证（默认关闭）
- `result_validator.checks: list[str] = ["file_exists", "code_syntax", "command_success", "schema"]` — 启用的验证检查类型
- `result_validator.on_fail: str = "annotate"` — 检查失败时的动作（`"block"` / `"warn"` / `"annotate"`）
- `result_validator.on_pass: str = "silent"` — 所有检查通过时的动作（`"silent"` / `"annotate"`）
- `result_validator.custom_validators: list = []` — 自定义验证器函数列表


---

## LLM

LLM 模块提供与大语言模型交互的客户端。

### create_llm 工厂函数

```python
from nano_agent.llm import create_llm
```

```python
# Ollama 本地模型
llm = create_llm(provider="ollama", model="qwen2.5:7b")

# OpenAI
llm = create_llm(provider="openai", api_key="sk-...")

# DeepSeek
llm = create_llm(provider="deepseek", api_key="sk-...")

# 自定义 OpenAI 兼容 API
llm = create_llm(
    provider="openai_compatible",
    model="custom-model",
    base_url="https://api.example.com/v1",
    api_key="your-key"
)
```

### LLMUsage

LLM 返回的使用统计信息。

```python
@dataclass
class LLMUsage:
    prompt_tokens: int = 0       # 输入 token 数
    completion_tokens: int = 0   # 输出 token 数
    total_tokens: int = 0        # 总 token 数
```

### chat() 方法

```python
content, tool_calls, usage = llm.chat(
    messages: list,              # 消息列表
    tools: list | None = None    # 工具定义（可选）
)
```

**返回值**:
- `content`: 文本响应
- `tool_calls`: ToolCall 对象列表
- `usage`: LLMUsage 实例

### 重试机制

`BaseLLM.chat()` 内置指数退避重试，429/500/网络错误自动恢复：

```python
from nano_agent.llm.retry import with_retry, is_retryable_error, calculate_delay
```

- `with_retry(func, config, on_retry)` — 通用重试包装器
- `is_retryable_error(exc, config)` — 判断异常是否可重试（429/500/网络→可重试，400/401/ValueError→不可重试）
- `calculate_delay(attempt, config)` — 指数退避延迟：`min(base * 2^attempt + jitter, max_delay)`

重试事件通过 `AgentEvent.LLM_RETRY` 发出，verbose 模式打印 `[Retry 1/3] ConnectionError, waiting 1.0s...`。

---

## Memory

Memory 模块管理对话历史和长期记忆。

### ShortTermMemory

短期记忆，仅在当前会话有效。

```python
from nano_agent.memory import ShortTermMemory

memory = ShortTermMemory(
    max_messages: int = 50,      # 最大消息数
    system_prompt: str = "..."   # 系统提示
)
```

### PersistentMemory

持久化记忆，支持会话保存和恢复。

```python
from nano_agent.memory import PersistentMemory, FileStorage

storage = FileStorage(base_dir=".nano_agent/memory")
memory = PersistentMemory(
    storage=storage,
    session_id="session_001",
    max_messages=50
)
```

#### 方法

```python
# 会话管理
memory.new_session()              # 创建新会话
memory.load_session(session_id)   # 加载会话
memory.list_sessions()            # 列出所有会话

# 消息操作
memory.add_user_message(content)
memory.add_assistant_message(content, tool_calls=None)
memory.add_tool_result(tool_call_id, content)
```

### HybridMemory

混合记忆，结合工作记忆和长期记忆。

```python
from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory

working_memory = PersistentMemory(...)
long_term_memory = LongTermMemory(storage_path=".nano_agent/long_term")

memory = HybridMemory(
    working_memory=working_memory,
    long_term_memory=long_term_memory,
    auto_extract=True    # 自动提取重要信息
)
```

#### 长期记忆操作

```python
# 存储信息
entry_id = memory.memorize(
    content="用户喜欢使用 Python",
    category="preference",
    importance=0.8
)

# 检索信息
results = memory.recall("编程语言偏好", limit=5)

# 列出所有
entries = memory.get_all_long_term()

# 删除
memory.forget(entry_id)
```

---

## Tools

Tools 模块提供工具定义和注册机制。

### BaseTool

所有工具的基类。

```python
from nano_agent.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "工具描述"
    can_offload = True  # 允许大结果卸载到文件（默认 False）

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

    def execute(self, input: str) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, output="结果")
```

### ToolResult

工具执行结果。

```python
@dataclass
class ToolResult:
    success: bool           # 是否成功
    output: str = ""        # 输出内容
    error: str | None = None  # 错误信息
    metadata: dict | None = None  # 可选元数据（用于传递额外信息）
```

**metadata 用途示例**：

`MemorizeTool` 使用 metadata 传递检测到的名字信息：

```python
result = ToolResult(
    success=True,
    output="Successfully stored...",
    metadata={"name_type": "user_name", "name_value": "天宇"}
)
```

### ToolRegistry

工具注册表。

```python
from nano_agent.tools.base import ToolRegistry

registry = ToolRegistry()
registry.register(MyTool())

# 获取工具
tool = registry.get("my_tool")

# 列出所有工具
tools = registry.list_tools()

# 获取工具 schema
schemas = registry.get_all_schemas()
```

### 内置工具

| 工具名称 | 描述 |
|---------|------|
| `python_execute` | 执行 Python 代码 |
| `file_read` | 读取文件 |
| `file_write` | 写入文件 |
| `file_search` | 搜索文件 |
| `shell_execute` | 执行 Shell 命令 |
| `web_search` | 网络搜索 |
| `memorize` | 存储到长期记忆 |
| `recall` | 从长期记忆检索 |
| `list_memories` | 列出长期记忆 |
| `forget` | 删除长期记忆条目 |
| `get_stats` | 获取运行统计 |

---

## Monitoring

Monitoring 模块提供运行时监控能力。

### MetricsTracker

```python
from nano_agent.monitoring import MetricsTracker

tracker = MetricsTracker(enabled=True)
```

#### 方法

```python
# 运行追踪
tracker.start_run(user_input)
tracker.end_run(response)

# 迭代追踪
tracker.start_iteration(number)
tracker.end_iteration()

# 记录 LLM 调用
tracker.record_llm_call(
    model="gpt-4o",
    prompt_tokens=100,
    completion_tokens=50,
    latency_ms=200.0,
    tool_calls_count=1
)

# 记录工具执行
tracker.record_tool_execution(
    tool_name="file_read",
    arguments={"path": "/tmp/test.txt"},
    success=True,
    latency_ms=50.0,
    output_length=100
)

# 获取统计
summary = tracker.get_summary()           # 当前运行
session_summary = tracker.get_session_summary()  # 会话总计
full_report = tracker.get_full_report()   # 完整报告
detailed_usage = tracker.get_detailed_usage()  # 详细 Token 消耗列表

# Token 估算相关
base_ratio = tracker.get_base_ratio()     # 获取基准比例
base_chars = tracker.get_base_chars()     # 获取基准字符长度
```

### 统计数据结构

```python
@dataclass
class LLMCallMetrics:
    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    tool_calls_count: int
    # 新增字段
    input_messages: list[dict]    # 输入消息列表
    output_text: str              # 输出文本
    tool_calls: list[dict]        # 工具调用列表
    tools_schema: list[dict]      # 工具定义 schema

@dataclass
class ToolExecutionMetrics:
    timestamp: datetime
    tool_name: str
    arguments: dict
    success: bool
    latency_ms: float
    output_length: int
    error: str | None

@dataclass
class RunMetrics:
    session_id: str
    start_time: datetime
    end_time: datetime
    user_input: str
    final_response: str
    iterations: list[IterationMetrics]
    total_tokens: int
    total_latency_ms: float
```

---

## Config

Config 模块提供配置加载和管理。

### 配置结构

```yaml
llm:
  provider: ollama           # ollama / openai / deepseek / moonshot / openai_compatible
  model: qwen2.5:7b
  base_url: http://localhost:11434
  api_key: null
  api_key_env: OPENAI_API_KEY
  timeout: 120
  temperature: 0.7
  context_length: null       # 可选，手动指定上下文长度

agent:
  max_iterations: 10
  verbose: true
  system_prompt: null

  user_name: User            # 用户显示名
  agent_name: Agent          # Agent 显示名

memory:
  type: hybrid               # short_term / persistent / hybrid
  max_messages: 50
  storage_path: .nano_agent/memory
  long_term_storage_path: .nano_agent/long_term_memory
  auto_extract: true

tools:
  enabled: [all]
  disabled: []

plugins:
  directories: []            # 扫描插件的目录
  modules: []                # 导入的 Python 模块
  files: []                  # 加载的特定文件

skills:
  enabled: []
  directory: .nano_agent/skills

cache:
  enabled: true
  ttl_seconds: 300
  cacheable_tools: [file_read, file_search, shell_execute]
  excluded_tools: [file_write, memorize, forget]
  max_cache_size: 100
  persist: false             # 是否持久化到磁盘
  persist_dir: .nano_agent/cache
  warmup_on_restore: true    # 会话恢复时预热缓存
  mtime_invalidation: true   # 基于文件修改时间失效

offload:
  enabled: true
  size_threshold_tokens: 1000  # 超过此 token 数触发卸载
  offload_dir: /tmp/nano_agent_offload
  auto_cleanup: true
  summary_max_tokens: 200
  excluded_tools: [memorize, recall]

semantic_compressor:
  enabled: false               # 默认关闭，需 embedding 服务
  similarity_threshold: 0.85   # 相似度阈值
  min_messages_to_compress: 8  # 最少消息数触发
  provider: ollama             # ollama / sentence-transformers / openai
  embedding_model: nomic-embed-text
  cache_embeddings: true
  merge_tag: "[merged {n} similar]"

rate_limiter:
  enabled: true                # 启用速率限制
  requests_per_minute: 60      # 每分钟最大请求数
  burst: 10                    # 令牌桶容量（允许突发请求数）

sanitizer:
  enabled: true                # 启用输入净化
  injection_patterns: null     # 使用默认 18 条注入检测正则
  custom_patterns: []          # 自定义注入检测正则
  max_input_length: 10000      # 输入最大字符长度
  length_action: truncate      # 超长处理方式：truncate / reject
  reject_null_bytes: true      # 拒绝含 null 字节的输入
  reject_control_chars: true   # 剥离控制字符
  pii_enabled: false           # 启用 PII 脱敏
  pii_mask_mode: partial       # 遮蔽模式：partial / full
  pii_mask_char: "*"           # 遮蔽字符
  pii_types:                   # 启用的 PII 类型
    - phone
    - id_card
    - email
    - api_key

harmful_content_filter:
  enabled: false                     # 启用有害内容过滤（默认关闭）
  categories:                        # 启用的检测类别
    - violence
    - hate
    - dangerous
    - illegal
  default_action: block              # 默认动作：block / warn / replace
  category_actions: {}               # 按类别覆盖动作
  replacement_text: "[Content removed for safety]"  # replace 动作的替换文本
  custom_patterns: []                # 自定义有害内容模式

result_validator:
  enabled: false                     # 启用结果正确性验证（默认关闭）
  checks:                           # 启用的验证检查类型
    - file_exists
    - code_syntax
    - command_success
  on_fail: annotate                  # 失败时动作：block / warn / annotate
  on_pass: silent                    # 通过时动作：silent / annotate
  custom_validators: []              # 自定义验证器函数列表
```

### ConfigLoader

```python
from nano_agent.config.loader import ConfigLoader

# 加载默认配置
config = ConfigLoader.load()

# 从文件加载
config = ConfigLoader.load("config.yaml")
```

### 配置对象

```python
config.llm.provider      # LLM 提供商
config.llm.model         # 模型名称
config.llm.get_context_length()  # 获取上下文长度

config.agent.max_iterations
config.memory.type
config.skills.directory
```

---

## CLI 使用

### 命令行参数

```bash
nano-agent [选项]
```

| 参数 | 说明 |
|------|------|
| `-c, --config` | 配置文件路径 |
| `-m, --model` | 覆盖模型名称 |
| `-r, --resume` | 恢复会话 |
| `-n, --new-session` | 创建新会话 |
| `--list-sessions` | 列出所有会话 |
| `--show-session` | 显示会话内容 |
| `--non-interactive` | 非交互模式 |
| `-q, --quiet` | 安静模式 |

### 交互命令

在交互模式中：

**基本操作**

| 命令 | 说明 |
|------|------|
| `/exit` / `/quit` | 退出（保存摘要） |
| `exit` / `quit` | 直接退出 |
| `/clear` | 清空对话 |
| `/?` / `help` | 显示帮助 |

**查看信息**

| 命令 | 说明 |
|------|------|
| `/config` | 查看配置 |
| `/memory` | 查看记忆状态 |
| `/stats` | 查看统计 |
| `/tools` | 查看工具列表 |
| `/skills` | 查看技能列表 |
| `/sessions` | 查看会话列表 |
| `/auto` | 熔断器恢复 AUTO 模式 |

**项目管理**

| 命令 | 说明 |
|------|------|
| `/init` | 初始化项目 |
| `/config init` | 生成配置文件（合并） |
| `/config init -f` | 强制覆盖配置文件 |
| `/memory on` | 启用长期记忆 |
| `/memory off` | 禁用长期记忆 |
| `/stats on` | 启用统计自动显示 |
| `/stats off` | 禁用统计自动显示 |

**个性化设置**

| 命令 | 说明 |
|------|------|
| `/setname` | 查看当前名字 |
| `/setname <用户名>` | 设置用户名 |
| `/setname user <用户名>` | 设置用户名 |
| `/setname agent <Agent名>` | 设置 Agent 名 |
| `/setname <用户名> <Agent名>` | 同时设置两个 |

**技能管理**

| 命令 | 说明 |
|------|------|
| `/skill reload <n>` | 重载技能 |
| `/skill unload <n>` | 卸载技能 |

**导出**

| 命令 | 说明 |
|------|------|
| `/report` | 导出监控报告 |

### 示例

```bash
# 交互模式
nano-agent

# 指定模型
nano-agent -m gpt-4o

# 恢复会话
nano-agent --resume session_abc123

# 非交互模式
echo "列出当前目录文件" | nano-agent --non-interactive
```

### Slash Command 输出格式规范

所有内置 slash command 的输出遵循以下统一格式：

**标题区**

```
==================================================
📊 标题（中文）
==================================================
```

- 分隔线：ASCII `"=" * 50`
- 标题：中文 + 📊 emoji 前缀
- 上下各一条分隔线

**子标题**

```
## 子标题（中文）
```

- 使用 `## ` Markdown 风格，中文

**结束区**

```
==================================================
```

- 单条分隔线 + 换行：`print("=" * 50 + "\n")`

**表格分隔线**

- 使用 ASCII `"-" * N`（N 根据内容宽度调整）
- 不使用 Unicode 字符（─、━ 等）

**键值对**

```
  键名:    值
```

- 左对齐标签，使用 `format_line()` 处理宽度

---

## 扩展开发

### 创建自定义工具

```python
from nano_agent.tools.base import BaseTool, ToolResult

class WeatherTool(BaseTool):
    name = "get_weather"
    description = "获取指定城市的天气信息"

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称"
                }
            },
            "required": ["city"]
        }

    def execute(self, city: str) -> ToolResult:
        # 实现天气查询逻辑
        weather = f"{city} 今天晴，温度 25°C"
        return ToolResult(success=True, output=weather)

# 注册工具
from nano_agent.tools.builtin import register_builtin_tools
from nano_agent.tools.base import ToolRegistry

registry = ToolRegistry()
register_builtin_tools(registry)
registry.register(WeatherTool())
```

### 创建技能包

创建 YAML 文件 `.nano_agent/skills/my_skill.yaml`:

```yaml
name: my_skill
description: 我的自定义技能包
system_prompt: |
  你是一个专门的助手，擅长...
  
tools:
  - my_custom_tool

enabled: true
```

---

## 版本历史

| 版本 | 主要功能 |
|------|---------|
| v0.8.7 | 结果正确性验证（`ResultValidatorConfig`、`ResultValidator`、`ValidationCheck`、`ValidationResult`、`summarize_validation_checks`、file_exists/code_syntax/command_success 三类检查、block/warn/annotate 三级动作） |
| v0.8.9 | 反馈闭环（`FeedbackLoopConfig`、`FeedbackLoop`、`DeviationFeedbackResult`、`SelfCorrectionResult`、偏差信号回流、自纠正循环、DEVIATION_FEEDBACK/SELF_CORRECTION 事件、SELF_CORRECTION_EXHAUSTED 终止原因） |
| v0.8.6 | 有害内容过滤（`HarmfulContentFilter`、`HarmfulContentFilterConfig`、`HarmfulMatch`、`HarmfulFilterResult`、`summarize_harmful_matches`、`HarmfulContentMiddleware`、4 类检测、block/warn/replace 三级动作） |
| v0.8.5 | 输出护栏（`OutputGuardConfig`、`OutputGuard`、`SensitiveMatch`、`OutputGuardResult`、敏感信息拦截） |
| v0.8.4 | PII 脱敏（`PIIDesensitizer`、`PIIMatch`、`summarize_pii_matches`、phone/id_card/email/api_key 检测、partial/full 遮蔽、重叠处理） |
| v0.8.3 | 输入净化器（`SanitizerConfig`、`InputSanitizer`、prompt injection 检测、格式验证、编排层硬门控） |
| v0.8.1 | 速率限制（`RateLimiterConfig`、令牌桶算法、`rate_limiter→retry→_chat_impl` 三层调用链） |
| v0.8.0 | 指数退避重试（`RetryConfig`、`with_retry`、`is_retryable_error`、`BaseLLM.chat→_chat_impl` 模式） |
| v0.7.19 | 语义压缩（`SemanticCompressor`、`SemanticCompressorConfig`、`BaseEmbeddingClient`、Ollama/sentence-transformers/OpenAI embedding） |
| v0.7.18 | 估算审计与准确性增强（`EstimationAudit`、`effective_token_estimate`、`/stats estimation`、偏差告警） |
| v0.7.16 | 复杂度预算 Profile 与 Stall Detection（`RoutingResult.suggested_budget_ratio`、`TokenBudget.set_budget_ratio`、`StallDetector`、`StallConfig`、`AgentEvent.STALL_DETECTED`） |
| v0.7.15 | 激进输出精简与工具输出标准化（`AggressiveOutputConfig`、`OutputSimplifier`、`StandardToolOutput`、`OutputFormat`） |
| v0.7.14 | 预判机制（`QueryPrejudgment`、`PrejudgmentResult`、两级路由：规则优先 + LLM 补充） |
| v0.7.13 | 统一截断比率与校准闭环（`calculate_max_chars`、`calibration_factor` 参数、`CalibrationData`） |
| v0.7.12 | 决策点真实 Token（`last_prompt_tokens` 参数、偏差日志） |
| v0.7.11 | 模型上下文窗口准确性（API 查询 + fallback 链） |
| v0.7.10 | 柔化硬限制（TerminationReason、智能重复检测、预算收尾轮） |
| v0.5.0 | PyPI 发布准备，API 文档 |
| v0.4.1 | WebSearchTool 工具 |
| v0.4.0 | 运行监控（Token 统计、上下文使用率） |
| v0.3.0 | 技能包机制，热加载 |
| v0.2.0 | 持久化记忆，会话管理 |
| v0.1.0 | ReAct 模式，基础工具 |

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [constraints.md](constraints.md) | 资源约束与限制参考 — 所有硬限制/软限制、默认值、交互关系 |
| [architecture.md](architecture.md) | 系统架构设计 |
| [tutorial.md](tutorial.md) | 使用教程 |
| [plugins.md](plugins.md) | 插件开发指南 |
| [testing.md](testing.md) | 测试指南 |