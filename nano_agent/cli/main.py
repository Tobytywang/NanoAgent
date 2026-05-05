"""
CLI entry point for NanoAgent.
"""

import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path

from ..llm import create_llm_from_config
from ..memory import ShortTermMemory, PersistentMemory, HybridMemory, FileStorage, SQLiteStorage, LongTermMemory
from ..tools.base import ToolRegistry
from ..tools.builtin import register_builtin_tools
from ..agent.react import ReActAgent
from ..config.loader import ConfigLoader
from ..skills import SkillRegistry, SkillLoader
from ..monitoring.reporter import ReportGenerator
from .console import Console
from .scanner import ProjectScanner


class GracefulExitManager:
    """管理优雅退出状态"""

    ctrl_c_count = 0  # Ctrl+C 按下次数
    generating_summary = False  # 是否正在生成摘要
    agent = None  # 当前 agent 引用
    config = None  # 当前 config 引用
    report_enabled = False  # 是否启用报告导出
    report_format = "json"  # 报告格式
    report_output = None  # 报告输出路径
    show_run_stats = True  # 是否在每次对话后显示统计

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

                # 导出监控报告
                if cls.report_enabled:
                    _export_report(cls.agent, cls.report_format, cls.report_output)
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

    # Create storage based on type
    if config.memory.storage_type == "sqlite":
        db_path = config.memory.storage_path
        # Ensure it's a .db file path, not a directory
        if not db_path.endswith(".db"):
            db_path = db_path + ".db"
        storage = SQLiteStorage(db_path=db_path)
    else:
        storage = FileStorage(base_dir=config.memory.storage_path)

    if config.memory.type == "hybrid":
        # Create working memory (persistent for session support)
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


def update_gitignore(project_root: Path | None = None) -> bool:
    """
    Automatically add .nano_agent/ to project's .gitignore.

    Only updates if .gitignore already exists (won't create new one).
    Skips if entry already present.

    Args:
        project_root: Project root directory, defaults to current working directory

    Returns:
        True if updated successfully or entry already exists
    """
    if project_root is None:
        project_root = Path.cwd()

    gitignore_path = project_root / ".gitignore"
    entry = ".nano_agent/"

    try:
        # Only update if .gitignore already exists
        if not gitignore_path.exists():
            return False

        # Check if entry already exists
        content = gitignore_path.read_text(encoding="utf-8")
        # Check both with and without trailing slash
        if entry in content or entry.rstrip("/") in content:
            return True  # Already exists, no need to update

        # Append to file
        with open(gitignore_path, "a", encoding="utf-8") as f:
            # Ensure file ends with newline
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(f"\n# NanoAgent\n{entry}\n")

        return True

    except (IOError, PermissionError) as e:
        # Silently fail if can't write to .gitignore
        Console.print(f"Warning: Could not update .gitignore: {e}", style="warning")
        return False


def _find_config_file(config_path: str | None = None) -> tuple[Path | None, str]:
    """
    Find configuration file with priority.

    Priority:
    1. Explicitly specified path (-c option)
    2. ./.nano_agent/config.yaml (project local)
    3. ~/.nano_agent/config.yaml (global)
    4. None (use default config)

    Args:
        config_path: Explicitly specified config path

    Returns:
        Tuple of (config_path, source_description)
    """
    if config_path:
        path = Path(config_path)
        if path.exists():
            return path, f"specified: {config_path}"
        return None, "default (specified file not found)"

    # Priority 1: Project local config (./.nano_agent/config.yaml)
    local_config = Path.cwd() / ".nano_agent" / "config.yaml"
    if local_config.exists():
        return local_config, f"local: {local_config}"

    # Priority 2: Global config (~/.nano_agent/config.yaml)
    global_config = Path.home() / ".nano_agent" / "config.yaml"
    if global_config.exists():
        return global_config, f"global: {global_config}"

    return None, "default (no config file found)"


