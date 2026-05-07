# NanoAgent Roadmap

本文档记录 NanoAgent 的开发路线图和增强计划。

## 项目定位

**NanoAgent 是一个纯粹的 Agent 技术底座/框架**：
- 提供通用的 Agent 核心能力
- 不包含特定领域的技能包
- CodingAgent、跑团 Agent 等作为独立项目引用 NanoAgent

```
┌─────────────────────────────────────────────────────┐
│                   独立 Agent 项目                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │CodingAgent  │  │ 跑团Agent   │  │  其他Agent  │  │
│  │ 技能包      │  │  技能包     │  │  技能包     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         └────────────────┼────────────────┘         │
│                          ▼                          │
│              ┌───────────────────────┐              │
│              │     NanoAgent         │              │
│              │   (技术底座/框架)      │              │
│              └───────────────────────┘              │
└─────────────────────────────────────────────────────┘
```

---

## 版本规划

### v0.1.0 ✅

- [x] ReAct 模式实现
- [x] 基础工具系统（文件操作、Shell、Python 执行）
- [x] Ollama 本地 LLM 支持
- [x] OpenAI 兼容 API 支持
- [x] YAML 配置系统
- [x] CLI 交互界面

---

### v0.2.0 - 持久化记忆 ✅

**目标**: 实现跨会话记忆能力，让 Agent 能够记住之前的对话。

**任务列表**:
- [x] 实现 `BaseStorage` 存储抽象接口
- [x] 实现 `FileStorage` JSON 文件存储
- [x] 实现 `PersistentMemory` 持久化记忆
- [x] 扩展配置支持存储后端选择
- [x] 添加会话管理（新建、恢复、列出历史）
- [x] 更新 CLI 支持会话选择

**新增文件**:
```
nano_agent/memory/
├── persistent.py
└── storage/
    ├── __init__.py
    ├── base.py
    └── file_storage.py
```

---

### v0.3.0 - 技能包机制 ✅

**目标**: 提供可扩展的技能包机制，支持外部项目扩展。

**任务列表**:
- [x] 实现 `Skill` 技能包数据结构
- [x] 实现 `SkillRegistry` 技能包注册表
- [x] 支持从 YAML 配置加载技能包
- [x] 实现技能包热加载
- [x] 添加技能包开发文档

**技能包定义**:
```python
@dataclass
class Skill:
    """技能包定义"""
    name: str
    system_prompt: str
    tools: list[BaseTool]
    knowledge: list[dict]  # 可选的知识库
```

**配置示例**:
```yaml
skills:
  enabled:
    - coding
  directory: .nano_agent/skills
```

---

### v0.4.0 - 运行监控 ✅

**目标**: 提供运行时监控和调试能力。

**任务列表**:
- [x] 实现 Token 使用统计
- [x] 实现调用链路追踪
- [x] 实现耗时分析
- [x] 实现上下文使用率显示
- [x] 实现 LLM 调用次数统计
- [x] 添加 `get_stats` 工具供 Agent 查询统计

**新增文件**:
```
nano_agent/monitoring/
├── __init__.py
├── metrics.py      # 数据结构定义
└── tracker.py      # 运行时追踪器

nano_agent/tools/
└── monitoring_tools.py  # get_stats 工具
```

---

### v0.5.0 - 框架完善 ✅

**目标**: 提供完整的框架能力，准备发布。

**任务列表**:
- [x] 调试日志输出（`logger.py`）
  - [x] 可配置日志工具类
  - [x] CLI 初始化日志（根据 config.logging 配置）
  - [x] LLM 层集成日志（记录 tool call 解析错误等）
- [x] 导出运行报告（`reporter.py`, CLI `--report`）
- [x] 插件化工具加载机制（`plugin.py`）
- [x] 多存储后端支持（File/SQLite）
- [x] 完善的 API 文档（`docs/api.md`）
- [x] 使用示例和教程（`docs/tutorial.md`）
- [x] PyPI 发布准备

**新增文件**:
```
nano_agent/monitoring/
├── logger.py           # 可配置日志工具
└── reporter.py         # 报告生成器

nano_agent/memory/storage/
└── sqlite_storage.py   # SQLite 存储后端

nano_agent/tools/
└── plugin.py           # 插件加载机制

docs/
├── api.md              # API 文档
├── tutorial.md         # 使用教程
└── plugins.md          # 插件开发指南

examples/plugins/
└── tool_weather.py     # 插件示例
```

