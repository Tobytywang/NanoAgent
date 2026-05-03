"""
CLI entry point for NanoAgent.
"""

import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path

from ..llm import create_llm_from_config
from ..memory import ShortTermMemory, PersistentMemory, HybridMemory, FileStorage, LongTermMemory
from ..tools.base import ToolRegistry
from ..tools.builtin import register_builtin_tools
from ..agent.react import ReActAgent
from ..config.loader import ConfigLoader
from ..skills import SkillRegistry, SkillLoader
from .console import Console


class GracefulExitManager:
    """管理优雅退出状态"""

    ctrl_c_count = 0  # Ctrl+C 按下次数
    generating_summary = False  # 是否正在生成摘要
    agent = None  # 当前 agent 引用
    config = None  # 当前 config 引用

    @classmethod
    def reset(cls):
        """重置状态（新会话时调用）"""
        cls.ctrl_c_count = 0
        cls.generating_summary = False

    @classmethod
    def handler(cls, signum, frame):
        """信号处理函数"""
        if cls.generating_summary:
            # 摘要生成中，强制退出
            print("\n强制退出")
            sys.exit(0)

        cls.ctrl_c_count += 1

        if cls.ctrl_c_count == 1:
            print("\n再按 Ctrl+C 退出并保存摘要，或继续对话")
        elif cls.ctrl_c_count >= 2:
            # 触发摘要生成并退出
            cls.exit_with_summary()

    @classmethod
    def exit_with_summary(cls):
        """生成摘要并退出"""
        cls.generating_summary = True
        print("\n正在生成会话摘要...")

        try:
            if cls.agent and cls.config:
                summary = _generate_session_summary(cls.agent, cls.config)
                _save_session_summary(cls.agent, cls.config, summary)
                print("摘要已保存")
        except Exception as e:
            print(f"摘要生成失败: {e}")

        print("Goodbye!")
        sys.exit(0)


def create_memory(config):
    """
    Create memory system based on configuration.

    Args:
        config: Config object

    Returns:
        Memory instance
    """
    system_prompt = config.agent.system_prompt or "You are a helpful AI assistant."

    if config.memory.type == "hybrid":
        # Create working memory (persistent for session support)
        storage = FileStorage(base_dir=config.memory.storage_path)
        working_memory = PersistentMemory(
            storage=storage,
            session_id=config.memory.session_id,
            max_messages=config.memory.max_messages,
            system_prompt=system_prompt
        )

        # Create long-term memory
        long_term_memory = LongTermMemory(
            storage_path=config.memory.long_term_storage_path
        )

        # Create hybrid memory
        memory = HybridMemory(
            working_memory=working_memory,
            long_term_memory=long_term_memory,
            auto_extract=config.memory.auto_extract
        )

    elif config.memory.type == "persistent":
        storage = FileStorage(base_dir=config.memory.storage_path)
        memory = PersistentMemory(
            storage=storage,
            session_id=config.memory.session_id,
            max_messages=config.memory.max_messages,
            system_prompt=system_prompt
        )
    else:
        memory = ShortTermMemory(
            max_messages=config.memory.max_messages,
            system_prompt=system_prompt
        )

    return memory


def create_agent(config_path: str | None = None) -> ReActAgent:
    """
    Create and configure a ReAct agent.

    Args:
        config_path: Path to configuration file

    Returns:
        Configured ReActAgent instance
    """
    # Load configuration
    if config_path:
        config = ConfigLoader.load(config_path)
    else:
        # Try default config path
        default_path = Path("config/config.yaml")
        if default_path.exists():
            config = ConfigLoader.load(default_path)
        else:
            config = ConfigLoader.load()  # Returns default config

    # Create LLM client using factory function
    llm = create_llm_from_config(config.llm)

    # Create memory system
    memory = create_memory(config)

    # Set LLM on hybrid memory for auto-extraction
    if config.memory.type == "hybrid" and hasattr(memory, 'set_llm'):
        memory.set_llm(llm)

    # Create tool registry and register built-in tools
    tool_registry = ToolRegistry()

    # Create agent first (to get tracker)
    agent = ReActAgent(
        llm=llm,
        memory=memory,
        tool_registry=tool_registry,
        max_iterations=config.agent.max_iterations,
        verbose=config.agent.verbose,
        skill_prompt=""
    )

    # Register built-in tools with tracker and context_length
    register_builtin_tools(tool_registry, memory=memory, tracker=agent.tracker, context_length=config.llm.get_context_length())

    # Load and register skills
    skill_registry = SkillRegistry()
    skill_loader = SkillLoader(skill_registry)
    skill_loader.load_from_directory(config.skills.directory)

    # Register skill tools
    for tool in skill_registry.get_all_tools():
        tool_registry.register(tool)

    # Get combined skill system prompt
    skill_prompt = skill_registry.get_combined_system_prompt()

    # Update agent's skill prompt
    agent.skill_prompt = skill_prompt
    agent._setup_system_prompt()

    # Attach skill registry and loader for hot-reload support
    agent.skill_registry = skill_registry
    agent.skill_loader = skill_loader

    return agent