def create_agent(config_path: str | None = None) -> ReActAgent:
    """
    Create and configure a ReAct agent.

    Args:
        config_path: Path to configuration file

    Returns:
        Configured ReActAgent instance
    """
    # Find and load configuration with priority
    config_file, config_source = _find_config_file(config_path)

    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()  # Returns default config

    # Auto-update .gitignore
    update_gitignore()

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

    # Load plugins from configuration
    from ..tools.plugin import load_plugins_from_config
    plugins_config = {
        "directories": config.plugins.directories if hasattr(config, 'plugins') else [],
        "modules": config.plugins.modules if hasattr(config, 'plugins') else [],
        "files": config.plugins.files if hasattr(config, 'plugins') else [],
    }
    load_plugins_from_config(plugins_config, tool_registry)

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

    # Store config source for display
    agent._config_source = config_source

    return agent


def _load_project_context() -> str:
    """
    Load project context from NANOPROJECT.md and .nano_agent/.

    Returns:
        Context string to add to system prompt
    """
    context_parts = []
    project_root = Path.cwd()

    # 1. Load NANOPROJECT.md (required if exists)
    nanoproject_path = project_root / "NANOPROJECT.md"
    if nanoproject_path.exists():
        try:
            content = nanoproject_path.read_text(encoding="utf-8")
            # Truncate if too long
            if len(content) > 3000:
                content = content[:3000] + "\n\n... (truncated)"
            context_parts.append(f"## Project Context\n\n{content}")
        except Exception:
            pass

    # 2. Load .nano_agent/long_term_memory (optional)
    long_term_path = project_root / ".nano_agent" / "long_term_memory"
    if long_term_path.exists():
        try:
            from ..memory import LongTermMemory
            ltm = LongTermMemory(storage_path=str(long_term_path))
            memories = ltm.search("", limit=10)  # Get recent memories
            if memories:
                memory_text = "\n".join([
                    f"- [{m.category}] {m.content[:200]}"
                    for m in memories[:5]
                ])
                context_parts.append(f"## Long-term Memories\n\n{memory_text}")
        except Exception:
            pass

    if context_parts:
        return "\n\n---\n\n".join(context_parts)
    return ""