---

### v0.5.1 - 功能优化与增强 ✅

**目标**: 汇总 v0.5.0 之后已实现的功能优化和增强。

**已实现功能**:
- [x] `/init` 命令 - 项目扫描初始化，自动识别项目结构
- [x] `/config` 命令增强 - 支持 `--force` 强制重新生成配置
- [x] `/memory` 命令 - 长期记忆开关控制
- [x] `/stats` 命令增强 - 支持 on/off 切换
- [x] CLI 命令统一 - 所有命令使用 `/` 前缀
- [x] 帮助菜单重构 - 按功能场景分类，更清晰的布局
- [x] CLI 短选项 - `-l` (list-sessions), `-s` (session)
- [x] 可配置名称 - `user_name` 和 `agent_name` 配置支持
- [x] `/setname` 命令 - 运行时动态修改用户/Agent 名称
- [x] 配置文件优先级 - project > global 修复
- [x] 会话管理 CLI - 新增会话管理选项
- [x] 自定义 LLM providers - 支持自定义 base_url
- [x] Undo 机制 - `/undo` 撤销本轮所有操作
- [x] 记忆去重 - 相似条目自动更新而非重复创建
- [x] 会话迁移 - `--migrate-sessions` 从 File 到 SQLite

---

### v0.6.0 - 渐进式执行与 Git 集成

**目标**: 改善 Agent 的交互模式，实现可控的渐进式执行和状态回退能力。

**背景**:
实际使用中发现 Agent 存在以下问题：
1. 一次视图进行过多的开发工作，而不是一步一步慢慢来
2. 做事情之前缺少规划，没有 plan 就直接开整
3. 做事情之前没有征求用户同意，就直接开整
4. 缺少状态管理，尤其是回退功能

**任务列表**:

**渐进式执行与确认**:
- [ ] 前置规划 - 复杂任务先制定计划，展示给用户确认后再执行
- [ ] 渐进式执行 - 一次只做一小步，等待用户确认后继续
- [ ] 用户确认机制 - 关键操作前征求用户同意

**Git 集成与状态回退**:
- [ ] Git 状态检测 - 检测当前是否在 Git 仓库中
- [ ] 自动提交 - 每步操作后自动 commit（可配置）
- [ ] 撤销命令 - `/undo` 回退到上一个状态
- [ ] 回退历史 - 查看可回退的操作历史
- [ ] 分支管理 - 可选的分支隔离功能

**技术方案**:
```python
# 渐进式执行流程
class InteractiveAgent(ReActAgent):
    def run_interactive(self, task: str) -> str:
        # 1. 前置规划
        plan = self.plan(task)
        print(f"计划:\n{plan}")

        # 2. 用户确认计划
        if not self.confirm("是否按此计划执行?"):
            return "已取消"

        # 3. 渐进式执行
        for step in plan.steps:
            print(f"即将执行: {step}")
            if not self.confirm("是否执行此步骤?"):
                return "已取消"
            result = self.execute_step(step)
            # 每步自动提交
            self.git_manager.auto_commit(f"Execute: {step.name}")

        return result

# Git 管理器
class GitManager:
    def auto_commit(self, message: str):
        """自动提交当前更改"""
        if not self.is_git_repo():
            return
        self.repo.index.add(self.get_changed_files())
        self.repo.index.commit(message)

    def undo(self):
        """撤销上一次操作"""
        self.repo.git.reset('--hard', 'HEAD~1')
```

---

### v0.7.0 - 模式切换

**目标**: 支持在 Agent 会话中切换执行模式，提供更灵活的交互方式。

**背景**:
有时用户希望直接执行基础的 shell 命令（如 ls、cat、grep 等），而不需要经过 Agent 的推理过程。模式切换可以让用户在 Agent 模式和直接命令模式之间灵活切换。

**任务列表**:
- [ ] `/mode` 命令 - 切换执行模式（agent/shell）
- [ ] Agent 模式 - 默认模式，通过 Agent 推理执行
- [ ] Shell 模式 - 直接执行 shell 命令，不经过 Agent
- [ ] 模式状态显示 - 在提示符中显示当前模式
- [ ] 模式配置 - 支持配置默认启动模式

