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

skills:
  enabled: []
  directory: .nano_agent/skills
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
| v0.5.0 | PyPI 发布准备，API 文档 |
| v0.4.1 | WebSearchTool 工具 |
| v0.4.0 | 运行监控（Token 统计、上下文使用率） |
| v0.3.0 | 技能包机制，热加载 |
| v0.2.0 | 持久化记忆，会话管理 |
| v0.1.0 | ReAct 模式，基础工具 |