def run_interactive(
    agent: ReActAgent,
    config,
    report_enabled: bool = False,
    report_format: str = "json",
    report_output: str | None = None
) -> None:
    """
    Run interactive chat loop.

    Args:
        agent: The agent to interact with
        config: The configuration object
        report_enabled: Whether to export report on exit
        report_format: Report format (json, markdown, summary)
        report_output: Report output path
    """
    import os

    # Load project context at startup and add to system prompt
    project_context = _load_project_context()

    # 设置优雅退出管理器
    GracefulExitManager.agent = agent
    GracefulExitManager.config = config
    GracefulExitManager.report_enabled = report_enabled
    GracefulExitManager.report_format = report_format
    GracefulExitManager.report_output = report_output
    signal.signal(signal.SIGINT, GracefulExitManager.handler)

    # Print header with all info
    Console.print_header("NanoAgent - AI Assistant")

    # Show config source
    if hasattr(agent, '_config_source'):
        Console.print(f"Config: {agent._config_source}", style="info")

    # Show project context status
    if project_context:
        # Append to system prompt
        current_prompt = agent.memory.system_prompt or ""
        agent.memory.set_system_prompt(f"{current_prompt}\n\n---\n\n{project_context}")
        Console.print("Project: NANOPROJECT.md loaded", style="success")

    Console.print("Type '/?' or 'help' for available commands", style="info")
    Console.print_separator()

    # Get display names from config
    user_display = config.agent.user_name
    agent_display = config.agent.agent_name

    while True:
        try:
            cwd = os.getcwd()
            print(f"\n[{user_display}] [{cwd}]:")
            user_input = input("> ").strip()

            if not user_input:
                continue

            # 显示帮助信息
            if user_input.lower() in ["/?", "/help", "help", "?", "？", "/？"]:
                _show_help()
                continue

            # 优雅退出命令（生成摘要）
            if user_input.lower() in ["/exit", "/quit", "/bye"]:
                GracefulExitManager.exit_with_summary()
                break

            # 直接退出命令（不生成摘要）
            if user_input.lower() in ["exit", "quit"]:
                Console.print("Goodbye!", style="success")
                break

            if user_input.lower() == "/clear":
                agent.reset()
                Console.print("Conversation history cleared", style="success")
                continue

            if user_input.lower() == "/tools":
                tools = agent.tool_registry.list_tools()
                Console.print(f"Available tools: {', '.join(tools)}", style="info")
                continue

            if user_input.lower().startswith("/stats"):
                _handle_stats_command(agent, config, user_input[6:].strip())
                continue

            if user_input.lower() == "/init":
                _init_project(agent)
                continue

            if user_input.lower() == "/config":
                _show_config(config, agent)
                continue

            if user_input.lower().startswith("/config "):
                _handle_config_command(agent, config, user_input[8:])
                continue

            if user_input.lower().startswith("/memory"):
                _handle_memory_command(agent, config, user_input[7:].strip())
                continue

            if user_input.lower() == "/report":
                _export_report(agent, report_format, report_output)
                continue

            if user_input.lower() == "/sessions":
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
            if user_input.lower() == "/skills":
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

            if user_input.lower().startswith("/skill "):
                _handle_skill_command(agent, user_input[7:])
                continue

            # 重置 Ctrl+C 计数
            GracefulExitManager.ctrl_c_count = 0

            # Run agent
            print(f"\n[{agent_display}]:")
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
    # Custom formatter with wider help column for alignment
    class WideHelpFormatter(argparse.RawTextHelpFormatter):
        def __init__(self, prog):
            super().__init__(prog, max_help_position=28, width=100)

    parser = argparse.ArgumentParser(
        description="NanoAgent - A lightweight AI Agent framework",
        formatter_class=WideHelpFormatter,
        add_help=False,
        epilog="""
Examples:
  nano-agent                          Start interactive session
  nano-agent -c ~/.nano_agent/config.yaml    Use global config
  nano-agent --report                 Export report after session
  nano-agent --list-sessions          List saved sessions
  nano-agent -r session_xxx           Resume a session

Config file priority:
  1. ./.nano_agent/config.yaml (project)
  2. ~/.nano_agent/config.yaml (global)
  3. Built-in defaults
"""
    )
    parser.add_argument(
        "-h", "--help", action="help",
        help="Show this [h]elp message and exit"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        metavar="PATH",
        help="[c]onfig file path (see priority below)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=None,
        metavar="NAME",
        help="Override [m]odel name"
    )
    parser.add_argument(
        "-l", "--list-sessions",
        action="store_true",
        help="[l]ist all saved sessions"
    )
    parser.add_argument(
        "-s", "--session", type=str, metavar="ID", default=None,
        help="[s]how a specific session"
    )
    parser.add_argument(
        "-r", "--resume",
        type=str,
        metavar="ID",
        default=None,
        help="[r]esume an existing session"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode (read from stdin)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress verbose output ([q]uiet mode)"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Export monitoring report after session"
    )
    parser.add_argument(
        "--report-format",
        type=str,
        choices=["json", "markdown", "summary"],
        default="json",
        metavar="FORMAT",
        help="Report format: json, markdown, summary"
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default=None,
        metavar="PATH",
        help="Report output file path"
    )

    args = parser.parse_args()

    # Handle --list-sessions
    if args.list_sessions:
        _list_sessions(args.config)
        return

    # Handle --session
    if args.session:
        _show_session(args.session, args.config)
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

            # Export report if enabled
            if args.report:
                _export_report(agent, args.report_format, args.report_output)
    else:
        # Interactive mode - use the same config as create_agent
        # Re-load config to get the actual loaded config
        config_file, _ = _find_config_file(args.config)
        if config_file:
            config = ConfigLoader.load(config_file)
        else:
            config = ConfigLoader.load()
        run_interactive(
            agent,
            config,
            report_enabled=args.report,
            report_format=args.report_format,
            report_output=args.report_output
        )


def _get_storage(config):
    """Get storage instance based on configuration."""
    if config.memory.storage_type == "sqlite":
        db_path = config.memory.storage_path
        # Ensure path ends with .db
        if not db_path.endswith(".db"):
            db_path = db_path + ".db"
        return SQLiteStorage(db_path=db_path)
    else:
        return FileStorage(base_dir=config.memory.storage_path)