**技术方案**:
```python
# 模式定义
class ExecutionMode(Enum):
    AGENT = "agent"      # Agent 推理模式
    SHELL = "shell"      # 直接 shell 模式

# 模式切换
class ModeManager:
    def __init__(self):
        self.mode = ExecutionMode.AGENT

    def switch(self, mode: str):
        self.mode = ExecutionMode(mode)
        print(f"已切换到 {mode} 模式")

    def execute(self, command: str):
        if self.mode == ExecutionMode.SHELL:
            # 直接执行 shell 命令
            return subprocess.run(command, shell=True)
        else:
            # 通过 Agent 推理执行
            return self.agent.run(command)
```

---

### v0.8.0 - Hooks 机制

**目标**: 提供优雅的扩展机制，解耦组件间的依赖。

**背景**:
当前 undo 操作需要返回值传递链条来更新 UI 层变量，不够优雅。Hooks 机制可以让组件间通信更加解耦。

**任务列表**:
- [ ] 定义 `Hooks` 基类和注册机制
- [ ] 在 Agent 中集成 hooks 点位
- [ ] 实现 `on_name_changed` hook 用于名字更新
- [ ] 实现 `on_tool_executed` hook 用于工具执行后回调
- [ ] 实现 `on_memory_changed` hook 用于记忆变更

**技术方案**:
```python
# Hooks 定义
class AgentHooks:
    def on_name_changed(self, name_type: str, old_value: str, new_value: str):
        """名字变更时触发"""
        pass

    def on_tool_executed(self, tool_name: str, result: ToolResult):
        """工具执行后触发"""
        pass

    def on_memory_changed(self, action: str, entry_id: str):
        """记忆变更时触发"""
        pass

# CLI 中注册 hooks
agent.hooks.on_name_changed = lambda t, old, new: update_display(t, new)
```

---

### v0.9.0 - 配置系统优化

**目标**: 简化配置系统维护，新增配置项时自动同步显示和保存。

**任务列表**:
- [ ] 配置自动显示 - `_show_config()` 自动遍历 config 对象字段
- [ ] 配置自动保存 - `_init_config_file()` 自动生成所有配置字段
- [ ] 条件显示支持 - 支持类似 `if config.memory.type == "hybrid"` 的条件逻辑
- [ ] 字段排序控制 - 支持自定义显示顺序

**技术方案**:
```python
# 方案：使用 dataclass 字段元数据
@dataclass
class MemoryConfig:
    max_messages: int = field(default=50, metadata={"display": True, "order": 1})
    clean_threshold: int = field(default=3, metadata={"display": True, "order": 10})
    long_term_storage_path: str = field(
        default=".nano_agent/long_term_memory",
        metadata={"display": True, "condition": "type == 'hybrid'"}
    )

# _show_config() 自动遍历
def _show_config(config, agent):
    for section_name, section_config in get_config_sections(config):
        for field_name, field_value in get_display_fields(section_config):
            if should_display(field_name, section_config):
                print(format_line(field_name, field_value))
```

---

### v0.10.0 - 反思与规划能力

**目标**: 增强 Agent 的推理能力，支持复杂任务的规划与自我改进。

**任务列表**:
- [ ] 反思能力 - 执行后自我评估结果质量并调整策略
- [ ] RCI (Reason-Call-Interact) 反思循环实现
- [ ] Plan-Execute 模式增强 - 于反思优化计划

**技术方案**:
```python
# 反思循环示例
class ReflectiveAgent(ReActAgent):
    def run_with_reflection(self, task: str) -> str:
        # 1. 初始执行
        result = self.run(task)

        # 2. 反思评估
        reflection = self.reflect(task, result)

        # 3. 如果质量不足，调整策略重试
        if reflection.needs_improvement:
            result = self.run(task, strategy=reflection.suggested_strategy)

        return result
```

---

### v0.11.0 - 主动学习能力

**目标**: Agent 能够主动从交互中提取知识、建立关联。

