# NanoAgent Roadmap

> **定位**: 项目战略规划文档 - 版本规划、测试系统、架构演进
>
> **日常工作**: 详见 [CLAUDE.md](CLAUDE.md) - 命令参考、操作规范、设计哲学

本文档记录 NanoAgent 的开发路线图和增强计划。

## 文档定位

| 文档 | 定位 | 内容 | 目标读者 |
|------|------|------|---------|
| **CLAUDE.md** | 开发者日常工作手册 | 命令参考、架构概览、操作规范、设计哲学 | 每日开发者 |
| **ROADMAP.md** | 项目战略规划文档 | 版本规划、测试系统、架构演进、技术方案 | 规划者、贡献者 |

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

### v0.6.0 - 编排层与执行层分离 ✅

**目标**: 建立稳定的架构基础，实现编排层与执行层的清晰分离。

**背景**:
当前架构只有一层半：CLI 直接调用 `agent.run()`，会话管理、统计收集散落各处，执行循环是一个 100+ 行的大方法。通过分层重构，为后续功能演进奠定稳定基础。

**架构对应**: 编排层 + 执行层的基础实现

**任务列表**:

**编排层实现**:
- [x] 定义 `ExecutionResult` - 不可变结果类型，作为层间契约
- [x] 定义 `ExecutionEvent` - 执行事件类型，为流式输出预留
- [x] 实现 `AgentOrchestrator` 类 - 统一入口，委托执行层
- [x] 会话管理 - 生成 session_id、保存/恢复会话状态
- [x] 统计收集 - 累计 token、成本、事件日志
- [x] 真实/模拟切换 - 支持预览模式（不实际执行工具）

**执行层实现**:
- [x] 定义 `ThinkResult` - 思考阶段结果类型
- [x] 拆分 `_think()` 方法 - 调用 LLM，返回 `ThinkResult`
- [x] 拆分 `_act()` 方法 - 执行单个工具调用
- [x] 拆分 `_observe()` 方法 - 记录工具结果到内存
- [x] 重构 `run()` 方法 - 组合阶段方法，返回 `ExecutionResult`
- [x] 预算检查 - 多维度约束（token、迭代次数、工具调用次数）

**基础设施**:
- [x] 定义 `AgentEvent` 枚举 - RUN_START/THINK_START/TOOL_CALL/TOOL_RESULT/RUN_END
- [x] 实现 `EventEmitter` 类 - 事件注册和触发
- [x] 在执行阶段触发事件 - 支持外部监听

**更新 CLI**:
- [x] 通过编排层调用 - 不再直接调用 `agent.run()`
- [x] 监听事件更新 UI - 替代硬编码的 `print()`

**新增文件**:
```
nano_agent/agent/
├── types.py        # ExecutionResult, ThinkResult, ExecutionEvent, AgentEvent
├── events.py       # EventEmitter
├── budget.py       # Budget, BudgetChecker
└── orchestrator.py # AgentOrchestrator, SessionStats
```

**技术方案**:
```python
# nano_agent/agent/types.py

@dataclass(frozen=True)
class ExecutionResult:
    """执行结果 - 编排层与执行层的契约（不可变）"""
    response: str
    success: bool
    iterations: int
    tool_calls: list[dict]
    tokens_used: int
    session_id: str

@dataclass
class ExecutionEvent:
    """执行事件 - 流式输出的基本单位"""
    type: str              # "text" / "tool_call" / "tool_result" / "think" / "end"
    data: dict             # 事件数据
    timestamp: float

@dataclass
class ThinkResult:
    """思考阶段结果"""
    response_text: str
    tool_calls: list[ToolCall]
    usage: LLMUsage
    is_final: bool

# nano_agent/agent/events.py

class AgentEvent(Enum):
    RUN_START = "run_start"
    THINK_START = "think_start"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RUN_END = "run_end"

class EventEmitter:
    def on(self, event: AgentEvent, handler: Callable): ...
    def emit(self, event: AgentEvent, data: dict): ...

# nano_agent/agent/orchestrator.py

class AgentOrchestrator:
    """编排层 - 对外统一接口"""

    def __init__(self, agent: ReActAgent, config: AgentConfig):
        self.agent = agent
        self.config = config
        self.session_id = self._generate_session_id()
        self.stats = SessionStats()

    def run(self, user_input: str, dry_run: bool = False) -> ExecutionResult:
        """统一入口 - 同步执行"""
        self._ensure_session()

        # 委托执行层
        result = self.agent.run(user_input, dry_run=dry_run)

        # 统计收集
        self._collect_stats(result)
        return result

    def run_dry(self, user_input: str) -> ExecutionResult:
        """模拟执行 - 预览模式"""
        return self.run(user_input, dry_run=True)

# nano_agent/agent/react.py

class ReActAgent:
    """执行层 - 核心执行循环"""

    def __init__(self, ..., events: EventEmitter = None):
        self.events = events or EventEmitter()
        self.budget = BudgetChecker(config.budget)

    def run(self, user_input: str, dry_run: bool = False) -> ExecutionResult:
        """重构后的主循环"""
        self._prepare(user_input)
        self.events.emit(AgentEvent.RUN_START, {"input": user_input})

        while not self._should_stop():
            # 预算检查
            if not self.budget.can_continue(self.state):
                break

            think = self._think()
            if think.is_final:
                return self._build_result(think.response_text)

            for tool_call in think.tool_calls:
                result = self._act(tool_call, dry_run)
                self._observe(tool_call, result)

        return self._build_result(self._timeout_msg())

    def _think(self) -> ThinkResult:
        """思考：调用 LLM"""
        self.events.emit(AgentEvent.THINK_START, {})
        messages = self.memory.get_all()
        response_text, tool_calls, usage = self.llm.chat(messages, tools=...)
        return ThinkResult(response_text, tool_calls, usage, is_final=not tool_calls)

    def _act(self, tool_call: ToolCall, dry_run: bool = False) -> ToolResult:
        """行动：执行工具"""
        self.events.emit(AgentEvent.TOOL_CALL, {"tool": tool_call.name, "arguments": tool_call.arguments})
        if dry_run:
            return ToolResult(success=True, output="[预览模式] 未实际执行")
        result = self.execute_tool(tool_call.name, tool_call.arguments)
        self.events.emit(AgentEvent.TOOL_RESULT, {"tool": tool_call.name, "result": result})
        return result

    def _observe(self, tool_call: ToolCall, result: ToolResult):
        """观察：记录结果"""
        content = result.output if result.success else f"Error: {result.error}"
        self.memory.add_tool_result(tool_call.id, content)

# nano_agent/agent/budget.py

@dataclass
class Budget:
    max_iterations: int = 10
    max_tokens: int = 100000
    max_tool_calls: int = 50

class BudgetChecker:
    def can_continue(self, state: ExecutionState) -> bool:
        return (
            state.iterations < self.budget.max_iterations and
            state.tokens_used < self.budget.max_tokens and
            state.tool_calls < self.budget.max_tool_calls
        )
```

---

### v0.6.1 - 上下文管理 ✅

**目标**: 实现上下文压力检测和压缩策略，防止上下文溢出。

**背景**:
长对话会导致上下文超出模型限制。需要在执行过程中检测压力，按成本递增的策略压缩上下文。

**架构归属**: 执行层 - 上下文管理

**任务列表**:
- [x] 实现 `ContextManager` 类 - 检测上下文压力
- [x] Token 估算工具 - `estimate_tokens()` 支持中英文混合
- [x] 三层压缩策略 - 轻量清理 → 摘要标记 → 模型压缩
- [x] 九段式摘要结构 - 用户请求/技术概念/文件代码/错误修复/问题解决/用户消息/待处理任务/当前工作/下一步
- [x] 熔断机制 - 连续压缩失败后停止自动压缩
- [x] 在 `_think()` 前检测上下文压力
- [x] 配置支持 - `ContextConfig` 数据类

**新增文件**:
```
nano_agent/agent/
├── token_utils.py  # estimate_tokens, estimate_text_tokens
└── context.py      # ContextManager, NineSectionSummary
```

**技术方案**:
```python
# nano_agent/agent/context.py

class ContextManager:
    """上下文管理"""

    def __init__(self, memory: BaseMemory, llm, config: ContextConfig):
        self.memory = memory
        self.llm = llm
        self.config = config
        self.compress_failures = 0

    def check_and_compress(self, max_context_tokens: int | None = None) -> bool:
        """检测上下文压力并执行压缩"""
        tokens = estimate_tokens(self.memory.get_all())
        ratio = tokens / max_context_tokens

        if ratio < 0.70:
            return False  # 不需要压缩
        elif ratio < 0.85:
            return self._try_light_cleanup()  # 第一层
        elif ratio < 0.95:
            return self._try_summary_mark()   # 第二层
        else:
            return self._try_model_compress() # 第三层
```

---

### v0.6.2 - 前置规划 ✅

**目标**: 复杂任务先制定计划，展示给用户确认后再执行。

**背景**:
当前 Agent 接到任务后直接进入 Think-Act-Observe 循环，缺少规划阶段。用户无法预览执行计划，也无法在执行前调整。

**架构对应**: 独立的 PlanMode 类，支持多轮规划和持久化

**任务列表**:
- [x] 定义 `Plan` 和 `PlanPhase` 数据结构
- [x] 实现 `PlanMode` 类 - 多轮规划逻辑
- [x] 实现 Plan 文件操作工具 - SavePlanTool, ListPlansTool, LoadPlanTool
- [x] Plan 持久化 - `.nano_agent/plans/` 目录
- [x] CLI 命令支持 - `/plan`, `/plans`
- [x] 单元测试 - 20+ 测试用例

**新增文件**:
```
nano_agent/agent/types.py      # Plan, PlanPhase 数据类
nano_agent/cli/plan_mode.py    # PlanMode 类
nano_agent/tools/plan_tools.py # Plan 文件操作工具
tests/test_plan.py             # 测试用例
```

---

### v0.6.3 - PlanMode 演进优化 ✅

**目标**: 优化 PlanMode 架构，为未来多模式和多 Agent 集成做准备。

**背景**:
v0.6.2 的 PlanMode 实现了基础功能，但 I/O 逻辑与核心逻辑耦合。为了支持未来的独立 Agent 模式和多模式切换，需要将核心逻辑与 I/O 分离。

**架构对应**: 演进友好设计 - 核心逻辑无 I/O，可被 CLI 或独立 Agent 包装

**任务列表**:
- [x] EventEmitter 集成 - 支持事件驱动的 UI 更新
- [x] 核心逻辑 I/O 无关 - generate_plan(), adjust_plan(), save_plan() 不依赖 print/input
- [x] CLI 包装函数 - run_plan_mode_interactive() 作为可替换的 CLI 层
- [x] 事件类型定义 - plan_generated, plan_adjusted, plan_saved
- [x] 测试更新 - 验证事件触发和 I/O 分离

**改进内容**:
```python
# 演进友好设计
class PlanMode:
    def __init__(self, llm, config, events: EventEmitter = None):
        self.events = events or EventEmitter()  # 支持外部注入
        self.current_plan: Plan | None = None

    def generate_plan(self, task: str) -> Plan:
        """纯逻辑，无 I/O"""
        self.events.emit("plan_generated", {"plan": self.current_plan})
        return self.current_plan

# CLI 包装层（可被未来独立 Agent 替换）
def run_plan_mode_interactive(llm, config, task, input_fn=input, print_fn=print):
    ...
```

---

### v0.6.4 - 渐进式执行与用户确认 ✅

**目标**: 工具执行前暂停，等待用户确认；支持风险分级确认策略。

**背景**:
当前 Agent 连续执行多个工具调用，用户无法干预。危险操作（删除、Shell）应该确认，安全操作（读取）可以自动执行。

**架构对应**: 基于事件流，监听 CONFIRMATION_REQUIRED 事件实现暂停和确认

**任务列表**:
- [x] 定义 `RiskLevel` 枚举 - SAFE/MODERATE/DANGEROUS
- [x] 工具添加 `risk_level` 属性
- [x] 实现 `ConfirmationManager` 类 - 管理确认策略和白名单
- [x] 在 `_act()` 前插入确认逻辑 - 根据风险级别决定是否确认
- [x] CLI 实现 `confirm_handler` - 监听 CONFIRMATION_REQUIRED 事件弹出确认
- [x] 配置开关 - `confirmation.enabled`/`confirm_safe`/`confirm_moderate`/`confirm_dangerous`
- [x] 白名单管理 - 内存白名单 + 可选持久化到配置文件

**新增文件**:
```
nano_agent/agent/confirmation.py   # ConfirmationManager, ConfirmationConfig
tests/test_confirmation.py          # 22 测试用例
```

**修改文件**:
```
nano_agent/agent/types.py          # RiskLevel 枚举, AgentEvent.CONFIRMATION_REQUIRED
nano_agent/agent/react.py          # 集成确认逻辑到 _act()
nano_agent/tools/base.py           # risk_level 属性
nano_agent/tools/builtin.py        # 各工具设置 risk_level
nano_agent/cli/main.py             # 确认事件处理
nano_agent/config/schema.py       # ConfirmationConfig
```

**技术方案**:
```python
# nano_agent/agent/types.py

class RiskLevel(Enum):
    """工具风险级别"""
    SAFE = "safe"           # 只读、查询
    MODERATE = "moderate"   # 写入、创建
    DANGEROUS = "dangerous" # 删除、Shell

# nano_agent/agent/confirmation.py

class ConfirmationManager:
    """确认管理器"""

    def needs_confirmation(self, tool: BaseTool) -> bool:
        """判断工具是否需要确认"""
        if tool.name in self.config.whitelist:
            return False
        return getattr(self.config, f"confirm_{tool.risk_level.value}", True)

    def request_confirmation(self) -> None:
        """请求确认（设置等待状态）"""
        self._pending_confirmation = True

    def set_result(self, confirmed: bool) -> None:
        """设置确认结果"""
        self._confirmation_result = confirmed
        self._pending_confirmation = False

# CLI 确认处理
def handle_confirmation(event, data):
    response = input(f"确认执行 {data['tool']}? [y/N/a/s]: ")
    if response == 'y':
        agent.confirm_tool(True)
    elif response == 'a':
        agent.add_tool_to_whitelist(data['tool'])
        agent.confirm_tool(True)
    elif response == 's':
        agent.add_tool_to_whitelist(data['tool'])
        save_whitelist_to_config(data['tool'])
        agent.confirm_tool(True)
    else:
        agent.confirm_tool(False)
```

---

### v0.6.5 - Git 集成与状态回退 ✅

**目标**: 集成 Git 实现自动提交和状态回退能力。

**背景**:
当前 `/undo` 只能撤销当前轮次操作。Git 集成提供更强大的回退能力，支持跨轮次撤销和完整操作历史。

**架构对应**: 基于事件流，监听 TOOL_RESULT 事件自动提交

**任务列表**:
- [x] 实现 `GitManager` 类 - 检测仓库、自动提交、回退
- [x] 监听 TOOL_RESULT 事件 - 工具执行后自动提交
- [x] 监听 RUN_END 事件 - round 模式批量提交
- [x] `/undo` 命令增强 - 回退到上一个 Git commit
- [x] `/history` 命令 - 查看可回退的操作历史
- [x] 配置开关 - `git.enabled`/`git.auto_commit`/`git.commit_mode`

**新增文件**:
```
nano_agent/agent/git_manager.py  # GitManager, GitCommit
tests/test_git_manager.py         # 26 测试用例
```