def _list_sessions(config_path: str | None = None) -> None:
    """List all available sessions."""
    # Find config file with priority
    config_file, _ = _find_config_file(config_path)

    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()

    storage = _get_storage(config)
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
    # Find config file with priority
    config_file, _ = _find_config_file(config_path)

    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()

    storage = _get_storage(config)

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

    storage = _get_storage(config)
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
    # 检查是否启用了统计显示
    if not GracefulExitManager.show_run_stats:
        return

    if not hasattr(agent, 'tracker') or not agent.tracker.run_metrics:
        return

    # Get current run and session statistics
    current_summary = agent.tracker.get_summary()
    session_summary = agent.tracker.get_session_summary()

    if not current_summary or not session_summary:
        return

    # 收集工具调用类型 (from current run)，合并相同工具
    tool_counts = {}
    full_report = agent.tracker.get_full_report()
    if full_report and full_report.get('iterations'):
        for iteration in full_report['iterations']:
            for tool in iteration.get('tool_executions', []):
                status = "✓" if tool['success'] else "✗"
                key = (status, tool['tool_name'])
                tool_counts[key] = tool_counts.get(key, 0) + 1

    # 格式化工具调用显示
    tool_types = []
    for (status, name), count in tool_counts.items():
        if count > 1:
            tool_types.append(f"{status}{name}*{count}")
        else:
            tool_types.append(f"{status}{name}")

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


def _export_report(
    agent,
    report_format: str = "json",
    report_output: str | None = None
) -> None:
    """导出监控报告

    Args:
        agent: Agent 实例
        report_format: 报告格式 (json, markdown, summary)
        report_output: 输出路径 (默认 .nano_agent/report.{format})
    """
    if not hasattr(agent, 'tracker') or not agent.tracker.run_metrics:
        Console.print("No monitoring data available yet. Run a query first.", style="info")
        return

    # 确定输出路径
    if report_output is None:
        ext = "md" if report_format == "markdown" else report_format
        report_output = f".nano_agent/report.{ext}"

    # 确保目录存在
    from pathlib import Path
    Path(report_output).parent.mkdir(parents=True, exist_ok=True)

    try:
        # 获取完整的运行指标
        metrics = agent.tracker.run_metrics

        # 使用 ReportGenerator 导出
        if report_format == "json":
            ReportGenerator.save_json(metrics, report_output)
            Console.print(f"Report exported to: {report_output}", style="success")
        elif report_format == "markdown":
            ReportGenerator.save_markdown(metrics, report_output)
            Console.print(f"Report exported to: {report_output}", style="success")
        elif report_format == "summary":
            summary = ReportGenerator.to_summary(metrics)
            print(f"\n{summary}")
        else:
            Console.print(f"Unknown format: {report_format}", style="error")

    except Exception as e:
        Console.print(f"Failed to export report: {e}", style="error")


def _show_config(config, agent) -> None:
    """显示当前配置信息

    Args:
        config: 配置对象
        agent: Agent 实例
    """
    print("\n" + "=" * 50)
    print("Current Configuration")
    print("=" * 50)

    # 格式化函数：左对齐标签，右对齐值
    def format_line(label: str, value: str, width: int = 20) -> str:
        return f"  {label:<{width}} {value}"

    # LLM 配置
    print("\n## LLM Settings")
    print(format_line("Provider:", config.llm.provider))
    print(format_line("Model:", config.llm.model))
    print(format_line("Base URL:", config.llm.base_url))
    print(format_line("Timeout:", f"{config.llm.timeout}s"))
    print(format_line("Temperature:", str(config.llm.temperature)))
    print(format_line("Context Length:", f"{config.llm.get_context_length():,}"))

    # Agent 配置
    print("\n## Agent Settings")
    print(format_line("Max Iterations:", str(config.agent.max_iterations)))
    print(format_line("Verbose:", str(config.agent.verbose)))

    # Memory 配置
    print("\n## Memory Settings")
    print(format_line("Type:", config.memory.type))
    print(format_line("Storage Type:", config.memory.storage_type))
    print(format_line("Storage Path:", config.memory.storage_path))
    print(format_line("Max Messages:", str(config.memory.max_messages)))
    if config.memory.type == "hybrid":
        print(format_line("Long-term Path:", config.memory.long_term_storage_path))
        print(format_line("Auto Extract:", str(config.memory.auto_extract)))

    # Skills 配置
    print("\n## Skills Settings")
    print(format_line("Directory:", config.skills.directory))
    if hasattr(agent, 'skill_loader'):
        skills = agent.skill_loader.list_loaded_skills()
        print(format_line("Loaded Skills:", ', '.join(skills) if skills else 'None'))

    # Plugins 配置
    print("\n## Plugins Settings")
    print(format_line("Directories:", ', '.join(config.plugins.directories) if config.plugins.directories else 'None'))
    print(format_line("Modules:", ', '.join(config.plugins.modules) if config.plugins.modules else 'None'))

    # Logging 配置
    print("\n## Logging Settings")
    print(format_line("Level:", config.logging.level))
    print(format_line("Console:", str(config.logging.console)))
    print(format_line("File:", config.logging.file or 'None'))

    # 工具统计
    print("\n## Tools")
    tools = agent.tool_registry.list_tools()
    print(format_line("Total:", str(len(tools))))
    tools_display = ', '.join(tools[:10])
    if len(tools) > 10:
        tools_display += f"... (+{len(tools) - 10} more)"
    print(format_line("Tools:", tools_display))

    print("\n" + "=" * 50 + "\n")