**任务列表**:
- [ ] 自动知识提取 - 从对话中识别重要信息
- [ ] 知识关联建立 - 连接相关概念和经验
- [ ] 语义搜索增强 - 基于向量相似度的记忆检索
- [ ] 学习反馈机制 - 用户确认/纠正学习结果

**技术方案**:
```python
# 主动学习示例
class LearningAgent(ReActAgent):
    def learn_from_interaction(self, interaction: dict):
        # 1. 提取知识点
        knowledge = self.extract_knowledge(interaction)

        # 2. 建立关联
        connections = self.find_connections(knowledge)

        # 3. 存储到长期记忆
        self.memorize(knowledge, connections)
```

---

### v0.12.0 - 个性化与角色

**目标**: 支持可配置的 Agent 性格和专业领域深度。

**任务列表**:
- [ ] 角色配置系统 - 定义 Agent 性格、语气、专业领域
- [ ] 角色模板库 - 预定义常见角色（程序员、分析师、写作助手等）
- [ ] 动态角色切换 - 运行时切换角色
- [ ] 领域知识注入 - 加载专业领域知识库

**配置示例**:
```yaml
persona:
  name: "Code Assistant"
  traits:
    - professional
    - concise
    - helpful
  expertise:
    - python
    - web_development
  communication_style: "technical_but_friendly"
```

---

### v0.13.0 - 多 Agent 协作

**目标**: 支持多 Agent 协作和人机协作机制。

**任务列表**:
- [ ] 多 Agent 编排框架
- [ ] Agent 间通信协议
- [ ] 协作模式支持（并发、辩论、角色分工）
- [ ] 人机协作接口 - 人类审批/干预点
- [ ] 任务分解与分配

**架构示例**:
```
┌─────────────────────────────────────┐
│           Orchestrator              │
├─────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐
│  │ Agent A │  │ Agent B │  │ Agent C │
│  │ Coder   │  │ Reviewer│  │ Tester  │
│  └─────────┘  └─────────┘  └─────────┘
└─────────────────────────────────────┘
```

---

### v0.14.0 - 安全与体验

**目标**: 完善安全机制和用户体验。

**任务列表**:
- [ ] 安全审批机制 - 危险操作确认
- [ ] 沙箱执行环境 - 隔离执行代码
- [ ] Web UI - 更友好的交互界面
- [ ] 流式输出优化 - 实时显示思考过程
- [ ] 完善的权限控制

---

## 特性总览

| 版本 | 特性 | 说明 |
|------|------|------|
| v0.5.1 | 功能优化与增强 ✅ | CLI 增强、/init、/config、/memory、/setname、/undo 等 |
| v0.6.0 | 渐进式执行与 Git 集成 | 前置规划、逐步执行、用户确认、/undo 回退 |
| v0.7.0 | 模式切换 | Agent/Shell 模式切换，直接执行基础命令 |
| v0.8.0 | Hooks 机制 | 解耦组件间依赖，优雅的回调扩展 |
| v0.9.0 | 配置系统优化 | 自动显示/保存配置项 |
| v0.10.0 | 反思与规划能力 | RCI 反思循环、Plan-Execute 增强 |
| v0.11.0 | 主动学习 | 知识提取、语义搜索 |
| v0.12.0 | 个性化角色 | 可配置性格、专业领域 |
| v0.13.0 | 多 Agent 协作 | 编排框架、Agent 通信 |
| v0.14.0 | 安全与体验 | 沙箱、Web UI、权限控制 |

---

## 如何基于 NanoAgent 开发专用 Agent

1. **安装 NanoAgent**
   ```bash
   pip install nano-agent
   ```

2. **定义技能包**
   ```yaml
   # my_skill.yaml
   name: my_custom_agent
   system_prompt: |
     You are a specialized agent for...
   tools:
     - my_tool_1
     - my_tool_2
   ```

3. **创建自定义工具**
   ```python
   from nano_agent.tools.base import BaseTool, ToolResult

   class MyTool(BaseTool):
       name = "my_tool"
       description = "My custom tool"
       # ...
   ```

4. **运行 Agent**
   ```python
   from nano_agent import create_agent

   agent = create_agent(config_path="my_config.yaml")
   response = agent.run("Hello!")
   ```

---

## 贡献指南

如果你想参与开发：

