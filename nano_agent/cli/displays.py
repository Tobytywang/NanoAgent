"""
CLI 展示函数 — 所有 _show_* 函数集中于此。

从 main.py 迁移而来，职责分离：显示逻辑在此，命令处理在 main.py。
"""

import sys

from ..config.loader import ConfigLoader
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
    Console.print_kv(
        "/verbose on", "开启详细输出（工具执行、Token 消耗等）", key_width=24
    )
    Console.print_kv("/verbose off", "关闭详细输出", key_width=24)
    Console.print_kv("/verbose", "查看当前状态", key_width=24)
    Console.print_kv("/effort concise", "最简模式，低 token 消耗", key_width=24)
    Console.print_kv("/effort standard", "标准模式（默认）", key_width=24)
    Console.print_kv("/effort detailed", "详细模式，最深推理", key_width=24)
    Console.print_kv("/effort", "查看当前推理强度", key_width=24)
    Console.print_kv("/prompt", "查看当前系统提示词", key_width=24)

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
    Console.print_kv(
        "/setname <用户名> <Agent名>", "同时设置用户和 Agent 名", key_width=24
    )
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
        current_context_tokens = (
            last_tokens.get("prompt_tokens", 0) if last_tokens else 0
        )
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
    Console.print_kv("- 成功:", str(summary.get("successful_tool_calls", 0)), indent=4)
    Console.print_kv("- 失败:", str(summary.get("failed_tool_calls", 0)), indent=4)

    full_report = agent.tracker.get_full_report()
    if full_report and full_report.get("iterations"):
        print("\n## 迭代明细")
        for iteration in full_report["iterations"]:
            print(f"\n  迭代 {iteration['iteration_number']}:")
            if iteration.get("llm_call"):
                llm = iteration["llm_call"]
                print(f"    LLM: {llm['model']}")
                print(
                    f"      Token: {llm['prompt_tokens']} 输入 + {llm['completion_tokens']} 输出 = {llm['total_tokens']} 总计"
                )
                print(f"      延迟: {llm['latency_ms']:.2f} ms")
                print(f"      工具调用: {llm['tool_calls_count']}")
            if iteration.get("tool_executions"):
                print("    工具执行:")
                for tool in iteration["tool_executions"]:
                    status = "✓" if tool["success"] else "✗"
                    print(
                        f"      {status} {tool['tool_name']}: {tool['latency_ms']:.2f} ms"
                    )

    Console.print_end()


def _show_config(config, agent) -> None:
    """显示当前配置信息"""
    from .config_display import render_config

    print(render_config(config, agent))


def _show_memory_status(config) -> None:
    """显示当前记忆配置状态"""
    Console.print_title("📊 记忆配置")

    Console.print_subtitle("当前设置")
    Console.print_kv("记忆类型:", config.memory.type, key_width=16)
    Console.print_kv("存储类型:", config.memory.storage_type, key_width=16)
    Console.print_kv("存储路径:", config.memory.storage_path, key_width=16)

    if config.memory.type == "hybrid":
        Console.print_kv(
            "长期记忆路径:", config.memory.long_term_storage_path, key_width=16
        )
        Console.print_kv("自动提取:", str(config.memory.auto_extract), key_width=16)
        if config.memory_gc.eviction_enabled:
            Console.print_kv(
                "淘汰上限:", f"{config.memory_gc.eviction_max_entries} 条", key_width=16
            )

    Console.print_subtitle("记忆模式")
    print("  short_term  - 仅当前上下文（无持久化）")
    print("  hybrid      - 短期 + 长期记忆（推荐）")

    Console.print_subtitle("命令")
    Console.print_kv("/memory", "查看当前记忆状态", key_width=16)
    Console.print_kv("/memory on", "启用长期记忆（需重启生效）", key_width=16)
    Console.print_kv("/memory off", "禁用长期记忆（需重启生效）", key_width=16)

    Console.print_end()


