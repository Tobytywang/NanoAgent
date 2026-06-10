# NanoAgent 使用教程

本教程将帮助你快速上手 NanoAgent 框架。

## 目录

1. [快速开始](#1-快速开始)
2. [基础使用](#2-基础使用)
3. [配置详解](#3-配置详解)
4. [工具系统](#4-工具系统)
5. [记忆系统](#5-记忆系统)
6. [技能包](#6-技能包)
7. [个性化设置](#7-个性化设置)
8. [运行监控](#8-运行监控)
9. [高级用法](#9-高级用法)

---

## 1. 快速开始

### 1.1 安装

```bash
# 从 PyPI 安装
pip install nano-agent

# 或从源码安装
git clone https://github.com/Tobytywang/NanoAgent.git
cd NanoAgent
pip install -e ".[dev]"
```

### 1.2 准备 LLM

**方式一：使用 Ollama 本地模型（推荐）**

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull qwen2.5:7b

# 启动服务
ollama serve
```

**方式二：使用在线 API**

支持 OpenAI、DeepSeek、Moonshot 等 OpenAI 兼容 API。

### 1.3 第一个 Agent

```bash
# 启动交互式 Agent
nano-agent
```

```
> 你好，请帮我列出当前目录的文件

[Agent 思考中...]
[Tool Call] shell_execute({"command": "ls -la"})
[Observe] total 16
drwxr-xr-x  4 user  staff  128 May  4 10:00 .
...

当前目录包含以下文件：
- README.md
- pyproject.toml
- nano_agent/
- tests/

📊 本轮:   1500 tokens |   2.50s | LLM调用:   1 | 迭代: 1 | 工具: ✓shell_execute
📊 总计:   1500 tokens |   2.50s | LLM调用:   1 | 上下文: 1.2% (1500/128000)
```

---

## 2. 基础使用

### 2.1 代码中使用

```python
from nano_agent.llm import create_llm
from nano_agent.memory import ShortTermMemory
from nano_agent.agent.react import ReActAgent
from nano_agent.tools.base import ToolRegistry
from nano_agent.tools.builtin import register_builtin_tools

# 创建 LLM 客户端
llm = create_llm(
    provider="ollama",
    model="qwen2.5:7b"
)

# 创建记忆系统
memory = ShortTermMemory(max_messages=50)

# 创建工具注册表
tool_registry = ToolRegistry()
register_builtin_tools(tool_registry)

# 创建 Agent
agent = ReActAgent(
    llm=llm,
    memory=memory,
    tool_registry=tool_registry,
    max_iterations=10,
    verbose=True
)

# 运行
response = agent.run("帮我创建一个 hello.txt 文件，内容是 'Hello World'")
print(response)
```

### 2.2 使用在线 API

```python
from nano_agent.llm import create_llm

# OpenAI
llm = create_llm(
    provider="openai",
    api_key="sk-..."
)

# DeepSeek
llm = create_llm(
    provider="deepseek",
    api_key="sk-..."
)

# 自定义 API
llm = create_llm(
    provider="openai_compatible",
    model="custom-model",
    base_url="https://api.example.com/v1",
    api_key="your-api-key"
)
```

### 2.3 使用配置文件

```python
from nano_agent.cli.main import create_agent

# 从配置文件创建 Agent
agent = create_agent("~/.nano_agent/config.yaml")
response = agent.run("你好")
```

---

## 3. 配置详解

### 3.1 完整配置示例

```yaml
# .nano_agent/config.yaml

# LLM 设置
llm:
  provider: ollama                    # ollama / openai / deepseek / moonshot / openai_compatible
  model: qwen2.5:7b                   # 模型名称
  base_url: http://localhost:11434    # API 地址
  api_key: null                       # API Key（可省略）
  api_key_env: OPENAI_API_KEY         # 环境变量名
  timeout: 120                        # 超时时间（秒）
  temperature: 0.7                    # 温度参数
  context_length: null                # 上下文长度（null=自动检测）

# Agent 设置
agent:
  max_iterations: 10                  # 最大推理轮数
  verbose: true                       # 显示详细过程
  system_prompt: |                    # 自定义系统提示
    You are a helpful AI assistant.

# 记忆设置
memory:
  type: hybrid                        # short_term / persistent / hybrid
  max_messages: 50                    # 最大消息数
  storage_path: .nano_agent/memory    # 存储路径
  long_term_storage_path: .nano_agent/long_term_memory
  auto_extract: true                  # 自动提取重要信息

# 工具设置
tools:
  enabled: [all]                      # 启用的工具
  disabled: []                        # 禁用的工具

# 技能包设置
skills:
  enabled: []                         # 启用的技能包
  directory: .nano_agent/skills       # 技能包目录

# 输入净化设置
sanitizer:
  enabled: true                       # 启用输入净化（prompt injection 防护）
  max_input_length: 10000             # 输入最大字符长度
  length_action: truncate             # 超长处理方式：truncate / reject
  reject_null_bytes: true             # 拒绝含 null 字节的输入
  reject_control_chars: true          # 剥离控制字符
  custom_patterns: []                 # 自定义注入检测正则
  pii_enabled: false                  # 启用 PII 脱敏（phone/id_card/email/api_key）
  pii_mask_mode: partial              # 遮蔽模式：partial（保留首尾）/ full（全遮蔽）
  pii_mask_char: "*"                  # 遮蔽字符
  pii_types:                          # 启用的 PII 检测类型
    - phone
    - id_card
    - email
    - api_key
```

### 3.2 不同 LLM 配置

**Ollama 本地模型**：
```yaml
llm:
  provider: ollama
  model: qwen2.5:7b
  base_url: http://localhost:11434
```

**OpenAI**：
```yaml
llm:
  provider: openai
  model: gpt-4o
  api_key_env: OPENAI_API_KEY
```

**DeepSeek**：
```yaml
llm:
  provider: deepseek
  model: deepseek-chat
  api_key_env: DEEPSEEK_API_KEY
```

**自定义 API**：
```yaml
llm:
  provider: openai_compatible
  model: custom-model
  base_url: https://api.example.com/v1
  api_key_env: CUSTOM_API_KEY
```

---

## 4. 工具系统

### 4.1 内置工具

| 工具 | 功能 | 示例 |
|------|------|------|
| `python_execute` | 执行 Python 代码 | 计算数学问题、处理数据 |
| `file_read` | 读取文件 | 查看文件内容 |
| `file_write` | 写入文件 | 创建、修改文件 |
| `file_search` | 搜索文件 | 查找特定文件 |
| `shell_execute` | 执行 Shell 命令 | 系统操作 |
| `web_search` | 网络搜索 | 获取实时信息 |
| `memorize` | 存储长期记忆 | 记住用户偏好 |
| `recall` | 检索长期记忆 | 回忆之前的信息 |
| `get_stats` | 获取运行统计 | 查看 token 消耗 |

### 4.2 创建自定义工具

```python
from nano_agent.tools.base import BaseTool, ToolResult

class WeatherTool(BaseTool):
    """天气查询工具"""
    
    name = "get_weather"
    description = "获取指定城市的天气信息。当用户询问天气时使用此工具。"
    
    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如：北京、上海"
                }
            },
            "required": ["city"]
        }
    
    def execute(self, city: str) -> ToolResult:
        # 这里实现实际的天气查询逻辑
        # 示例：模拟返回天气信息
        weather_data = {
            "北京": "晴，温度 25°C，空气质量良好",
            "上海": "多云，温度 28°C，有轻微雾霾",
            "广州": "小雨，温度 30°C，湿度较高"
        }
        
        result = weather_data.get(city, f"未找到 {city} 的天气信息")
        return ToolResult(success=True, output=result)

# 注册工具
from nano_agent.tools.base import ToolRegistry

registry = ToolRegistry()
registry.register(WeatherTool())
```

### 4.3 动态添加工具

```python
# 在运行时添加工具
agent.add_tool(WeatherTool())

# 验证工具已添加
print("weather" in agent.tool_registry.list_tools())  # True
```

---

## 5. 记忆系统

### 5.1 记忆类型

**ShortTermMemory** - 短期记忆
```python
from nano_agent.memory import ShortTermMemory

memory = ShortTermMemory(
    max_messages=50,
    system_prompt="You are a helpful assistant."
)
```

**PersistentMemory** - 持久化记忆
```python
from nano_agent.memory import PersistentMemory, FileStorage

storage = FileStorage(base_dir=".nano_agent/memory")
memory = PersistentMemory(
    storage=storage,
    session_id="my_session",
    max_messages=50
)

# 会话管理
memory.new_session()              # 创建新会话
memory.load_session("session_id") # 恢复会话
memory.list_sessions()            # 列出所有会话
```

**HybridMemory** - 混合记忆
```python
from nano_agent.memory import HybridMemory, PersistentMemory, LongTermMemory, FileStorage

# 工作记忆
working_memory = PersistentMemory(
    storage=FileStorage(base_dir=".nano_agent/memory"),
    session_id="session_001"
)

# 长期记忆
long_term_memory = LongTermMemory(
    storage_path=".nano_agent/long_term"
)

# 混合记忆
memory = HybridMemory(
    working_memory=working_memory,
    long_term_memory=long_term_memory,
    auto_extract=True  # 自动提取重要信息
)
```

### 5.2 长期记忆操作

```python
# 存储信息
entry_id = memory.memorize(
    content="用户喜欢使用 Python 进行数据分析",
    category="preference",  # fact / preference / experience / task / note
    importance=0.8          # 重要性 0-1
)

# 检索信息
results = memory.recall("编程语言偏好", limit=5)
for entry in results:
    print(f"- {entry.content} (重要性: {entry.importance})")

# 列出所有长期记忆
all_memories = memory.get_all_long_term()

# 删除记忆
memory.forget(entry_id)
```

### 5.3 会话管理

```bash
# CLI 中管理会话
nano-agent --list-sessions           # 列出所有会话
nano-agent --resume session_abc123    # 恢复会话
nano-agent --new-session              # 创建新会话
nano-agent --show-session session_id  # 查看会话内容
```

---

## 6. 技能包

### 6.1 什么是技能包

技能包是一组预定义的能力，包括：
- 系统提示（告诉 Agent 如何处理特定任务）
- 需要的工具
- 可选的知识库

### 6.2 创建技能包

创建文件 `.nano_agent/skills/coding.yaml`:

```yaml
name: coding
description: 编程助手技能包
system_prompt: |
  你是一个专业的编程助手。
  
  在编写代码时：
  1. 遵循最佳实践和代码规范
  2. 添加必要的注释
  3. 考虑错误处理
  4. 提供清晰的解释
  
  支持的语言：Python, JavaScript, Go, Rust

tools:
  - python_execute
  - file_read
  - file_write
  - shell_execute

enabled: true
```

### 6.3 技能包热加载

在交互模式中：

```
> skills
Loaded skills (1):
  coding <- .nano_agent/skills/coding.yaml

> skill reload coding
Skill 'coding' reloaded successfully

> skill unload coding
Skill 'coding' unloaded successfully
```

---

## 7. 个性化设置

### 7.1 设置用户名和 Agent 名

你可以自定义对话中显示的用户名和 Agent 名：

```
> /setname
当前设置: 用户名=User, Agent名=Agent

> /setname 天宇
用户名已更新: 天宇

> /setname agent Nano
Agent名已更新: Nano

> /setname 天宇 Nano
名字已更新: 用户=天宇, Agent=Nano
```

### 7.2 自动名字识别

当你告诉 Agent 你的名字时，Agent 会自动识别并更新显示：

```
[User] [/path/to/project]:
> 我的名字是天宇

[Agent]:
好的，我会记住你的名字是天宇。
名字已更新: user name = 天宇

[天宇] [/path/to/project]:
> 你好
```

Agent 支持识别以下表达方式：
- 用户名：`我的名字是...`、`我叫...`、`用户名是...`
- Agent 名：`你的名字是...`、`你叫...`、`Agent名是...`

### 7.3 配置文件设置

你也可以在配置文件中直接设置：

```yaml
agent:
  user_name: 天宇
  agent_name: Nano
```

---

## 8. 运行监控

NanoAgent 提供三个层次的 Token 消耗监控：

| 命令 | 说明 |
|------|------|
| `/stats` | 会话级累计统计 |
| `/usage` | 每次请求的 Token 明细 |
| `/context` | 下次请求的预算分析 |

### 8.1 监控输出

每次 Agent 回复后会显示统计信息：

```
📊 本轮:   1500 tokens |   2.50s | LLM调用:   2 | 迭代: 2 | 工具: ✓web_search, ✓file_read
📊 总计:  15000 tokens |  45.20s | LLM调用:  12 | 上下文: 11.7% (15000/128000)
```

**指标说明**：
- **tokens**: Token 消耗量
- **LLM调用**: API 调用次数（计费相关）
- **迭代**: ReAct 循环次数
- **上下文**: 上下文使用率，超过 80% 会警告

### 8.2 会话统计 `/stats`

```
> /stats

==================================================
📊 会话消耗统计
==================================================

## 累计消耗
  总 Token:      15000
  总 LLM 用:    12
  总迭代次数:    8
  总轮次:        3

## 工具调用
  总调用:        5
  成功:          5
  失败:          0

## 命令
  /stats        - 显示会话消耗统计
  /stats on     - 启用每次对话后自动显示
  /stats off    - 禁用自动显示
  /usage        - 显示上下文消息组成
  /context      - 显示上下文预算分析

==================================================
```

### 8.3 Token 消耗明细 `/usage`

```
> /usage

==================================================
📊 Token 消耗详情
==================================================

## 迭代明细
  ID   轮次  迭代  工具[*]   系统[*]   技能[*]   摘要[*]   消息[*]   输入    输出(工具)[*] 输出[*]   总和    简要描述
  ---------------------------------------------------------------------------------------------------------
  1    1     1     1487      306       -         -         5         1798    22            -         1820    [用户] 你好
  2          2     1487      306       -         -         86        1879    -             206       2085    [回答] ...
  ---------------------------------------------------------------------------------------------------------
  [*] 表示按字符长度比例估算
  - 表示该值为 0

## 总计
  输入:        3677
  输出(工具):  22
  输出:        206
  总和:        3905

==================================================
```

**列说明**：
- **工具[*]**: 工具定义 schema 的 Token
- **系统[*]**: 系统提示词 Token
- **技能[*]**: Skills 提示 Token
- **摘要[*]**: 历史摘要 Token（压缩生成）
- **消息[*]**: 对话消息 Token
- **输入**: API 返回的 prompt_tokens（准确值）
- **输出(工具)[*]**: tool_calls 参数 Token
- **输出[*]**: content 文本 Token

### 8.4 上下文预算 `/context`

```
> /context

==================================================
📊 上下文预算分析
==================================================

## Token 组成
  工具定义:    1487
  系统提示:    306
  技能提示:    -
  摘要:        -
  对话消息:    2228
  总计:        4021

## 占比分布 (限制: 128000)
  [█▓▒·····································] 3.1%
    █ 工具定义: 1.2%
    ▓ 系统提示: 0.2%
    ▒ 对话消息: 1.7%
    · 剩余: 96.9%

==================================================
```

`/context` 显示的是**下一次请求会发送的内容**，包括：
- 工具定义：每次请求都会发送
- 系统提示：固定部分
- 对话消息：历史消息 + LLM 回复

### 8.5 控制统计显示

```
> /stats off
Auto stats display disabled!
Use /stats to view statistics manually.

> /stats on
Auto stats display enabled!
Statistics will be shown after each run.
```

### 7.4 代码中获取统计

```python
from nano_agent.monitoring import MetricsTracker

# 创建 tracker
tracker = MetricsTracker()

# 创建 Agent 时传入
agent = ReActAgent(
    llm=llm,
    memory=memory,
    tool_registry=tools,
    tracker=tracker
)

# 运行后获取统计
response = agent.run("你好")
summary = tracker.get_summary()
session_summary = tracker.get_session_summary()

print(f"Token 消耗: {session_summary['total_tokens']}")
print(f"LLM 调用: {session_summary['total_llm_calls']}")
```

### 8.6 熔断器与执行模式

当 Agent 检测到异常行为（LLM 响应过大、重复工具调用、执行停滞），会自动从 AUTO 模式降级到 SUPERVISED 模式，要求用户确认每个工具调用。

输入 `/auto` 可手动恢复 AUTO 模式：

```
> /auto
[熔断器] 已恢复 AUTO 模式
```

**配置**：

```yaml
smart_optimization:
  circuit_breaker:
    enabled: true
    max_response_tokens: 8000     # LLM 单次响应上限
    duplicate_trigger_count: 3    # 重复调用触发次数
    stall_trigger_count: 3        # 停滞触发次数
    auto_reset_on_user_confirm: true  # 确认后自动恢复 AUTO
```

---

## 9. 高级用法

### 9.1 自定义 Agent 行为

```python
# 自定义系统提示
from nano_agent.memory import ShortTermMemory

memory = ShortTermMemory(
    system_prompt="""
    你是一个专业的数据分析师。
    
    在分析数据时：
    1. 先理解数据结构
    2. 提出分析思路
    3. 使用 Python 进行分析
    4. 给出清晰的结论
    
    可用工具：python_execute, file_read, file_write
    """
)
```

### 9.2 限制工具使用

```python
from nano_agent.tools.base import ToolRegistry
from nano_agent.tools.python_executor import PythonExecutorTool
from nano_agent.tools.file_ops import FileReadTool, FileWriteTool

# 只注册特定工具
registry = ToolRegistry()
registry.register(PythonExecutorTool())
registry.register(FileReadTool())
registry.register(FileWriteTool())
# 不注册 shell_execute，限制系统命令执行
```

### 9.3 流式响应

```python
# 流式获取响应
for chunk in agent.run_stream("请写一个快速排序算法"):
    print(chunk, end="", flush=True)
```

### 9.4 错误处理

```python
from nano_agent.tools.base import ToolResult

class SafeFileReadTool(BaseTool):
    name = "safe_file_read"
    description = "安全读取文件"
    
    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        }
    
    def execute(self, path: str) -> ToolResult:
        try:
            # 限制只能读取特定目录
            if not path.startswith("/safe/directory/"):
                return ToolResult(
                    success=False,
                    error="只能读取 /safe/directory/ 目录下的文件"
                )
            
            with open(path, 'r') as f:
                content = f.read()
            return ToolResult(success=True, output=content)
            
        except FileNotFoundError:
            return ToolResult(success=False, error=f"文件不存在: {path}")
        except PermissionError:
            return ToolResult(success=False, error=f"无权限读取: {path}")
        except Exception as e:
            return ToolResult(success=False, error=f"读取失败: {str(e)}")
```

### 9.5 多 Agent 协作示例

```python
from nano_agent.agent.react import ReActAgent
from nano_agent.llm import create_llm
from nano_agent.memory import ShortTermMemory
from nano_agent.tools.base import ToolRegistry

# 创建专门的代码审查 Agent
code_reviewer = ReActAgent(
    llm=create_llm(provider="ollama", model="qwen2.5:7b"),
    memory=ShortTermMemory(system_prompt="你是代码审查专家..."),
    tool_registry=ToolRegistry(),
    max_iterations=5
)

# 创建专门的测试 Agent
tester = ReActAgent(
    llm=create_llm(provider="ollama", model="qwen2.5:7b"),
    memory=ShortTermMemory(system_prompt="你是测试专家..."),
    tool_registry=ToolRegistry(),
    max_iterations=5
)

# 协作流程
code = "def hello(): print('hello')"
review_result = code_reviewer.run(f"请审查这段代码：{code}")
test_result = tester.run(f"请为这段代码编写测试：{code}")
```

---

## 常见问题

### Q: 如何选择 LLM？

**本地开发**：推荐 Ollama + qwen2.5:7b 或 llama3
**生产环境**：推荐 DeepSeek（性价比高）或 OpenAI GPT-4o

### Q: Token 消耗太快怎么办？

1. 使用 `max_messages` 限制上下文长度
2. 选择较小的模型
3. 使用 HybridMemory 自动管理记忆

### Q: 如何保护敏感操作？

1. 不注册 `shell_execute` 工具
2. 自定义工具添加权限检查
3. 使用环境变量管理 API Key
4. 启用输入净化器（`sanitizer.enabled: true`），自动过滤 prompt injection 模式和异常格式输入
5. 启用 PII 脱敏（`sanitizer.pii_enabled: true`），自动遮蔽手机号、身份证号、邮箱、API Key 等敏感信息

### Q: Agent 陷入循环怎么办？

1. Stall Detection 默认启用（`stall_detection_enabled: True`），连续 3 次相似迭代会自动注入转向提示
2. 调整 `stall_patience` 控制触发阈值（默认 3）
3. 调整 `max_iterations` 参数限制最大迭代次数（默认 10）
4. 使用 `duplicate_threshold` 控制重复调用检测（默认 3）
5. 熔断器检测到异常（重复调用/停滞/响应过大）会自动降级为 SUPERVISED 模式，每个工具调用需确认

### Q: 配置文件中 null 值如何处理？

YAML 中 `key: null` 表示显式设为 null，会使用字段的默认值。如果字段无默认值，则传入 `None`。省略 key 与设为 `null` 行为一致。

---

## 下一步

- 阅读 [API 文档](api.md) 了解详细接口
- 查看 [ROADMAP](../ROADMAP.md) 了解开发计划
- 访问 [GitHub Issues](https://github.com/Tobytywang/NanoAgent/issues) 反馈问题