**修改文件**:
```
nano_agent/config/schema.py      # GitConfig
nano_agent/cli/main.py           # Git 事件处理、/undo 增强、/history 命令
nano_agent/agent/__init__.py     # 导出 GitManager
```

**技术方案**:
```python
# nano_agent/agent/git_manager.py

class GitManager:
    """Git 集成管理器"""

    def is_enabled(self) -> bool:
        """检查 Git 是否可用"""
        ...

    def auto_commit(self, message: str, step_info: dict = None) -> str | None:
        """自动提交更改，返回 commit hash"""
        ...

    def undo(self, steps: int = 1) -> bool:
        """回退到历史 commit"""
        ...

    def get_history(self, limit: int = 10) -> list[GitCommit]:
        """获取操作历史"""
        ...

# CLI Git 事件处理
def _setup_git_handler(agent, git_manager, config):
    if config.git.commit_mode == "step":
        # 每步提交
        agent.events.on(AgentEvent.TOOL_RESULT, 
            lambda e, d: git_manager.auto_commit(f"Tool: {d['tool']}"))
    elif config.git.commit_mode == "round":
        # 本轮结束后批量提交
        ...

# /undo 增强
if user_input.lower() == "/undo":
    if git_manager and git_manager.is_enabled():
        history = git_manager.get_history(limit=5)
        # 显示历史，让用户选择回退步数
        ...

# /history 命令
if user_input.lower() == "/history":
    history = git_manager.get_history(limit=10)
    for commit in history:
        print(f"  {commit.hash} [{time}] {commit.message}")
```

---

### v0.7.0 - Hooks 机制与架构优化 ✅

**目标**: 提供优雅的扩展机制，解耦组件间的依赖。

**背景**:
当前 undo 操作需要返回值传递链条来更新 UI 层变量，不够优雅。Hooks 机制可以让组件间通信更加解耦。

**架构归属**: 基础设施层 - 扩展系统

**任务列表**:
- [x] 定义 `AgentEvent` 扩展 - NAME_CHANGED, MEMORY_CHANGED, UNDO_COMPLETED
- [x] 统一 EventEmitter - Orchestrator 和 Agent 共享事件系统
- [x] 移除 Agent 层的 CLI 特定代码 - 名字更新逻辑移至 CLI 层
- [x] CLI 事件驱动更新 - 监听 NAME_CHANGED 事件更新显示
- [x] 14 个测试用例 - 验证 hooks 机制

**架构优化 (P0-P2)**:
- [x] P0 - ToolRegistry.unregister() 方法
- [x] P1 - 关注点分离：CLI 逻辑移出 Agent 层
- [x] P1 - LongTermMemoryCapable Protocol 替代 hasattr()
- [x] P2 - BaseRegistry 泛型基类
- [x] P2 - AgentBuilder 模式
- [x] P2 - nano_agent/core/ 共享基础设施模块

**新增文件**:
```
nano_agent/core/
├── __init__.py    # 模块导出
├── builder.py     # AgentBuilder 模式
└── registry.py    # BaseRegistry 泛型基类

nano_agent/tools/
├── registry.py    # ToolRegistry (从 base.py 分离)
└── builtin/       # 内置工具子包
    ├── __init__.py
    ├── builtin.py
    ├── file_ops.py
    ├── memory_tools.py
    ├── monitoring_tools.py
    ├── plan_tools.py
    ├── python_executor.py
    ├── shell.py
    └── web_search.py
```

**技术方案**:
```python
# nano_agent/agent/events.py

class AgentEvent(Enum):
    # ... 原有事件 ...
    NAME_CHANGED = "name_changed"
    MEMORY_CHANGED = "memory_changed"
    UNDO_COMPLETED = "undo_completed"

# CLI 中监听事件
agent.events.on(AgentEvent.NAME_CHANGED, lambda e, d: update_display(d))

# AgentBuilder 模式
builder = AgentBuilder(config)
builder.with_llm_instance(llm)
builder.with_memory_instance(memory)
builder.with_tool_registry(tool_registry)
orchestrator = builder.build()
```

---

### v0.7.1 - Token 消耗优化 ✅

**目标**: 减少 Agent 运行时的 Token 消耗，降低使用成本。

**背景**:
用户反馈两轮对话消耗 27k tokens，主要原因是：
1. 每次工具调用都会把完整上下文重新发送给 LLM
2. LLM 输出内容冗长（表格、emoji、详细总结）
3. 迭代次数多，每次迭代累积 token

**架构归属**: 执行层 - 输出优化

**任务列表**:
- [x] 优化 Agent 系统提示词 - 简化指令，减少冗余描述
- [x] 输出风格控制 - 配置项控制输出详细程度（简洁/标准/详细）
- [x] 工具结果截断 - 大型工具输出自动截断后再加入上下文
- [x] 配置支持 - `output_style` 配置项

**新增文件**:
```
tests/test_output_style.py  # 输出风格单元测试
```

**修改文件**:
```
nano_agent/agent/prompts.py       # 添加 concise/standard 提示词模板
nano_agent/config/schema.py       # OutputStyleConfig
nano_agent/config/loader.py       # 配置解析和保存
nano_agent/agent/react.py         # 集成输出风格控制
nano_agent/core/builder.py        # 传递配置到 Agent
nano_agent/cli/main.py            # 输出风格配置显示
```

**技术方案**:
```python
# nano_agent/config/schema.py

class OutputStyle(Enum):
    CONCISE = "concise"    # 简洁：一句话回答，无表格/emoji
    STANDARD = "standard" # 标准：适度格式化
    DETAILED = "detailed" # 详细：完整分析、表格、emoji

@dataclass
class OutputStyleConfig:
    style: OutputStyle = OutputStyle.STANDARD
    max_response_length: int = 500  # 最大响应长度（字符）
    use_emoji: bool = False
    use_table: bool = False

# nano_agent/agent/prompts.py

# 简化后的系统提示词（减少约 50% tokens）
SYSTEM_PROMPT_CONCISE = """
你是 {agent_name}，一个 AI 助手。
用户: {user_name}

规则:
1. 回答简洁，直接给出答案
2. 必须使用工具时才调用
3. 每轮最多 2 次工具调用
"""

# nano_agent/agent/output_style.py

class OutputStyleManager:
    """输出风格管理"""

    def __init__(self, config: OutputStyleConfig):
        self.config = config

    def get_system_prompt(self, base_prompt: str) -> str:
        """根据输出风格调整系统提示词"""
        if self.config.style == OutputStyle.CONCISE:
            return self._make_concise(base_prompt)
        return base_prompt

    def _make_concise(self, prompt: str) -> str:
        """简化提示词"""
        # 移除冗余描述、示例、格式要求
        ...

    def format_response(self, response: str) -> str:
        """格式化响应"""
        if self.config.style == OutputStyle.CONCISE:
            # 截断过长响应
            if len(response) > self.config.max_response_length:
                return response[:self.config.max_response_length] + "..."
        return response
```

**预期效果**:
- 简洁模式下 token 消耗减少 40-60%
- 单轮对话控制在 5k tokens 以内

---

### v0.7.2 - Token 消耗深度优化 ✅

**目标**: 进一步减少 Token 消耗，目标两轮对话 < 8k tokens。

**背景**:
v0.7.1 实现了基础优化，concise 模式下两轮对话仍有 14k tokens。需要更激进的优化。

**架构归属**: 执行层 - 智能优化

**任务列表**:
- [x] 智能工具合并 - 合并相似工具调用，减少迭代次数
- [x] 工具结果智能摘要 - file_read/shell_execute 结果只保留关键信息
- [ ] 预判机制 - 先分析问题复杂度，简单问题直接回答（暂缓）
- [ ] 更激进的输出精简 - 一句话回答、无表格、无列表（暂缓）

**新增文件**:
```
nano_agent/agent/tool_merger.py  # ToolCallMerger, ToolMergeConfig
tests/test_tool_merger.py        # 工具合并测试
```

**修改文件**:
```
nano_agent/config/schema.py      # ToolMergeConfig, 扩展 OutputStyleConfig
nano_agent/agent/react.py        # 集成工具合并、智能摘要配置
nano_agent/agent/result_summarizer.py  # 增强智能摘要逻辑
nano_agent/core/builder.py       # 传递 tool_merge_config
tests/test_output_style.py       # 智能摘要测试
```

**技术方案**:
```python
# 1. 智能工具合并
# 原始：3次 file_search 调用
# 优化：合并为 1 次 file_search，使用 glob pattern

# 2. 工具结果智能摘要
class ToolResultSummarizer:
    def summarize(self, output: str, tool_name: str) -> str:
        if tool_name == "file_read":
            # 提取 imports + signatures + 首尾行
            return self._extract_key_lines(output)
        elif tool_name == "shell_execute":
            # 提取 errors + 有意义的输出
            return self._filter_meaningful(output)
```

**预期效果**:
- 智能工具合并: ~25-30% 节省
- 工具结果智能摘要: ~20-25% 节省
- 两轮对话目标 < 8k tokens

---

### v0.7.3 - Token 消耗进阶优化 ✅

**目标**: 基于 report.json 分析，实现更精准的 Token 优化。

**背景**:
通过 report.json 分析发现以下问题：
1. 重复工具调用：同一文件被多次读取（file_search → file_read → file_search recursive）
2. 历史消息累积：prompt_tokens 线性增长（2589 → 2701 → 2968 → 3122 → 3333）
3. 长项目文件：NANOPROJECT.md 嵌入系统提示词，每次调用都发送
4. 默认参数不当：file_search 的 recursive=false 导致重试

**架构归属**: 执行层 - 智能缓存与压缩

**任务列表**:

**1. 检测重复工具调用 (~30% 节省)**:
- [x] 实现 `ToolResultCache` 类 - 缓存只读工具结果
- [x] 缓存 TTL: 5 分钟（可配置）
- [x] 仅缓存只读工具（file_read, file_search, shell_execute 查询）
- [x] 显示 "[cached]" 指示器
- [x] 不缓存写操作（file_write, memorize）

**2. 压缩历史消息 (~20% 节省)**:
- [x] 实现 `MessageCompressor` 类 - 摘要旧消息
- [x] 阈值: 2000 prompt_tokens（可配置）
- [x] 保留最近 3 轮对话原文
- [x] 摘要格式: "Previous iterations: [brief summary]"
- [x] 在 LLM 调用前触发压缩

**3. 简化项目文件 (~10% 节省)**:
- [x] 添加 `project_file_mode: full|condensed|reference` 配置
- [x] 默认: condensed（平衡上下文与完整性）
- [x] 自动生成精简版本
- [x] 仅首轮发送完整文件，后续引用文件名

**4. file_search 默认 recursive=true**:
- [x] 修改工具 schema 默认值（已实现）
- [x] 更新帮助文本
- [x] 添加测试验证

**技术方案**:
```python
# nano_agent/agent/cache.py

class ToolResultCache:
    """工具结果缓存"""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict[str, tuple[ToolResult, float]] = {}
        self._ttl = ttl_seconds

    def get_cached_result(self, tool_name: str, args: dict) -> ToolResult | None:
        """检查缓存是否命中"""
        cache_key = self._make_key(tool_name, args)
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._ttl:
                return result
        return None

    def set_cached_result(self, tool_name: str, args: dict, result: ToolResult):
        """缓存结果"""
        cache_key = self._make_key(tool_name, args)
        self._cache[cache_key] = (result, time.time())

# nano_agent/agent/compressor.py

class MessageCompressor:
    """历史消息压缩"""

    def __init__(self, keep_recent: int = 3, threshold_tokens: int = 2000):
        self.keep_recent = keep_recent
        self.threshold = threshold_tokens

    def compress_old_messages(self, messages: list) -> list:
        """压缩旧消息"""
        if estimate_tokens(messages) < self.threshold:
            return messages

        # 保留最近 N 轮
        recent = messages[-self.keep_recent * 2:]  # user + assistant
        old = messages[:-self.keep_recent * 2]

        # 摘要旧消息
        summary = self._summarize(old)
        return [{"role": "system", "content": f"[历史摘要] {summary}"}] + recent
```

**新增文件**:
```
nano_agent/agent/cache.py      # ToolResultCache
nano_agent/agent/compressor.py # MessageCompressor
tests/test_cache.py            # 缓存测试
tests/test_compressor.py       # 压缩测试
```

**修改文件**:
```
nano_agent/tools/builtin.py    # file_search recursive=true
nano_agent/config/schema.py    # project_file_mode 配置
nano_agent/agent/react.py      # 集成缓存和压缩
```

**预期效果**:
- 重复调用场景节省 ~30% tokens
- 长对话场景节省 ~20% tokens
- 项目文件场景节省 ~10% tokens
- 两轮对话目标 < 8k tokens

---

### v0.7.4 - Token 统计增强 ✅

**目标**: 增强 `/stats` 命令，按类型显示 Token 消耗明细，帮助用户定位优化点。

**背景**:
当前 `/stats` 只显示总 Token 数，无法区分不同来源的消耗。用户需要知道：
- 系统提示词消耗多少？
- 工具输出消耗多少？
- 历史消息消耗多少？
- LLM 响应消耗多少？

**架构归属**: 监控层 - 统计分析

**任务列表**:

**1. Token 分类统计**:
- [x] 定义 `TokenCategory` 枚举 - system/tools/history/response/compressed
- [x] 实现 `TokenAnalyzer` 类 - 分析 Token 来源
- [x] 在 `record_llm_call()` 中记录分类信息
- [x] 累计各类 Token 消耗

**2. `/stats` 命令增强**:
- [x] `/stats` - 显示完整统计（含分类明细）
- [x] `/stats tokens` - 仅显示 Token 分类明细
- [x] `/stats breakdown` - 显示各轮 Token 消耗详情
- [x] `/stats tools` - 显示各工具的 Token 消耗排名

**3. Token 分类明细显示**:
- [x] 系统提示词 Token（固定成本）
- [x] 工具输出 Token（可优化成本）
- [x] 历史消息 Token（累积成本）
- [x] LLM 响应 Token（输出成本）
- [x] 压缩节省 Token（优化效果）

**新增文件**:
```
nano_agent/monitoring/
├── token_analyzer.py    # TokenAnalyzer, TokenCategory
tests/test_token_analyzer.py  # 测试用例
```

**修改文件**:
```
nano_agent/monitoring/tracker.py    # 集成 TokenAnalyzer
nano_agent/cli/main.py              # /stats 子命令增强
```