def _handle_memory_command(agent, config, command: str) -> None:
    """处理 /memory 子命令

    Args:
        agent: Agent 实例
        config: 配置对象
        command: 子命令字符串
    """
    parts = command.strip().split() if command else []

    if not parts or parts[0].lower() in ["status", ""]:
        # 显示当前记忆状态
        _show_memory_status(config)
    elif parts[0].lower() == "on":
        _enable_long_term_memory(config)
    elif parts[0].lower() == "off":
        _disable_long_term_memory(config)
    else:
        Console.print(f"Unknown subcommand: {parts[0]}", style="error")
        Console.print("Available: status, on, off", style="info")


def _show_memory_status(config) -> None:
    """显示当前记忆配置状态"""
    print("\n" + "=" * 50)
    print("Memory Configuration")
    print("=" * 50)

    def format_line(label: str, value: str, width: int = 20) -> str:
        return f"  {label:<{width}} {value}"

    print("\n## Current Settings")
    print(format_line("Memory Type:", config.memory.type))
    print(format_line("Storage Type:", config.memory.storage_type))
    print(format_line("Storage Path:", config.memory.storage_path))

    if config.memory.type == "hybrid":
        print(format_line("Long-term Path:", config.memory.long_term_storage_path))
        print(format_line("Auto Extract:", str(config.memory.auto_extract)))

    print("\n## Memory Modes")
    print("  short_term  - Only current context (no persistence)")
    print("  hybrid      - Short-term + Long-term memory (recommended)")

    print("\n## Commands")
    print("  /memory on   - Enable long-term memory (hybrid mode)")
    print("  /memory off  - Disable long-term memory (short_term mode)")

    print("\n" + "=" * 50 + "\n")


def _enable_long_term_memory(config) -> None:
    """启用长期记忆功能"""
    import yaml
    from pathlib import Path

    # 检查当前状态
    if config.memory.type == "hybrid":
        Console.print("Long-term memory is already enabled.", style="info")
        return

    # 更新配置文件
    config_path = Path.cwd() / ".nano_agent" / "config.yaml"

    if not config_path.exists():
        # 创建配置文件
        Console.print("Creating config file...", style="info")
        _init_config_file(config)

    # 读取并更新配置
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f) or {}

        # 更新 memory 配置
        existing_config["memory"] = existing_config.get("memory", {})
        existing_config["memory"]["type"] = "hybrid"
        existing_config["memory"]["auto_extract"] = True

        # 确保路径存在
        if "storage_path" not in existing_config["memory"]:
            existing_config["memory"]["storage_path"] = ".nano_agent/memory"
        if "long_term_storage_path" not in existing_config["memory"]:
            existing_config["memory"]["long_term_storage_path"] = ".nano_agent/long_term_memory"

        # 写入配置
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        Console.print("Long-term memory enabled!", style="success")
        Console.print(f"Config updated: {config_path}", style="info")
        Console.print("Memory type changed to: hybrid", style="info")
        Console.print("Restart nano-agent to apply changes.", style="warning")

    except Exception as e:
        Console.print(f"Failed to update config: {e}", style="error")


