# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NanoAgent is a lightweight AI Agent framework implementing the ReAct (Reasoning + Acting) pattern. It's written in Python 3.10+ and uses Ollama as the local LLM backend.

## Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run interactive agent
nano-agent

# Run with custom config/model
nano-agent -c config/config.yaml
nano-agent -m llama3

# Run tests
pytest tests/ -v

# Run tests with coverage
python tests/run_tests.py --coverage

# Format code
black .
```

## Architecture

```
nano_agent/
├── agent/          # ReAct agent implementation (base.py, react.py, prompts.py)
├── llm/            # LLM client layer (abstract base + Ollama implementation)
├── memory/         # Conversation history management
├── tools/          # Built-in tools: python_execute, file_*, shell_execute
├── config/         # YAML configuration loading and schemas
└── cli/            # Entry point and console utilities
```

## Key Patterns

- **Abstract Base Classes**: All major components (BaseAgent, BaseLLM, BaseMemory, BaseTool) use ABC with `@abstractmethod`
- **ToolRegistry**: Central registry for tool management
- **ToolResult**: Dataclass with `success`, `output`, `error` fields for consistent tool outputs
- **ReAct Loop**: Agent follows Think -> Act -> Observe cycle with configurable `max_iterations`
- **LLM chat() return**: Tuple of `(text_response, tool_calls)`

## Configuration

Configuration is loaded from YAML files (see `config/config.yaml`):

```yaml
llm:
  provider: ollama
  model: qwen3.5:9b
  base_url: http://localhost:11434
  timeout: 120

agent:
  max_iterations: 10
  verbose: true

memory:
  type: short_term
  max_messages: 50
```

## Built-in Tools

- `python_execute`: Execute Python code in subprocess
- `file_read`/`file_write`/`file_search`: File operations
- `shell_execute`: Cross-platform shell command execution
