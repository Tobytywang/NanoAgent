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

### v0.1.0 (当前版本)

- [x] ReAct 模式实现
- [x] 基础工具系统（文件操作、Shell、Python 执行）
- [x] Ollama 本地 LLM 支持
- [x] OpenAI 兼容 API 支持
- [x] YAML 配置系统
- [x] CLI 交互界面

---

### v0.2.0 - 持久化记忆

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

### v0.3.0 - 技能包机制

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

### v0.4.0 - 运行监控

**目标**: 提供运行时监控和调试能力。

**任务列表**:
- [ ] 实现 Token 使用统计
- [ ] 实现调用链路追踪
- [ ] 实现耗时分析
- [ ] 添加调试日志输出
- [ ] 支持导出运行报告

---

### v0.5.0 - 框架完善

**目标**: 提供完整的框架能力，准备发布。

**任务列表**:
- [ ] 插件化工具加载机制
- [ ] 多存储后端支持（File/SQLite）
- [ ] 完善的 API 文档
- [ ] 使用示例和教程
- [ ] PyPI 发布准备

---

## Future（非核心，延后）

| 特性 | 说明 |
|------|------|
| 计划与反思循环 | Plan-Execute 或 RCI 反思 |
| 多 Agent 编排 | 并发、辩论、角色分工 |
| 安全审批/沙箱 | 命令行确认、危险操作拦截 |
| Web UI | 更友好的交互界面 |
| 长期记忆 | 支持语义搜索的知识库 |

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