def run_interactive(agent: ReActAgent, config) -> None:
    """
    Run interactive chat loop.

    Args:
        agent: The agent to interact with
        config: The configuration object
    """
    import os

    # 设置优雅退出管理器
    GracefulExitManager.agent = agent
    GracefulExitManager.config = config
    signal.signal(signal.SIGINT, GracefulExitManager.handler)

    Console.print_header("NanoAgent - AI Assistant")
    Console.print("Type '/exit' or '/quit' to exit with summary", style="info")
    Console.print("Type 'exit' or 'quit' to exit directly", style="info")
    Console.print("Type 'clear' to clear conversation history", style="info")
    Console.print("Type 'tools' to list available tools", style="info")
    Console.print("Type 'sessions' to list available sessions", style="info")
    Console.print("Type 'skills' to list loaded skills", style="info")
    Console.print("Type 'skill reload <name>' to reload a skill", style="info")
    Console.print("Type 'skill unload <name>' to unload a skill", style="info")
    Console.print("Type 'stats' to show monitoring statistics", style="info")
    Console.print_separator()

    while True:
        try:
            cwd = os.getcwd()
            print(f"\n[User] [{cwd}]:")
            user_input = input("> ").strip()

            if not user_input:
                continue

            # 优雅退出命令（生成摘要）
            if user_input.lower() in ["/exit", "/quit", "/bye"]:
                GracefulExitManager.exit_with_summary()
                break

            # 直接退出命令（不生成摘要）
            if user_input.lower() in ["exit", "quit"]:
                Console.print("Goodbye!", style="success")
                break

            if user_input.lower() == "clear":
                agent.reset()
                Console.print("Conversation history cleared", style="success")
                continue

            if user_input.lower() == "tools":
                tools = agent.tool_registry.list_tools()
                Console.print(f"Available tools: {', '.join(tools)}", style="info")
                continue

            if user_input.lower() == "stats":
                _show_monitoring_stats(agent)
                continue

            if user_input.lower() == "sessions":
                if hasattr(agent.memory, 'list_sessions'):
                    sessions = agent.memory.list_sessions()
                    if not sessions:
                        Console.print("No sessions found.", style="info")
                    else:
                        Console.print(f"Available sessions ({len(sessions)}):", style="info")
                        for sid in sessions:
                            print(f"  {sid}")
                else:
                    Console.print("Session listing not available (requires persistent/hybrid memory)", style="warning")
                continue

            # Skill commands
            if user_input.lower() == "skills":
                if hasattr(agent, 'skill_loader'):
                    skills = agent.skill_loader.list_loaded_skills()
                    if not skills:
                        Console.print("No skills loaded.", style="info")
                    else:
                        Console.print(f"Loaded skills ({len(skills)}):", style="info")
                        for skill_name in skills:
                            source = agent.skill_loader.get_skill_source(skill_name)
                            print(f"  {skill_name} <- {source}")
                else:
                    Console.print("Skill system not available", style="warning")
                continue

            if user_input.lower().startswith("skill "):
                _handle_skill_command(agent, user_input[6:])
                continue

            # 重置 Ctrl+C 计数
            GracefulExitManager.ctrl_c_count = 0

            # Run agent
            Console.print("\n", style="agent", end="")
            response = agent.run(user_input)
            print(f"> {response}")

            # Show monitoring stats after each run
            _show_run_stats(agent, config)

        except KeyboardInterrupt:
            # 被 signal handler 处理，继续循环
            continue
        except Exception as e:
            Console.print(f"Error: {e}", style="error")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="NanoAgent - A lightweight AI Agent framework"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Configuration file path (default: config/config.yaml)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=None,
        help="Override model name from config"
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all available sessions and exit"
    )
    parser.add_argument(
        "--show-session",
        type=str,
        metavar="SESSION_ID",
        default=None,
        help="Show messages in a specific session"
    )
    parser.add_argument(
        "-r", "--resume",
        type=str,
        metavar="SESSION_ID",
        default=None,
        help="Resume an existing session"
    )
    parser.add_argument(
        "-n", "--new-session",
        action="store_true",
        help="Force start a new session"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode, read input from stdin"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress verbose output"
    )

    args = parser.parse_args()

    # Check for conflicting arguments
    if args.resume and args.new_session:
        Console.print("Error: --resume and --new-session cannot be used together", style="error")
        sys.exit(1)

    # Handle --list-sessions
    if args.list_sessions:
        _list_sessions(args.config)
        return

    # Handle --show-session
    if args.show_session:
        _show_session(args.show_session, args.config)
        return

    # Create agent
    agent = create_agent(args.config)

    # Handle --resume
    if args.resume:
        if hasattr(agent.memory, 'load_session'):
            success = agent.memory.load_session(args.resume)
            if not success:
                Console.print(f"Session '{args.resume}' not found", style="error")
                sys.exit(1)
            Console.print(f"Resumed session: {args.resume}", style="success")
        else:
            Console.print("Session resume not available (requires persistent/hybrid memory)", style="warning")

    # Handle --new-session
    if args.new_session:
        if hasattr(agent.memory, 'new_session'):
            new_id = agent.memory.new_session()
            Console.print(f"Started new session: {new_id}", style="success")
        else:
            Console.print("New session not available (requires persistent/hybrid memory)", style="warning")

    # Override model if specified
    if args.model:
        agent.llm.model = args.model

    # Override verbose if quiet mode
    if args.quiet:
        agent.verbose = False

    if args.non_interactive:
        # Non-interactive mode
        user_input = sys.stdin.read().strip()
        if user_input:
            response = agent.run(user_input)
            print(response)
    else:
        # Interactive mode - load config for graceful exit
        if args.config:
            config = ConfigLoader.load(args.config)
        else:
            default_path = Path("config/config.yaml")
            if default_path.exists():
                config = ConfigLoader.load(default_path)
            else:
                config = ConfigLoader.load()
        run_interactive(agent, config)


