# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

Key sections: `llm`, `agent`, `memory`, `skills`, `plugins`, `logging`. Use `/config` in interactive mode to view current settings.

## Built-in Tools

- `python_execute`: Execute Python code in subprocess
- `file_read`/`file_write`/`file_search`: File operations
- `shell_execute`: Cross-platform shell command execution
- `web_search`: Web search functionality
- `memorize`/`recall`/`list_memories`/`forget`: Long-term memory tools
- `get_stats`: Get execution statistics

## Development Guidelines

### Before Committing

Always verify the following before committing code changes:

1. **Tests**: Run `pytest tests/ -v` to ensure all tests pass
2. **Test Coverage**: If fixing a bug or adding/modifying features, add test cases if coverage is missing
3. **Documentation**: Update relevant documentation (help text, docs/api.md, docs/tutorial.md)
4. **Roadmap**: Check if ROADMAP.md needs updates for new/changed features

### Testing

- Write formal test cases in `tests/` directory instead of using `python -c` for ad-hoc testing
- **Always check test coverage** when fixing bugs or adding/modifying features. Add tests if missing.
- **Run tests after resolving merge conflicts** to verify no syntax errors or broken functionality

### Documentation

When adding or modifying features, always update the relevant documentation:
- **Interactive help**: Update `_show_help()` in `nano_agent/cli/main.py`
- **API documentation**: Update `docs/api.md`
- **Tutorial**: Update `docs/tutorial.md` if it affects user workflow

### 新增功能的完整链路

实现新功能时，需确保以下环节全部连通：

1. **配置定义** → `config/schema.py` 添加配置项
2. **配置显示** → `_show_config()` 中显示
3. **配置保存** → `_init_config_file()` 中保存
4. **CLI 集成** → `create_agent()` 中使用新配置
5. **测试验证** → 单元测试 + 端到端验证

常见遗漏：
- 配置添加了但忘记在 `_show_config()` 显示
- 核心模块实现了但忘记在 `create_agent()` 调用
- 只有单元测试，缺少端到端验证

### Roadmap

When adding or modifying features, always check `ROADMAP.md`:
- If the feature is described in ROADMAP.md, ensure the implementation matches the description
- If the feature is NOT described, add it to the appropriate version section
- Periodically review git commit history to update ROADMAP.md with important feature details

### Bash Commands

When executing Bash commands, always provide a clear purpose explaining:
- What the command does
- Why it's needed
- What output is expected

Example:
```bash
# Purpose: Verify the session management feature works correctly
# by testing the --list-sessions CLI option
python -m nano_agent.cli.main --list-sessions
```

## Design Philosophy

### User Intervention Control

NanoAgent follows a "critical decision confirmation" model for balancing user control and LLM automation:

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
