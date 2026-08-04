# CLAUDE.md

> **定位**: 开发者入口索引 — 各维度仅列简介与指针，详情按需通过工具（Read/Grep/Glob）读取
>
> **进度**: [ROADMAP.md](ROADMAP.md) | **BUG 复盘**: [BUGLIST.md](BUGLIST.md) | **更新规范**: [docs/update-checklist.md](docs/update-checklist.md)

---

## 维度一：代码结构 → `nano_agent/`

| 子目录 | 一句话 | 关键入口文件 |
|--------|--------|-------------|
| agent/ | 执行层：ReAct 循环、Token 优化、管控护栏、提示词 | base.py, react.py, orchestrator.py, prejudgment.py, router.py, token_budget.py, cache.py, output_simplifier.py, sanitizer.py, circuit_breaker.py, prompt_builder.py |
| cli/ | 交互层：命令处理、展示层、配置显示 | main.py, displays.py, console.py, config_display.py, constants.py |
| config/ | 配置定义与加载 | schema.py, loader.py, model_contexts.yaml |
| core/ | 构建器与注册表 | builder.py, registry.py, types.py |
| llm/ | LLM 客户端 + 重试/限流/provider 解耦 | base.py, anthropic.py, ollama.py, openai_compatible.py, retry.py, rate_limiter.py, normalizer.py |
| memory/ | 多级记忆 + 存储后端 | short_term.py, hybrid.py, long_term.py, persistent.py, gc.py, migration.py, storage/(file_storage, sqlite_storage) |
| monitoring/ | 执行追踪与统计上报 | tracker.py, metrics.py, raw_data.py, reporter.py, token_analyzer.py |
| skills/ | 技能定义与加载 | base.py, loader.py |
| tools/ | 工具注册 + 内建工具 + 标准化输出 | base.py, registry.py, plugin.py, standard_output.py, resource_limiter.py, builtin/(file_ops, shell, python_executor, web_search, memory_tools, plan_tools) |
| utils/ | 通用工具函数 | patterns.py, strings.py |

协议：需要具体模块实现时 Read 对应文件；需要理解模块间关系时 Read docs/architecture.md。

---

## 维度二：开发进度 → ROADMAP.md, BUGLIST.md, docs/superpowers/

| 条目 | 内容 | 何时读取 |
|------|------|---------|
| ROADMAP.md | 版本规划（v0.1–v0.9.2 ✅，v0.10–v0.16 规划）+ 特性总览表 + 测试系统规划（T1/T2/T3） | 了解进度、开始新版本开发 |
| BUGLIST.md | BUG-001~009 复盘（问题→根因→修复→教训） | 修 BUG 前参考、复盘 |
| docs/superpowers/specs/ | 大功能设计文档（如 CLI 输出标准化设计） | 开始大功能前 |
| docs/superpowers/plans/ | 对应实施计划 | 执行设计时 |

---

## 维度三：架构/功能/约束/技术文档 → `docs/`

| 文件 | 一句话 | 何时读取 |
|------|--------|---------|
| architecture.md | 分层架构与数据流（含 mermaid 图） | 理解系统结构、新增组件 |
| api.md | 完整 API 参考 | 查接口签名/用法 |
| tutorial.md | 使用教程 | 用户上手引导 |
| constraints.md | 硬限制 + 软限制 + 交互图 | 新增终止/检测机制 |
| plugins.md | 插件开发指南 | 开发外部插件 |
| skill-development.md | 技能开发指南 | 开发新技能 |
| token-feature-tree.md | Token 特性树（✅/⏳/🔴 标注 + 版本号） | Token 优化相关工作 |
| token-optimization-methodology.md | Token 优化方法论 | 设计新 Token 优化方案 |
| agent-control-audit.md | 管控体系审计（四层 16 控制点） | 审查/增强安全管控 |
| update-checklist.md | 代码更新后固定检查清单 | 提交前自查 |
| testing.md | 测试指南 | 了解测试策略、编写新测试 |
| examples/ | 配置示例（ollama/online/default） | 用户配置参考 |

---

## 维度四：测试 → `tests/`, docs/testing.md, scripts/