def _list_sessions(config_path: str | None = None) -> None:
    """List all available sessions."""
    # Get storage path from config
    if config_path:
        config = ConfigLoader.load(config_path)
    else:
        default_path = Path("config/config.yaml")
        if default_path.exists():
            config = ConfigLoader.load(default_path)
        else:
            config = ConfigLoader.load()

    storage_path = config.memory.storage_path
    storage = FileStorage(base_dir=storage_path)
    sessions = storage.list_sessions()

    if not sessions:
        Console.print("No sessions found.", style="info")
        return

    Console.print(f"Found {len(sessions)} session(s):", style="info")
    Console.print_separator()
    for session_id in sessions:
        info = storage.get_session_info(session_id)
        print(f"  {session_id}")
        print(f"    Messages: {info['message_count']}")
        if info['last_message']:
            print(f"    Last activity: {info['last_message'][:19]}")
        print()


def _show_session(session_id: str, config_path: str | None = None) -> None:
    """Show messages in a specific session."""
    # Get storage path from config
    if config_path:
        config = ConfigLoader.load(config_path)
    else:
        default_path = Path("config/config.yaml")
        if default_path.exists():
            config = ConfigLoader.load(default_path)
        else:
            config = ConfigLoader.load()

    storage_path = config.memory.storage_path
    storage = FileStorage(base_dir=storage_path)

    if not storage.session_exists(session_id):
        Console.print(f"Session '{session_id}' not found", style="error")
        sys.exit(1)

    entries = storage.load_session(session_id)
    Console.print_header(f"Session: {session_id}")
    Console.print(f"Total messages: {len(entries)}", style="info")
    Console.print_separator()

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
            content = entry.content[:100] + "..." if len(entry.content) > 100 else entry.content
            print(f"  [{entry.role}]: {content}")
        if len(entries) > 3:
            print(f"  ... 还有 {len(entries) - 3} 条消息")


