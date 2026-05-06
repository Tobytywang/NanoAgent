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

---

### v0.5.2 - 渐进式执行与确认

**目标**: 改善 Agent 的交互模式，避免"一锤子买卖"式的工作方式。

**背景**:
实际使用中发现 Agent 存在以下问题：
1. 一次视图进行过多的开发工作，而不是一步一步慢慢来
2. 做事情之前缺少规划，没有 plan 就直接开整
3. 做事情之前没有征求用户同意，就直接开整

**任务列表**:
- [ ] 前置规划 - 复杂任务先制定计划，展示给用户确认后再执行
- [ ] 渐进式执行 - 一次只做一小步，等待用户确认后继续
- [ ] 用户确认机制 - 关键操作前征求用户同意

**技术方案**:
```python
# 执行流程
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
            # 展示即将执行的步骤
            print(f"即将执行: {step}")

            # 用户确认
            if not self.confirm("是否执行此步骤?"):
                return "已取消"

            # 执行单步
            result = self.execute_step(step)

        return result
```

---

### v0.5.3 - Git 集成与状态回退

**目标**: 接入 Git 工作流，支持撤销/回退操作。

**任务列表**:
- [ ] Git 状态检测 - 检测当前是否在 Git 仓库中
- [ ] 自动提交 - 每步操作后自动 commit（可配置）
- [ ] 撤销命令 - `/undo` 回退到上一个状态
- [ ] 回退历史 - 查看可回退的操作历史
- [ ] 分支管理 - 可选的分支隔离功能

**技术方案**:
```python
# Git 集成示例
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

# Agent 集成
class GitAwareAgent(InteractiveAgent):
    def execute_step(self, step):
        result = super().execute_step(step)
        self.git_manager.auto_commit(f"Execute: {step.name}")
        return result
```

---

### v0.6.1 - 配置系统优化

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

### v0.6.2 - Hooks 机制

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

### v0.7.0 - 反思与规划能力

**目标**: 增强 Agent 的推理能力，支持复杂任务的规划与自我改进。

**任务列表**:
- [ ] 反思能力 - 执行后自我评估结果质量并调整策略
- [ ] RCI (Reason-Call-Interact) 反思循环实现
- [ ] Plan-Execute 模式增强 - 基于反思优化计划

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

### v0.8.0 - 主动学习能力

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

### v0.9.0 - 个性化与角色

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

### v0.10.0 - 多 Agent 协作

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

### v0.11.0 - 安全与体验

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
| v0.5.1 | 功能优化与增强 | CLI 增强、/init、/config、/memory、/setname 等 |
| v0.5.2 | 渐进式执行与确认 | 前置规划、逐步执行、用户确认 |
| v0.5.3 | Git 集成与状态回退 | 自动提交、撤销/回退操作 |
| v0.6.1 | 配置系统优化 | 自动显示/保存配置项 |
| v0.6.2 | Hooks 机制 | 解耦组件间依赖，优雅的回调扩展 |
| v0.7.0 | 反思与规划能力 | RCI 反思循环、Plan-Execute 增强 |
| v0.8.0 | 主动学习 | 知识提取、语义搜索 |
| v0.9.0 | 个性化角色 | 可配置性格、专业领域 |
| v0.10.0 | 多 Agent 协作 | 编排框架、Agent 通信 |
| v0.11.0 | 安全与体验 | 沙箱、Web UI、权限控制 |

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
