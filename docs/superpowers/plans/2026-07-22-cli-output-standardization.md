# CLI 输出标准化与展示层重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 main.py 中的显示函数抽出为独立 displays.py，统一 Console 高阶格式化方法，统一所有命令输出为中文 + Console.print style。

**Architecture:** console.py 新增 5 个格式化方法 → displays.py 集中所有 _show_* → main.py 保留 _handle_* 和事件循环。

**Tech Stack:** Python 3.10+, pytest

## Global Constraints

- 不修改 config_display.py（已独立）
- 不修改命令处理逻辑 _handle_* 函数
- 不修改事件循环结构
- 不修改测试

---
## 文件结构

### 创建
- `nano_agent/cli/displays.py` — 所有 _show_* 展示函数 + _get_display_width / _pad_to_width

### 修改
- `nano_agent/cli/console.py` — 新增 5 个格式化方法
- `nano_agent/cli/main.py` — 删除迁移的函数，替换 import，修复语言/style

## 引用关系

```
main.py → imports Console, Commands, displays._show_*
              │
displays.py → imports Console, GracefulExitManager (from main)
                  │
console.py → (无 nano_agent 内部 import)
```

### Task 1: Console 类增强

**Files:**
- Modify: `nano_agent/cli/console.py:73-92`
- No test changes (纯工具方法, 现有 Console 测试覆盖)

**Interfaces:**
- Produces: `Console.print_title(title)`, `Console.print_subtitle(title)`, `Console.print_end()`, `Console.print_kv(key, value, key_width=12, indent=0)`, `Console.print_progress_bar(pct, width=40)`

- [ ] **Step 1: 在 console.py 末尾新增 5 个格式化方法**

```python
    @classmethod
    def print_title(cls, title: str) -> None:
        """标准标题块"""
        print()
        print("=" * 50)
        print(title)
        print("=" * 50)

    @classmethod
    def print_subtitle(cls, title: str) -> None:
        """标准小标题"""
        print(f"\n## {title}")

    @classmethod
    def print_end(cls) -> None:
        """标准结尾分隔线"""
        print("\n" + "=" * 50 + "\n")

    @classmethod
    def print_kv(cls, key: str, value: str, key_width: int = 12, indent: int = 0) -> None:
        """对齐 key-value 行

        Args:
            key: 键名（可含冒号，如 "工具定义:"）
            value: 值字符串
            key_width: 键区域总显示宽度（含缩进）
            indent: 额外缩进空格数
        """
        prefix = " " * indent
        current_width = 0
        for char in key:
            if '一' <= char <= '鿿':
                current_width += 2
            else:
                current_width += 1
        padding = key_width - current_width - indent
        print(f"{prefix}{key}{' ' * padding} {value}")

    @classmethod
    def print_progress_bar(cls, pct: float, width: int = 40) -> None:
        """标准进度条，用 █ 填充 + · 表示剩余"""
        filled = int(pct / 100 * width)
        bar = "█" * filled + "·" * (width - filled)
        print(f"  [{bar}] {pct:.1f}%")
```

- [ ] **Step 2: 验证无语法错误**

```bash
python -c "from nano_agent.cli.console import Console; Console.print_title('Test'); Console.print_subtitle('Sub'); Console.print_end(); Console.print_kv('名称:', '值'); Console.print_progress_bar(45.0)"
```
预期：打印格式化的标题、子标题、结尾线、kv、进度条，无异常。

- [ ] **Step 3: 提交**

```bash
git add nano_agent/cli/console.py
git commit -m "feat: Console 类新增 print_title / print_subtitle / print_end / print_kv / print_progress_bar"
```

---

### Task 2: 创建 displays.py

**Files:**
- Create: `nano_agent/cli/displays.py`
- Remove from `nano_agent/cli/main.py`: 以下函数定义 + 辅助函数

**Interfaces:**
- Consumes: `Console` (from .console), `GracefulExitManager` (from .main), `MetricsTracker` (from monitoring.tracker), `render_config` (from .config_display)
- Produces: `_show_help()`, `_show_run_stats(agent, config)`, `_show_monitoring_stats(agent)`, `_show_config(config, agent)`, `_show_memory_status(config)`, `_show_stats_status(agent, config)`, `_show_context_composition(agent, config)`, `_show_context_budget(agent, config)`, `_show_estimation_audit(agent, config)`, `_show_iteration_breakdown(agent)`, `_show_session(session_id, config_path)`, `_get_display_width(text)`, `_pad_to_width(text, width, align)`