def _disable_long_term_memory(config) -> None:
    """禁用长期记忆功能"""
    import yaml
    from pathlib import Path

    # 检查当前状态
    if config.memory.type == "short_term":
        Console.print("Long-term memory is already disabled.", style="info")
        return

    # 更新配置文件
    config_path = Path.cwd() / ".nano_agent" / "config.yaml"

    if not config_path.exists():
        Console.print("No config file found. Memory is using defaults.", style="info")
        return

    # 读取并更新配置
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f) or {}

        # 更新 memory 配置
        existing_config["memory"] = existing_config.get("memory", {})
        existing_config["memory"]["type"] = "short_term"
        existing_config["memory"]["auto_extract"] = False

        # 写入配置
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        Console.print("Long-term memory disabled!", style="success")
        Console.print(f"Config updated: {config_path}", style="info")
        Console.print("Memory type changed to: short_term", style="info")
        Console.print("Restart nano-agent to apply changes.", style="warning")

    except Exception as e:
        Console.print(f"Failed to update config: {e}", style="error")


def _handle_stats_command(agent, config, command: str) -> None:
    """处理 /stats 子命令

    Args:
        agent: Agent 实例
        config: 配置对象
        command: 子命令字符串
    """
    parts = command.strip().split() if command else []

    if not parts or parts[0].lower() in ["status", ""]:
        # 显示当前会话统计
        _show_stats_status(agent, config)
    elif parts[0].lower() == "on":
        _enable_run_stats()
    elif parts[0].lower() == "off":
        _disable_run_stats()
    else:
        Console.print(f"Unknown subcommand: {parts[0]}", style="error")
        Console.print("Available: status, on, off", style="info")


def _show_stats_status(agent, config) -> None:
    """显示当前会话统计状态"""
    print("\n" + "=" * 50)
    print("Session Statistics")
    print("=" * 50)

    def format_line(label: str, value: str, width: int = 20) -> str:
        return f"  {label:<{width}} {value}"

    # 显示自动统计开关状态
    auto_status = "on" if GracefulExitManager.show_run_stats else "off"
    print("\n## Auto Display")
    print(format_line("Show after each run:", auto_status))

    # 显示会话统计
    if hasattr(agent, 'tracker'):
        session_summary = agent.tracker.get_session_summary()
        if session_summary:
            print("\n## Session Summary")
            duration_ms = session_summary.get('session_duration_ms', 0)
            duration_s = duration_ms / 1000
            print(format_line("Duration:", f"{duration_s:.2f} s"))
            print(format_line("Total Tokens:", str(session_summary.get('total_tokens', 0))))
            print(format_line("Total LLM Calls:", str(session_summary.get('total_llm_calls', 0))))
            print(format_line("Total Iterations:", str(session_summary.get('total_iterations', 0))))
            print(format_line("Tool Calls:", str(session_summary.get('total_tool_calls', 0))))
            print(format_line("  - Successful:", str(session_summary.get('successful_tool_calls', 0))))
            print(format_line("  - Failed:", str(session_summary.get('failed_tool_calls', 0))))

            # 上下文使用率
            if config and hasattr(config, 'llm'):
                context_length = config.llm.get_context_length()
                total_tokens = session_summary.get('total_tokens', 0)
                if context_length > 0:
                    usage_percent = (total_tokens / context_length) * 100
                    print(format_line("Context Usage:", f"{usage_percent:.1f}% ({total_tokens}/{context_length})"))
        else:
            print("\n## Session Summary")
            print("  No data yet. Run a query first.")

    print("\n## Commands")
    print("  /stats on   - Enable auto display after each run")
    print("  /stats off  - Disable auto display after each run")

    print("\n" + "=" * 50 + "\n")


def _enable_run_stats() -> None:
    """启用每次对话后的统计显示"""
    if GracefulExitManager.show_run_stats:
        Console.print("Auto stats display is already enabled.", style="info")
        return

    GracefulExitManager.show_run_stats = True
    Console.print("Auto stats display enabled!", style="success")
    Console.print("Statistics will be shown after each run.", style="info")


def _disable_run_stats() -> None:
    """禁用每次对话后的统计显示"""
    if not GracefulExitManager.show_run_stats:
        Console.print("Auto stats display is already disabled.", style="info")
        return

    GracefulExitManager.show_run_stats = False
    Console.print("Auto stats display disabled!", style="success")
    Console.print("Use /stats to view statistics manually.", style="info")