def _generate_session_summary(agent, config) -> str:
    """使用 LLM 生成会话摘要（不超过10行）"""
    messages = agent.memory.get_all()
    # 过滤掉 system 消息
    messages = [m for m in messages if m.get("role") != "system"]

    if not messages:
        return "空会话"

    # 构建对话文本
    conversation = "\n".join(
        f"[{m.get('role')}]: {m.get('content', '')[:200]}"
        for m in messages
    )

    prompt = f"""请用不超过10行总结以下对话的主要内容：

{conversation}

要求：
1. 提取关键话题和结论
2. 简洁明了，不超过10行
3. 用中文回答"""

    try:
        response, _, _ = agent.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None
        )
        return response
    except Exception:
        # 失败时返回简单摘要
        return f"共 {len(messages)} 条消息"


def _save_session_summary(agent, config, summary: str) -> None:
    """保存会话摘要"""
    # 获取 session_id
    if hasattr(agent.memory, 'working_memory') and hasattr(agent.memory.working_memory, 'session_id'):
        session_id = agent.memory.working_memory.session_id
    elif hasattr(agent.memory, 'session_id'):
        session_id = agent.memory.session_id
    else:
        return  # 无法获取 session_id

    storage = FileStorage(base_dir=config.memory.storage_path)
    messages = agent.memory.get_all()
    message_count = len([m for m in messages if m.get("role") != "system"])

    storage.save_summary(session_id, summary, message_count)


def _handle_skill_command(agent, command: str) -> None:
    """处理技能包命令

    Args:
        agent: Agent 实例
        command: 命令字符串（如 'reload coding'）
    """
    if not hasattr(agent, 'skill_loader'):
        Console.print("Skill system not available", style="warning")
        return

    parts = command.strip().split()
    if not parts:
        Console.print("Usage: skill <reload|unload> <name>", style="info")
        return

    action = parts[0].lower()
    skill_name = parts[1] if len(parts) > 1 else None

    if action == "reload":
        if not skill_name:
            Console.print("Usage: skill reload <name>", style="info")
            return

        if skill_name not in agent.skill_loader.list_loaded_skills():
            Console.print(f"Skill '{skill_name}' not found", style="error")
            return

        success = agent.skill_loader.reload_skill(skill_name)
        if success:
            Console.print(f"Skill '{skill_name}' reloaded successfully", style="success")
            # Update agent's tools and prompt
            _update_agent_skills(agent)
        else:
            Console.print(f"Failed to reload skill '{skill_name}'", style="error")

    elif action == "unload":
        if not skill_name:
            Console.print("Usage: skill unload <name>", style="info")
            return

        if skill_name not in agent.skill_loader.list_loaded_skills():
            Console.print(f"Skill '{skill_name}' not found", style="error")
            return

        success = agent.skill_loader.unload_skill(skill_name)
        if success:
            Console.print(f"Skill '{skill_name}' unloaded successfully", style="success")
            # Update agent's tools and prompt
            _update_agent_skills(agent)
        else:
            Console.print(f"Failed to unload skill '{skill_name}'", style="error")

    else:
        Console.print(f"Unknown action: {action}. Use 'reload' or 'unload'", style="error")


def _update_agent_skills(agent) -> None:
    """更新 Agent 的工具和系统提示（热加载后）

    Args:
        agent: Agent 实例
    """
    # Update tools
    for tool in agent.skill_registry.get_all_tools():
        if tool.name not in agent.tool_registry.list_tools():
            agent.tool_registry.register(tool)

    # Update system prompt
    skill_prompt = agent.skill_registry.get_combined_system_prompt()
    agent.skill_prompt = skill_prompt
    agent._setup_system_prompt()