**技术方案**:
```python
# nano_agent/monitoring/token_analyzer.py

class TokenCategory(Enum):
    """Token 消耗分类"""
    SYSTEM = "system"        # 系统提示词
    TOOLS = "tools"          # 工具输出
    HISTORY = "history"      # 历史消息（非工具）
    RESPONSE = "response"    # LLM 响应
    COMPRESSED = "compressed" # 压缩节省

@dataclass
class TokenBreakdown:
    """Token 消耗明细"""
    category: TokenCategory
    tokens: int
    percentage: float
    details: dict[str, int]  # 子分类详情

class TokenAnalyzer:
    """Token 分析器"""

    def __init__(self):
        self._category_totals: dict[TokenCategory, int] = {}
        self._tool_token_usage: dict[str, int] = {}  # 工具名 → Token 数

    def analyze_llm_call(self, metrics: LLMCallMetrics) -> TokenBreakdown:
        """分析单次 LLM 调用的 Token 消耗"""
        # 从 input_messages 中分类统计
        for msg in metrics.input_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                self._category_totals[TokenCategory.SYSTEM] += estimate_tokens(content)
            elif "tool_result" in msg:
                self._category_totals[TokenCategory.TOOLS] += estimate_tokens(content)
            else:
                self._category_totals[TokenCategory.HISTORY] += estimate_tokens(content)

        # 响应 Token
        self._category_totals[TokenCategory.RESPONSE] += metrics.completion_tokens

    def get_breakdown(self) -> list[TokenBreakdown]:
        """获取 Token 消耗明细"""
        total = sum(self._category_totals.values())
        return [
            TokenBreakdown(
                category=cat,
                tokens=tokens,
                percentage=tokens / total * 100 if total > 0 else 0,
                details={}
            )
            for cat, tokens in self._category_totals.items()
        ]

    def get_tool_ranking(self, limit: int = 10) -> list[tuple[str, int]]:
        """获取工具 Token 消耗排名"""
        return sorted(
            self._tool_token_usage.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

# CLI 显示格式
def _show_token_breakdown(analyzer: TokenAnalyzer):
    """显示 Token 分类明细"""
    print("\n📊 Token 消耗明细:")
    print("-" * 40)

    breakdown = analyzer.get_breakdown()
    for item in breakdown:
        bar = "█" * int(item.percentage / 5)  # 5% = 1 格
        print(f"  {item.category.value:<12} {item.tokens:>6} ({item.percentage:>5.1f}%) {bar}")

    # 工具消耗排名
    print("\n🔧 工具消耗排名:")
    for tool, tokens in analyzer.get_tool_ranking(5):
        print(f"  {tool:<20} {tokens:>6} tokens")
```

**预期效果**:
- 用户可快速定位高消耗来源
- 工具优化有明确数据支撑
- 历史消息压缩效果可视化

---

### v0.7.5 - Token 消耗智能优化 ✅

**目标**: 实现动态思考深度控制，让 Agent 学会"适可而止"。

**背景**:
v0.7.1-v0.7.4 实现了静态优化（输出风格、工具合并、缓存、压缩）。但 Agent 仍会在所有场景使用相同策略，无法根据任务复杂度动态调整。

**架构归属**: 执行层 - 动态优化

**任务列表**:

**1. 置信度评估与早停 (P0)**:
- [x] 扩展 `ThinkResult` 数据类 - 增加 `confidence` 和 `can_answer` 字段
- [x] 修改 System Prompt - 要求 LLM 输出置信度评估
- [x] 实现 `ConfidenceParser` 类 - 解析置信度标记
- [x] 集成早停逻辑 - 置信度 >= threshold 且可回答时早停
- [x] 测试验证 - 37 个测试用例

**2. Token 预算管理增强 (P0)**:
- [x] 实现 `TokenBudget` 类 - 剩余预算追踪
- [x] 预算耗尽时强制总结 - `_force_summarize()` 方法
- [x] 配置支持 - `SmartOptimizationConfig` 配置项

**3. 查询复杂度路由 (P1)**:
- [x] 实现 `QueryRouter` 类 - 分类查询复杂度（SIMPLE/MODERATE/COMPLEX）
- [x] 支持中英文问候语识别
- [x] 中等复杂度处理 - 单次 LLM + 最多 1 次工具
- [x] 配置支持 - `routing.enabled` 配置项

**4. 工具返回智能摘要增强 (P1)**:
- [ ] 实现 `ToolResultProcessor` 类 - 提取-摘要-结构化（暂缓）
- [ ] 针对每个工具定制处理逻辑（暂缓）
- [x] 配置支持 - `tool_processor.enabled` 配置项已预留

**新增文件**:
```
nano_agent/agent/
├── router.py              # QueryRouter, QueryComplexity, RoutingResult
├── token_budget.py        # TokenBudget, TokenBudgetConfig
├── confidence.py          # ConfidenceParser, ConfidenceResult
tests/test_smart_optimization.py  # 37 个测试用例
```

**修改文件**:
```
nano_agent/agent/types.py      # ThinkResult 扩展 confidence/can_answer
nano_agent/agent/react.py      # 早停逻辑、预算管理、路由集成
nano_agent/agent/prompts.py    # CONFIDENCE_SUFFIX 置信度提示词
nano_agent/agent/__init__.py   # 导出新模块
nano_agent/config/schema.py    # SmartOptimizationConfig 配置类
nano_agent/core/builder.py     # 传递 smart_optimization_config
```

**技术方案**:
```python
# nano_agent/agent/types.py
@dataclass
class ThinkResult:
    response_text: str
    tool_calls: list[ToolCall]
    usage: LLMUsage
    is_final: bool
    confidence: float = 1.0      # 当前结论置信度 (0-1)
    can_answer: bool = True      # 是否已有足够信息回答

# nano_agent/agent/token_budget.py
class TokenBudget:
    def __init__(self, config: TokenBudgetConfig):
        self.initial_budget = config.initial_budget
        self.remaining = self.initial_budget

    def consume(self, tokens: int) -> None:
        self.remaining = max(0, self.remaining - tokens)

    def should_summarize(self) -> bool:
        """剩余预算耗尽时，强制进入总结模式"""
        return self.remaining <= 0 and self.config.force_summarize

# nano_agent/agent/router.py
class QueryComplexity(Enum):
    SIMPLE = "simple"       # 问候、简单问答
    MODERATE = "moderate"   # 单步推理
    COMPLEX = "complex"     # 多步推理

class QueryRouter:
    def classify(self, query: str) -> RoutingResult:
        # 优先检查简单模式（问候、感谢等）
        # 然后检查复杂模式（分析、实现、重构等）
        # 最后检查中等模式
        # 默认返回复杂
```

**预期效果**:
- 置信度早停: 减少 30% 无效迭代
- Token 预算: 防止无限消耗
- 查询路由: 减少 50% 简单任务消耗

---

### v0.7.6 - 模块化提示词系统 ✅

**目标**: 实现可配置、可组合的提示词系统，支持 Excel 配置和动态组装。

**背景**:
当前系统提示词硬编码在 `prompts.py` 中，难以灵活调整。不同场景需要不同的提示词组合（简洁模式 vs 详细模式），用户无法自定义提示词内容。

**架构归属**: 执行层 - 提示词管理

**任务列表**:

**1. 提示词模块化 (P0)**:
- [x] 定义 `PromptModule` 数据类 - 名称、内容、优先级、Token 估算
- [x] 实现 17 个提示词模块 - 按功能分类（基础、效率、安全、输出、上下文、记忆）
- [x] 模块优先级排序 - 确保关键模块优先加载

**2. Builder 模式组装 (P0)**:
- [x] 实现 `PromptBuilder` 类 - Builder 模式组装提示词
- [x] 支持模块选择 - 按名称/类别启用/禁用模块
- [x] 风格预设 - concise (~200)、standard (~1000)、detailed (~2000)
- [x] 缓存机制 - 稳定部分缓存，动态部分按需组装

**3. Excel 配置支持 (P1)**:
- [x] 创建 `prompts.xlsx` 配置文件 - 便于非程序员编辑
- [x] 支持从 Excel 加载模块 - 名称、内容、优先级、启用状态
- [x] 配置热更新 - 修改 Excel 后自动生效

**4. 动态工具支持 (P1)**:
- [x] 动态添加工具时重建提示词 - `add_tool()` 触发重建
- [x] 稳定缓存键 - SHA256 替代 Python hash()，跨会话稳定

**新增文件**:
```
nano_agent/agent/
├── prompt_modules.py    # PromptModule, 17 个预定义模块
├── prompt_builder.py    # PromptBuilder, 缓存机制
├── prompts.xlsx         # Excel 配置文件
tests/test_prompt_config.py  # 提示词配置测试
```

**修改文件**:
```
nano_agent/agent/react.py     # 集成 PromptBuilder, add_tool() 重建
nano_agent/agent/prompts.py   # 保留 legacy 兼容
nano_agent/config/schema.py   # PromptConfig 配置类
nano_agent/core/builder.py    # 传递 prompt_config
```

**模块分类**:
| 类别 | 模块 | Token 估算 |
|------|------|-----------|
| Basic | core, tools | ~50, ~100 |
| Efficiency | efficiency, modification | ~30, ~20 |
| Security | constitution, risk_awareness, security_rules | ~40, ~30, ~50 |
| Output | output_style, language | ~20, ~10 |
| Context | environment, git_status | ~30, ~20 |
| Memory | memory_guide | ~40 |

**技术方案**:
```python
# nano_agent/agent/prompt_modules.py

@dataclass
class PromptModule:
    """提示词模块"""
    name: str
    content: str
    priority: int          # 排序优先级（越小越优先）
    token_estimate: int    # Token 估算
    category: str          # 分类：basic/efficiency/security/output/context/memory
    enabled: bool = True   # 是否启用

# 预定义模块
CORE_MODULE = PromptModule(
    name="core",
    content="你是 {agent_name}，一个 AI 助手...",
    priority=1,
    token_estimate=50,
    category="basic"
)

# nano_agent/agent/prompt_builder.py

class PromptBuilder:
    """提示词构建器"""

    def __init__(self, modules: list[PromptModule], config: PromptConfig):
        self.modules = modules
        self.config = config
        self._stable_cache: str | None = None
        self._cache_key: str | None = None

    def build(self, style: str = "standard", enabled_modules: list[str] = None) -> str:
        """组装提示词"""
        # 1. 筛选启用的模块
        selected = self._select_modules(enabled_modules)

        # 2. 按优先级排序
        sorted_modules = sorted(selected, key=lambda m: m.priority)

        # 3. 组装内容
        parts = [m.content for m in sorted_modules]
        return "\n\n".join(parts)

    def build_stable(self) -> str:
        """构建稳定部分（不含动态工具）"""
        cache_key = self._make_cache_key()
        if self._stable_cache and self._cache_key == cache_key:
            return self._stable_cache

        self._stable_cache = self.build(exclude_dynamic=True)
        self._cache_key = cache_key
        return self._stable_cache

    def _make_cache_key(self) -> str:
        """生成稳定缓存键（SHA256）"""
        import hashlib
        key_data = "".join(m.content for m in self.modules if m.enabled)
        return hashlib.sha256(key_data.encode()).hexdigest()

    def rebuild_on_tool_add(self, tool_description: str) -> str:
        """动态添加工具时重建提示词"""
        # 更新工具模块内容
        self._update_tools_module(tool_description)
        # 重建稳定部分
        self._stable_cache = None
        return self.build_stable()

# Excel 配置加载
def load_from_excel(path: str) -> list[PromptModule]:
    """从 Excel 加载模块配置"""
    import pandas as pd
    df = pd.read_excel(path)
    modules = []
    for row in df.itertuples():
        modules.append(PromptModule(
            name=row.name,
            content=row.content,
            priority=row.priority,
            token_estimate=row.token_estimate,
            category=row.category,
            enabled=row.enabled
        ))
    return modules
```

**预期效果**:
- 提示词可配置：用户可通过 Excel 自定义
- 提示词可组合：按场景选择不同模块组合
- Token 可控：风格预设精确控制 Token 消耗
- 缓存高效：稳定部分缓存减少重复计算

---

### v0.7.7 - Prefix Caching 优化 ✅

**目标**: 实现 LLM API 的 prefix caching，减少重复发送稳定部分的 token 消耗。

**背景**:
v0.7.6 实现了模块化提示词系统，已有 `build_stable()` 和 `build_dynamic()` 方法。但这些方法的结果只是字符串拼接，没有真正利用 LLM API 的 caching 能力。Anthropic Claude 支持 Prompt Caching，OpenAI 支持自动缓存。

**架构归属**: LLM 层 + Memory 层

**任务列表**:

**1. Message 类扩展 (P0)**:
- [x] 添加 `cache_control` 字段 - 支持 Anthropic API
- [x] 添加 `with_cache_control()` 工厂方法

**2. LLM 接口扩展 (P0)**:
- [x] `LLMUsage` 添加 `cache_read_tokens` 和 `cache_write_tokens` 字段
- [x] `BaseLLM` 添加 `supports_explicit_caching` 属性
- [x] `BaseLLM.chat()` 添加 `system_stable` 参数

**3. AnthropicLLM 客户端 (P0)**:
- [x] 创建 `nano_agent/llm/anthropic.py`
- [x] 支持 `cache_control: {"type": "ephemeral"}` 参数
- [x] 解析缓存命中信息

**4. OpenAICompatibleLLM 优化 (P1)**:
- [x] 支持 `system_stable` 参数
- [x] 保证消息前缀稳定性（触发自动缓存）

**5. Memory 层扩展 (P1)**:
- [x] `ShortTermMemory` 添加 `stable_system_prompt` 字段
- [x] 添加 `set_stable_system_prompt()` 方法
- [x] 添加 `get_stable_system_prompt()` 方法
- [x] 添加 `get_messages_without_system()` 方法
- [x] `HybridMemory` 同步支持

**6. 配置支持 (P2)**:
- [x] `PromptConfig` 添加 `enable_caching` 字段

**7. Agent 层集成 (P1)**:
- [x] `_setup_prompt_builder()` 设置 stable prompt 到 memory
- [x] `_think()` 传递 `system_stable` 给 LLM

**新增文件**:
```
nano_agent/llm/anthropic.py      # AnthropicLLM 客户端
tests/test_prefix_caching.py     # 21 个测试用例
```

**修改文件**:
```
nano_agent/llm/messages.py       # cache_control 字段
nano_agent/llm/base.py           # LLMUsage 缓存字段, supports_explicit_caching
nano_agent/llm/openai_compatible.py  # system_stable 参数
nano_agent/llm/ollama.py         # system_stable 参数（忽略）
nano_agent/llm/__init__.py       # 导出 AnthropicLLM
nano_agent/memory/base.py        # get_stable_system_prompt()
nano_agent/memory/short_term.py  # stable_system_prompt 字段
nano_agent/memory/hybrid.py      # 同步支持
nano_agent/agent/react.py        # _think() 集成 caching
nano_agent/config/schema.py      # enable_caching 配置
nano_agent/cli/main.py           # /config 显示 enable_caching
```

**技术方案**:
```python
# nano_agent/llm/messages.py
@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    cache_control: dict | None = None  # 用于 Anthropic Prompt Caching

    @classmethod
    def with_cache_control(cls, role, content, cache_type="ephemeral"):
        return cls(role=role, content=content, cache_control={"type": cache_type})

# nano_agent/llm/anthropic.py
class AnthropicLLM(BaseLLM):
    supports_explicit_caching = True

    def chat(self, messages, tools=None, system_stable=None):
        if system_stable:
            system_content = [{
                "type": "text",
                "text": system_stable,
                "cache_control": {"type": "ephemeral"}
            }]
        # ... 调用 Anthropic API

# nano_agent/agent/react.py
def _think(self):
    system_stable = None
    if self.prompt_config.enable_caching and self._stable_system_prompt:
        system_stable = self._stable_system_prompt

    response, tool_calls, usage = self.llm.chat(
        messages=messages,
        tools=tools_schema,
        system_stable=system_stable,
    )

    if usage.cache_read_tokens > 0:
        print(f"[Caching] Cache hit: {usage.cache_read_tokens} tokens saved")
```