def _show_help() -> None:
    """显示交互模式帮助信息"""
    print("\n" + "=" * 50)
    print("Available Commands")
    print("=" * 50)

    print("\n## 基本操作")
    print("  /exit, /quit      退出（保存摘要）")
    print("  exit, quit        直接退出")
    print("  /clear            清空对话")
    print("  /?, help          显示帮助")

    print("\n## 查看信息")
    print("  /config           查看配置")
    print("  /memory           查看记忆状态")
    print("  /stats            查看统计")
    print("  /tools            查看工具列表")
    print("  /skills           查看技能列表")
    print("  /sessions         查看会话列表")

    print("\n## 项目管理")
    print("  /init             初始化项目")
    print("  /config init      生成配置文件（合并）")
    print("  /config init -f   强制覆盖配置文件")
    print("  /memory on        启用长期记忆")
    print("  /memory off       禁用长期记忆")
    print("  /stats on         启用统计自动显示")
    print("  /stats off        禁用统计自动显示")

    print("\n## 技能管理")
    print("  /skill reload <n> 重载技能")
    print("  /skill unload <n> 卸载技能")

    print("\n## 导出")
    print("  /report           导出监控报告")

    print("\n" + "=" * 50 + "\n")


def _handle_config_command(agent, config, command: str) -> None:
    """处理 /config 子命令

    Args:
        agent: Agent 实例
        config: 配置对象
        command: 子命令字符串
    """
    parts = command.strip().split()
    if not parts:
        Console.print("Usage: /config <init [--force]>", style="info")
        return

    subcommand = parts[0].lower()

    if subcommand == "init":
        force = "--force" in parts or "-f" in parts
        _init_config_file(config, force=force)
    else:
        Console.print(f"Unknown subcommand: {subcommand}", style="error")
        Console.print("Available: init [--force]", style="info")


