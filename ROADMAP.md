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

### v0.7.5 - Token 消耗智能优化

**目标**: 实现动态思考深度控制，让 Agent 学会"适可而止"。

**背景**:
v0.7.1-v0.7.4 实现了静态优化（输出风格、工具合并、缓存、压缩）。但 Agent 仍会在所有场景使用相同策略，无法根据任务复杂度动态调整。

**架构归属**: 执行层 - 动态优化

**任务列表**:

**1. 置信度评估与早停 (P0)**:
- [ ] 扩展 `ThinkResult` 数据类 - 增加 `confidence` 和 `can_answer` 字段
- [ ] 修改 System Prompt - 要求 LLM 输出置信度评估
- [ ] 实现 `_should_stop_early()` 方法 - 置信度 > 0.9 且可回答时早停
- [ ] 测试验证 - 确保早停逻辑正确

**2. Token 预算管理增强 (P0)**:
- [ ] 实现 `TokenBudget` 类 - 剩余预算追踪
- [ ] 预算耗尽时强制总结 - 返回最佳尝试答案
- [ ] 配置支持 - `token_budget` 配置项

**3. 查询复杂度路由 (P1)**:
- [ ] 实现 `QueryRouter` 类 - 分类查询复杂度（SIMPLE/MODERATE/COMPLEX）
- [ ] 扩展 `_answer_simple_question()` - 支持更多简单任务
- [ ] 中等复杂度处理 - 单次 LLM + 最多 1 次工具
- [ ] 配置支持 - `routing.enabled` 配置项

**4. 工具返回智能摘要增强 (P1)**:
- [ ] 实现 `ToolResultProcessor` 类 - 提取-摘要-结构化
- [ ] 针对每个工具定制处理逻辑
- [ ] 配置支持 - `tool_summary.enabled` 配置项

**新增文件**:
```
nano_agent/agent/
├── router.py              # QueryRouter
├── token_budget.py        # TokenBudget
└── tool_processor.py      # ToolResultProcessor
```

**修改文件**:
```
nano_agent/agent/types.py      # ThinkResult 扩展
nano_agent/agent/react.py      # 早停逻辑、预算管理
nano_agent/agent/prompts.py    # 置信度评估提示词
nano_agent/config/schema.py    # 新增配置项
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
    confidence: float = 1.0      # 新增：当前结论置信度 (0-1)
    can_answer: bool = True      # 新增：是否已有足够信息回答

# nano_agent/agent/token_budget.py
class TokenBudget:
    def __init__(self, initial_budget: int = 2000):
        self.initial_budget = initial_budget
        self.remaining = initial_budget

    def consume(self, tokens: int) -> None:
        self.remaining = max(0, self.remaining - tokens)

    def should_summarize(self) -> bool:
        """剩余预算 < 20% 时，强制进入总结模式"""
        return self.remaining < self.initial_budget * 0.2

# nano_agent/agent/router.py
class QueryComplexity(Enum):
    SIMPLE = "simple"       # 问候、简单问答
    MODERATE = "moderate"   # 单步推理
    COMPLEX = "complex"     # 多步推理

class QueryRouter:
    def classify(self, query: str) -> QueryComplexity:
        if self._is_greeting(query):
            return QueryComplexity.SIMPLE
        if self._is_simple_fact(query):
            return QueryComplexity.SIMPLE
        if self._needs_single_tool(query):
            return QueryComplexity.MODERATE
        return QueryComplexity.COMPLEX
```

**预期效果**:
- 置信度早停: 减少 30% 无效迭代
- Token 预算: 防止无限消耗
- 查询路由: 减少 50% 简单任务消耗
- 工具摘要: 减少 40% 工具输出 token

---

### v0.7.6 - Prompt 模块完善

**目标**: 补充 Claude Code harness 对标的 prompt 模块，完善系统提示词体系。

**背景**:
通过分析 Claude Code 的 `/context` API 调用记录，发现 NanoAgent 缺少部分 prompt 模块。这些模块对 Agent 的行为规范和安全性有重要作用。

**架构归属**: 执行层 - Prompt 系统

**任务列表**:

**1. 开发规范模块 (P1)**:
- [ ] 添加 `development_guidelines` 模块 - 文档更新规则、测试覆盖率检查
- [ ] 内容包括：提交前验证、文档同步、测试要求
- [ ] 更新 `prompt_modules.py` 和 `config/prompts.xlsx`

**2. 记忆类型定义模块 (P1)**:
- [ ] 扩展 `memory_guide` 模块 - 完整记忆类型定义
- [ ] 类型包括：user（用户信息）、feedback（用户反馈）、project（项目信息）、reference（外部引用）
- [ ] 添加记忆存储/访问规则说明

**3. 会话指导模块 (P2)**:
- [ ] 添加 `session_guidance` 模块 - Agent 使用策略、Skill 调用规则
- [ ] 内容包括：多 Agent 场景、技能包使用、子任务委托

**4. 项目配置模板 (P3)**:
- [ ] 创建 `CLAUDE.md` 模板文件 - 项目级配置示例
- [ ] 包含：项目概述、开发规范、架构说明、常用命令