| 条目 | 内容 | 何时使用 |
|------|------|---------|
| tests/ | 78 个 test_\<module\>.py 按模块对应 | 运行/新增测试 |
| tests/conftest.py | 共享 fixtures | 理解测试基础设施 |
| tests/factories.py | Mock 工厂函数 | 编写新测试 |
| tests/run_tests.py | 自定义运行器（支持 --coverage） | 本地快速验证 |
| tests/test_cases.xlsx | 测试用例 Excel 记录 | 新增测试后更新 |
| pytest markers | unit / integration / e2e / slow | 分层运行（-m unit） |
| 覆盖率 | pytest-cov 门禁 ≥54% | 质量检查 |
| scripts/test_token_consumption.py | Token 消耗专项验证（独立于 pytest） | Token 修改后 |

---

## 维度五：技术栈与工程工具 → pyproject.toml, scripts/, .pre-commit-config.yaml

| 条目 | 内容 |
|------|------|
| pyproject.toml | 运行时依赖: requests, pyyaml, httpx；开发依赖: pytest, black, pre-commit, pytest-cov, pytest-asyncio；可选: sentence-transformers |
| 构建 | setuptools + pyproject.toml；CLI 入口: `nano-agent` |
| Python | ≥3.10，支持 3.10–3.13 |
| pre-commit | 7 个 hooks（6 检查脚本 + black），git commit 时自动运行 |
| scripts/ | check_version_consistency / check_doc_updates / check_test_cases / check_config_chain / check_show_commands / check_interface_implementation |

---

## 维度六：其他

| 条目 | 说明 |
|------|------|
| .nano_agent/ | 本地运行配置（config.yaml, skills/） |
| examples/ | 插件示例（tool_weather.py）+ 技能示例（coding/translation/web_search） |
| NANOPROJECT.md | `/init` 命令由 LLM 自动生成的项目摘要 |
| main.py / ChatDemo.py | PyCharm 示例残留，非项目代码 |
| 记忆系统 | `~/.claude/projects/-Users-tobytywang-Repositories-NanoAgent/memory/` — Claude Code 会话记忆（独立于 NanoAgent 的 memory/） |

---

## Quick Commands

```bash
pip install -e ".[dev]"               # 安装 + 开发依赖
pytest tests/ -v                      # 运行所有测试
python tests/run_tests.py --coverage  # 覆盖率
black .                               # 格式化
pre-commit run --all-files            # 全量检查
```

**CLI**: `nano-agent`（恢复最近会话）/ `-n`（新建）/ `-l`（列出）/ `-r <ID>`（恢复指定）/ `-d <ID>`（删除）/ `--clean-sessions`（清理低价值会话）/ `-c <path>`（指定配置）

---

## Key Patterns

- **ABC 基类**: BaseAgent, BaseLLM, BaseMemory, BaseTool, BaseStorage
- **ReAct 循环**: Think → Act → Observe; max_iterations 限制; 置信度早停; Token 预算管理
- **LLM 接口**: chat() → (text, tool_calls); chat_stream() 流式

---

## Critical Rules

| # | 规则 | 详情 |
|---|------|------|
| 1 | **版本同步** | 发版时 pyproject.toml + `__init__.py` 双处一致；ROADMAP 版本标题加 ✅（pre-commit 自动检查） |
| 2 | **pre-commit** | 7 hooks 必过；禁止 `--no-verify` |
| 3 | **新功能全链路** | schema → loader（parse+save）→ config_display → create_agent → 测试（详情: update-checklist.md §2.1） |
| 4 | **接口扩展** | 给基类加方法 → 检查所有子类 → 补接口一致性测试（pre-commit: check_interface_implementation） |
| 5 | **BUG 修复** | 补回归测试 + 更新 BUGLIST.md + 更新 test_cases.xlsx（详情: update-checklist.md §3.2） |
| 6 | **测试运行** | pytest 前台运行；禁止 `\| tail`/`\| head` 管道；长命令用 --timeout（详情: update-checklist.md §九） |
| 7 | **新增测试** | 同步更新 tests/test_cases.xlsx |