def _show_stats_status(agent, config) -> None:
    """显示当前会话统计状态"""
    Console.print_title("📊 会话消耗统计")

    if hasattr(agent, "tracker"):
        session_summary = agent.tracker.get_session_summary()
        if session_summary:
            Console.print_subtitle("累计消耗")
            Console.print_kv(
                "总 Token:", str(session_summary.get("total_tokens", 0)), key_width=16
            )
            Console.print_kv(
                "总 LLM 调用:",
                str(session_summary.get("total_llm_calls", 0)),
                key_width=16,
            )
            Console.print_kv(
                "总迭代次数:",
                str(session_summary.get("total_iterations", 0)),
                key_width=16,
            )
            Console.print_kv(
                "总轮次:", str(session_summary.get("total_runs", 0)), key_width=16
            )

            Console.print_subtitle("工具调用")
            Console.print_kv(
                "总调用:", str(session_summary.get("total_tool_calls", 0)), key_width=16
            )
            Console.print_kv(
                "成功:",
                str(session_summary.get("successful_tool_calls", 0)),
                key_width=16,
            )
            Console.print_kv(
                "失败:", str(session_summary.get("failed_tool_calls", 0)), key_width=16
            )
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
        run_display = (
            str(row["run_number"]) if row["run_number"] != prev_run_number else ""
        )
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
    use_tracker = False
    if hasattr(agent, "tracker") and agent.tracker:
        detailed_usage = agent.tracker.get_detailed_usage()
        if detailed_usage:
            use_tracker = True
            last_row = detailed_usage[-1]
            base_chars = agent.tracker.get_base_chars()
            base_ratio = agent.tracker.get_base_ratio()
            tools_tokens = (
                int(base_chars["tool_chars"] * base_ratio)
                if base_chars["tool_chars"] > 0
                else 0
            )
            if tools_tokens > 0:
                breakdown["工具定义"] = tools_tokens
            system_tokens = (
                int(base_chars["system_chars"] * base_ratio)
                if base_chars["system_chars"] > 0
                else 0
            )
            if system_tokens > 0:
                breakdown["系统提示"] = system_tokens
            skill_tokens = (
                int(base_chars["skill_chars"] * base_ratio)
                if base_chars["skill_chars"] > 0
                else 0
            )
            if skill_tokens > 0:
                breakdown["技能提示"] = skill_tokens
            summary_tokens = last_row.get("summary_tokens", 0)
            if summary_tokens > 0:
                breakdown["摘要"] = summary_tokens
            messages_tokens = (
                last_row.get("message_tokens", 0)
                + last_row.get("output_tool_tokens", 0)
                + last_row.get("output_text_tokens", 0)
            )
            if messages_tokens > 0:
                breakdown["对话消息"] = messages_tokens

    # Fallback: estimate from messages when tracker has no data yet
    if not use_tracker:
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
                    breakdown["技能提示"] = (
                        breakdown.get("技能提示", 0) + estimated_tokens
                    )
                else:
                    breakdown["系统提示"] = (
                        breakdown.get("系统提示", 0) + estimated_tokens
                    )
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
    Console.print_kv(
        "高估次数:",
        f"{summary['over_count']} ({summary['over_pct']:.0f}%)",
        key_width=14,
    )
    Console.print_kv(
        "低估次数:",
        f"{summary['under_count']} ({summary['under_pct']:.0f}%)",
        key_width=14,
    )
    Console.print_kv("告警次数 (>50%):", str(summary["warning_count"]), key_width=14)
    Console.print_kv("校准系数:", f"{summary['calibration_factor']:.3f}", key_width=14)
    Console.print_kv("已收敛:", "是" if summary["is_converged"] else "否", key_width=14)

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
    print(f"  最大: {max_iter['total_tokens']}（轮次 {max_iter['iteration_number']}）")
    print(f"  最小: {min_iter['total_tokens']}（轮次 {min_iter['iteration_number']}）")

    Console.print_end()


def _show_session(session_id: str, config_path: str | None = None) -> None:
    """显示会话详情"""
    from .main import _find_config_file, _get_storage

    config_file, _ = _find_config_file(config_path)
    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()

    storage = _get_storage(config)

    if not storage.session_exists(session_id):
        Console.print(f"会话 '{session_id}' 未找到", style="error")
        sys.exit(1)

    entries = storage.load_session(session_id)
    Console.print_title(f"📊 会话: {session_id}")
    Console.print(f"消息总数: {len(entries)}", style="info")

    # 显示摘要（如果存在）
    summary = storage.load_summary(session_id)
    if summary:
        print("摘要:")
        print(summary.get("summary", "无摘要"))
        print()
    else:
        # 没有摘要时显示消息预览
        print("消息预览:")
        for entry in entries[:3]:
            content = (
                entry.content[:100] + "..."
                if len(entry.content) > 100
                else entry.content
            )
            print(f"  [{entry.role}]: {content}")
        if len(entries) > 3:
            print(f"  ... 还有 {len(entries) - 3} 条消息")

    Console.print_end()