- [ ] **Step 1: 创建 displays.py，粘贴所有迁移函数**

```python
"""
CLI 展示函数 — 所有 _show_* 函数集中于此。

从 main.py 迁移而来，职责分离：显示逻辑在此，命令处理在 main.py。
"""

from .console import Console
from ..monitoring.tracker import MetricsTracker


def _get_display_width(text: str) -> int:
    """计算字符串的显示宽度（中文字符占 2 宽度）"""
    width = 0
    for char in text:
        if "一" <= char <= "鿿":
            width += 2
        else:
            width += 1
    return width


def _pad_to_width(text: str, width: int, align: str = "left") -> str:
    """将字符串填充到指定显示宽度"""
    current_width = _get_display_width(text)
    if current_width >= width:
        return text
    padding = width - current_width
    if align == "left":
        return text + " " * padding
    elif align == "right":
        return " " * padding + text
    else:  # center
        left_pad = padding // 2
        right_pad = padding - left_pad
        return " " * left_pad + text + " " * right_pad


def _show_help() -> None:
    """显示交互模式帮助信息"""
    Console.print_title("📊 可用命令")

    Console.print_subtitle("基本操作")
    Console.print_kv("/exit, /quit", "退出（保存摘要）", key_width=24)
    Console.print_kv("exit, quit", "直接退出", key_width=24)
    Console.print_kv("/clear", "清空对话", key_width=24)
    Console.print_kv("/undo", "撤销操作（支持 Git 回退）", key_width=24)
    Console.print_kv("/history", "查看操作历史（需要 Git）", key_width=24)
    Console.print_kv("/?, help", "显示帮助", key_width=24)

    Console.print_subtitle("查看信息")
    Console.print_kv("/config", "查看配置", key_width=24)
    Console.print_kv("/memory", "查看记忆状态", key_width=24)
    Console.print_kv("/stats", "查看统计", key_width=24)
    Console.print_kv("/usage", "显示上下文消息组成", key_width=24)
    Console.print_kv("/context", "显示上下文预算分析", key_width=24)
    Console.print_kv("/tools", "查看工具列表", key_width=24)
    Console.print_kv("/skills", "查看技能列表", key_width=24)
    Console.print_kv("/sessions", "查看会话列表", key_width=24)
    Console.print_kv("/plans", "查看已保存的计划", key_width=24)

    Console.print_subtitle("输出控制")
    Console.print_kv("/verbose on", "开启详细输出（工具执行、Token 消耗等）", key_width=24)
    Console.print_kv("/verbose off", "关闭详细输出", key_width=24)
    Console.print_kv("/verbose", "查看当前状态", key_width=24)
    Console.print_kv("/effort concise", "最简模式，低 token 消耗", key_width=24)
    Console.print_kv("/effort standard", "标准模式（默认）", key_width=24)
    Console.print_kv("/effort detailed", "详细模式，最深推理", key_width=24)
    Console.print_kv("/effort", "查看当前推理强度", key_width=24)

    Console.print_subtitle("项目管理")
    Console.print_kv("/init", "初始化项目", key_width=24)
    Console.print_kv("/config init", "生成配置文件（合并）", key_width=24)
    Console.print_kv("/config init -f", "强制覆盖配置文件", key_width=24)
    Console.print_kv("/memory on", "启用长期记忆", key_width=24)
    Console.print_kv("/memory off", "禁用长期记忆", key_width=24)
    Console.print_kv("/stats on", "启用统计自动显示", key_width=24)
    Console.print_kv("/stats off", "禁用统计自动显示", key_width=24)
    Console.print_kv("/stats context", "显示当前上下文组成", key_width=24)
    Console.print_kv("/stats breakdown", "显示各轮消耗趋势", key_width=24)
    Console.print_kv("/stats estimation", "显示估算偏差审计", key_width=24)

    Console.print_subtitle("规划模式")
    Console.print_kv("/plan <任务>", "进入规划模式，制定分阶段计划", key_width=24)
    Console.print_kv("/plans", "列出所有已保存的计划", key_width=24)

    Console.print_subtitle("个性化设置")
    Console.print_kv("/setname", "查看当前名字", key_width=24)
    Console.print_kv("/setname <用户名>", "设置用户名", key_width=24)
    Console.print_kv("/setname <用户名> <Agent名>", "同时设置用户和 Agent 名", key_width=24)
    Console.print_kv("/snapshot", "查看快照状态", key_width=24)
    Console.print_kv("/snapshot list", "列出快照", key_width=24)
    Console.print_kv("/snapshot create", "创建快照（系统自动）", key_width=24)
    Console.print_kv("/snapshot restore <id>", "恢复快照", key_width=24)
    Console.print_kv("/snapshot delete <id>", "删除指定快照", key_width=24)
    Console.print_kv("/snapshot audit", "查看审计日志", key_width=24)
    Console.print_kv("/snapshot rollback <id>", "从审计条目回滚", key_width=24)

    Console.print_end()


def _show_run_stats(agent, config=None) -> None:
    """显示本轮运行的统计信息"""
    # 延迟导入避免循环引用（main.py ← displays.py）
    from .main import GracefulExitManager

    if not GracefulExitManager.show_run_stats:
        return
    if not hasattr(agent, "tracker") or not agent.tracker.run_metrics:
        return

    current_summary = agent.tracker.get_summary()
    session_summary = agent.tracker.get_session_summary()
    if not current_summary or not session_summary:
        return

    # 收集工具调用 (同上，保留现有逻辑)
    tool_counts = {}
    full_report = agent.tracker.get_full_report()
    if full_report and full_report.get("iterations"):
        for iteration in full_report["iterations"]:
            for tool in iteration.get("tool_executions", []):
                status = "✓" if tool["success"] else "✗"
                key = (status, tool["tool_name"])
                tool_counts[key] = tool_counts.get(key, 0) + 1

    tool_types = []
    for (status, name), count in tool_counts.items():
        tool_types.append(f"{status}{name}*{count}" if count > 1 else f"{status}{name}")

    current_duration = current_summary.get("duration_ms", 0) / 1000
    current_tokens = current_summary.get("total_tokens", 0)
    current_iterations = current_summary.get("total_iterations", 0)

    session_duration = session_summary.get("session_duration_ms", 0) / 1000
    session_tokens = session_summary.get("total_tokens", 0)
    session_llm_calls = session_summary.get("total_llm_calls", 0)
    session_runs = session_summary.get("total_runs", 0)

    context_info = ""
    if config and hasattr(config, "llm"):
        context_length = config.llm.get_context_length()
        last_tokens = agent.tracker.get_last_iteration_tokens()
        current_context_tokens = last_tokens.get("prompt_tokens", 0) if last_tokens else 0
        usage_percent = (
            (current_context_tokens / context_length) * 100
            if context_length > 0 and current_context_tokens > 0
            else 0
        )
        if usage_percent >= 80:
            context_info = f" | ⚠️ 上下文: {usage_percent:.1f}%（接近上限!）"
        else:
            context_info = f" | 上下文: {usage_percent:.1f}% ({current_context_tokens}/{context_length})"

    print(
        f"\n📊 本轮: {current_tokens:>6} tokens | {current_duration:>6.2f}s | LLM调用: {current_iterations:>3} | 迭代: {current_iterations}",
        end="",
    )
    if tool_types:
        print(f" | 工具: {', '.join(tool_types)}", end="")
    print(
        f"\n📊 总计: {session_tokens:>6} tokens | {session_duration:>6.2f}s | LLM调用: {session_llm_calls:>3} | 轮次: {session_runs}{context_info}"
    )


def _show_monitoring_stats(agent) -> None:
    """显示监控统计信息"""
    import json

    if not hasattr(agent, "tracker"):
        Console.print("监控不可用", style="warning")
        return

    summary = agent.tracker.get_summary()
    if not summary:
        Console.print("暂无监控数据。请先运行查询。", style="info")
        return

    Console.print_title("📊 监控统计")
    print(f"  会话 ID: {summary.get('session_id', 'N/A')}")
    print(f"  持续时间: {summary.get('duration_ms', 0):.2f} ms")
    print(f"  总迭代数: {summary.get('total_iterations', 0)}")
    print(f"  总 Token: {summary.get('total_tokens', 0)}")
    print(f"  总工具调用: {summary.get('total_tool_calls', 0)}")
    Console.print_kv("- 成功:", str(summary.get('successful_tool_calls', 0)), indent=4)
    Console.print_kv("- 失败:", str(summary.get('failed_tool_calls', 0)), indent=4)

    full_report = agent.tracker.get_full_report()
    if full_report and full_report.get("iterations"):
        print(f"\n## 迭代明细")
        for iteration in full_report["iterations"]:
            print(f"\n  迭代 {iteration['iteration_number']}:")
            if iteration.get("llm_call"):
                llm = iteration["llm_call"]
                print(f"    LLM: {llm['model']}")
                print(f"      Token: {llm['prompt_tokens']} 输入 + {llm['completion_tokens']} 输出 = {llm['total_tokens']} 总计")
                print(f"      延迟: {llm['latency_ms']:.2f} ms")
                print(f"      工具调用: {llm['tool_calls_count']}")
            if iteration.get("tool_executions"):
                print(f"    工具执行:")
                for tool in iteration["tool_executions"]:
                    status = "✓" if tool["success"] else "✗"
                    print(f"      {status} {tool['tool_name']}: {tool['latency_ms']:.2f} ms")

    Console.print_end()


def _show_config(config, agent) -> None:
    """显示当前配置信息"""
    from .config_display import render_config
    print(render_config(config, agent))


def _show_memory_status(config) -> None:
    """显示当前记忆配置状态"""
    Console.print_title("📊 记忆配置")

    def format_line(label: str, value: str, width: int = 20) -> str:
        return f"  {label:<{width}} {value}"

    Console.print_subtitle("当前设置")
    Console.print_kv("记忆类型:", config.memory.type, key_width=16)
    Console.print_kv("存储类型:", config.memory.storage_type, key_width=16)
    Console.print_kv("存储路径:", config.memory.storage_path, key_width=16)

    if config.memory.type == "hybrid":
        Console.print_kv("长期记忆路径:", config.memory.long_term_storage_path, key_width=16)
        Console.print_kv("自动提取:", str(config.memory.auto_extract), key_width=16)
        if config.memory_gc.eviction_enabled:
            Console.print_kv("淘汰上限:", f"{config.memory_gc.eviction_max_entries} 条", key_width=16)

    Console.print_subtitle("记忆模式")
    print("  short_term  - 仅当前上下文（无持久化）")
    print("  hybrid      - 短期 + 长期记忆（推荐）")

    Console.print_subtitle("命令")
    print("  /memory          查看当前记忆状态")
    print("  /memory on       启用长期记忆（需重启生效）")
    print("  /memory off      禁用长期记忆（需重启生效）")

    Console.print_end()


def _show_stats_status(agent, config) -> None:
    """显示当前会话统计状态"""
    Console.print_title("📊 会话消耗统计")

    if hasattr(agent, "tracker"):
        session_summary = agent.tracker.get_session_summary()
        if session_summary:
            Console.print_subtitle("累计消耗")
            total_tokens = session_summary.get("total_tokens", 0)
            total_llm_calls = session_summary.get("total_llm_calls", 0)
            total_iterations = session_summary.get("total_iterations", 0)
            total_runs = session_summary.get("total_runs", 0)

            Console.print_kv("总 Token:", str(total_tokens), key_width=16)
            Console.print_kv("总 LLM 调用:", str(total_llm_calls), key_width=16)
            Console.print_kv("总迭代次数:", str(total_iterations), key_width=16)
            Console.print_kv("总轮次:", str(total_runs), key_width=16)

            Console.print_subtitle("工具调用")
            Console.print_kv("总调用:", str(session_summary.get("total_tool_calls", 0)), key_width=16)
            Console.print_kv("成功:", str(session_summary.get("successful_tool_calls", 0)), key_width=16)
            Console.print_kv("失败:", str(session_summary.get("failed_tool_calls", 0)), key_width=16)
        else:
            print("\n  无数据。请先运行查询。")

    Console.print_subtitle("命令")
    Console.print_kv("/stats", "显示会话消耗统计", key_width=16)
    Console.print_kv("/stats on", "启用每次对话后自动显示", key_width=16)
    Console.print_kv("/stats off", "禁用自动显示", key_width=16)
    Console.print_kv("/usage", "显示上下文消息组成", key_width=16)
    Console.print_kv("/context", "显示上下文预算分析", key_width=16)

    Console.print_end()


def _show_context_composition(agent, config) -> None:
    """显示 Token 消耗详情"""
    if not hasattr(agent, "tracker"):
        Console.print("Tracker 不可用", style="warning")
        return

    detailed_usage = agent.tracker.get_detailed_usage()
    if not detailed_usage:
        Console.print("暂无数据。请先运行查询。", style="info")
        return

    Console.print_title("📊 Token 消耗详情")

    # 表头
    print("\n## 迭代明细")
    print(
        f"  {_pad_to_width('ID', 4)} "
        f"{_pad_to_width('轮次', 5)} "
        f"{_pad_to_width('迭代', 5)} "
        f"{_pad_to_width('工具[*]', 9)} "
        f"{_pad_to_width('系统[*]', 9)} "
        f"{_pad_to_width('技能[*]', 9)} "
        f"{_pad_to_width('摘要[*]', 9)} "
        f"{_pad_to_width('消息[*]', 9)} "
        f"{_pad_to_width('输入', 7)} "
        f"{_pad_to_width('输出(工具)[*]', 13)} "
        f"{_pad_to_width('输出[*]', 9)} "
        f"{_pad_to_width('总和', 7)} 简要描述"
    )
    print("  " + "-" * 105)

    def fmt_token(n: int) -> str:
        return str(n) if n > 0 else "-"

    prev_run_number = None
    for row in detailed_usage:
        run_display = str(row["run_number"]) if row["run_number"] != prev_run_number else ""
        prev_run_number = row["run_number"]
        description = MetricsTracker.format_iteration_description(
            iter_num=row["iteration_number"],
            tool_names=row.get("tool_names", []),
            input_messages=row.get("input_messages", []),
            output_text=row.get("output_text", ""),
            skipped_tool_calls=row.get("skipped_tool_calls", []),
        )
        print(
            f"  {_pad_to_width(str(row['id']), 4)} "
            f"{_pad_to_width(run_display, 5)} "
            f"{_pad_to_width(str(row['iteration_number']), 5)} "
            f"{_pad_to_width(fmt_token(row['tool_tokens']), 9)} "
            f"{_pad_to_width(fmt_token(row['system_tokens']), 9)} "
            f"{_pad_to_width(fmt_token(row['skill_tokens']), 9)} "
            f"{_pad_to_width(fmt_token(row['summary_tokens']), 9)} "
            f"{_pad_to_width(fmt_token(row['message_tokens']), 9)} "
            f"{_pad_to_width(str(row['input_tokens']), 7)} "
            f"{_pad_to_width(fmt_token(row['output_tool_tokens']), 13)} "
            f"{_pad_to_width(fmt_token(row['output_text_tokens']), 9)} "
            f"{_pad_to_width(str(row['total_tokens']), 7)} {description}"
        )

    print("  " + "-" * 105)
    print("  [*] 表示按字符长度比例估算")
    print("  - 表示该值为 0")

    total_input = sum(r["input_tokens"] for r in detailed_usage)
    total_output_tool = sum(r["output_tool_tokens"] for r in detailed_usage)
    total_output_text = sum(r["output_text_tokens"] for r in detailed_usage)
    total_all = sum(r["total_tokens"] for r in detailed_usage)

    print("\n## 总计")
    Console.print_kv("输入:", str(total_input), key_width=14)
    Console.print_kv("输出(工具):", str(total_output_tool), key_width=14)
    Console.print_kv("输出:", str(total_output_text), key_width=14)
    Console.print_kv("总和:", str(total_all), key_width=14)

    Console.print_end()


def _show_context_budget(agent, config) -> None:
    """显示上下文预算分析"""
    if not hasattr(agent, "memory"):
        Console.print("Memory 不可用", style="warning")
        return

    messages = agent.memory.get_all()
    if not messages:
        Console.print("Memory 中无消息", style="info")
        return

    Console.print_title("📊 上下文预算分析")

    context_limit = 8192
    if config and hasattr(config, "llm"):
        context_limit = config.llm.get_context_length()

    breakdown = {}
    if hasattr(agent, "tracker") and agent.tracker:
        detailed_usage = agent.tracker.get_detailed_usage()
        if detailed_usage:
            last_row = detailed_usage[-1]
            base_chars = agent.tracker.get_base_chars()
            base_ratio = agent.tracker.get_base_ratio()
            tools_tokens = int(base_chars["tool_chars"] * base_ratio) if base_chars["tool_chars"] > 0 else 0
            if tools_tokens > 0:
                breakdown["工具定义"] = tools_tokens
            system_tokens = int(base_chars["system_chars"] * base_ratio) if base_chars["system_chars"] > 0 else 0
            if system_tokens > 0:
                breakdown["系统提示"] = system_tokens
            skill_tokens = int(base_chars["skill_chars"] * base_ratio) if base_chars["skill_chars"] > 0 else 0
            if skill_tokens > 0:
                breakdown["技能提示"] = skill_tokens
            summary_tokens = last_row.get("summary_tokens", 0)
            if summary_tokens > 0:
                breakdown["摘要"] = summary_tokens
            messages_tokens = last_row.get("message_tokens", 0) + last_row.get("output_tool_tokens", 0) + last_row.get("output_text_tokens", 0)
            if messages_tokens > 0:
                breakdown["对话消息"] = messages_tokens
    else:
        base_ratio = 0.25
        if hasattr(agent, "tool_registry"):
            import json
            tools_schema = agent.tool_registry.get_all_schemas()
            if tools_schema:
                tools_json = json.dumps(tools_schema, ensure_ascii=False)
                tools_tokens = int(len(tools_json) * base_ratio)
                if tools_tokens > 0:
                    breakdown["工具定义"] = tools_tokens
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "") or ""
                chars = len(content)
                if chars == 0:
                    continue
                estimated_tokens = int(chars * base_ratio)
                if content.startswith("[历史摘要]"):
                    breakdown["摘要"] = breakdown.get("摘要", 0) + estimated_tokens
                elif "## Skills" in content or "skill" in content.lower():
                    breakdown["技能提示"] = breakdown.get("技能提示", 0) + estimated_tokens
                else:
                    breakdown["系统提示"] = breakdown.get("系统提示", 0) + estimated_tokens
        messages_tokens = 0
        for msg in messages:
            if msg.get("role") not in ("system",):
                content = msg.get("content", "") or ""
                messages_tokens += int(len(content) * base_ratio) if content else 0
        if messages_tokens > 0:
            breakdown["对话消息"] = messages_tokens

    total_tokens = sum(breakdown.values())

    Console.print_subtitle("Token 组成")
    display_order = ["工具定义", "系统提示", "技能提示", "摘要", "对话消息"]
    for name in display_order:
        tokens = breakdown.get(name, 0)
        display_val = str(tokens) if tokens > 0 else "-"
        Console.print_kv(name + ":", display_val, key_width=12)
    Console.print_kv("总计:", str(total_tokens), key_width=12)

    usage_pct = (total_tokens / context_limit * 100) if context_limit > 0 else 0
    remaining_pct = 100 - usage_pct

    Console.print_subtitle(f"占比分布 (上限: {context_limit})")
    Console.print_progress_bar(usage_pct)
    Console.print_kv("· 剩余:", f"{remaining_pct:.1f}%", key_width=12)

    if usage_pct >= 80:
        print("\n  建议: 使用 /clear 清空历史")
    elif usage_pct >= 50:
        print("\n  建议: 关注剩余预算")

    Console.print_end()


def _show_estimation_audit(agent, config) -> None:
    """显示估算偏差审计"""
    if not hasattr(agent, "tracker"):
        Console.print("Tracker 不可用", style="warning")
        return

    audit = agent.tracker.estimation_audit
    summary = audit.get_summary()

    Console.print_title("📊 估算偏差审计")

    if summary.get("total_checks", 0) == 0:
        print("\n  无数据。请先运行查询。")
        Console.print_end()
        return

    Console.print_kv("平均偏差:", f"{summary['avg_deviation_pct']:.1%}", key_width=14)
    Console.print_kv("最大偏差:", f"{summary['max_deviation_pct']:.1%}", key_width=14)
    Console.print_kv("高估次数:", f"{summary['over_count']} ({summary['over_pct']:.0f}%)", key_width=14)
    Console.print_kv("低估次数:", f"{summary['under_count']} ({summary['under_pct']:.0f}%)", key_width=14)
    Console.print_kv("告警次数 (>50%):", str(summary['warning_count']), key_width=14)
    Console.print_kv("校准系数:", f"{summary['calibration_factor']:.3f}", key_width=14)
    Console.print_kv("已收敛:", "是" if summary['is_converged'] else "否", key_width=14)

    history = audit.get_deviation_history()
    if len(history) >= 3:
        recent = history[-5:]
        trend = " -> ".join(f"{d.deviation_pct:.0%}" for d in recent)
        Console.print_kv("近期趋势:", trend, key_width=14)

    Console.print_end()


def _show_iteration_breakdown(agent) -> None:
    """显示各轮 Token 消耗趋势"""
    if not hasattr(agent, "tracker"):
        Console.print("Tracker 不可用", style="warning")
        return

    iterations = agent.tracker.get_iteration_token_list()
    if not iterations:
        Console.print("暂无迭代数据。请先运行查询。", style="info")
        return

    Console.print_title("📊 Token 消耗趋势")

    max_total = max(i["total_tokens"] for i in iterations) if iterations else 1

    print(f"  {'轮次':<6} {'输入':<8} {'输出':<8} {'总计':<8} 趋势")
    print("  " + "-" * 55)

    for iter_data in iterations:
        i = iter_data["iteration_number"]
        prompt = iter_data["prompt_tokens"]
        completion = iter_data["completion_tokens"]
        total = iter_data["total_tokens"]
        bar_len = int(total / max_total * 20) if max_total > 0 else 0
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {i:<6} {prompt:<8} {completion:<8} {total:<8} {bar}")

    print("-" * 55)

    total_all = sum(i["total_tokens"] for i in iterations)
    avg = total_all / len(iterations) if iterations else 0
    max_iter = max(iterations, key=lambda x: x["total_tokens"])
    min_iter = min(iterations, key=lambda x: x["total_tokens"])

    print(f"  平均每轮: {avg:.0f} tokens")
    print(f"  最大: {max_iter['total_tokens']} (轮次 {max_iter['iteration_number']})")
    print(f"  最小: {min_iter['total_tokens']} (轮次 {min_iter['iteration_number']})")

    Console.print_end()


def _show_session(session_id: str, config_path: str | None = None) -> None:
    """显示会话详情"""
    from .main import _find_config_file, _get_storage

    config_file, _ = _find_config_file(config_path)
    if not config_file:
        Console.print("未找到配置文件", style="error")
        return
    from ..config.loader import ConfigLoader
    config = ConfigLoader.load(config_file)
    storage = _get_storage(config)
    entries = storage.load(session_id)

    if not entries:
        Console.print(f"会话 '{session_id}' 未找到", style="error")
        return

    Console.print_title(f"📊 会话: {session_id}")
    Console.print(f"消息总数: {len(entries)}", style="info")
    Console.print_end()
```