**各 API Caching 机制**:
| API | 机制 | 参数 | 缓存条件 |
|-----|------|------|----------|
| Anthropic Claude | Prompt Caching | `cache_control: {"type": "ephemeral"}` | 显式标记 |
| OpenAI | Automatic Caching | 无需参数 | >= 1024 tokens |
| DeepSeek | Context Caching | 无需参数 | 类似 OpenAI |
| Ollama | 不支持 | - | - |

**预期效果**:
- Anthropic: 显式 caching，可看到 `cache_read_input_tokens`
- OpenAI: 自动 caching，通过 prompt_tokens 减少体现
- 第二轮请求节省 ~50% input tokens

---

### v0.7.8 - Token 优化增强 ✅

**目标**: 进一步优化 Token 消耗，实现 Tool Caching、动态模块激活和 Token Budget 集成。

**背景**:
v0.7.7 实现了 system prompt 的 Prefix Caching，但 tool definitions 仍未缓存。同时，environment/git_status 模块始终携带或始终禁用，无法按需激活。Token Budget 也缺乏与实际 LLMUsage 的反馈闭环。

**架构归属**: LLM 层 + Prompt 层 + Token 管理

**任务列表**:

**1. Tool Definitions Caching (P1)**:
- [x] 修改 `AnthropicLLM._format_tools()` - 添加 `cache_control` 参数
- [x] 在最后一个 tool definition 上添加 `cache_control: {"type": "ephemeral"}`
- [x] 添加 `cache_tools` 参数到 `chat()` 和 `chat_stream()`
- [x] 测试验证 - 10 个测试用例

**2. Dynamic Module Activation (P2)**:
- [x] 创建 `IntentDetector` 类 - 关键词匹配意图检测
- [x] 定义 git_status 和 environment 关键词列表
- [x] 修改 `PromptBuilder.build_dynamic()` - 支持 `user_input` 参数
- [x] 基于意图检测动态激活 git/environment 模块
- [x] 测试验证 - 22 个测试用例

**3. Token Budget 与 LLMUsage 集成 (P3)**:
- [x] 扩展 `TokenBudget` - 添加 `_usage_history` 和 `_calibration_factor`
- [x] 实现 `consume_usage()` 方法 - 记录 LLMUsage 并更新校准
- [x] 实现动态校准算法 - 基于历史 usage 计算校准系数
- [x] 扩展 `TokenBudgetConfig` - 添加校准相关配置
- [x] 测试验证 - 26 个测试用例

**新增文件**:
```
nano_agent/agent/intent_detector.py  # IntentDetector 类
tests/test_tool_caching.py           # Tool Caching 测试
tests/test_intent_detector.py        # 意图检测测试
tests/test_token_budget_integration.py  # Budget 集成测试
```

**修改文件**:
```
nano_agent/llm/anthropic.py          # Tool caching
nano_agent/agent/prompt_builder.py   # Dynamic module activation
nano_agent/agent/token_budget.py     # LLMUsage 集成
```

**技术方案**:
```python
# nano_agent/llm/anthropic.py

def _format_tools(self, tools, cache_tools=True):
    """Format tools with optional cache_control."""
    formatted = []
    for i, tool in enumerate(tools):
        tool_def = {
            "name": tool["function"]["name"],
            "description": tool["function"]["description"],
            "input_schema": tool["function"]["parameters"]
        }
        # Add cache_control to last tool
        if cache_tools and i == len(tools) - 1:
            tool_def["cache_control"] = {"type": "ephemeral"}
        formatted.append(tool_def)
    return formatted

# nano_agent/agent/intent_detector.py

class IntentDetector:
    KEYWORDS = {
        "git_status": ["提交", "commit", "push", "pull", "merge", "分支", "branch"],
        "environment": ["环境变量", "env", "配置文件", "config", ".env"],
    }

    def detect(self, user_input: str) -> set[str]:
        detected = set()
        for intent, keywords in self.KEYWORDS.items():
            if any(kw in user_input.lower() for kw in keywords):
                detected.add(intent)
        return detected

# nano_agent/agent/token_budget.py

class TokenBudget:
    def consume_usage(self, usage: LLMUsage) -> None:
        """Consume tokens and record for calibration."""
        self._usage_history.append(usage)
        self.consume(usage.total_tokens)
        self._update_calibration()

    def _update_calibration(self) -> None:
        """Update calibration factor based on usage history."""
        if len(self._usage_history) >= self.config.min_calibration_samples:
            avg_actual = sum(u.total_tokens for u in self._usage_history) / len(self._usage_history)
            expected_per_call = self.initial_budget / 10
            self._calibration_factor = avg_actual / expected_per_call
```

**预期效果**:
- Tool Caching: 10 轮对话节省 90% tools tokens
- Dynamic Module: 纯问答场景节省 100% git/environment tokens
- Budget 集成: 预算基于实际使用校准，减少过早耗尽

---

### v0.7.9 - Agent/Monitoring/CLI 解耦与斜杠命令统一 ✅

**目标**: 解耦 Agent 与 Monitoring 层的直接依赖，统一斜杠命令格式。

**背景**:
Agent 层（react.py）直接调用 tracker 的具体方法（record_llm_call），导致两层紧耦合。当 tracker API 变更时，agent 层也需同步修改。通过引入 RawData 容器，agent 只需传递原始数据，由 tracker 自行提取和转换。

**架构归属**: 基础设施层 - 层间解耦

**任务列表**:

**1. RawData 容器 (P0)**:
- [x] 创建 `RawLLMCallData` 数据类 - 封装 LLM 调用原始数据
- [x] 创建 `RawToolExecutionData` 数据类 - 封装工具执行原始数据
- [x] Agent 传递原始对象而非提取字段

**2. Tracker 解耦 API (P0)**:
- [x] 实现 `record_raw_llm_call()` 方法 - 接收 RawLLMCallData
- [x] 实现 `record_raw_tool_execution()` 方法 - 接收 RawToolExecutionData
- [x] Tracker 内部处理类型转换和字段提取
- [x] 新增 `record_skipped_tool_call()` 方法 - 记录跳过的工具调用

**3. Metrics 扩展 (P1)**:
- [x] `LLMCallMetrics` 添加 `tools_schema` 字段 - 支持工具定义 Token 分类
- [x] 新增 `SkippedToolCall` 数据类 - 记录跳过原因（routing_limit/merged/duplicate/budget_exceeded）
- [x] `IterationMetrics` 添加 `skipped_tool_calls` 字段
- [x] `RunMetrics` 添加 `run_number` 字段 - 全局轮次编号

**4. 斜杠命令格式统一 (P1)**:
- [x] 统一所有命令使用 `/` 前缀
- [x] 新增 `/usage` 命令 - 显示上下文组成明细
- [x] 新增 `/context` 命令 - 显示上下文预算
- [x] `/stats` 增强 - 显示轮次计数、当前上下文大小
- [x] 配置显示中文化

**5. 渐进式预算警告 (P1)**:
- [x] `TokenBudgetConfig` 扩展多级警告阈值
- [x] 实现 `check_warning()` 方法 - 按阈值触发不同级别警告
- [x] 重复工具调用检测 - `_tool_call_history` + `_check_duplicate_tool_call()`
- [x] 跳过的工具调用记录为 `SkippedToolCall`

**6. 文档与测试**:
- [x] 创建 `docs/architecture.md` - 架构文档
- [x] 创建 `docs/constraints.md` - 资源约束参考
- [x] 新增 `tests/test_cli_main.py` - 935 个 CLI 测试用例
- [x] 新增 `tests/test_memory_interface.py` - 接口一致性测试
- [x] BUGLIST.md 记录历史 BUG

**新增文件**:
```
nano_agent/monitoring/
├── raw_data.py              # RawLLMCallData, RawToolExecutionData
docs/
├── architecture.md           # 架构文档
├── constraints.md            # 资源约束参考
tests/
├── test_cli_main.py          # 935 测试用例
├── test_memory_interface.py  # 接口一致性测试
```

**修改文件**:
```
nano_agent/agent/react.py            # 使用 RawData API, 重复检测
nano_agent/monitoring/tracker.py      # record_raw_* API, 多级警告
nano_agent/monitoring/metrics.py      # SkippedToolCall, tools_schema
nano_agent/cli/main.py               # /usage, /context, 中文化
nano_agent/agent/token_budget.py     # 多级警告配置
nano_agent/config/schema.py          # 新配置字段
```

---

### v0.7.10 - 柔化硬限制 ✅

**目标**: 将 ReAct 循环的硬限制柔化为动态软限制，避免过早终止。

**背景**:
ReAct 循环有多层硬限制（迭代次数、Token 预算、重复调用检测），这些限制经常过早触发终止。例如：预算归零时"突然猝死"，不给收尾机会；重复调用阈值不可配置；终止原因无记录。

**任务列表**:

**Phase 0: TerminationReason**:
- [x] 添加 `TerminationReason` 枚举到 `types.py`
- [x] 添加 `termination_reason` 字段到 `ExecutionResult`
- [x] 所有 8 个退出路径设置对应的终止原因

**Phase 1: 智能重复检测**:
- [x] 新建 `DuplicateDetector` 类 (`duplicate.py`)
- [x] 支持可配置 threshold (`duplicate_threshold`)
- [x] 支持 deep_equal 模式 (`duplicate_deep_equal`)
- [x] 替换 `react.py` 内联重复检测逻辑
- [x] 配置加载器解析新字段

**Phase 2: 预算收尾轮**:
- [x] 添加 wrapup 配置到 `TokenBudgetConfig`
- [x] 实现 `should_wrapup()` 方法
- [x] 在 `react.py` 循环中插入收尾逻辑
- [x] 配置加载器解析 wrapup 字段
- [x] 更新 `docs/constraints.md`

**新增/修改文件**:
```
nano_agent/agent/duplicate.py          # 新建
nano_agent/agent/types.py              # TerminationReason, AgentEvent
nano_agent/agent/react.py              # DuplicateDetector, wrap-up logic
nano_agent/agent/token_budget.py       # wrapup config + should_wrapup()
nano_agent/config/schema.py            # 新配置字段
nano_agent/config/loader.py            # smart_optimization 解析
tests/test_duplicate.py                # 15 tests
tests/test_budget_wrapup.py            # 13 tests
docs/constraints.md                    # 文档更新
```

**后续规划** (本轮不做):
- Phase 3: 增量感知迭代控制（stall detection）
- Phase 4: 置信度验证触发
- Phase 5: 按复杂度分配预算 profile

---

### v0.7.11 - 模型上下文窗口准确性 ✅

**目标**: 修复所有百分比决策的分母 —— 模型上下文窗口长度。

**背景**:
`LLMConfig.get_context_length()` 使用硬编码查找表，新增模型需手动更新；部分匹配可能匹配错误模型（如 `llama3` 匹配 `llama3.1`）；`ContextManager` 默认值硬编码 128000 而非从配置获取。这是特性树 0.1 生存条件级别的准确性缺陷 —— 窗口错了，压缩阈值和预算全部算错。

**架构归属**: 准确性线 - 决策分母

**任务列表**:

- [x] 重构 `LLMConfig.get_context_length()` - 支持 API 查询 + 配置覆盖 + fallback 链
- [x] 实现 Ollama `/api/show` 端点查询 - 获取模型实际 `context_length`
- [x] 实现 OpenAI `/models` 端点查询 - 获取模型 `context_window`
- [x] 修复部分匹配逻辑 - 防止 `llama3` 匹配 `llama3.1` 的不同长度
- [x] 实现 fallback 链 - API 查询 → 精确匹配 → 配置覆盖 → 保守默认 (8192)
- [x] 统一 `ContextManager` 的默认值 - 使用 `LLMConfig.get_context_length()` 而非硬编码 128000
- [x] 配置支持 - `llm.context_length` 显式覆盖优先

**新增文件**:
```
tests/
├── test_context_length.py       # 模型窗口准确性测试
```

**修改文件**:
```
nano_agent/config/schema.py          # get_context_length() 重构, fallback 链
nano_agent/llm/ollama.py             # /api/show 查询 context_length
nano_agent/llm/openai_compatible.py  # /models 查询 context_window
nano_agent/llm/base.py               # get_context_length() 抽象方法
nano_agent/agent/context.py          # 统一默认值
```

**预期效果**:

| 修复前 | 修复后 |
|--------|--------|
| 新模型/部分匹配错误 → 阈值/预算失效 | API 查询 + 安全 fallback |
| ContextManager 硬编码 128000 | 从配置获取实际窗口长度 |

---

### v0.7.12 - 决策点真实 Token ✅

**目标**: 上下文压力检测和压缩触发从估算切换到实际 prompt_tokens。

**背景**:
`ContextManager.check_and_compress()` 和 `MessageCompressor.should_compress()` 基于 `estimate_tokens()` 判断是否需要压缩。估算偏差 30-50% 时，压缩时机过晚（窗口溢出）或过早（浪费上下文）。这是特性树 0.2 场景完整性级别的缺陷。

**架构归属**: 准确性线 - 决策点数据源

**任务列表**:

- [x] `ContextManager.check_and_compress()` 增加 `last_prompt_tokens` 参数
- [x] 优先使用实际 `prompt_tokens`，fallback 到 `estimate_tokens()`
- [x] `MessageCompressor.should_compress()` 同理增加 `last_prompt_tokens` 参数
- [x] `react.py._think()` 中传递 `usage.prompt_tokens` 给上下文管理器
- [x] 记录估算 vs 实际偏差日志 - 为后续校准闭环提供数据

**新增文件**:
```
tests/
├── test_real_token_decision.py  # 决策点真实 token 测试
```

**修改文件**:
```
nano_agent/agent/context.py          # 使用真实 prompt_tokens
nano_agent/agent/compressor.py       # 使用真实 prompt_tokens
nano_agent/agent/react.py            # 传递 usage.prompt_tokens, 记录估算偏差
```

**预期效果**:

| 修复前 | 修复后 |
|--------|--------|
| 压缩/压力检测基于猜测，偏差 30-50% | 基于实际数据，偏差 <5% |
| 过晚压缩 → 窗口溢出 | 准确触发压缩 |

---

### v0.7.13 - 统一截断比率与校准闭环 ✅

**目标**: 修复中文场景截断丢信息 + 修正校准公式并让闭环生效。

**背景**:
两个问题都是准确性缺陷，且互相关联 —— 校准系数用于调整估算准确度，截断比率依赖估算。特性树 0.2~0.3 层级。

1. **截断**: `react.py._observe()` 和 `compressor.py` 统一用 `max_tokens * 4`，中文场景（每字 ~2 token）截断过早丢信息。`result_summarizer.estimate_tokens()` 的 `len(text) // 4` 也不支持中文。
2. **校准**: 当前 `_calibration_factor = avg_actual / (budget/10)` 测量的是预算消耗率而非估算准确度，且校准系数从未被 `estimate_tokens()` 消费。

**架构归属**: 准确性线 - 截断 + 校准

**任务列表**:

**1. 统一截断比率 (P1)**:
- [x] `react.py._observe()` 中 `max_tokens * 4` → `calculate_max_chars()` 反算字符数
- [x] `compressor.py` 中 `summary_max_tokens * 4` → 同上
- [x] 消除 `result_summarizer.estimate_tokens()` 的 `len(text) // 4`，统一到 `token_utils.estimate_text_tokens()`
- [x] 激活 `SummarizerConfig.max_summary_tokens` 死字段 - 用 `calculate_max_chars()` 实施截断

