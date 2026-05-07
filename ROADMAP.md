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

### v0.6.3 - PlanMode 演进优化

**目标**: 优化 PlanMode 架构，为未来多模式和多 Agent 集成做准备。

**背景**:
v0.6.2 的 PlanMode 实现了基础功能，但 I/O 逻辑与核心逻辑耦合。为了支持未来的独立 Agent 模式和多模式切换，需要将核心逻辑与 I/O 分离。

**架构对应**: 演进友好设计 - 核心逻辑无 I/O，可被 CLI 或独立 Agent 包装

**任务列表**:
- [ ] EventEmitter 集成 - 支持事件驱动的 UI 更新
- [ ] 核心逻辑 I/O 无关 - generate_plan(), adjust_plan(), save_plan() 不依赖 print/input
- [ ] CLI 包装函数 - run_plan_mode_interactive() 作为可替换的 CLI 层
- [ ] 事件类型定义 - plan_generated, plan_adjusted, plan_saved
- [ ] 测试更新 - 验证事件触发和 I/O 分离

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

### v0.6.4 - 渐进式执行与用户确认

**目标**: 工具执行前暂停，等待用户确认；支持风险分级确认策略。

**背景**:
当前 Agent 连续执行多个工具调用，用户无法干预。危险操作（删除、Shell）应该确认，安全操作（读取）可以自动执行。

**架构对应**: 基于事件流，监听 TOOL_CALL 事件实现暂停和确认

**任务列表**:
- [ ] 定义 `RiskLevel` 枚举 - SAFE/MODERATE/DANGEROUS
- [ ] 工具添加 `risk_level` 属性
- [ ] 实现 `ConfirmationManager` 类 - 管理确认策略和白名单
- [ ] 在 `_act()` 前插入确认逻辑 - 根据风险级别决定是否确认
- [ ] CLI 实现 `confirm_handler` - 监听 TOOL_CALL 事件弹出确认
- [ ] 配置开关 - `agent.confirm_safe`/`confirm_moderate`/`confirm_dangerous`

**技术方案**:
```python
# nano_agent/agent/types.py

class RiskLevel(Enum):
    SAFE = "safe"           # 安全：读取、查询
    MODERATE = "moderate"   # 中等：写入、创建
    DANGEROUS = "dangerous" # 危险：删除、Shell

# nano_agent/tools/base.py

class BaseTool:
    risk_level: RiskLevel = RiskLevel.MODERATE

# nano_agent/agent/confirmation.py

class ConfirmationManager:
    def needs_confirmation(self, tool: BaseTool, config: AgentConfig) -> bool:
        """根据风险级别和配置决定是否需要确认"""
        if tool.name in config.confirm_whitelist:
            return False
        return getattr(config, f"confirm_{tool.risk_level.value}", True)

# nano_agent/agent/react.py

class ReActAgent:
    def _act(self, tool_call: ToolCall) -> ToolResult:
        tool = self.tool_registry.get(tool_call.name)

        # 确认逻辑
        if self.confirmation.needs_confirmation(tool, self.config):
            self.events.emit(AgentEvent.TOOL_CALL, {"tool": tool_call})
            # 等待外部确认（通过事件回调设置结果）
            if not self._wait_for_confirmation():
                return ToolResult(success=False, error="用户取消")

        return self.execute_tool(tool_call.name, tool_call.arguments)
```

---

### v0.6.5 - Git 集成与状态回退

**目标**: 集成 Git 实现自动提交和状态回退能力。

**背景**:
当前 `/undo` 只能撤销当前轮次操作。Git 集成提供更强大的回退能力，支持跨轮次撤销和完整操作历史。

**架构对应**: 基于事件流，监听 TOOL_RESULT 事件自动提交

**任务列表**:
- [ ] 实现 `GitManager` 类 - 检测仓库、自动提交、回退
- [ ] 监听 TOOL_RESULT 事件 - 工具执行后自动提交
- [ ] 监听 RUN_END 事件 - 执行结束时提交（可选）
- [ ] `/undo` 命令增强 - 回退到上一个 Git commit
- [ ] `/history` 命令 - 查看可回退的操作历史
- [ ] 配置开关 - `git.enabled`/`git.auto_commit`/`git.commit_mode`

**技术方案**:
```python
# nano_agent/agent/git_manager.py

class GitManager:
    def __init__(self, repo_path: str = "."):
        self.repo = self._detect_repo(repo_path)

    def is_enabled(self) -> bool:
        return self.repo is not None

    def auto_commit(self, message: str, step_info: dict = None):
        """自动提交当前更改"""
        if not self.is_enabled():
            return
        changed = [item.a_path for item in self.repo.index.diff(None)]
        if changed:
            self.repo.index.add(changed)
            self.repo.index.commit(message)

    def undo(self) -> bool:
        """回退到上一个 commit"""
        if self.is_enabled():
            self.repo.git.reset('--hard', 'HEAD~1')
            return True
        return False

# nano_agent/cli/main.py

# CLI 初始化时注册 Git 监听
if config.git.enabled:
    git_manager = GitManager()
    agent.events.on(AgentEvent.TOOL_RESULT, lambda e, d: git_manager.auto_commit(d['tool']))
```
        """获取操作历史"""
        return [
            {"hash": c.hexsha[:7], "message": c.message, "time": c.committed_datetime}
            for c in list(self.repo.iter_commits())[:limit]
        ]

# 配置示例
git:
  enabled: true              # 启用 Git 集成
  auto_commit: true          # 自动提交
  commit_mode: "step"        # step=每步提交, round=每轮提交
  branch_prefix: "nano-"     # 工作分支前缀（可选）
```

---

### v0.7.0 - 流式执行

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

### v0.7.1 - 异步流式执行

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

### v0.8.0 - 模式切换

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

### v0.9.0 - Hooks 机制

**目标**: 提供优雅的扩展机制，解耦组件间的依赖。

**背景**:
当前 undo 操作需要返回值传递链条来更新 UI 层变量，不够优雅。Hooks 机制可以让组件间通信更加解耦。

**架构归属**: 基础设施层 - 扩展系统

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
| v0.6.0 | 编排层与执行层分离 ✅ | AgentOrchestrator、阶段拆分、事件流、预算检查、会话管理 |
| v0.6.1 | 上下文管理 ✅ | ContextManager、三层压缩策略、九段式摘要、Token 估算 |
| v0.6.2 | 前置规划 ✅ | PlanMode、Plan 持久化、多轮规划、CLI 命令 |
| v0.6.3 | PlanMode 演进优化 | EventEmitter 集成、I/O 无关设计、CLI 包装层 |
| v0.6.4 | 渐进式执行与用户确认 | RiskLevel 分级、ConfirmationManager、工具确认 |
| v0.6.5 | Git 集成与状态回退 | GitManager、自动提交、/undo 增强 |
| v0.7.0 | 流式执行 | ExecutionHandle、run_stream()、事件生成器 |
| v0.7.1 | 异步流式执行 | 异步生成器、LLM 流式 API 对接 |
| v0.8.0 | 模式切换 | Agent/Shell 模式切换，直接执行基础命令 |
| v0.9.0 | Hooks 机制 | 解耦组件间依赖，优雅的回调扩展 |
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