- [ ] **Step 2: 验证 displays.py 无语法错误**

```bash
python -c "from nano_agent.cli.displays import _show_help; print('OK')"
```
预期: OK（可能警告 GracefulExitManager 循环引用，但可运行时解析）

- [ ] **Step 3: 从 main.py 删除迁移的函数 + 更新 import**

在 main.py 末尾删除从 `_show_help` 定义开始到文件末尾的全部显示函数（`_show_help`, `_enable_run_stats`, `_disable_run_stats` 等），然后在 main.py 顶部增加：

```python
from .displays import (
    _show_help,
    _show_run_stats,
    _show_monitoring_stats,
    _show_config,
    _show_memory_status,
    _show_stats_status,
    _show_context_composition,
    _show_context_budget,
    _show_estimation_audit,
    _show_iteration_breakdown,
    _show_session,
    _get_display_width,
    _pad_to_width,
)
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/ -v
```
预期: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add nano_agent/cli/displays.py nano_agent/cli/main.py
git commit -m "refactor: 抽出 displays.py，迁移所有 _show_* 展示函数"
```

---

### Task 3: 命令输出统一 — 语言 + Console.print style

**Files:**
- Modify: `nano_agent/cli/main.py` `_handle_slash_command` 和 `main()` 中的 Console.print 调用

- [ ] **Step 1: main.py — 改 _handle_slash_command 中的英文输出为中文**

```python
# Line 750 - /clear
Console.print("对话历史已清空", style="success")