def _show_run_stats(agent, config=None) -> None:
    """显示本轮运行的统计信息

    Args:
        agent: Agent 实例
        config: 配置对象（用于获取上下文长度）
    """
    if not hasattr(agent, 'tracker') or not agent.tracker.run_metrics:
        return

    # Get current run and session statistics
    current_summary = agent.tracker.get_summary()
    session_summary = agent.tracker.get_session_summary()

    if not current_summary or not session_summary:
        return

    # 收集工具调用类型 (from current run)
    tool_types = []
    full_report = agent.tracker.get_full_report()
    if full_report and full_report.get('iterations'):
        for iteration in full_report['iterations']:
            for tool in iteration.get('tool_executions', []):
                status = "✓" if tool['success'] else "✗"
                tool_types.append(f"{status}{tool['tool_name']}")

    # 本轮统计
    current_duration = current_summary.get('duration_ms', 0) / 1000
    current_tokens = current_summary.get('total_tokens', 0)
    current_iterations = current_summary.get('total_iterations', 0)

    # 会话总计
    session_duration = session_summary.get('session_duration_ms', 0) / 1000
    session_tokens = session_summary.get('total_tokens', 0)
    session_llm_calls = session_summary.get('total_llm_calls', 0)

    # 上下文使用率
    context_info = ""
    if config and hasattr(config, 'llm'):
        context_length = config.llm.get_context_length()
        usage_percent = (session_tokens / context_length) * 100 if context_length > 0 else 0
        context_info = f" | 上下文: {usage_percent:.1f}% ({session_tokens}/{context_length})"

        # 警告接近上限
        if usage_percent >= 80:
            context_info = f" | ⚠️ 上下文: {usage_percent:.1f}% (接近上限!)"

    # 格式化输出 - 右对齐数字
    def format_tokens(n: int) -> str:
        return f"{n:>6}"

    def format_duration(s: float) -> str:
        return f"{s:>6.2f}"

    def format_llm_calls(n: int) -> str:
        return f"{n:>3}"

    # 本轮
    print(f"\n📊 本轮: {format_tokens(current_tokens)} tokens | {format_duration(current_duration)}s | LLM调用: {format_llm_calls(current_iterations)} | 迭代: {current_iterations}", end="")
    if tool_types:
        print(f" | 工具: {', '.join(tool_types)}", end="")
    # 总计
    print(f"\n📊 总计: {format_tokens(session_tokens)} tokens | {format_duration(session_duration)}s | LLM调用: {format_llm_calls(session_llm_calls)}{context_info}")


def _show_monitoring_stats(agent) -> None:
    """显示监控统计信息

    Args:
        agent: Agent 实例
    """
    import json

    if not hasattr(agent, 'tracker'):
        Console.print("Monitoring not available", style="warning")
        return

    summary = agent.tracker.get_summary()
    if not summary:
        Console.print("No monitoring data available yet. Run a query first.", style="info")
        return

    Console.print("\n=== Monitoring Statistics ===", style="info")
    print(f"Session ID: {summary.get('session_id', 'N/A')}")
    print(f"Duration: {summary.get('duration_ms', 0):.2f} ms")
    print(f"Total Iterations: {summary.get('total_iterations', 0)}")
    print(f"Total Tokens: {summary.get('total_tokens', 0)}")
    print(f"Total Tool Calls: {summary.get('total_tool_calls', 0)}")
    print(f"  - Successful: {summary.get('successful_tool_calls', 0)}")
    print(f"  - Failed: {summary.get('failed_tool_calls', 0)}")

    # Show detailed report if available
    full_report = agent.tracker.get_full_report()
    if full_report and full_report.get('iterations'):
        print("\n--- Iteration Details ---")
        for iteration in full_report['iterations']:
            print(f"\nIteration {iteration['iteration_number']}:")
            if iteration.get('llm_call'):
                llm = iteration['llm_call']
                print(f"  LLM: {llm['model']}")
                print(f"    Tokens: {llm['prompt_tokens']} prompt + {llm['completion_tokens']} completion = {llm['total_tokens']} total")
                print(f"    Latency: {llm['latency_ms']:.2f} ms")
                print(f"    Tool calls: {llm['tool_calls_count']}")
            if iteration.get('tool_executions'):
                print(f"  Tool Executions:")
                for tool in iteration['tool_executions']:
                    status = "✓" if tool['success'] else "✗"
                    print(f"    {status} {tool['tool_name']}: {tool['latency_ms']:.2f} ms")

    print("\n" + "=" * 30)


if __name__ == "__main__":
    main()