**2. 校准闭环修复 (P1)**:
- [x] 修正校准公式 - `avg(actual / estimated)`
- [x] 在 `_think()` 中同时记录估算值和实际值 - 为校准提供数据
- [x] `estimate_tokens()` 增加 `calibration_factor` 参数 - 乘以返回值
- [x] `should_compress()` 和 `check_and_compress()` 使用校准后估算
- [x] 校准系数值域限制 - clamp 到 [0.5, 2.0]，防止异常值
- [x] 除零保护 + 最低采样次数 (≥3 次)

**新增文件**:
```
tests/
├── test_truncation_ratio.py     # 截断比率测试
├── test_calibration_loop.py     # 校准闭环测试
```

**修改文件**:
```
nano_agent/agent/react.py            # 截断比率修复, 记录估算值
nano_agent/agent/compressor.py       # estimate_text_tokens() 截断
nano_agent/agent/token_utils.py      # calibration_factor 参数
nano_agent/agent/token_budget.py     # 校准公式修正, 闭环生效
nano_agent/agent/result_summarizer.py # 统一到 estimate_text_tokens()
```

**预期效果**:

| 修复项 | 修复前 | 修复后 |
|--------|--------|--------|
| 截断比率 | 中文场景截断丢信息 | 中英混合正确截断 |
| 校准闭环 | 校准系数死指标，偏差 30% | 闭环生效，偏差收敛到 5% |

---

### v0.7.14 - 预判机制

**目标**: 简单问题不走 ReAct 循环，节省 ~90% token。

**背景**:
特性树 1.3.2 — 0.2 场景完整性：问候、感谢、简单事实查询等无需工具调用的问题，仍走完整 Think→Act→Observe 循环，浪费大量 token。预判机制可在 ReAct 循环前用极简提示词（~50 tokens）判断复杂度，简单问题直接回答。

**架构归属**: 效率线 - 循环层

**任务列表**:

- [x] 实现 `QueryPrejudgment` 类 - 预判问题复杂度
- [x] 定义极简预判提示词 - ~50 tokens
- [x] 实现简单问题直接回答 - 不走 ReAct 循环
- [x] 实现中等复杂度限制 - 最多 1 次工具调用
- [x] 与现有 QueryRouter 协同 - 规则优先，LLM 补充
- [x] 配置支持 - `prejudgment.enabled`、`prejudgment.simple_prompt`

**新增文件**:
```
nano_agent/agent/
├── prejudgment.py               # QueryPrejudgment 类
tests/
├── test_prejudgment.py          # 预判机制测试
```

**修改文件**:
```
nano_agent/config/schema.py          # PrejudgmentConfig
nano_agent/agent/react.py            # 集成预判机制
```

**预期效果**:

| 场景 | Token 节省 |
|------|-----------|
| 简单问题（问候、感谢、事实查询） | ~90% |

---

### v0.7.15 - 激进输出精简与工具输出标准化

**目标**: 减少 LLM 输出冗余 + 统一工具输出结构。

**背景**:
两个优化都作用于输出层，收益互补：
1. **激进输出精简**: LLM 输出包含冗余格式（表格、emoji、列表），每轮 ~200 token 可降到 ~30 token
2. **工具输出标准化**: 工具输出是自由格式字符串，LLM 需要额外解析和记忆，标准化后可减少 70-90% token

**架构归属**: 效率线 - 输出层

**任务列表**:

**1. 激进输出精简 (P1)**:
- [x] 定义 `AggressiveOutputConfig` 配置 - mild/aggressive/extreme 三级
- [x] 实现输出格式约束提示词 - 一句话、无表格、无列表、无 emoji
- [x] 实现 `OutputSimplifier` 类 - 后处理强制精简
- [x] 实现 emoji/Markdown 过滤 - 正则清理
- [x] 实现长度截断策略 - 按字数限制
- [x] 配置支持 - `aggressive_output.enabled`、`aggressive_output.level`

**2. 工具输出标准化 (P1)**:
- [x] 定义 `StandardToolOutput` 数据类 - 统一输出结构
- [x] 定义 `OutputFormat` 枚举 - structure/list/status/content/error
- [x] 重构 `file_read` 工具 - 输出 imports/classes/functions 结构
- [x] 重构 `shell_execute` 工具 - 解析 ls/git 等常见命令输出
- [x] 重构 `file_search` 工具 - 输出分组统计结果
- [x] 实现 `to_llm_message()` 方法 - 转换为精简 LLM 消息
- [x] 配置支持 - `standardized_output.enabled`、`standardized_output.detailed`

**新增文件**:
```
nano_agent/agent/
├── output_simplifier.py         # OutputSimplifier 类
nano_agent/tools/
├── standard_output.py           # StandardToolOutput, OutputFormat
tests/
├── test_output_simplifier.py    # 输出精简测试
├── test_standard_output.py      # 标准化输出测试
```

**修改文件**:
```
nano_agent/config/schema.py          # AggressiveOutputConfig, StandardizedOutputConfig
nano_agent/tools/builtin/file_ops.py # 标准化输出
nano_agent/tools/builtin/shell.py    # 标准化输出
```

**预期效果**:

| 优化项 | 场景 | Token 节省 |
|--------|------|-----------|
| 激进输出精简 | 快速查询、状态确认 | ~80% |
| 工具输出标准化 | file_read/shell_execute | ~70-90% |

---

### v0.7.16 - 复杂度预算 Profile 与 Stall Detection ✅

**目标**: 小任务不浪费预算 + 无进展时转向。

**背景**:
两个 feature 都作用于循环层，影响 ReAct 执行策略：
1. **复杂度预算 Profile**: 当前所有任务使用同一预算，SIMPLE 任务浪费 50K+，COMPLEX 任务不够用。按 QueryRouter 分类结果分配不同预算。
2. **Stall Detection**: v0.7.10 实现了 Phase 0-2（柔化终止），Phase 3 Stall Detection 被推迟。无进展时死磕浪费 token，应注入提示转向。

**架构归属**: 效率线 - 循环层

**任务列表**:

**1. 复杂度预算 Profile (P1)**:
- [x] `QueryRouter.classify()` 结果传递给 `TokenBudget`
- [x] 按复杂度预设预算 - SIMPLE=15K / MODERATE=60K / COMPLEX=120K
- [x] 可配置预算映射表 - 非硬编码
- [x] `RoutingResult` 增加 `suggested_budget_ratio` 字段

**2. Stall Detection (P2)**:
- [x] 实现 `StallDetector` 类 - 检测迭代无进展
- [x] 定义进展度量 - 工具结果差异度、新信息量
- [x] 连续 N 次无进展时触发转向 - 注入提示让 LLM 换策略
- [x] 配置支持 - `stall_detection.enabled`、`stall_detection.patience`

**新增文件**:
```
nano_agent/agent/
├── stall_detector.py            # StallDetector 类
tests/
├── test_complexity_budget.py    # 复杂度预算测试
├── test_stall_detector.py       # Stall Detection 测试
```

**修改文件**:
```
nano_agent/agent/router.py           # RoutingResult 增加 suggested_budget_ratio
nano_agent/agent/token_budget.py     # 按复杂度分配预算
nano_agent/agent/react.py            # Stall Detection 集成
nano_agent/config/schema.py          # ComplexityBudgetConfig, StallDetectionConfig
```

**预期效果**:

| 优化项 | 场景 | 效果 |
|--------|------|------|
| 复杂度预算 Profile | SIMPLE 任务 | 避免浪费 50K+ 预算 |
| Stall Detection | 迭代无进展 | 避免无效消耗，转向新策略 |

---

### v0.7.17 - 多轮缓存与 Tool Offloading

**目标**: 跨轮次工具结果复用 + 大结果不撑爆窗口。

**背景**:
两个 feature 都作用于数据流层，解决 token 量的硬约束问题：
1. **多轮缓存**: 当前 `ToolResultCache` 仅限单次工具调用，跨轮次重复调用相同工具浪费 token。扩展为跨轮次缓存，基于文件修改时间失效。
2. **Tool Offloading**: `web_search` 返回 200KB 结果直接注入消息窗口，撑爆上下文。超过阈值时写入临时文件，注入精简摘要 + 路径引用。

**架构归属**: 效率线 - 缓存层 + 数据流

**任务列表**:

**1. 多轮对话增量缓存 (P2)**:
- [x] 扩展 `ToolResultCache` - 支持跨轮次缓存
- [x] 实现缓存持久化 - 会话结束时保存到磁盘
- [x] 实现缓存预热 - 会话恢复时加载历史缓存
- [x] 实现缓存失效策略 - 基于文件修改时间
- [x] 配置支持 - `cache.persist`、`cache.warmup`

**2. Tool Output Offloading (P2)**:
- [x] 当 tool output > offload_threshold 时写入 `/tmp/`，注入 `{path, summary, size}`
- [x] 工具声明 `can_offload` 标记 - file_read/file_search/shell_execute/python_execute/web_search
- [x] 系统提示词告知 LLM 可 `file_read(path)` 按需加载全文
- [x] 会话结束时清理 offload 文件
- [x] 配置支持 - `offload.enabled`、`offload.size_threshold_tokens`

**新增文件**:
```
nano_agent/agent/
├── tool_offload.py               # ToolOffloadManager
tests/
├── test_multi_turn_cache.py      # 跨轮次缓存测试
├── test_tool_offload.py          # Offloading 测试
```

**修改文件**:
```
nano_agent/agent/cache.py            # 跨轮次缓存
nano_agent/agent/react.py            # 集成 offload + cache
nano_agent/tools/base.py             # can_offload 属性
nano_agent/tools/builtin/file_ops.py # can_offload=True
nano_agent/tools/builtin/shell.py    # can_offload=True
nano_agent/tools/builtin/python_executor.py # can_offload=True
nano_agent/tools/builtin/web_search.py # can_offload=True
nano_agent/config/schema.py          # ToolOffloadConfig, CacheConfig 扩展
nano_agent/config/loader.py          # 配置解析
nano_agent/core/builder.py           # 配置传递
nano_agent/cli/main.py               # 配置显示
```

**预期效果**:

| 优化项 | 场景 | 效果 |
|--------|------|------|
| 多轮缓存 | 重复工具调用 | ~30% Token 节省 |
| Tool Offloading | web_search 大结果 | 防止窗口撑爆 |

---

### v0.7.18 - 估算审计与准确性增强

**目标**: 校准闭环的验证环节 + 估算准确性提升。

**背景**:
v0.7.13 修复了校准公式并让闭环生效，但缺少验证机制 —— 不知道校准收敛了没有。同时 `PromptModule.token_estimate` 硬编码、`base_ratio` 首轮偏差等问题仍存在。

**架构归属**: 准确性线 - 校准验证 + 估算增强

**任务列表**:

**1. 估算 vs 实际对比机制 (P1)**:
- [x] 每次 LLM 调用后记录 `estimate_tokens(messages) vs usage.prompt_tokens` 偏差
- [x] 日志/指标记录估算偏差 - 可在 `/stats estimation` 中查看
- [x] 基于偏差的自动校准 - 驱动校准系数更新
- [x] 偏差过大时告警 - 估算偏差 >50% 时记录 warning

**2. 估算准确性增强 (P2)**:
- [x] `PromptModule.token_estimate` 动态计算 - 基于 `estimate_text_tokens()` 而非硬编码
- [x] `result_summarizer` 截断使用校准后估算
- [x] `base_ratio` 首轮偏差修正 - 排除首轮 prompt_tokens 偏高对 base_ratio 的影响

**新增文件**:
```
nano_agent/agent/
├── estimation_audit.py          # EstimationAudit 类
tests/
├── test_estimation_audit.py     # 估算审计测试
```

**修改文件**:
```
nano_agent/agent/react.py            # 记录估算偏差
nano_agent/agent/token_utils.py      # 动态 PromptModule 估算
nano_agent/agent/result_summarizer.py # 校准后估算
nano_agent/monitoring/tracker.py     # base_ratio 首轮修正
nano_agent/monitoring/token_analyzer.py # 估算偏差统计
```

**预期效果**:

| 优化项 | 修复前 | 修复后 |
|--------|--------|--------|
| 估算 vs 实际对比 | 校准收敛不可观测 | 偏差可查看，>50% 告警 |
| 估算准确性增强 | PromptModule 硬编码，base_ratio 首轮偏差 | 动态估算，排除首轮干扰 |

---

### v0.7.19 - 语义压缩 ✅

**目标**: 合并相似历史消息，长对话场景节省 ~20% token。

**背景**:
三层压缩已覆盖结构性压缩（上下文压力 → 压缩 → 摘要），但未处理语义重复 —— 多轮对话中用户反复问相似问题，历史消息存在语义冗余。语义压缩通过 embedding 相似度检测并合并重复内容。

这是效率线最后一个未实现的 feature，依赖 embedding API，属于 P3 优先级。前置条件（校准闭环、估算审计）已在前序版本完成。

**架构归属**: 效率线 - 语义层

**任务列表**:

- [x] 实现 `SemanticCompressor` 类 - 合并相似历史消息
- [x] 集成 embedding 模型 - 计算消息相似度（Ollama / sentence-transformers / OpenAI）
- [x] 实现相似消息合并策略 - 保留最早消息 + merge_tag 标注
- [x] 配置支持 - `semantic_compressor.enabled`、`semantic_compressor.similarity_threshold`

**新增文件**:
```
nano_agent/llm/
├── embedding.py                   # BaseEmbeddingClient + Ollama/sentence-transformers/OpenAI 实现
nano_agent/agent/
├── semantic_compressor.py         # SemanticCompressor 类
tests/
├── test_embedding.py              # 8 个测试
├── test_semantic_compressor.py    # 16 个测试
```

**修改文件**:
```
nano_agent/config/schema.py          # SemanticCompressorConfig
nano_agent/config/loader.py          # 解析/保存逻辑
nano_agent/core/builder.py           # 传递 semantic_compressor_config
nano_agent/agent/react.py            # _think() 第二遍压缩
nano_agent/llm/__init__.py           # embedding exports
nano_agent/agent/__init__.py         # SemanticCompressor exports
nano_agent/cli/main.py              # /config 显示
pyproject.toml                       # v0.7.19 + optional embedding dep
```

**预期效果**:

| 场景 | Token 节省 |
|------|-----------|
| 长对话重复提问 | ~20% |

---

### v0.8.0 - 指数退避重试与熔断降级 ✅

**目标**: 最小粒度的生产兜底：429/500 自动退避 + 异常行为熔断降级。

**背景**:
Agent 管控体系审计发现 Stability 稳控层完全缺失（8/16 完整，1/16 缺失）。P0 优先级 — 无限流/熔断/退避/成本上限，API 调用失控导致成本爆炸或服务不可用。本版本先实现最轻量的兜底：指数退避重试和熔断降级（替代 Token 硬上限）。

**架构归属**: Runtime 层 - Stability 稳控 (P0)

**任务列表**:
- [x] #3 指数退避重试 (`nano_agent/llm/retry.py`) — 429/500 等错误自动退避重试
- [x] #4 熔断器 + 用户介入降级 (`nano_agent/agent/circuit_breaker.py`) — 异常行为检测后 AUTO→SUPERVISED 降级

---

### v0.8.1 - LLM API 限流器 ✅

**目标**: 防止突发请求打爆 API。

**架构归属**: Runtime 层 - Stability 稳控 (P0)

**任务列表**:
- [x] #1 LLM API 限流器 (`nano_agent/llm/rate_limiter.py`) — 调用频率限制

---

### v0.8.2 - 熔断器 (已合并到 v0.8.0)