# Line 775 - /tools
Console.print(f"可用工具: {', '.join(tools)}", style="info")

# Line 867, 869, 873 - /sessions
Console.print("暂无会话", style="info")
Console.print(f"可用会话 ({len(sessions)}):", style="info")
Console.print("当前记忆类型不支持会话列表", style="warning")

# Line 891, 893, 898 - /skills
Console.print("未加载技能", style="info")
Console.print(f"已加载技能 ({len(skills)}):", style="info")
Console.print("技能系统不可用", style="warning")
```

- [ ] **Step 2: main() 中的英文输出改中文**

```python
# Line 1627-1629
Console.print(f"恢复会话: {args.resume_session}", style="info")
Console.print("开始新会话", style="info")

# Line 1636
Console.print(f"已创建新会话: {new_sid}", style="success")

# Line 1644, 1649
Console.print(f"会话 '{args.resume_session}' 未找到", style="error")
Console.print(f"已恢复会话: {args.resume_session}", style="success")

# Line 1653
Console.print("会话恢复不可用（需要持久化或混合记忆）", style="warning")

# Line 1661
Console.print(f"[MemoryGC] {gc_result.summary()}", style="info")

# Line 1057 — _setup_git_handler
Console.print("Git 集成已启用", style="info")

# Line 1086 — startup prompt
Console.print("输入 '/?' 或 'help' 查看可用命令", style="info")

