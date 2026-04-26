# NanoAgent Roadmap

本文档记录 NanoAgent 的开发路线图和增强计划。

## 版本规划

### v0.1.0 (当前版本)

- [x] ReAct 模式实现
- [x] 基础工具系统（文件操作、Shell、Python 执行）
- [x] Ollama 本地 LLM 支持
- [x] OpenAI 兼容 API 支持
- [x] YAML 配置系统
- [x] CLI 交互界面

---

### v0.2.0 - 持久化记忆

**目标**: 实现跨会话记忆能力，让 Agent 能够记住之前的对话和经验。

**任务列表**:
- [ ] 实现 `BaseStorage` 存储抽象接口
- [ ] 实现 `FileStorage` JSON 文件存储
- [ ] 实现 `PersistentMemory` 持久化记忆
- [ ] 扩展配置支持存储后端选择
- [ ] 添加会话管理（新建、恢复、列出历史）
- [ ] 更新 CLI 支持会话选择

**新增文件**:
```
nano_agent/memory/
├── persistent.py
└── storage/
    ├── __init__.py
    ├── base.py
    └── file_storage.py
```

**配置示例**:
```yaml
memory:
  type: persistent
  storage:
    type: file
    path: .nano_agent/memory
```

---

### v0.3.0 - 人机协作

**目标**: 实现关键操作审批机制，让用户能够控制高风险行为。

**任务列表**:
- [ ] 实现 `HumanInterface` 人机交互抽象
- [ ] 实现 `ConsoleInterface` 控制台交互
- [ ] 实现 `ApprovalPolicy` 审批策略
- [ ] 实现 `ApprovalManager` 审批管理
- [ ] 实现 `CollaborativeAgent` 协作 Agent
- [ ] 添加 `ask_user` 工具

**新增文件**:
```
nano_agent/human/
├── __init__.py
├── base.py
├── console_interface.py
└── approval.py
```

**配置示例**:
```yaml
human_collab:
  enabled: true
  auto_approve_low_risk: true
  tools_requiring_approval:
    - shell_execute
    - file_write
```

---

### v0.4.0 - 任务规划

**目标**: 实现复杂任务分解能力，让 Agent 能够有计划地执行任务。

**任务列表**:
- [ ] 实现 `Task` 和 `Plan` 数据结构
- [ ] 实现 `BasePlanner` 规划器抽象
- [ ] 实现 `SimplePlanner` 基于 LLM 的规划器
- [ ] 实现 `PlanningAgent` 规划 Agent
- [ ] 添加规划相关提示词
- [ ] 支持任务依赖和并行执行

**新增文件**:
```
nano_agent/planning/
├── __init__.py
├── base.py
├── task.py
├── simple_planner.py
└── prompts.py
```

**配置示例**:
```yaml
planning:
  enabled: true
  planner_type: simple
  approve_plans: false
```

---

### v0.5.0 - 自我反思

**目标**: 实现执行评估能力，让 Agent 能够从失败中学习和改进。

**任务列表**:
- [ ] 实现 `BaseReflector` 反思器抽象
- [ ] 实现 `SimpleReflector` 简单反思器
- [ ] 实现 `ReflectiveAgent` 反思 Agent
- [ ] 支持失败重试和策略调整
- [ ] 添加反思相关提示词

**新增文件**:
```
nano_agent/reflection/
├── __init__.py
├── base.py
├── simple_reflector.py
└── prompts.py
```

**配置示例**:
```yaml
reflection:
  enabled: true
  max_retries: 2
```

---

### v0.6.0 - 统一集成

**目标**: 整合所有能力，提供统一的增强型 Agent。

**任务列表**:
- [ ] 实现 `EnhancedAgent` 统一入口
- [ ] 实现工厂函数 `create_enhanced_agent()`
- [ ] 完善配置系统
- [ ] 添加完整测试覆盖
- [ ] 更新文档和示例

**配置示例**:
```yaml
# 完整增强配置
memory:
  type: persistent
  storage:
    type: file
    path: .nano_agent/memory

planning:
  enabled: true

reflection:
  enabled: true
  max_retries: 2

human_collab:
  enabled: true
  tools_requiring_approval:
    - shell_execute
    - file_write
```

---

## 未来展望

### v0.7.0+ 可能的方向

- **长期记忆**: 支持语义搜索的知识库
- **层级规划**: 多层任务分解
- **学习型反思**: 积累经验，避免重复错误
- **多 Agent 协作**: 不同角色的 Agent 协作
- **RAG 支持**: 文档检索增强生成
- **Web 界面**: 基于 Web 的交互界面

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