1. 选择一个未完成的任务
2. 在 Issue 中说明你的计划
3. 提交 Pull Request

每个版本的开发应遵循：
- 先实现核心功能
- 添加单元测试
- 更新文档
- 更新配置示例

---

## 测试系统规划（与功能版本并行）

> **说明**: 测试计划与功能版本并行推进，不使用功能版本号。测试阶段以 T（Test）为前缀标识。

### 测试覆盖率现状

| 模块 | 当前覆盖率 | 目标覆盖率 | 优先级 |
|------|-----------|-----------|--------|
| cli/main.py | 9% | 70% | P0 |
| memory/migration.py | 0% | 90% | P1 |
| tools/plugin.py | 17% | 80% | P1 |
| tools/web_search.py | 20% | 75% | P2 |
| monitoring/reporter.py | 24% | 80% | P2 |
| cli/scanner.py | 12% | 70% | P2 |
| llm/ollama.py | 30% | 70% | P2 |
| **总体** | **50%** | **75%** | - |

---

### T1 阶段 - 测试基础设施完善

**目标**: 建立完善的测试基础设施，提升核心模块测试覆盖率。

**关联功能版本**: v0.6.0 渐进式执行与 Git 集成

**任务列表**:

**测试框架增强**:
- [ ] 引入 pytest-mock 统一 mock 策略
- [ ] 建立 fixture 工厂模式，减少测试代码重复
- [ ] 添加测试覆盖率门禁（CI 中强制最低 60%）
- [ ] 建立 mock 数据目录 `tests/fixtures/`

**CLI 模块测试 (P0)**:
- [ ] 会话管理测试 - 新建、恢复、删除、列表
- [ ] 命令解析测试 - `/config`, `/memory`, `/stats` 等
- [ ] 交互流程测试 - 用户输入、Agent 响应、错误处理
- [ ] 信号处理测试 - Ctrl+C 退出流程
- [ ] 使用 `click.testing.CliRunner` 或 `pytest-console-scripts`

**Migration 模块测试 (P1)**:
- [ ] File → SQLite 迁移测试
- [ ] 空数据迁移边界测试
- [ ] 损坏数据恢复测试
- [ ] 大数据量迁移性能测试
- [ ] 幂等性测试（重复迁移）

**Plugin 模块测试 (P1)**:
- [ ] 从模块加载工具测试
- [ ] 从文件加载工具测试
- [ ] 从目录加载工具测试
- [ ] 加载失败处理测试
- [ ] 工具卸载测试

**WebSearch 模块测试 (P2)**:
- [ ] HTML 解析逻辑测试（使用 fixture 文件）
- [ ] Bing 搜索结果提取测试
- [ ] 超时处理测试
- [ ] 网络错误处理测试
- [ ] 使用 `responses` 或 `pytest-httpserver` mock HTTP

**Monitoring 模块测试 (P2)**:
- [ ] JSON 报告生成测试
- [ ] Markdown 报告生成测试
- [ ] 统计数据聚合测试
- [ ] 边界情况测试（空数据、大数据）

**Scanner 模块测试 (P2)**:
- [ ] 项目结构扫描测试
- [ ] 技术栈检测测试
- [ ] Git 信息获取测试
- [ ] Markdown 生成测试

---

### T2 阶段 - 代码可测试性改进

**目标**: 重构代码以提升可测试性，降低测试编写难度。

**关联功能版本**: v0.7.0 模式切换、v0.8.0 Hooks 机制

**可测试性问题与改进**:

**问题 1: 紧耦合的外部依赖**
- **现状**: CLI 直接调用 `requests`、`subprocess`、文件系统
- **影响**: 测试需要真实环境，难以隔离
- **改进方案**:
  ```python
  # 引入依赖注入模式
  class OllamaLLM:
      def __init__(self, model: str, http_client: HttpClient = None):
          self._http = http_client or RequestsHttpClient()

  # 测试时注入 mock
  def test_ollama_chat():
      mock_http = MockHttpClient(response={"message": {"content": "test"}})
      llm = OllamaLLM("llama3", http_client=mock_http)
      # ...
  ```

