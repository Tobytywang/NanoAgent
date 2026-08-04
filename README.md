# NanoAgent

一个轻量级的 AI Agent 框架，实现 ReAct (Reasoning + Acting) 模式，专为学习和实验设计。

**[使用教程](docs/tutorial.md)** | **[API 文档](docs/api.md)** | **[开发路线图](ROADMAP.md)**

## 核心特性

- **ReAct 模式**: 实现 Think → Act → Observe 推理循环
- **工具调用**: 内置文件操作、Shell、Python 执行、网络搜索等工具
- **多 LLM 支持**: Ollama 本地模型 + OpenAI 兼容 API（OpenAI、DeepSeek、Moonshot 等）
- **持久化记忆**: 会话保存/恢复，跨会话记忆
- **技能包机制**: 可扩展技能包，支持热加载
- **运行监控**: Token 统计、上下文使用率、LLM 调用追踪
- **模块化设计**: 抽象基类分层，易于扩展
- **配置灵活**: YAML 配置，支持自定义模型和参数

## 快速开始

### 1. 安装

```bash
# macOS/Linux 安装 Ollama（本地 LLM 服务）
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b

# 克隆并安装 NanoAgent
git clone <repository-url>
cd NanoAgent
pip install -e ".[dev]"
```

### 2. 命令行使用

```bash
nano-agent            # 交互模式（恢复最近会话）
nano-agent -n         # 新建会话
nano-agent -c path    # 使用自定义配置文件
```

### 3. 代码中使用

```python
from nano_agent.llm import create_llm
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.agent.react import ReActAgent
from nano_agent.tools.builtin import create_default_tool_registry

llm = create_llm(provider="ollama", model="qwen2.5:7b")
# llm = create_llm(provider="deepseek", api_key_env="DEEPSEEK_API_KEY")

memory = ShortTermMemory()
tools = create_default_tool_registry()

agent = ReActAgent(
    llm=llm,
    memory=memory,
    tool_registry=tools,
    max_iterations=10,
    verbose=True,
)

response = agent.run("帮我创建一个 hello.txt 文件，内容是 'Hello World'")
print(response)
```

## 配置

配置文件位于 `.nano_agent/config.yaml`，首次运行自动生成。配置覆盖 `llm`、`agent`、`memory`、`tools`、`skills`、`plugins`、`logging`、`output_style` 等部分，完整示例见 [docs/examples/config.yaml](docs/examples/config.yaml)，交互模式下可用 `/config` 查看当前配置。

## 运行监控

运行时显示 Token 消耗、LLM 调用次数、上下文使用率（超过 80% 警告）和工具调用追踪：

```
📊 本轮:   1500 tokens |   2.50s | LLM调用:   2 | 迭代: 2 | 工具: ✓web_search
📊 总计:  15000 tokens |  45.20s | LLM调用:  12 | 上下文: 11.7% (15000/128000)
```

## 文档导航

| 文档 | 内容 |
|------|------|
| [docs/tutorial.md](docs/tutorial.md) | 使用教程（含会话管理、在线 API 配置） |
| [docs/api.md](docs/api.md) | 完整 API 参考（含内置工具列表） |
| [docs/plugins.md](docs/plugins.md) | 插件开发指南 |
| [docs/skill-development.md](docs/skill-development.md) | 技能开发指南 |
| [docs/architecture.md](docs/architecture.md) | 架构设计（含 ReAct 原理与分层结构） |
| [docs/constraints.md](docs/constraints.md) | 资源约束与限制 |
| [ROADMAP.md](ROADMAP.md) | 版本规划与开发路线图 |

## 许可证

MIT License