def _init_config_file(config, force: bool = False) -> None:
    """生成或更新配置文件到 .nano_agent 目录

    采用合并策略：保留用户已修改的配置，只补充缺失的默认配置。

    Args:
        config: 当前配置对象
        force: 是否强制覆盖
    """
    import yaml
    from pathlib import Path

    # 确保 .nano_agent 目录存在
    nano_agent_dir = Path.cwd() / ".nano_agent"
    nano_agent_dir.mkdir(parents=True, exist_ok=True)

    config_path = nano_agent_dir / "config.yaml"

    # 生成默认配置模板（带注释标记）
    default_config = {
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "base_url": config.llm.base_url,
            "api_key": config.llm.api_key or "YOUR_API_KEY_HERE",
            "timeout": config.llm.timeout,
            "temperature": config.llm.temperature,
            "context_length": config.llm.context_length,
        },
        "agent": {
            "max_iterations": config.agent.max_iterations,
            "verbose": config.agent.verbose,
            "user_name": config.agent.user_name,
            "agent_name": config.agent.agent_name,
            "system_prompt": config.agent.system_prompt or "You are a helpful AI assistant.",
        },
        "memory": {
            "type": config.memory.type,
            "storage_type": config.memory.storage_type,
            "storage_path": config.memory.storage_path,
            "max_messages": config.memory.max_messages,
            "long_term_storage_path": config.memory.long_term_storage_path,
            "auto_extract": config.memory.auto_extract,
        },
        "tools": {
            "enabled": ["all"],
            "disabled": [],
        },
        "skills": {
            "enabled": [],
            "directory": config.skills.directory,
        },
        "logging": {
            "level": config.logging.level,
            "console": config.logging.console,
            "file": config.logging.file or ".nano_agent/debug.log",
        },
    }

    # 如果文件不存在或强制覆盖，直接写入
    if not config_path.exists() or force:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        Console.print(f"Config file created: {config_path}", style="success")
        return

    # 文件已存在，进行合并
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f) or {}

        # 深度合并：补充缺失的配置项，保留用户已修改的
        merged_config = _merge_config(default_config, existing_config)

        # 检查是否有新增配置项
        if merged_config == existing_config:
            Console.print("Config file is up to date. No changes needed.", style="info")
            return

        # 写入合并后的配置
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(merged_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        Console.print(f"Config file updated: {config_path}", style="success")
        Console.print("Missing default values have been added.", style="info")

    except Exception as e:
        Console.print(f"Failed to merge config: {e}", style="error")
        Console.print("Use '/config init --force' to overwrite", style="info")


def _merge_config(default: dict, existing: dict) -> dict:
    """深度合并配置，保留用户已修改的值，补充缺失的默认值

    Args:
        default: 默认配置
        existing: 现有配置

    Returns:
        合并后的配置
    """
    import copy
    result = copy.deepcopy(existing)

    for key, value in default.items():
        if key not in result:
            # 缺失的配置项，添加默认值
            result[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            # 递归合并嵌套字典
            result[key] = _merge_config(value, result[key])

    return result


def _init_project(agent) -> None:
    """扫描项目并使用 LLM 生成 NANOPROJECT.md

    Args:
        agent: Agent 实例
    """
    Console.print("Scanning project structure...", style="info")

    try:
        scanner = ProjectScanner()
        info = scanner.scan()

        # 显示扫描结果摘要
        Console.print(f"Project: {info['project_name']}", style="info")
        Console.print(f"Files: {info['structure']['total_files']} | Dirs: {info['structure']['total_dirs']}", style="info")

        if info['tech_stack']:
            Console.print(f"Tech: {', '.join(info['tech_stack'])}", style="info")

        # 使用 LLM 生成项目摘要
        Console.print("\nGenerating project summary with LLM...", style="info")

        # 构建扫描信息摘要
        scan_summary = f"""
Project Name: {info['project_name']}
Tech Stack: {', '.join(info['tech_stack']) or 'Unknown'}
Files: {info['structure']['total_files']}
Directories: {info['structure']['total_dirs']}
Top Directories: {', '.join(info['structure']['top_dirs'][:10])}
Entry Points: {', '.join(info['code_summary']['entry_points']) or 'None detected'}
Languages: {dict(info['code_summary']['languages'])}
Git Branch: {info['git_info'].get('branch', 'N/A')}
Recent Commits: {info['git_info'].get('recent_commits', [])[:3]}
"""

        prompt = f"""Based on the following project scan results, generate a comprehensive project summary in Markdown format.

The summary should include:
1. A brief project description (infer from name and structure)
2. Technology stack analysis
3. Project structure overview
4. Development notes and suggestions

Scan Results:
{scan_summary}

Please generate NANOPROJECT.md content (in Chinese, concise and professional):"""

        # 调用 LLM
        response, _, _ = agent.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None
        )

        # 保存 LLM 生成的摘要
        output_path = Path.cwd() / "NANOPROJECT.md"

        # 添加头部信息
        header = f"""# {info['project_name']} - 项目摘要

> 由 NanoAgent 生成于 {info['scan_time'][:19]}
> 基于 LLM 分析

---

"""
        full_content = header + response

        output_path.write_text(full_content, encoding="utf-8")

        Console.print(f"\nNANOPROJECT.md created at: {output_path}", style="success")
        Console.print("Project summary generated by LLM.", style="success")

        # 将项目信息导入长期记忆（如果启用了 hybrid 模式）
        _save_project_to_long_term_memory(agent, info, response)

    except Exception as e:
        Console.print(f"Failed to scan project: {e}", style="error")


def _save_project_to_long_term_memory(agent, info: dict, summary: str) -> None:
    """将项目信息保存到长期记忆

    Args:
        agent: Agent 实例
        info: 项目扫描信息
        summary: LLM 生成的摘要
    """
    # 检查是否启用了长期记忆
    if not hasattr(agent.memory, 'long_term_memory'):
        return

    try:
        from ..memory import LongTermMemory

        ltm = agent.memory.long_term_memory

        # 保存项目基本信息
        project_info = f"""项目: {info['project_name']}
技术栈: {', '.join(info['tech_stack']) or 'Unknown'}
文件数: {info['structure']['total_files']}
目录数: {info['structure']['total_dirs']}
入口: {', '.join(info['code_summary']['entry_points']) or 'Unknown'}
"""

        ltm.add(
            content=project_info,
            category="project_info",
            metadata={"source": "/init", "project_name": info['project_name']}
        )

        # 保存项目摘要（截取关键部分）
        summary_preview = summary[:500] if len(summary) > 500 else summary
        ltm.add(
            content=f"项目摘要:\n{summary_preview}",
            category="project_summary",
            metadata={"source": "/init", "project_name": info['project_name']}
        )

        Console.print("Project info saved to long-term memory.", style="success")

    except Exception as e:
        Console.print(f"Warning: Could not save to long-term memory: {e}", style="warning")


if __name__ == "__main__":
    main()