**问题 2: 全局状态管理**
- **现状**: `GracefulExitManager` 使用类属性管理状态
- **影响**: 测试间状态污染，需要手动重置
- **改进方案**:
  ```python
  # 改为实例化管理
  class ExitManager:
      def __init__(self):
          self.ctrl_c_count = 0
          self.generating_summary = False

  # CLI 中创建实例
  exit_manager = ExitManager()
  ```

**问题 3: 宽泛的异常捕获**
- **现状**: 大量 `except Exception: pass` 隐藏错误
- **影响**: 测试无法捕获失败场景
- **改进方案**:
  ```python
  # 使用具体异常类型
  except (IOError, OSError) as e:
      logger.warning(f"File operation failed: {e}")

  # 或显式记录
  except Exception as e:
      logger.error(f"Unexpected error: {e}", exc_info=True)
  ```

**问题 4: 难以 mock 的静态方法**
- **现状**: `ReportGenerator.to_json()` 等静态方法
- **影响**: 无法在测试中替换实现
- **改进方案**:
  ```python
  # 改为实例方法或使用策略模式
  class ReportGenerator:
      def __init__(self, formatter: Formatter = None):
          self._formatter = formatter or JsonFormatter()

      def generate(self, metrics: RunMetrics) -> str:
          return self._formatter.format(metrics.to_dict())
  ```

**问题 5: 接口类型不明确**
- **现状**: `BaseMemory.add(message: Any)` 使用 Any 类型
- **影响**: 测试无法验证输入类型正确性
- **改进方案**:
  ```python
  from typing import TypeVar, Generic

  M = TypeVar('M')

  class BaseMemory(ABC, Generic[M]):
      @abstractmethod
      def add(self, message: M) -> None:
          pass

  class ShortTermMemory(BaseMemory[dict]):
      def add(self, message: dict) -> None:
          # 类型检查器可验证
          pass
  ```

**任务列表**:
- [ ] 引入依赖注入框架（或手动实现）
- [ ] 重构全局状态为实例管理
- [ ] 替换宽泛异常为具体异常
- [ ] 添加类型注解，启用 mypy 检查
- [ ] 提取接口抽象层（HttpClient, FileSystem, SubprocessRunner）
- [ ] 建立 mock 实现库 `tests/mocks/`

---

### T3 阶段 - 测试自动化与质量门禁

**目标**: 建立自动化测试流程，确保代码质量。

**关联功能版本**: v0.9.0 配置系统优化

**任务列表**:

**CI/CD 集成**:
- [ ] GitHub Actions 测试工作流
- [ ] 测试覆盖率报告上传（Codecov/Coveralls）
- [ ] 覆盖率门禁检查（最低 60%，新增代码 80%）
- [ ] 多 Python 版本测试（3.10, 3.11, 3.12）

**测试分类**:
- [ ] 单元测试 - 快速、隔离、无外部依赖
- [ ] 集成测试 - 真实依赖、端到端
- [ ] 标记测试 - `@pytest.mark.unit`, `@pytest.mark.integration`
- [ ] 分层运行 - `pytest -m unit` 快速反馈

**测试数据管理**:
- [ ] 建立 fixture 工厂（消息、配置、工具）
- [ ] 模块化 fixture 定义
- [ ] 测试数据版本管理

**测试文档**:
- [ ] 测试编写指南 `docs/testing.md`
- [ ] Mock 使用规范
- [ ] 测试命名约定

---

### 测试用例补充计划

#### CLI 模块测试用例 (`tests/test_cli.py`)

```python
# 会话管理测试
class TestSessionManagement:
    def test_new_session_creates_unique_id(self): ...
    def test_resume_session_loads_messages(self): ...
    def test_delete_session_removes_data(self): ...
    def test_list_sessions_shows_all(self): ...
    def test_clean_sessions_removes_low_value(self): ...

# 命令解析测试
class TestCommandParsing:
    def test_config_command_shows_all_fields(self): ...
    def test_memory_command_toggles_long_term(self): ...
    def test_stats_command_shows_statistics(self): ...
    def test_setname_updates_display_names(self): ...
    def test_undo_reverts_last_operation(self): ...

# 交互流程测试
class TestInteractionFlow:
    def test_user_input_processed_correctly(self): ...
    def test_agent_response_displayed(self): ...
    def test_tool_execution_shown_in_stats(self): ...
    def test_error_recovered_gracefully(self): ...
    def test_ctrl_c_exits_with_summary(self): ...
```

