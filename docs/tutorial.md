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
9. [安全防护](#9-安全防护)
10. [状态快照](#10-状态快照)
11. [高级用法](#11-高级用法)

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

# 输出护栏设置
output_guard:
  enabled: true                       # 启用输出护栏（敏感信息拦截）
  action: mask                        # 拦截动作：mask（遮蔽）/ block（拦截）/ warn（警告）
  mask_mode: partial                  # 遮蔽模式：partial / full
  mask_char: "*"                      # 遮蔽字符
  sensitive_types:                    # 启用的敏感类型
    - api_key
    - password
    - private_key
    - connection_string
    - phone
    - id_card
    - email
  block_severity:                     # 强制拦截的类型（即使 action 为 mask）
    - private_key
  custom_patterns: []                 # 自定义检测模式

# 有害内容过滤设置
harmful_content_filter:
  enabled: false                      # 启用有害内容过滤（默认关闭）
  categories:                         # 启用的检测类别
    - violence
    - hate
    - dangerous
    - illegal
  default_action: block               # 默认动作：block / warn / replace
  category_actions: {}                # 按类别覆盖动作
  replacement_text: "[Content removed for safety]"
  custom_patterns: []                 # 自定义有害内容模式

# 结果正确性验证设置
result_validator:
  enabled: false                      # 启用结果正确性验证（默认关闭）
  checks:                             # 启用的验证检查类型
    - file_exists                     # 验证声称创建的文件是否存在
    - code_syntax                     # 验证声称正确的代码语法
    - command_success                 # 验证声称成功的命令结果
  on_fail: annotate                   # 失败时动作：block / warn / annotate
  on_pass: silent                     # 通过时动作：silent / annotate
  custom_validators: []               # 自定义验证器函数列表

# 反馈闭环设置
feedback_loop:
  deviation_feedback_enabled: true    # 偏差信号回流（Token 估算偏差过高时提示 LLM）
  deviation_feedback_threshold: 0.50  # 触发回流的偏差阈值
  deviation_feedback_cooldown: 3      # 每 N 次警告注入 1 次提示
  deviation_feedback_hint_injection: true  # 注入提示到 LLM 上下文
  self_correction_enabled: true       # 自纠正循环（验证失败时重试）
  self_correction_max_attempts: 2     # 最大纠正尝试次数

# 工具资源限制设置
tool_resource_limiter:
  enabled: true                       # 主开关
  timeout_enabled: true               # 启用框架级工具超时
  default_timeout: 60                 # 默认超时时间（秒）
  timeout_overrides: {}               # 按工具名覆盖超时
  rate_limit_enabled: true            # 启用工具调用频率限制
  per_tool_calls_per_minute: 30       # 单工具每分钟最大调用次数
  global_calls_per_minute: 60         # 全局每分钟最大工具调用次数

# 记忆衰减与回收设置
memory_gc:
  decay_enabled: true                 # 启用衰减权重计算（长期记忆随时间衰减）
  decay_half_life_days: 30.0          # 衰减半衰期（天），值越大衰减越慢
  dedup_merge_enabled: true           # 启用去重合并标注
  dedup_merge_tag: "[merged {n} similar]"  # 合并标注模板
  gc_enabled: true                    # 启用会话启动 GC（自动清理低权重旧记忆）
  gc_threshold: 0.05                  # 有效权重低于此值的条目被清理
  gc_min_age_days: 7                  # 不清理创建不足此天数的条目
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

## 9. 安全防护

NanoAgent 提供三层安全防护机制，从输入到输出形成完整保护链：

### 9.1 输入净化（sanitizer）

防止 prompt injection 和异常格式输入进入 ReAct 循环：

```yaml
sanitizer:
  enabled: true
  max_input_length: 10000
  length_action: truncate       # truncate / reject
  pii_enabled: true             # 启用 PII 脱敏
  pii_mask_mode: partial        # partial / full
```

### 9.2 输出护栏（output_guard）

防止敏感信息（API Key、密码、私钥等）通过 Agent 响应泄露：

```yaml
output_guard:
  enabled: true
  action: mask                  # mask / block / warn
  mask_mode: partial
  sensitive_types:
    - api_key
    - password
    - private_key
    - connection_string
```

### 9.3 有害内容过滤（harmful_content_filter）

防止有害/危险内容（暴力、仇恨、危险活动、违法内容）触达用户。默认关闭，需显式启用：

```yaml
harmful_content_filter:
  enabled: true                       # 启用有害内容过滤
  categories:                         # 启用的检测类别
    - violence                        # 暴力内容（严重度: high）
    - hate                            # 仇恨言论（严重度: high）
    - dangerous                       # 危险内容（严重度: high）
    - illegal                         # 违法内容（严重度: medium）
  default_action: block               # 默认动作：block / warn / replace
  category_actions:                   # 按类别覆盖动作
    illegal: warn                     # 违法内容仅警告，不拦截
  replacement_text: "[Content removed for safety]"
  custom_patterns: []                 # 自定义有害内容模式
```

**使用场景**：

1. **客服系统**：启用所有类别，`default_action: block`，确保客服回复不包含有害内容
2. **内容创作助手**：启用 violence 和 hate，`default_action: warn`，提醒但不阻止创作
3. **技术文档助手**：仅启用 dangerous（防止黑客教程），其他类别关闭
4. **教育平台**：启用所有类别，illegal 设为 `warn`（允许讨论法律概念但提醒注意）

**三种动作的区别**：

| 动作 | 行为 | 适用场景 |
|------|------|---------|
| `block` | 整个响应被拦截，返回空文本 | 严格环境（客服、教育） |
| `warn` | 响应正常返回，添加 `[Content Warning: ...]` 前缀 | 宽松环境（创作、讨论） |
| `replace` | 有害片段替换为安全文本，非有害部分保留 | 部分过滤（保留上下文） |

**自定义模式示例**：

```yaml
harmful_content_filter:
  enabled: true
  categories:
    - violence
    - dangerous
  custom_patterns:
    # 添加企业特定的有害内容模式
    - category: corporate
      severity: medium
      pattern: "(?i)insider\\s+trading\\s+(?:tips|guide|methods)"
    - category: corporate
      severity: high
      pattern: "(?i)trade\\s+secret\\s+(?:theft|exfiltration)\\s+guide"
```

**防护管线**：输入 → `InputSanitizer` → ReAct 循环 → `OutputGuard` → `HarmfulContentFilter` → `ResultValidator` → 输出

### 9.4 结果正确性验证（result_validator）

验证 Agent 输出中的声明是否与实际结果一致（如声称创建了文件但文件不存在）。默认关闭，需显式启用：

```yaml
result_validator:
  enabled: true                       # 启用结果正确性验证
  checks:                             # 启用的验证检查类型
    - file_exists                     # 验证声称创建的文件是否存在（严重度: high）
    - code_syntax                     # 验证声称正确的代码语法（严重度: medium）
    - command_success                 # 验证声称成功的命令结果（严重度: high/low）
    - schema                          # 验证工具返回值结构是否符合格式 schema（严重度: medium）
  on_fail: annotate                   # 失败时动作：block / warn / annotate
  on_pass: silent                     # 通过时动作：silent / annotate
  custom_validators: []               # 自定义验证器函数列表
```

**使用场景**：

1. **文件操作密集场景**：启用 `file_exists`，确保 Agent 声称创建的文件确实存在
2. **代码生成场景**：启用 `code_syntax`，验证生成的 Python/JSON/YAML 代码语法正确
3. **命令执行场景**：启用 `command_success`，检查 Agent 声称命令成功但实际有错误
4. **高可靠性场景**：启用所有检查 + `on_fail: block`，任何 high-severity 失败都拦截响应

**三种失败动作的区别**：

| 动作 | 行为 | 适用场景 |
|------|------|---------|
| `block` | 仅 high-severity 失败时拦截整个响应 | 严格环境（生产部署） |
| `warn` | 响应正常返回，添加 `[Validation Warning: ...]` 前缀 | 宽松环境（开发调试） |
| `annotate` | 在响应中添加验证标注，标明哪些声明通过/失败 | 默认模式（渐进增强） |

### 9.5 工具资源限制（tool_resource_limiter）

为工具执行提供框架级超时保护和调用频率限制，防止失控工具阻塞 Agent 或工具被过度调用。

**基本配置**（使用默认值）：

```yaml
tool_resource_limiter:
  enabled: true                       # 主开关
  timeout_enabled: true               # 框架级工具超时
  default_timeout: 60                 # 默认超时 60 秒
  rate_limit_enabled: true            # 工具调用频率限制
  per_tool_calls_per_minute: 30       # 单工具每分钟最多 30 次
  global_calls_per_minute: 60         # 全局每分钟最多 60 次
```

**自定义超时覆盖**（为大文件读取或长时间计算调整超时）：

```yaml
tool_resource_limiter:
  enabled: true
  timeout_enabled: true
  default_timeout: 60                 # 默认 60 秒
  timeout_overrides:
    file_read: 120                    # 大文件读取允许 120 秒
    file_search: 90                   # 大项目搜索允许 90 秒
  rate_limit_enabled: true
  per_tool_calls_per_minute: 30
  global_calls_per_minute: 60
```

**禁用频率限制**（仅保留超时保护）：

```yaml
tool_resource_limiter:
  enabled: true
  timeout_enabled: true               # 保留超时保护
  default_timeout: 60
  rate_limit_enabled: false           # 关闭频率限制
```

**完全关闭**（不推荐，工具可能无限阻塞）：

```yaml
tool_resource_limiter:
  enabled: false                      # 关闭所有工具资源限制
```

**工作原理**：

- **框架级超时**：对无内置超时的工具（file_read、file_write、file_search 等）添加超时保护。已有内置超时的工具（shell_execute、python_execute、web_search）自动跳过，避免双重超时
- **调用频率限制**：采用两层令牌桶设计——全局桶限制所有工具总调用频率，单工具桶限制单个工具调用频率。频率超限时非阻塞返回失败结果（不等待），Agent 可在下一轮重试
- **事件通知**：频率超限时触发 `TOOL_RATE_LIMITED` 事件，提示 LLM 更换策略

---

## 10. 状态快照

v0.8.14 引入全局状态快照功能，类似"存档/读档"机制：一键保存 Agent 当前全量状态，随时恢复到任意存档点。

### 10.1 基本用法

在交互模式中使用 `/snapshot` 命令：

```
> /snapshot save before_refactor

[快照] 已保存: before_refactor (snap_a1b2c3d4)
       轮次: 5 | 消息: 12 | Token: 8500

> /snapshot list

==================================================
📊 状态快照
==================================================

## 已保存快照 (2)
  ID                名称               时间               轮次  消息  Token
  -------------------------------------------------------------------
  snap_a1b2c3d4    before_refactor    2026-06-21T10:30   5     12    8500
  snap_e5f6g7h8    auto              2026-06-21T10:25   3     7     4200

==================================================

> /snapshot restore snap_a1b2c3d4

[快照] 已恢复: snap_a1b2c3d4 (before_refactor)
       轮次: 5 | 消息: 12 | Token: 8500

> /snapshot delete snap_e5f6g7h8

[快照] 已删除: snap_e5f6g7h8
```

**命令一览**：

| 命令 | 说明 |
|------|------|
| `/snapshot save [name]` | 保存当前状态快照，name 可选 |
| `/snapshot list` | 列出所有已保存快照 |
| `/snapshot restore <id>` | 恢复到指定快照状态 |
| `/snapshot delete <id>` | 删除指定快照 |
| `/snapshot audit` | 查看审计日志 |
| `/snapshot rollback <audit_id>` | 从审计条目回滚 |

### 10.2 自动快照

启用 `auto_snapshot` 后，每次 `run()` 前自动保存快照（名称为 `auto`），适合高风险操作场景：

```yaml
snapshot:
  enabled: true
  auto_snapshot: true        # 每次 run() 前自动保存
  max_snapshots: 20         # 超出时自动淘汰最旧快照
  snapshot_dir: .nano_agent/snapshots
  audit_log_enabled: true   # 启用审计日志
  audit_log_dir: .nano_agent/snapshots
  max_audit_entries: 500    # 最大审计条目数
  auto_rollback_enabled: false  # 连续失败时自动回滚
  auto_rollback_threshold: 3    # 触发自动回滚的连续失败次数
  auto_rollback_on_failure: error  # 回滚后行为：error / retry
```

### 10.3 恢复机制说明

恢复快照时，`SnapshotManager.restore()` 执行**原位替换**：

- **替换的字段**: 执行状态（round_counter、session_id、total_tokens 等）、撤销栈、工具调用记录、记忆（messages + long_term）、Token 预算、缓存、熔断器状态、重复检测器、停滞检测器、反馈闭环、追踪器、连续失败检测器
- **保持不变的字段**: LLM 客户端实例、ToolRegistry 实例、EventEmitter 实例

这意味着恢复快照后，Agent 继续使用当前的 LLM 和工具集，但对话历史、预算、缓存等状态完全回滚到快照保存时的状态。

### 10.4 审计日志

v0.8.15 引入审计日志功能。每次快照操作（保存、恢复、删除、自动回滚）都会自动记录一条审计条目到 `audit_log.jsonl` 文件，提供 append-only 的操作历史追踪。

使用 `/snapshot audit` 查看审计日志：

```
> /snapshot audit

Audit Log (5 entries):
  audit_a1b2c3 [10:30] save snap_x1y2z3 trigger=manual outcome=success
    reason: Snapshot saved: before_refactor
  audit_d4e5f6 [10:31] save snap_m7n8o9 trigger=auto outcome=success
    reason: Snapshot saved: auto
  audit_g7h8i9 [10:35] restore snap_x1y2z3 trigger=manual outcome=success
    reason: Restored to snapshot: snap_x1y2z3
  audit_j0k1l2 [10:40] delete snap_m7n8o9 trigger=manual outcome=success
    reason: Snapshot deleted: snap_m7n8o9
  audit_p3q4r5 [10:45] auto_rollback snap_x1y2z3 trigger=auto_rollback outcome=success
    reason: Consecutive failures: 3, last tool: shell_execute
```

**审计条目字段**：

| 字段 | 说明 |
|------|------|
| `audit_id` | 审计条目唯一 ID（格式 `audit_{uuid[:8]}`） |
| `operation` | 操作类型：`save` / `restore` / `delete` / `auto_rollback` |
| `snap=` | 关联的快照 ID |
| `trigger` | 触发来源：`manual` / `auto` / `auto_rollback` / `audit_rollback` |
| `outcome` | 操作结果：`success` / `failure` |
| `reason` | 操作原因或备注 |

### 10.5 从审计条目回滚

审计日志中的 `save`、`restore`、`auto_rollback` 操作都关联了快照 ID，可以据此回滚到该快照状态：

```
> /snapshot rollback audit_a1b2c3

Rolled back from audit entry: audit_a1b2c3
```

**使用场景**：

1. 查看审计日志发现某次 `auto_rollback` 回滚到了错误的状态，用 `/snapshot rollback` 回到更早的快照
2. 查看审计日志发现某次手动 `restore` 后状态不对，用 `/snapshot rollback` 回到 restore 之前的快照
3. 审计日志提供了完整的操作历史，便于排查问题

**注意**: `delete` 操作的审计条目不支持回滚（快照已被删除）。

### 10.6 自动回滚

v0.8.15 引入连续失败自动回滚。当工具连续执行失败达到阈值时，自动恢复到最近的快照状态，防止级联故障。

```yaml
snapshot:
  enabled: true
  auto_snapshot: true           # 建议开启，确保有快照可回滚
  auto_rollback_enabled: true   # 启用连续失败自动回滚
  auto_rollback_threshold: 3    # 连续 3 次工具失败触发
  auto_rollback_on_failure: error  # 回滚后行为：error / retry
```

**工作流程**：

1. Agent 执行工具，工具返回失败（`success=False`）
2. `ConsecutiveFailureDetector` 记录失败，计数器递增
3. 连续失败次数达到 `auto_rollback_threshold`（默认 3）
4. `SnapshotManager.attempt_auto_rollback()` 恢复到最近快照
5. 根据 `auto_rollback_on_failure` 决定后续行为：
   - `"error"`（默认）：返回错误，终止当前查询
   - `"retry"`：重新执行当前查询

**配置建议**：

- 开启 `auto_snapshot` 确保每次 `run()` 前有快照可回滚
- `auto_rollback_threshold` 设为 3-5 较合适：太小容易误触发，太大失去保护意义
- 生产环境建议 `auto_rollback_on_failure: error`，避免无限重试循环

---

## 11. 高级用法

### 10.1 自定义 Agent 行为

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

### 10.2 限制工具使用

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

### 10.3 流式执行

v0.9.0 引入流式执行机制。`run_stream()` 返回 `ExecutionHandle`，通过事件生成器实时输出执行过程，允许调用方逐 token 观察 LLM 思考、工具调用和结果。

**基本用法**：

```python
from nano_agent.agent.types import ExecutionEventType, ExecutionHandle

# 流式执行
handle = agent.run_stream("请写一个快速排序算法")

for event in handle.events:
    if event.type == ExecutionEventType.THINK_TEXT and event.text_chunk:
        # 逐 token 输出 LLM 思考文本
        print(event.text_chunk, end="", flush=True)
    elif event.type == ExecutionEventType.TOOL_CALL:
        print(f"\n[调用工具] {event.tool_call}")
    elif event.type == ExecutionEventType.TOOL_RESULT:
        print(f"[工具结果] {event.tool_result}")
    elif event.type == ExecutionEventType.RUN_END:
        # 执行完成，获取最终结果
        print(f"\n完成: {event.result.response}")
```

**取消执行**：

```python
handle = agent.run_stream("长时间运行的任务")

# 在另一个线程或回调中取消
handle.cancel()

# 事件流中会出现 CANCELLED 事件
for event in handle.events:
    if event.type == ExecutionEventType.CANCELLED:
        print("执行已取消")
        break
```

**Guard 短路检测**：

当 guard clause（路由、预判等）提前终止执行时，会产出 `GUARD_SHORT_CIRCUIT` 事件：

```python
for event in handle.events:
    if event.type == ExecutionEventType.GUARD_SHORT_CIRCUIT:
        print(f"被 {event.guard_name} 提前终止")
        print(f"结果: {event.result.response}")
```

**事件类型一览**：

| 事件类型 | 说明 | 关键字段 |
|---------|------|---------|
| `RUN_START` | 执行开始 | `data.input` |
| `THINK_START` | Think 阶段开始 | `data.iteration` |
| `THINK_TEXT` | LLM 流式文本片段 | `text_chunk` |
| `THINK_END` | Think 阶段结束 | `think_result` |
| `TOOL_CALL` | 工具调用 | `tool_call` |
| `TOOL_RESULT` | 工具执行结果 | `tool_result` |
| `GUARD_SHORT_CIRCUIT` | Guard 提前终止 | `guard_name`, `result` |
| `RUN_END` | 执行结束 | `result` |
| `CANCELLED` | 执行被取消 | - |

> **注意**: `run()` 现在是 `run_stream()` 的薄封装，内部消费事件流并返回最终 `ExecutionResult`。如需实时观察执行过程，请使用 `run_stream()`。

### 10.4 错误处理

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

### 10.5 多 Agent 协作示例

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
6. 启用输出护栏（`output_guard.enabled: true`），自动拦截 Agent 响应中的敏感信息泄露
7. 启用有害内容过滤（`harmful_content_filter.enabled: true`），自动拦截或替换暴力、仇恨、危险、违法等有害内容
8. 启用结果正确性验证（`result_validator.enabled: true`），自动验证 Agent 声称创建的文件是否存在、代码语法是否正确、命令是否真正成功

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
- 查看 [架构文档](architecture.md) 了解 guard clause 等设计模式
- 查看 [ROADMAP](../ROADMAP.md) 了解开发计划
- 访问 [GitHub Issues](https://github.com/Tobytywang/NanoAgent/issues) 反馈问题