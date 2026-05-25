# CLAUDE.md

> **定位**: 开发者日常工作手册 - 快速参考与操作规范
>
> **战略规划**: 详见 [ROADMAP.md](ROADMAP.md) - 版本规划、测试系统、架构演进
>
> **BUG 复盘**: 详见 [BUGLIST.md](BUGLIST.md) - BUG 记录与经验教训

## Project Overview

Lightweight ReAct Agent framework in Python 3.10+ with Ollama backend.

## Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
python tests/run_tests.py --coverage

# Format code
black .
```

**CLI Usage** (see `nano-agent -h` for full options):
- `nano-agent` - Resume most recent session (default)
- `nano-agent -n` - Start new session
- `nano-agent -l` - List saved sessions
- `nano-agent -r <ID>` - Resume specific session
- `nano-agent -d <ID>` - Delete session
- `nano-agent --clean-sessions` - Auto-clean low-value sessions
- `nano-agent -c <path>` - Use specific config file

## Architecture

```
nano_agent/
├── agent/          # ReAct agent (base.py, react.py, prompts.py, undo.py)
├── cli/            # Entry point, console utilities
├── config/         # YAML config loading and schemas
├── llm/            # LLM client layer (abstract base + Ollama)
├── memory/         # Memory types (short_term, hybrid, long_term)
│   └── storage/    # Storage backends (file, sqlite)
├── monitoring/     # Execution tracking and reporting
├── skills/         # Skill definitions
└── tools/          # Built-in tools (python_execute, file_*, shell_execute)
```

## Key Patterns

- **Abstract Base Classes**: `BaseAgent`, `BaseLLM`, `BaseMemory`, `BaseTool`, `BaseStorage` use ABC
- **ToolResult**: Dataclass with `success`, `output`, `error` fields
- **ToolRegistry / SkillRegistry**: Central registries for tools and skills
- **ReAct Loop**: Think → Act → Observe cycle with `max_iterations` limit
- **LLM Interface**: `chat()` returns `(text, tool_calls)`, `chat_stream()` for streaming

## Configuration

Config loaded from YAML (priority: project > global > defaults). See `docs/examples/config.yaml`.

Key sections: `llm`, `agent`, `memory`, `skills`, `plugins`, `logging`, `output_style`. Use `/config` in interactive mode to view current settings.

### Output Style (Token Efficiency)

Control token consumption with `output_style` configuration:

```yaml
output_style:
  style: concise          # concise / standard / detailed
  tool_output_max_tokens: 500
```

| Style | System Prompt | Expected Savings | Use Case |
|-------|---------------|------------------|----------|
| concise | ~300 tokens | ~70% | Quick queries, simple tasks |
| standard | ~800 tokens | ~50% | General use (default) |
| detailed | ~1500 tokens | None | Complex analysis, debugging |

## Built-in Tools

- `python_execute`: Execute Python code in subprocess
- `file_read`/`file_write`/`file_search`: File operations
- `shell_execute`: Cross-platform shell command execution
- `web_search`: Web search functionality
- `memorize`/`recall`/`list_memories`/`forget`: Long-term memory tools
- `get_stats`: Get execution statistics

---

## Development Guidelines

### Before Committing

1. **Tests**: `pytest tests/ -v` - all tests must pass
2. **Coverage**: Check coverage when fixing bugs or adding features
3. **Documentation**: Update help text, `docs/api.md`, `docs/tutorial.md`
4. **Roadmap**: Update ROADMAP.md if adding/changing features
5. **Version**: Update version in `pyproject.toml` if releasing new version

### Testing

- Write tests in `tests/` directory (not `python -c` ad-hoc)
- Check coverage after bug fixes or feature changes
- Run tests after resolving merge conflicts
- **发现 BUG 后必须补充测试** - 防止回归，参见 [BUGLIST.md](BUGLIST.md)

> **详细测试规划**: 参见 [ROADMAP.md - 测试系统规划](ROADMAP.md#测试系统规划与功能版本并行)

### 新增功能完整链路

实现新功能时，确保以下环节全部连通：

1. **配置定义** → `config/schema.py` 添加配置项
2. **配置显示** → `_show_config()` 中显示
3. **配置保存** → `_init_config_file()` 中保存
4. **CLI 集成** → `create_agent()` 中使用新配置
5. **测试验证** → 单元测试 + 端到端验证

**常见遗漏**:
- 配置添加了但忘记在 `_show_config()` 显示
- 核心模块实现了但忘记在 `create_agent()` 调用
- 只有单元测试，缺少端到端验证
- **给基类/接口添加方法时，遗漏了某个子类** - 参见 [BUGLIST.md BUG-001](BUGLIST.md#bug-001-persistentmemory-缺失-stable_system_prompt-方法)

### 接口扩展检查清单

当给基类（如 `BaseMemory`、`BaseTool`、`BaseLLM`）添加新方法时：

1. **列出所有子类** - `grep -r "class.*BaseX" nano_agent/`
2. **逐个检查实现** - 确保每个子类都实现了新方法
3. **添加接口一致性测试** - 参考 `tests/test_memory_interface.py`
4. **测试所有组合场景** - 如 `HybridMemory` 可使用不同的 working memory 类型

### Documentation

When adding or modifying features, always update:
- **Interactive help**: `_show_help()` in `nano_agent/cli/main.py`
- **API documentation**: `docs/api.md`
- **Tutorial**: `docs/tutorial.md` if it affects user workflow

### Bash Commands

Always provide a clear purpose explaining what, why, and expected output:

```bash
# Purpose: Verify session management feature works correctly
# by testing the --list-sessions CLI option
python -m nano_agent.cli.main --list-sessions
```

---

## Design Philosophy

### User Intervention Control

NanoAgent follows a "critical decision confirmation" model:

**The Problem**: Users want final authority without micromanaging execution details.

**The Solution**: The `undo` mechanism provides "post-hoc veto power":
1. **Audit transparency**: Show brief summary after each memorize operation
2. **One-key veto**: User can type `undo` to revert the last operation
3. **No interruption**: Normal flow continues unless user explicitly intervenes

Example output:
```
[记忆] 存储用户名字: "王五" (importance: 0.8)
       输入 'undo' 撤销，或继续对话
```

**Why undo beats CLI commands**:
- `--memories`, `--forget`, `--set-importance` require users to manage details proactively
- `undo` gives users veto power without forcing them into execution details
- Like the emperor's veto: ministers handle affairs, emperor can strike down any decision

**Design principles**:
- Daily operations flow uninterrupted
- Information is transparent (user sees what happened)
- User can veto anytime with `undo`
- CLI commands are fallback for advanced use, not primary workflow