#### Migration 模块测试用例 (`tests/test_migration.py`)

```python
class TestFileToSqliteMigration:
    def test_migrate_empty_file_storage(self): ...
    def test_migrate_single_session(self): ...
    def test_migrate_multiple_sessions(self): ...
    def test_migrate_with_summary(self): ...
    def test_migrate_handles_unicode(self): ...
    def test_migrate_is_idempotent(self): ...
    def test_dry_run_reports_only(self): ...
    def test_migrate_large_session_performance(self): ...

class TestMigrationErrorHandling:
    def test_handles_corrupted_file(self): ...
    def test_handles_permission_error(self): ...
    def test_handles_disk_full(self): ...
    def test_reports_errors_in_result(self): ...
```

#### Plugin 模块测试用例 (`tests/test_plugin.py`)

```python
class TestPluginLoader:
    def test_load_from_module(self): ...
    def test_load_from_file(self): ...
    def test_load_from_directory(self): ...
    def test_load_handles_import_error(self): ...
    def test_load_handles_instantiation_error(self): ...
    def test_unload_tool(self): ...
    def test_list_loaded_plugins(self): ...

class TestPluginFromConfig:
    def test_load_from_directories(self): ...
    def test_load_from_modules(self): ...
    def test_load_from_files(self): ...
    def test_combined_config(self): ...
```

#### WebSearch 模块测试用例 (`tests/test_web_search.py`)

```python
class TestWebSearchTool:
    def test_search_returns_results(self): ...
    def test_parse_bing_results(self): ...
    def test_handle_timeout(self): ...
    def test_handle_network_error(self): ...
    def test_empty_results_message(self): ...
    def test_unicode_query_encoding(self): ...

# 使用 fixture 文件
@pytest.fixture
def bing_response_html():
    return Path("tests/fixtures/bing_response.html").read_text()

def test_parse_real_bing_response(bing_response_html):
    tool = WebSearchTool()
    results = tool._parse_search_results(bing_response_html)
    assert len(results) > 0
```

---

### 测试最佳实践

**1. 测试命名约定**
```python
# 格式: test_<method>_<scenario>_<expected_result>
def test_add_message_with_valid_dict_succeeds(): ...
def test_add_message_with_invalid_type_raises_error(): ...
```

**2. Arrange-Act-Assert 模式**
```python
def test_memory_add():
    # Arrange
    memory = ShortTermMemory()
    message = {"role": "user", "content": "test"}

    # Act
    memory.add(message)

    # Assert
    assert len(memory) == 2  # system + user
```

**3. 使用 Factory Boy 或手动工厂**
```python
# tests/factories.py
def create_message(role="user", content="test"):
    return {"role": role, "content": content}

def create_config(**overrides):
    defaults = {"llm": {"model": "test-model"}}
    defaults.update(overrides)
    return Config.from_dict(defaults)
```

**4. Mock 外部依赖**
```python
@pytest.fixture
def mock_http():
    with patch("requests.post") as mock:
        mock.return_value.json.return_value = {"message": {"content": "OK"}}
        yield mock

def test_ollama_chat_with_mock(mock_http):
    llm = OllamaLLM("test-model")
    text, _, _ = llm.chat([{"role": "user", "content": "hi"}])
    assert text == "OK"
```

**5. 参数化测试减少重复**
```python
@pytest.mark.parametrize("role,expected", [
    ("user", "user"),
    ("assistant", "assistant"),
    ("system", "system"),
])
def test_message_roles(role, expected):
    msg = create_message(role=role)
    assert msg["role"] == expected
```

---

### 测试覆盖率目标时间线

| 测试阶段 | 目标覆盖率 | 关键里程碑 | 关联功能版本 |
|------|-----------|-----------|--------|
| T1 | 60% | CLI、Migration、Plugin 测试完成 | v0.6.0 |
| T2 | 70% | 可测试性重构完成 | v0.7.0, v0.8.0 |
| T3 | 75% | CI 门禁建立，全模块测试完成 | v0.9.0 |
| T4+ | 80% | 持续维护，新增功能同步测试 | v0.10.0+ |