# Line 1197 — error handler  
Console.print(f"错误: {e}", style="error")
```

- [ ] **Step 3: _handle_snapshot_command 英文改中文**

查找 `_handle_snapshot_command` 中的所有 Console.print 调用，改为中文。

- [ ] **Step 4: _handle_skill_command 英文改中文**

```python
Console.print("技能系统不可用", style="warning")
Console.print("用法: /skill reload <名称>", style="info")
Console.print("用法: /skill unload <名称>", style="info")
Console.print(f"技能 '{skill_name}' 未找到", style="error")
# etc.
```

- [ ] **Step 5: _handle_undo / _handle_auto / _handle_config_command 检查**

这些命令已经中文，确认 style 正确。_handle_config_command 中的 `"Usage:"` 改中文。

```python
Console.print("用法: /config <init [--force]>", style="info")
Console.print(f"未知子命令: {subcommand}", style="error")
Console.print("可选: init [--force]", style="info")
```

- [ ] **Step 6: _handle_stats_command / _handle_memory_command / 等 handler 中的英文改中文**

```python
# 所有 "Unknown subcommand" → "未知子命令"
# 所有 "Available:" → "可选:"
```

- [ ] **Step 7: GracefulExitManager 相关输出改中文**

```python
# 查找 exit_with_summary 和 /exit 相关输出
```

- [ ] **Step 8: _export_report 输出改中文**

```python
# "Report exported to:" → "报告已导出到:"
# "Unknown format:" → "未知格式:"
```

- [ ] **Step 9: 运行测试**

```bash
pytest tests/ -v
```
预期: 全部 PASS

- [ ] **Step 10: 提交**

```bash
git add nano_agent/cli/main.py
git commit -m "i18n: 统一命令输出为中文 + Console.print style"
```

---

### Task 4: 进度条统一 + _handle_* 修复

**Files:**
- Modify: `nano_agent/cli/main.py`
- Already done in Task 2: _show_context_budget 进度条已改为 Console.print_progress_bar

- [ ] **Step 1: 确认 _show_context_budget 在 displays.py 中已使用 Console.print_progress_bar**

已在 Task 2 的 displays.py 中实现。

- [ ] **Step 2: 删除所有 console.py 中已废弃的调用**

```python
# main.py Line 1071 — 将 Console.print_header 替换为 Console.print_title
Console.print_title("NanoAgent - AI Assistant")
```

- [ ] **Step 3: 运行测试并确认**

```bash
pytest tests/ -v
```

- [ ] **Step 4: 提交**

```bash
git add nano_agent/cli/main.py
git commit -m "style: 使用 Console.print_title 替换 print_header，进度条统一"
```