**修改文件**:
```
nano_agent/agent/prompt_modules.py    # 新增模块定义
config/prompts.xlsx                    # 更新 Excel 配置
docs/examples/CLAUDE.md               # 项目配置模板
```

**技术方案**:
```python
# nano_agent/agent/prompt_modules.py

# 新增模块
MODULES = {
    # ... 现有模块 ...

    "development_guidelines": PromptModule(
        name="development_guidelines",
        description="开发规范",
        content="""## Development Guidelines

### Before Committing
1. Run tests: `pytest tests/ -v`
2. Check coverage: aim for 75%+
3. Update documentation if needed
4. Update ROADMAP.md for new features

### Code Quality
- Write tests for new features
- Fix bugs before adding features
- Keep changes minimal and focused""",
        priority=22,
        always_on=False,
        token_estimate=80,
        enabled=True,
    ),

    "memory_types": PromptModule(
        name="memory_types",
        description="记忆类型定义",
        content="""## Memory Types

### user
- User's role, preferences, knowledge level
- Save when learning about user's background

### feedback
- Guidance on how to approach work
- Save corrections and validated approaches

### project
- Ongoing work, goals, deadlines
- Save project context and decisions

### reference
- Pointers to external resources
- Save links to docs, dashboards, etc.""",
        priority=61,
        always_on=False,
        token_estimate=100,
        enabled=True,
    ),

    "session_guidance": PromptModule(
        name="session_guidance",
        description="会话指导",
        content="""## Session Guidance

- For shell commands requiring user interaction, suggest `! <command>`
- Use specialized agents for complex tasks
- For broad codebase exploration, spawn Explore agent
- Only invoke skills that match user request""",
        priority=70,
        always_on=False,
        token_estimate=50,
        enabled=False,  # 可选启用
    ),
}

# 更新 Style 预设
STYLE_PRESETS = {
    "concise": {...},
    "standard": {
        "modules": [
            "core", "tools", "efficiency", "modification",
            "constitution", "risk_awareness",
            "development_guidelines",  # 新增
            "language"
        ],
        "token_budget": 1200,
    },
    "detailed": {
        "modules": [
            "core", "tools", "efficiency", "modification",
            "constitution", "risk_awareness", "security_rules",
            "development_guidelines",  # 新增
            "memory_types",  # 新增
            "output_style", "memory_guide", "language"
        ],
        "token_budget": 2500,
    },
}
```

**预期效果**:
- 开发规范模块: 提升代码质量意识
- 记忆类型模块: 更好的记忆系统使用
- 会话指导模块: 支持未来多 Agent 场景
- 项目配置模板: 便于项目级定制

---

### v0.8.0 - 流式执行

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

### v0.8.1 - 异步流式执行

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

### v0.9.0 - 模式切换

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

### v0.10.0 - 配置系统优化

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

### v0.11.0 - 反思与规划能力

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

### v0.12.0 - 主动学习能力

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

### v0.13.0 - 个性化与角色

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

### v0.14.0 - 多 Agent 协作

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

### v0.15.0 - 安全与体验

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
| v0.7.5 | Token 消耗智能优化 | 置信度早停、Token 预算、查询路由、工具摘要增强 |
| v0.7.6 | Prompt 模块完善 | 开发规范、记忆类型、会话指导、项目配置模板 |
| v0.8.0 | 流式执行 | ExecutionHandle、run_stream()、事件生成器 |
| v0.8.1 | 异步流式执行 | 异步生成器、LLM 流式 API 对接 |
| v0.9.0 | 模式切换 | Agent/Shell 模式切换，直接执行基础命令 |
| v0.10.0 | 配置系统优化 | 自动显示/保存配置项 |
| v0.11.0 | 反思与规划能力 | RCI 反思循环、Plan-Execute 增强 |
| v0.12.0 | 主动学习 | 知识提取、语义搜索 |
| v0.13.0 | 个性化角色 | 可配置性格、专业领域 |
| v0.14.0 | 多 Agent 协作 | 编排框架、Agent 通信 |
| v0.15.0 | 安全与体验 | 沙箱、Web UI、权限控制 |

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

**历史记录**:
- 2026-05-11: 在 `tests/run_tests.py` 中设置 CI 门禁阈值 **54%** (`--cov-fail-under=54`)
  - 背景：v0.6.x 新增模块（Architecture、Confirmation、Context、GitManager、Plan、Session、Undo）测试覆盖完成
  - 测试用例从 147 增至 359 个
  - 54% 为当前实际执行的最低阈值，ROADMAP 中的 75% 为最终目标

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
| T0 | **54%** ✅ | CI 门禁阈值设置，v0.6.x 新模块测试完成 | v0.6.5 |
| T1 | 60% | CLI、Migration、Plugin 测试完成 | v0.6.0 |
| T2 | 70% | 可测试性重构完成 | v0.7.0, v0.8.0 |
| T3 | 75% | CI 门禁建立，全模块测试完成 | v0.9.0 |
| T4+ | 80% | 持续维护，新增功能同步测试 | v0.10.0+ |