**目标**: 已在 v0.8.0 中实现 — 异常行为检测后 AUTO→SUPERVISED 降级。

**架构归属**: Runtime 层 - Stability 稳控 (P0)

**任务列表**:
- [x] #2 熔断器 (`nano_agent/agent/circuit_breaker.py`) — 已实现，合并到 v0.8.0

---

### v0.8.3 - 输入净化 ✅

**目标**: 输入层安全防护。

**背景**:
Agent 管控体系审计发现 Sanitize 净化层仅 prompt 级软防护 + 确认拦截，缺少独立的输入清洗层。P1 优先级 — Prompt injection → agent 行为被劫持。

**架构归属**: Input 层 - Sanitize 净化 (P1)

**任务列表**:
- [x] #5 Prompt injection 特征过滤 (`nano_agent/agent/sanitizer.py`) — 硬性拦截 "ignore previous" / jailbreak 模板等特征模式
- [x] #6 输入长度/格式校验 (`nano_agent/agent/sanitizer.py`) — 超长输入截断、异常格式拒绝

**新增文件**:
```
nano_agent/agent/
├── sanitizer.py              # InputSanitizer, SanitizerResult
tests/
├── test_sanitizer.py         # 47 测试用例
```

**修改文件**:
```
nano_agent/config/schema.py          # SanitizerConfig + Config 字段
nano_agent/agent/types.py            # INPUT_REJECTED 枚举 (TerminationReason + AgentEvent)
nano_agent/agent/__init__.py         # 导出
nano_agent/agent/orchestrator.py     # sanitizer 集成到 run()
nano_agent/core/builder.py           # sanitizer 配置接线
nano_agent/cli/main.py               # 交互循环拒绝处理 + 配置显示 + 默认配置
```

**技术方案**:
```python
# nano_agent/config/schema.py

@dataclass
class SanitizerConfig:
    enabled: bool = True
    injection_patterns: list[str]  # 18 个默认中英文注入模式
    custom_patterns: list[str]     # 用户自定义扩展
    max_input_length: int = 10000
    length_action: Literal["truncate", "reject"] = "truncate"
    reject_null_bytes: bool = True
    reject_control_chars: bool = True
    max_line_length: int = 5000

# nano_agent/agent/sanitizer.py

class InputSanitizer:
    def sanitize(user_input) -> SanitizerResult:
        # 1. 格式检查 → null bytes 拒绝 + control chars 剥离
        # 2. 注入检查 → 正则匹配，命中硬拒绝
        # 3. 长度检查 → 截断或拒绝

# nano_agent/agent/orchestrator.py

def run(user_input):
    if self.sanitizer and self.sanitizer.enabled:
        result = self.sanitizer.sanitize(user_input)
        if result.rejected:
            return ExecutionResult(success=False, termination_reason=INPUT_REJECTED)
        user_input = result.sanitized_input
```

**预期效果**:

| 防护项 | 场景 | 效果 |
|--------|------|------|
| Prompt injection 过滤 | "ignore previous instructions" | 硬拦截，不走 ReAct |
| Null bytes | 含 \x00 的输入 | 拒绝 |
| Control chars | ANSI escape | 剥离后继续 |
| 超长输入 | > 10000 字符 | 截断或拒绝 |

---

### v0.8.4 - PII 脱敏 ✅

**目标**: 敏感信息自动脱敏（可选）。

**架构归属**: Input 层 - Sanitize 净化 (P1)

**任务列表**:
- [x] #7 PII 脱敏 (`nano_agent/agent/sanitizer.py`) — 手机号/身份证/API key 等敏感信息自动脱敏

**实现细节**:

PII 脱敏作为 `InputSanitizer` 的子功能，在格式校验后、注入检测前执行。默认关闭（`pii_enabled: false`）。

**支持的 PII 类型**:
| 类型 | 说明 | 示例 |
|------|------|------|
| phone | 中国手机号 (1xx-xxxx-xxxx) | 138\*\*\*\*5678 |
| id_card | 中国身份证 (18位) | 110\*\*\*\*\*\*\*\*\*\*\*1234 |
| email | 邮箱地址 | t\*\*\*@example.com |
| api_key | API Key/Token (Bearer/sk-/pk-/ghp_/AKIA等) | sk-\*\*\*\*abcd |

**脱敏模式**:
- partial: 保留首尾字符，中间替换为掩码字符（默认）
- full: 全部替换为掩码字符

**重叠检测**: 手机号模式可能匹配身份证号子串。`PIIDesensitizer` 自动检测重叠匹配，保留更长的匹配。

**配置示例**:
```yaml
sanitizer:
  enabled: true
  pii_enabled: true
  pii_mask_mode: partial
  pii_mask_char: "*"
  pii_types: ["phone", "id_card", "email", "api_key"]
```

**新增/修改文件**:
```
nano_agent/agent/sanitizer.py          # PIIDesensitizer, PIIMatch 类
nano_agent/config/schema.py            # SanitizerConfig 扩展 pii_* 字段
nano_agent/agent/orchestrator.py       # last_sanitizer_result 属性
nano_agent/cli/main.py                 # PII 配置显示 + 交互脱敏通知
tests/test_sanitizer.py                # 32 个 PII 测试用例
```

---

### v0.8.5 - 输出护栏 ✅

**目标**: 输出层安全防护。

**背景**:
Agent 管控体系审计发现 Guard 护栏层中间件框架存在但安全规则稀疏，仅依赖确认机制。P1 优先级 — 敏感信息泄露 / 有害输出。

**架构归属**: Output 层 - Guard 护栏 (P1)

**任务列表**:
- [x] #8 输出敏感信息拦截 (`nano_agent/agent/output_guard.py`) — 拦截 API key / 密码 / token 等泄露
- [x] #10 中间件安全规则扩充 (`nano_agent/tools/middleware.py` 扩展) — 当前仅确认拦截，需补充自动拦截规则

---

### v0.8.6 - 有害内容过滤 ✅

**目标**: 输出内容安全检查（可选）。

**架构归属**: Output 层 - Guard 护栏 (P1)

**任务列表**:
- [x] #9 有害内容过滤 (`nano_agent/agent/harmful_filter.py`) — 输出内容安全检查

**实现细节**:

独立模块 `HarmfulContentFilter`，与 OutputGuard 互补（防信息泄露 vs 防有害内容）。

**有害内容类别**:
| 类别 | severity | 中英文模式 |
|------|----------|-----------|
| violence | high | 制造炸弹/武器指令 |
| hate | high | 仇恨言论+暴力 |
| dangerous | high | 自杀/毒品/黑客指令 |
| illegal | medium | 洗钱/伪造指令 |

**动作模型**: block（拦截）/ warn（警告放行）/ replace（替换），按类别可配。

**新增文件**:
```
nano_agent/agent/harmful_filter.py   # HarmfulContentFilter, HarmfulMatch, HarmfulFilterResult
tests/test_harmful_filter.py          # 70 个测试用例
```

**修改文件**:
```
nano_agent/agent/types.py             # TerminationReason.HARMFUL_CONTENT_BLOCKED, AgentEvent.HARMFUL_CONTENT_DETECTED
nano_agent/agent/orchestrator.py      # harmful_filter 参数和管线步骤
nano_agent/agent/__init__.py          # 导出新模块
nano_agent/core/builder.py            # 创建和传递 harmful_filter
nano_agent/tools/middleware.py        # HarmfulContentMiddleware (priority=99)
nano_agent/config/schema.py           # HarmfulContentFilterConfig
nano_agent/cli/main.py                # CLI 拦截提示、结果通知、配置显示
```

**预期效果**:
- 默认关闭（opt-in），4 类有害内容检测
- 保守模式：仅匹配明确的指令性短语，避免误报

---

### v0.8.7 - 结果正确性验证 ✅

**目标**: 业务语义校验。

**背景**:
Agent 管控体系审计发现 Validate 校验层仅格式+置信度，无业务语义校验。P2 优先级。

**架构归属**: Output 层 - Validate 校验 (P2)

**任务列表**:
- [x] #11 结果正确性验证 hook (`nano_agent/agent/result_validator.py`) — 文件路径是否存在、代码是否可编译、命令是否真正执行成功

**实现细节**:

独立模块 `ResultValidator`，在 Orchestrator 管线中 OutputGuard 和 HarmfulContentFilter 之后执行。

**验证检查类型**:
| 检查类型 | 说明 | 严重度 |
|----------|------|--------|
| file_exists | Agent 声称创建了文件 → 验证路径是否存在 | high |
| code_syntax | Agent 声称代码正确 → 验证 Python/JSON/YAML 语法 | medium |
| command_success | Agent 声称命令成功 → 检查输出中是否有矛盾的非零退出码 | high/low |

**失败动作模式**: block（拦截）/ warn（警告放行）/ annotate（标注附注），按配置可配。

**配置示例**:
```yaml
result_validator:
  enabled: true
  checks: ["file_exists", "code_syntax", "command_success"]
  on_fail: annotate
  on_pass: silent
```

**新增文件**:
```
nano_agent/agent/result_validator.py   # ResultValidator, ValidationCheck, ValidationResult
tests/test_result_validator.py          # 57 个测试用例
```

**修改文件**:
```
nano_agent/agent/types.py               # TerminationReason.VALIDATION_FAILED, AgentEvent.VALIDATION_FAILED
nano_agent/agent/orchestrator.py        # validator 参数和管线步骤
nano_agent/agent/__init__.py            # 导出新模块
nano_agent/core/builder.py             # 创建和传递 validator
nano_agent/config/schema.py            # ResultValidatorConfig
nano_agent/config/loader.py            # 文档注释
nano_agent/cli/main.py                 # CLI 拦截提示、结果通知、配置显示
pyproject.toml                          # v0.8.7
nano_agent/__init__.py                  # v0.8.7
```

**预期效果**:
- 默认关闭（opt-in），3 类验证检查
- 保守模式：仅验证明确的可验证声明，避免误报

---

### v0.8.8 - Schema-based 校验 ✅

**目标**: 工具返回值结构校验。

**架构归属**: Output 层 - Validate 校验 (P2)

**任务列表**:
- [x] #12 Schema-based 校验 — StandardToolOutput.data 按格式 schema 校验，不符则回退原始输出

**新增文件**:
```
tests/test_result_validator.py  # 新增 TestSchemaValidation (20 个测试用例)
```

**修改文件**:
```
nano_agent/tools/standard_output.py  # FORMAT_SCHEMAS 常量 + validate() 方法
nano_agent/agent/result_validator.py # validate_tool_output() + _check_schema_claims() 分发
nano_agent/agent/react.py            # _observe() 集成 schema 验证
nano_agent/config/schema.py          # checks 默认列表添加 "schema"
nano_agent/core/builder.py           # 注入 _result_validator 到 agent
```

---

### v0.8.9 - 反馈闭环 ✅

**目标**: 执行结果回流与自纠正。

**背景**:
Agent 管控体系审计发现 Feedback 反馈层监控审计存在但闭环断裂。P2 优先级 — 偏差信号未回流到执行策略层。

**架构归属**: Output 层 - Feedback 反馈 (P2)

**任务列表**:
- [x] #13 偏差信号回流 (`nano_agent/agent/feedback_loop.py`) — EstimationAudit 的偏差数据回流到执行策略层
- [x] #14 自纠正循环 (`nano_agent/agent/feedback_loop.py`) — 执行→校验→偏差→策略调整→重执行的显式闭环

**实现细节**:

**#13 偏差信号回流**:
- `FeedbackLoop.check_deviation()` 检查 EstimationAudit 偏差结果
- 偏差超过阈值时生成提示注入 LLM 上下文（与 StallDetector 模式一致）
- 冷却机制：每 N 次警告注入 1 次提示，防止上下文污染
- over（高估）→ 告知 LLM 缩短回复；under（低估）→ 告知 LLM 预算消耗更快
- 事件: `AgentEvent.DEVIATION_FEEDBACK`

**#14 自纠正循环**:
- `FeedbackLoop.should_retry()` 判断是否应重试（仅 blocked 时）
- `FeedbackLoop.build_correction_feedback()` 构建结构化反馈消息
- Orchestrator.run() 中验证重试循环：blocked → 注入反馈 → 重新执行
- Token 累积：跨重试追踪总 token 消耗
- 终止原因: `TerminationReason.SELF_CORRECTION_EXHAUSTED`
- 事件: `AgentEvent.SELF_CORRECTION`

**新增文件**:
```
nano_agent/agent/feedback_loop.py   # FeedbackLoop, DeviationFeedbackResult, SelfCorrectionResult
tests/test_feedback_loop.py          # 28 个测试用例
```

**修改文件**:
```
nano_agent/agent/types.py            # TerminationReason.SELF_CORRECTION_EXHAUSTED, AgentEvent.DEVIATION_FEEDBACK/SELF_CORRECTION
nano_agent/agent/estimation_audit.py # get_latest_result() 方法
nano_agent/config/schema.py          # FeedbackLoopConfig, Config.feedback_loop
nano_agent/config/loader.py          # 文档注释
nano_agent/agent/subsystems.py       # feedback_loop 参数
nano_agent/core/builder.py           # 创建并注入 FeedbackLoop
nano_agent/agent/orchestrator.py     # feedback_loop 参数, 验证重试循环
nano_agent/agent/react.py            # _think() 偏差注入, _prepare_run() 重置
nano_agent/agent/__init__.py         # 导出新模块
nano_agent/cli/main.py               # 配置显示, 终止处理, 自纠正通知, /auto 重置
```

**配置示例**:
```yaml
feedback_loop:
  deviation_feedback_enabled: true    # 偏差信号回流
  deviation_feedback_threshold: 0.50  # 触发回流的偏差阈值
  deviation_feedback_cooldown: 3      # 每 N 次警告注入 1 次提示
  deviation_feedback_hint_injection: true  # 注入提示到 LLM
  self_correction_enabled: true       # 自纠正循环
  self_correction_max_attempts: 2     # 最大纠正尝试次数
```

---

### v0.8.10 - 工具资源限制 ✅

**目标**: 防止工具执行失控。

**背景**:
Agent 管控体系审计发现 ToolGuard 工具防护层无资源限制。P2 优先级 — 工具执行失控 → 资源耗尽。

**架构归属**: Runtime 层 - ToolGuard 工具防护 (P2)

**任务列表**:
- [x] #15 工具执行超时 (`nano_agent/tools/resource_limiter.py`) — 单次工具调用超时上限，防止挂死
- [x] #16 工具调用频率限制 (`nano_agent/tools/resource_limiter.py`) — 单工具/全局调用频率上限

**实现细节**:

框架级工具资源限制，提供两层保护：

1. **ToolTimeoutWrapper**: 框架级超时保护
   - `signal.setitimer` (Unix/macOS) + `ThreadPoolExecutor` (跨平台 fallback)
   - 超时后返回 `ToolResult(success=False, error="工具执行超时")`
   - `has_builtin_timeout` 属性：shell/python_executor/web_search 自管超时，跳过框架包装
   - `_build_result()` 中调用 `close()` 释放 ThreadPoolExecutor

2. **ToolRateLimiter**: 单工具+全局双层令牌桶频率限制
   - `_MiniTokenBucket`: try_acquire/release/wait_time/reset
   - 非阻塞设计：超限立即返回 `RateLimitResult(allowed=False, wait_time=N)`
   - 全局令牌归还：per-tool 拒绝时释放 global token
   - `RateLimitType(str, Enum)`: GLOBAL/PER_TOOL 类型安全标识

