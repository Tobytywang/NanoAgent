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