**_act() 集成顺序**:
```
1. 重复检测 → 跳过
2. 事件发射
3. 缓存检查
4. 熔断确认
5. 风险确认
6. 【新增】频率限制检查 → 超限则跳过
7. 【新增】超时包装执行
8. 记录追踪
```

**配置示例**:
```yaml
tool_resource_limiter:
  enabled: true
  timeout_enabled: true
  default_timeout: 60
  timeout_overrides:
    file_read: 30
    shell_execute: 120
  rate_limit_enabled: true
  per_tool_calls_per_minute: 30
  global_calls_per_minute: 60
```

**新增/修改文件**:
```
nano_agent/tools/resource_limiter.py          # ToolTimeoutWrapper, ToolRateLimiter, _MiniTokenBucket
nano_agent/config/schema.py                   # ToolResourceLimiterConfig
nano_agent/agent/types.py                     # AgentEvent.TOOL_RATE_LIMITED
nano_agent/agent/subsystems.py                # timeout_wrapper/rate_limiter 参数
nano_agent/core/builder.py                    # 注入 tool_resource_limiter_config
nano_agent/agent/react.py                     # _act() 集成 + close()
nano_agent/tools/base.py                      # has_builtin_timeout 属性
nano_agent/tools/builtin/shell.py             # has_builtin_timeout = True
nano_agent/tools/builtin/python_executor.py   # has_builtin_timeout = True
nano_agent/tools/builtin/web_search.py        # has_builtin_timeout = True
nano_agent/cli/main.py                        # 配置显示 + 默认配置 + /auto 重置
tests/test_resource_limiter.py                # 40 个测试
```

---

### v0.8.12 - 记忆衰减与去重 ✅

**实现细节**:

三层能力，作用于 LongTermMemory：

1. **衰减**: `compute_decay_weight(entry, half_life_days)` — 读取时懒计算
   - `effective_weight = importance × e^(-λ × age_days)`
   - 使用 `last_mentioned_at` 作为衰减基准（被重复提及的条目衰减更慢）
   - `search()` 传入 `half_life_days` 参数启用衰减

2. **去重增强**: `add()` 合并而非覆盖
   - `mention_count` 递增追踪重复提及
   - `last_mentioned_at` 更新为当前时间
   - 内容合并：metadata type 匹合时取新内容（偏好更新），否则取更长的 + `[merged N similar]` 标记
   - 关键词取并集、importance 取 max、metadata 新覆盖旧

3. **GC**: `MemoryGC.run()` 会话开始时轻量清理
   - 删除 `effective_weight < threshold` 且 `age > min_age_days` 的条目
   - CLI 会话启动时自动触发

**新增文件**:
```
nano_agent/memory/gc.py                # MemoryGC, GCResult
tests/test_memory_gc.py                # 27 个测试
```

**修改文件**:
```
nano_agent/memory/long_term.py         # LongTermEntry 新字段 + compute_decay_weight + 增强合并 + 衰减搜索
nano_agent/memory/hybrid.py            # _memory_gc_config + 衰减感知 recall + merge_tag 传递 + run_gc()
nano_agent/memory/__init__.py          # 导出 MemoryGC, GCResult, compute_decay_weight
nano_agent/config/schema.py            # MemoryGCConfig
nano_agent/cli/main.py                 # GC 配置注入 + 会话启动 GC + 配置显示 + 配置初始化
nano_agent/tools/builtin/memory_tools.py  # RecallTool mention_count 显示
pyproject.toml                          # v0.8.12
nano_agent/__init__.py                  # v0.8.12
```

---

### v0.8.11 - 工具沙箱隔离

**目标**: 进程级隔离（可选，实现成本高）。

**架构归属**: Runtime 层 - ToolGuard 工具防护 (P2)

**任务列表**:
- [ ] #17 工具沙箱隔离 (`nano_agent/tools/sandbox.py`) — 进程级隔离

---

### v0.8.12 - 记忆衰减与去重 ✅

**目标**: 对抗知识漂移。

**背景**:
Agent 管控体系审计发现 MemoryGC 记忆迭代层短时 FIFO 淘汰，长时只增不减。P2 优先级 — 存储爆炸 / 检索效率下降。

**架构归属**: Runtime 层 - MemoryGC 记忆迭代 (P2)

**任务列表**:
- [x] #18 记忆衰减策略 (`nano_agent/memory/gc.py`) — 时间衰减权重，旧记忆自动降权
- [x] #19 记忆去重/合并 (`nano_agent/memory/gc.py`) — 相同信息多次存储时自动合并

---

### v0.8.13 - 长时记忆淘汰 ✅

**目标**: 防止长时记忆无限膨胀。

**架构归属**: Runtime 层 - MemoryGC 记忆迭代 (P2)

**任务列表**:
- [x] #20 长时记忆淘汰 (`nano_agent/memory/gc.py`) — 容量上限淘汰 + 保护类别 + 提及计数保护

**实现细节**:

在 MemoryGC.run() 中增加 Phase 2 淘汰逻辑（Phase 1 为已有的衰减清理）：

1. **容量触发**: 当 `count() > eviction_max_entries` 时触发淘汰
2. **淘汰排序**: 按 `effective_weight` 升序（最低权重优先淘汰），同权重按年龄降序（老条目优先）
3. **保护机制**:
   - `eviction_protected_categories`: 保护类别（默认 `["preference"]`）不被淘汰
   - `eviction_mention_count_threshold`: 提及次数 >= 阈值的条目不被淘汰
4. **GCResult 扩展**: 新增 `evicted_ids`、`entries_evicted`、`capacity_before` 字段

**新增/修改文件**:
```
nano_agent/config/schema.py          # MemoryGCConfig 新增 4 个 eviction 字段
nano_agent/memory/gc.py              # GCResult 扩展 + MemoryGC.run() Phase 2
nano_agent/config/loader.py          # 注释更新
nano_agent/cli/main.py               # 配置显示 + 默认配置 + GC 输出增强
tests/test_memory_gc.py              # 13 个淘汰测试
pyproject.toml                       # v0.8.13
nano_agent/__init__.py               # v0.8.13
```

**配置示例**:
```yaml
memory_gc:
  eviction_enabled: true
  eviction_max_entries: 500
  eviction_protected_categories: ["preference"]
  eviction_mention_count_threshold: 3
```

---

### v0.8.14 - 全局状态快照 ✅

**目标**: 一键保存/恢复 agent 完整状态。

**背景**:
Agent 管控体系审计发现 Rollback&Audit 回溯兜底层操作级撤销存在但无全局快照。P3 优先级 — 无法一键恢复到任意时间点。

**架构归属**: Runtime 层 - Rollback&Audit 回溯兜底 (P3)

**任务列表**:
- [x] #21 全局状态快照 (`nano_agent/agent/snapshot.py`) — 一键保存/恢复 agent 完整状态到任意时间点

**实现细节**:

SnapshotManager 捕获 Agent 全部可序列化状态并持久化为 JSON，支持原地恢复：

1. **捕获范围**: Orchestrator 状态、Agent 执行状态、UndoStack、Memory（含 LongTermMemory）、TokenBudget、Cache、CircuitBreaker、DuplicateDetector、StallDetector、FeedbackLoop、Tracker
2. **原地恢复**: 替换 agent/orchestrator 字段，保持 LLM/ToolRegistry/EventEmitter 不变
3. **存储**: `.nano_agent/snapshots/` 目录，每快照一个 JSON 文件，max_snapshots 淘汰最旧
4. **CLI**: `/snapshot save [name]`、`/snapshot list`、`/snapshot restore <id>`、`/snapshot delete <id>`
5. **自动存档**: `auto_snapshot` 配置项，每次 `run()` 前自动保存
6. **事件**: `SNAPSHOT_SAVED`、`SNAPSHOT_RESTORED`

**新增文件**:
```
nano_agent/agent/snapshot.py           # SnapshotMetadata, Snapshot, SnapshotManager
tests/test_snapshot.py                  # 28 个测试
```

**修改文件**:
```
nano_agent/agent/types.py               # SNAPSHOT_SAVED, SNAPSHOT_RESTORED 事件
nano_agent/agent/__init__.py             # 导出新模块
nano_agent/config/schema.py             # SnapshotConfig + Config 字段
nano_agent/core/builder.py              # 创建 SnapshotManager
nano_agent/agent/orchestrator.py         # snapshot_manager 属性 + auto_snapshot
nano_agent/cli/constants.py             # SNAPSHOT 常量
nano_agent/cli/main.py                  # /snapshot 命令 + 帮助 + 配置显示
pyproject.toml                          # v0.8.14
nano_agent/__init__.py                  # v0.8.14
```

**配置示例**:
```yaml
snapshot:
  enabled: true
  auto_snapshot: false
  max_snapshots: 20
  snapshot_dir: .nano_agent/snapshots
```

---

### v0.8.15 - 审计回滚 ✅

**目标**: 审计与回滚联动。

**架构归属**: Runtime 层 - Rollback&Audit 回溯兜底 (P3)

**任务列表**:
- [x] #22 审计-回滚关联 (`nano_agent/agent/snapshot.py`) — 从审计日志直接触发回滚操作
- [x] #23 条件触发自动回滚 (`nano_agent/agent/snapshot.py`) — 连续失败 N 次自动回滚到上一检查点

---

### v0.9.0 - 流式执行

**目标**: 实现流式输出，让用户实时看到执行过程。

**背景**:
当前同步执行模式下，用户需要等待整个执行完成后才能看到结果。长任务执行时体验差，用户不知道 Agent 在做什么。流式执行通过生成器模式，逐事件输出，提供实时反馈。

**架构归属**: 执行层 - 流式输出

**任务列表**:
- [ ] 定义 `ExecutionHandle` 类 - 执行句柄，封装生成器
- [ ] 定义 `ExecutionEvent` 类型扩展 - stream/text/tool_call/tool_result/end
- [ ] 实现 `run_stream()` 方法 - 返回生成器，逐事件 yield
- [ ] 重构 `run()` 方法 - 内部调用 `run_stream()`，返回最终结果
- [ ] 编排层流式处理 - 逐事件更新 UI、记录统计
- [ ] 中断支持 - 用户可随时中断执行

**技术方案**:
```python
# nano_agent/agent/types.py

@dataclass
class ExecutionHandle:
    """执行句柄 - 管理流式执行"""
    events: Generator[ExecutionEvent, None, ExecutionResult]
    cancelled: bool = False

    def cancel(self):
        """中断执行"""
        self.cancelled = True

# nano_agent/agent/react.py

class ReActAgent:
    def run(self, user_input: str, dry_run: bool = False) -> ExecutionResult:
        """同步执行 - 内部调用流式执行"""
        handle = self.run_stream(user_input, dry_run)
        result = None
        for event in handle.events:
            result = event.data.get("result")
        return result

    def run_stream(self, user_input: str, dry_run: bool = False) -> ExecutionHandle:
        """流式执行 - 返回事件生成器"""
        def event_generator():
            self._prepare(user_input)
            yield ExecutionEvent(type="run_start", data={"input": user_input})

            while not self._should_stop():
                if handle.cancelled:
                    yield ExecutionEvent(type="cancelled", data={})
                    return self._build_result("用户中断")

                think = self._think()
                yield ExecutionEvent(type="think", data={"response": think.response_text})

                if think.is_final:
                    result = self._build_result(think.response_text)
                    yield ExecutionEvent(type="end", data={"result": result})
                    return result

                for tool_call in think.tool_calls:
                    yield ExecutionEvent(type="tool_call", data={"tool": tool_call.name})
                    result = self._act(tool_call, dry_run)
                    yield ExecutionEvent(type="tool_result", data={"result": result})
                    self._observe(tool_call, result)

            result = self._build_result(self._timeout_msg())
            yield ExecutionEvent(type="end", data={"result": result})
            return result

        handle = ExecutionHandle(events=event_generator())
        return handle

# nano_agent/agent/orchestrator.py

class AgentOrchestrator:
    def run_stream(self, user_input: str, dry_run: bool = False) -> ExecutionHandle:
        """流式执行入口"""
        handle = self.agent.run_stream(user_input, dry_run)
        return handle

    def run(self, user_input: str, dry_run: bool = False) -> ExecutionResult:
        """同步执行入口"""
        handle = self.run_stream(user_input, dry_run)
        result = None
        for event in handle.events:
            self._handle_event(event)  # 更新 UI、记录统计
            if event.type == "end":
                result = event.data["result"]
        return result

# nano_agent/cli/main.py

# CLI 流式处理
handle = orchestrator.run_stream(user_input)
for event in handle.events:
    if event.type == "think":
        print(f"[思考] {event.data['response'][:50]}...")
    elif event.type == "tool_call":
        print(f"[工具] {event.data['tool']}")
    elif event.type == "tool_result":
        print(f"[结果] {event.data['result'].output[:50]}...")
    elif event.type == "end":
        print(f"[完成] {event.data['result'].response}")
```

---

### v0.9.1 - 异步流式执行

**目标**: 支持真正的异步流式输出，与 LLM API 的流式响应对接。

**背景**:
v0.7.0 的生成器是同步的，无法与 LLM 的流式 API（SSE）对接。异步生成器可以逐 token 输出，提供更好的用户体验。

**架构归属**: 执行层 - 异步流式

**任务列表**:
- [ ] 实现 `run_stream_async()` 方法 - 异步生成器
- [ ] LLM 流式调用 - 逐 token 接收响应
- [ ] 编排层异步处理 - 异步事件处理
- [ ] CLI 异步支持 - 使用 asyncio

**技术方案**:
```python
# nano_agent/agent/react.py

class ReActAgent:
    async def run_stream_async(self, user_input: str) -> AsyncGenerator[ExecutionEvent, None]:
        """异步流式执行"""
        self._prepare(user_input)
        yield ExecutionEvent(type="run_start", data={"input": user_input})

        while not self._should_stop():
            # 流式调用 LLM
            async for chunk in self.llm.chat_stream_async(self.memory.get_all()):
                yield ExecutionEvent(type="stream", data={"text": chunk.text})

                if chunk.is_tool_call_complete:
                    result = await self._act_async(chunk.tool_call)
                    yield ExecutionEvent(type="tool_result", data={"result": result})

        yield ExecutionEvent(type="end", data={"result": self._build_result(...)})

# nano_agent/cli/main.py

import asyncio

async def run_interactive_async(orchestrator, user_input):
    async for event in orchestrator.run_stream_async(user_input):
        if event.type == "stream":
            print(event.data["text"], end="", flush=True)
        elif event.type == "tool_result":
            print(f"\n[工具结果] {event.data['result'].output[:50]}...")
```

---

### v0.10.0 - 模式切换

**目标**: 支持在 Agent 会话中切换执行模式，提供更灵活的交互方式。

**背景**:
有时用户希望直接执行基础的 shell 命令（如 ls、cat、grep 等），而不需要经过 Agent 的推理过程。模式切换可以让用户在 Agent 模式和直接命令模式之间灵活切换。

**架构归属**: CLI 交互层

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

### v0.11.0 - 配置系统优化

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

### v0.12.0 - 反思与规划能力

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

### v0.13.0 - 主动学习能力

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

### v0.14.0 - 个性化与角色

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

### v0.15.0 - 多 Agent 协作

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

### v0.16.0 - 安全与体验

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
| v0.6.0 | 编排层与执行层分离 ✅ | AgentOrchestrator、阶段拆分、事件流、预算检查、会话管理 |
| v0.6.1 | 上下文管理 ✅ | ContextManager、三层压缩策略、九段式摘要、Token 估算 |
| v0.6.2 | 前置规划 ✅ | PlanMode、Plan 持久化、多轮规划、CLI 命令 |
| v0.6.3 | PlanMode 演进优化 ✅ | EventEmitter 集成、I/O 无关设计、CLI 包装层 |
| v0.6.4 | 渐进式执行与用户确认 ✅ | RiskLevel 分级、ConfirmationManager、白名单管理 |
| v0.6.5 | Git 集成与状态回退 ✅ | GitManager、自动提交、/undo 增强、/history 命令 |
| v0.7.0 | Hooks 机制与架构优化 ✅ | EventEmitter 统一、AgentBuilder、BaseRegistry、tools/builtin/ |
| v0.7.1 | Token 消耗优化 ✅ | 输出风格控制、提示词简化、工具结果截断 |
| v0.7.2 | Token 消耗深度优化 ✅ | 智能工具合并、工具结果智能摘要 |
| v0.7.3 | Token 消耗进阶优化 ✅ | 工具结果缓存、历史消息压缩、项目文件精简 |
| v0.7.4 | Token 统计增强 ✅ | Token 分类统计、/stats 子命令增强、工具消耗排名 |
| v0.7.5 | Token 消耗智能优化 ✅ | 置信度早停、Token 预算、查询路由、SmartOptimizationConfig |
| v0.7.6 | 模块化提示词系统 ✅ | PromptBuilder、17 个模块、Excel 配置、稳定缓存 |
| v0.7.7 | Prefix Caching 优化 ✅ | AnthropicLLM、cache_control、稳定/动态分离、enable_caching |
| v0.7.8 | Token 优化增强 ✅ | Tool Caching、Dynamic Module、Budget 与 LLMUsage 集成 |
| v0.7.9 | Agent/Monitoring/CLI 解耦 ✅ | RawData 容器、Tracker 解耦 API、SkippedToolCall、/usage、/context |
| v0.7.10 | 柔化硬限制 ✅ | TerminationReason、DuplicateDetector、预算收尾轮 |
| v0.7.11 | 模型上下文窗口准确性 ✅ | API 查询 + fallback 链，修复所有百分比决策的分母 |
| v0.7.12 | 决策点真实 Token ✅ | 压缩/压力检测从估算切换到实际 prompt_tokens |
| v0.7.13 | 统一截断比率与校准闭环 ✅ | calculate_max_chars、calibration_factor 参数、校准公式修正 |
| v0.7.14 | 预判机制 ✅ | 简单问题不走 ReAct，节省 ~90% token |
| v0.7.15 | 激进输出精简与工具输出标准化 ✅ | LLM 输出精简 + 工具结果结构化 |
| v0.7.16 | 复杂度预算 Profile 与 Stall Detection ✅ | 小任务不浪费 + 无进展转向 |
| v0.7.17 | 多轮缓存与 Tool Offloading ✅ | 跨轮次缓存 + 大结果 offload |
| v0.7.18 | 估算审计与准确性增强 | 估算 vs 实际对比 + 估算准确性提升 |
| v0.7.19 | 语义压缩 | 合并相似历史消息 |
| v0.8.0 | 指数退避重试与熔断降级 | P0 — 429/500 自动退避 + 异常行为熔断降级 |
| v0.8.1 | LLM API 限流器 ✅ | P0 — 调用频率限制，防止突发请求打爆 API |
| v0.8.2 | 熔断器 (已合并到 v0.8.0) | P0 — 已在 v0.8.0 实现 |
| v0.8.3 | 输入净化 ✅ | P1 — Prompt injection 过滤 + 输入校验 |
| v0.8.4 | PII 脱敏 ✅ | P1 — 手机号/身份证/API key 等敏感信息自动脱敏 |
| v0.8.5 | 输出护栏 ✅ | P1 — 敏感信息拦截 + 中间件规则扩充 |
| v0.8.6 | 有害内容过滤 ✅ | P1 — 输出内容安全检查（可选） |
| v0.8.7 | 结果正确性验证 ✅ | P2 — 文件存在/代码语法/命令成功 验证 hook |
| v0.8.8 | Schema-based 校验 ✅ | P2 — StandardToolOutput.data 按格式 schema 校验 |
| v0.8.9 | 反馈闭环 ✅ | P2 — 偏差信号回流 + 自纠正循环 |
| v0.8.10 | 工具资源限制 ✅ | P2 — 执行超时 + 调用频率限制 |
| v0.8.11 | 工具沙箱隔离 | P2 — 进程级隔离（可选） |
| v0.8.12 | 记忆衰减与去重 ✅ | P2 — 时间衰减权重 + 相同信息合并 |
| v0.8.13 | 长时记忆淘汰 ✅ | P2 — 容量上限淘汰 + 保护类别 + 提及计数保护 |
| v0.8.14 | 全局状态快照 ✅ | P3 — 一键保存/恢复 agent 完整状态 |
| v0.8.15 | 审计回滚 | P3 — 审计-回滚关联 + 条件触发自动回滚 |
| v0.9.0 | 流式执行 | ExecutionHandle、run_stream()、事件生成器 |
| v0.9.1 | 异步流式执行 | 异步生成器、LLM 流式 API 对接 |
| v0.10.0 | 模式切换 | Agent/Shell 模式切换，直接执行基础命令 |
| v0.11.0 | 配置系统优化 | 自动显示/保存配置项 |
| v0.12.0 | 反思与规划能力 | RCI 反思循环、Plan-Execute 增强 |
| v0.13.0 | 主动学习 | 知识提取、语义搜索 |
| v0.14.0 | 个性化角色 | 可配置性格、专业领域 |
| v0.15.0 | 多 Agent 协作 | 编排框架、Agent 通信 |
| v0.16.0 | 安全与体验 | 沙箱、Web UI、权限控制 |

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
>
> **日常测试规范**: 参见 [CLAUDE.md - Testing](CLAUDE.md#testing) - 提交前检查、覆盖率要求、merge conflict 后验证

### 测试现状总览 (2026-05-19 更新)

| 指标 | 当前值 | 目标值 | 状态 |
|------|--------|--------|------|
| 总测试数 | 795 | 1000+ | 🟡 |
| 总覆盖率 | 71.64% | 75% | 🟡 |
| CI 门禁阈值 | 54% | 60% | 🟡 |
| 测试文件数 | 30 | 35+ | 🟡 |
| Mock 重复定义 | 8 处 | 0 处 | 🔴 |

---

### 已完成的测试文件

> 以下测试文件在各版本功能开发时同步完成，详见各版本规划章节。

| 测试文件 | 关联版本 | 测试用例数 | 状态 |
|----------|---------|-----------|------|
| `tests/test_plan.py` | v0.6.2 | 20+ | ✅ |
| `tests/test_confirmation.py` | v0.6.4 | 22 | ✅ |
| `tests/test_git_manager.py` | v0.6.5 | 26 | ✅ |
| `tests/test_output_style.py` | v0.7.1 | 31 | ✅ |
| `tests/test_tool_merger.py` | v0.7.2 | 14 | ✅ |
| `tests/test_cache.py` | v0.7.3 | 13 | ✅ |
| `tests/test_compressor.py` | v0.7.3 | 11 | ✅ |
| `tests/test_token_analyzer.py` | v0.7.4 | 15 | ✅ |
| `tests/test_smart_optimization.py` | v0.7.5 | 37 | ✅ |
| `tests/test_prompt_config.py` | v0.7.6 | 32 | ✅ |
| `tests/test_prefix_caching.py` | v0.7.7 | 21 | ✅ |
| `tests/test_intent_detector.py` | v0.7.8 | 22 | ✅ |
| `tests/test_token_budget_integration.py` | v0.7.8 | 26 | ✅ |
| `tests/test_tool_caching.py` | v0.7.8 | 10 | ✅ |

---

### 测试覆盖率现状 (2026-05-19 更新)

#### 高覆盖率模块 (≥70%)

| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| agent/types.py | 100% | ✅ |
| agent/budget.py | 100% | ✅ |
| agent/cache.py | 100% | ✅ |
| agent/compressor.py | 100% | ✅ |
| agent/token_budget.py | 100% | ✅ |
| agent/token_utils.py | 100% | ✅ |
| agent/prompt_modules.py | 100% | ✅ |
| core/builder.py | 100% | ✅ |
| skills/base.py | 86% | ✅ |
| tools/builtin/file_ops.py | 86% | ✅ |
| skills/loader.py | 76% | ✅ |

#### 低覆盖率模块 (<60%) - 需优先补充

| 模块 | 当前覆盖率 | 目标覆盖率 | 优先级 | 缺失测试类型 |
|------|-----------|-----------|--------|-------------|
| `__main__.py` | 5-8% | 70% | P0 | 入口点、CLI 启动 |
| `cli/constants.py` | 8-54% | 80% | P1 | 常量定义验证 |
| `utils/strings.py` | 20-21% | 90% | P1 | 字符串工具函数 |
| `tools/builtin/monitoring_tools.py` | 34-81% | 80% | P1 | get_stats 工具执行 |
| `config/loader.py` | 35% | 80% | P1 | 配置加载、合并、保存 |
| `memory/base.py` | 43-46% | 90% | P1 | 抽象方法、Protocol |
| `agent/events.py` | 45% | 90% | P1 | EventEmitter 完整流程 |
| `agent/base.py` | 47% | 80% | P1 | BaseAgent 抽象类 |

#### 中等覆盖率模块 (60-70%) - 需补充边界测试

| 模块 | 当前覆盖率 | 目标覆盖率 | 备注 |
|------|-----------|-----------|------|
| `tools/builtin/web_search.py` | 23% | 75% | 需要 HTTP mock |
| `monitoring/reporter.py` | 24% | 80% | 报告生成测试 |
| `cli/scanner.py` | 60% | 70% | 项目扫描测试 |
| `llm/ollama.py` | 60% | 70% | LLM 调用测试 |
| `monitoring/tracker.py` | 66% | 80% | 统计追踪测试 |

**历史记录**:
- 2026-05-11: 在 `tests/run_tests.py` 中设置 CI 门禁阈值 **54%** (`--cov-fail-under=54`)
  - 背景：v0.6.x 新增模块（Architecture、Confirmation、Context、GitManager、Plan、Session、Undo）测试覆盖完成
  - 测试用例从 147 增至 359 个
  - 54% 为当前实际执行的最低阈值，ROADMAP 中的 75% 为最终目标
- 2026-05-19: 测试用例增至 **795 个**，覆盖率提升至 **71.64%**

---

### T0 阶段 - 测试代码质量优化 ✅ (2026-05-19)

**目标**: 优化现有测试代码质量，消除重复，提升可维护性。

**发现的问题**:

#### 问题 1: Mock 类重复定义 🔴
- **现状**: `MockTool` 类在 8 个文件中重复定义
  - `tests/conftest.py`
  - `tests/test_agent.py`
  - `tests/factories.py`
  - `tests/test_confirmation.py`
  - `tests/test_middleware.py`
  - `tests/test_skills.py`
  - `tests/test_tools_plugin.py`
- **影响**: 维护困难，行为不一致风险
- **解决方案**: 统一使用 `factories.py` 中的 `create_mock_tool()`

#### 问题 2: pytest markers 使用不一致 🟡
- **现状**: 大多数文件使用 `pytestmark = pytest.mark.unit`
- **问题**: `test_e2e.py` 使用 `@pytest.mark.e2e`，`test_cli_scanner.py` 混用 `@pytest.mark.integration`
- **解决方案**: 在 `pyproject.toml` 或 `pytest.ini` 中统一定义 markers

#### 问题 3: E2E 测试依赖 Mock 🟡
- **现状**: `test_e2e.py` 名为端到端测试，但使用 Mock LLM
- **影响**: 测试分类不清晰，无法验证真实 LLM 交互
- **解决方案**:
  - 重命名为 `test_integration.py`
  - 添加真正的 E2E 测试（使用 `@pytest.mark.skipif` 控制真实 LLM）

#### 问题 4: 缺少参数化测试 🟡
- **现状**: 多个测试文件有重复的测试结构
- **影响**: 测试代码冗余，维护成本高
- **解决方案**: 使用 `@pytest.mark.parametrize` 简化

#### 问题 5: 缺少性能测试 🟡
- **现状**: 无性能测试
- **影响**: 无法验证大量消息、长时间运行、并发场景
- **解决方案**: 添加性能测试套件

**任务列表**:

**代码质量优化 (P0)**:
- [x] 分析测试代码现状 - 完成 2026-05-19
- [ ] 统一 Mock 类到 factories.py - 预估 2-3 小时
- [ ] 统一 pytest markers 配置 - 预估 30 分钟
- [ ] 重命名 test_e2e.py 为 test_integration.py - 预估 1-2 小时

**测试增强 (P1)**:
- [ ] 添加参数化测试 - 预估 2-3 小时
- [ ] 补充低覆盖率模块测试 - 预估 4-6 小时
- [ ] 添加性能测试 - 预估 3-4 小时

**基础设施优化 (P2)**:
- [ ] 增强 run_tests.py (--quick, --watch, 并行测试) - 预估 1-2 小时
- [ ] 添加更多 fixture (mock_llm_with_tool_calls, sample_conversation) - 预估 1 小时

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

**关联功能版本**: v0.9.0 Hooks 机制

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

**关联功能版本**: v0.11.0 配置系统优化

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

| 测试阶段 | 目标覆盖率 | 关键里程碑 | 关联功能版本 | 状态 |
|------|-----------|-----------|--------|------|
| T0 | **72%** | 测试代码质量优化，Mock 统一 | v0.7.8 | 🟡 进行中 |
| T1 | 75% | CLI、Migration、Plugin 测试完成 | v0.9.0 | 待开始 |
| T2 | 80% | 可测试性重构完成 | v0.10.0 | 待开始 |
| T3 | 85% | CI 门禁建立，全模块测试完成 | v0.11.0 | 待开始 |
| T4+ | 90% | 持续维护，新增功能同步测试 | v0.12.0+ | 待开始 |

---

### 测试优化任务清单

#### 立即执行 (本周)

| 任务 | 优先级 | 预估时间 | 状态 |
|------|--------|----------|------|
| 统一 Mock 类到 factories.py | P0 | 2-3h | 待开始 |
| 统一 pytest markers 配置 | P0 | 30min | 待开始 |
| 补充 `__main__.py` 入口点测试 | P0 | 1h | 待开始 |

#### 短期执行 (本月)

| 任务 | 优先级 | 预估时间 | 状态 |
|------|--------|----------|------|
| 重命名 test_e2e.py → test_integration.py | P1 | 1-2h | 待开始 |
| 补充 utils/strings.py 测试 | P1 | 1h | 待开始 |
| 补充 config/loader.py 测试 | P1 | 2h | 待开始 |
| 添加参数化测试 | P1 | 2-3h | 待开始 |

#### 中期执行 (下月)

| 任务 | 优先级 | 预估时间 | 状态 |
|------|--------|----------|------|
| 补充 agent/events.py 测试 | P1 | 1h | 待开始 |
| 补充 agent/base.py 测试 | P1 | 2h | 待开始 |
| 添加性能测试套件 | P2 | 3-4h | 待开始 |
| 增强 run_tests.py | P2 | 1-2h | 待开始 |