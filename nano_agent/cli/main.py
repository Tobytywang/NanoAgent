"""
CLI entry point for NanoAgent.
"""

import argparse
import signal
import sys
import re
from datetime import datetime
from pathlib import Path

from ..llm import create_llm_from_config
from ..memory import ShortTermMemory, PersistentMemory, HybridMemory, FileStorage, SQLiteStorage, LongTermMemory
from ..tools import ToolRegistry
from ..tools.builtin import register_builtin_tools
from ..agent import ReActAgent, AgentOrchestrator, AgentEvent
from ..agent.token_utils import estimate_text_tokens
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


def create_agent(config_path: str | None = None) -> AgentOrchestrator:
    """
    Create and configure an agent orchestrator.

    Args:
        config_path: Path to configuration file

    Returns:
        Configured AgentOrchestrator instance
    """
    from ..core.builder import AgentBuilder

    # Find and load configuration with priority
    config_file, config_source = _find_config_file(config_path)

    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()  # Returns default config

    # Initialize logging based on config
    from ..monitoring.logger import configure_logging
    configure_logging(
        level=config.logging.level,
        console=config.logging.console,
        file_path=config.logging.file
    )

    # Auto-update .gitignore
    update_gitignore()

    # Use AgentBuilder for clean assembly
    builder = AgentBuilder(config)

    # Create LLM
    llm = create_llm_from_config(config.llm)
    builder.with_llm_instance(llm)

    # Create memory and set LLM for auto-extraction
    memory = create_memory(config)
    if config.memory.type == "hybrid" and hasattr(memory, 'set_llm'):
        memory.set_llm(llm)
    builder.with_memory_instance(memory)

    # Create tool registry
    tool_registry = ToolRegistry()
    builder.with_tool_registry(tool_registry)

    # Build agent to get tracker for tool registration
    orchestrator = builder.build()
    agent = orchestrator.agent

    # Register built-in tools with tracker
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

    # Update agent's skill prompt
    skill_prompt = skill_registry.get_combined_system_prompt()
    agent.skill_prompt = skill_prompt
    agent._setup_system_prompt()

    # Attach skill registry and loader for hot-reload support
    agent.skill_registry = skill_registry
    agent.skill_loader = skill_loader

    # Store config source for display
    agent._config_source = config_source
    orchestrator._config_source = config_source

    return orchestrator


def _load_project_context(config=None) -> str:
    """
    Load project context from NANOPROJECT.md and .nano_agent/.

    Args:
        config: Configuration object (optional, for project_file_mode)

    Returns:
        Context string to add to system prompt
    """
    context_parts = []
    project_root = Path.cwd()

    # Get project file mode from config
    project_file_mode = "condensed"  # default
    if config and hasattr(config, 'project_file'):
        project_file_mode = config.project_file.mode

    # 1. Load NANOPROJECT.md (required if exists)
    nanoproject_path = project_root / "NANOPROJECT.md"
    if nanoproject_path.exists():
        try:
            content = nanoproject_path.read_text(encoding="utf-8")

            # Apply mode-specific processing
            if project_file_mode == "full":
                # Send complete file (with truncation for safety)
                if len(content) > 5000:
                    content = content[:5000] + "\n\n... (truncated)"
            elif project_file_mode == "condensed":
                # Send condensed version (extract key sections)
                content = _condense_project_file(content)
            elif project_file_mode == "reference":
                # Only send file name reference
                content = f"See NANOPROJECT.md for project context (file exists, {len(content)} chars)"

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


def _condense_project_file(content: str) -> str:
    """
    Condense NANOPROJECT.md content to key sections.

    Args:
        content: Full file content

    Returns:
        Condensed content with key sections only
    """
    import re

    # Extract key sections (## headers and their first paragraph)
    sections = []
    lines = content.split('\n')

    current_section = None
    section_content = []

    for line in lines:
        if line.startswith('## '):
            # Save previous section
            if current_section and section_content:
                # Keep first 3 lines of section content
                condensed = '\n'.join(section_content[:3])
                if len(condensed) > 200:
                    condensed = condensed[:200] + "..."
                sections.append(f"{current_section}\n{condensed}")

            current_section = line
            section_content = []
        elif current_section:
            section_content.append(line)

    # Don't forget last section
    if current_section and section_content:
        condensed = '\n'.join(section_content[:3])
        if len(condensed) > 200:
            condensed = condensed[:200] + "..."
        sections.append(f"{current_section}\n{condensed}")

    # Limit total length
    result = '\n\n'.join(sections[:5])  # Max 5 sections
    if len(result) > 1500:
        result = result[:1500] + "\n\n... (condensed)"

    return result


def run_interactive(
    orchestrator: AgentOrchestrator,
    config,
    report_enabled: bool = False,
    report_format: str = "json",
    report_output: str | None = None
) -> None:
    """
    Run interactive chat loop.

    Args:
        orchestrator: The agent orchestrator to interact with
        config: The configuration object
        report_enabled: Whether to export report on exit
        report_format: Report format (json, markdown, summary)
        report_output: Report output path
    """
    import os

    # Get the underlying agent for compatibility
    agent = orchestrator.agent

    # Set up confirmation handler
    def _setup_confirmation_handler():
        """Set up event handler for tool confirmation."""
        def handle_confirmation(event, data):
            """Handle confirmation request from agent."""
            tool_name = data.get("tool", "unknown")
            risk_level = data.get("risk_level", "moderate")
            arguments = data.get("arguments", {})

            # Risk level icons
            risk_icons = {
                "safe": "🟢",
                "moderate": "🟡",
                "dangerous": "🔴"
            }
            icon = risk_icons.get(risk_level, "❓")

            print(f"\n{icon} 确认执行工具: {tool_name}")
            print(f"   风险级别: {risk_level}")
            if arguments:
                args_str = str(arguments)[:100]
                print(f"   参数: {args_str}{'...' if len(str(arguments)) > 100 else ''}")

            while True:
                response = input("   确认执行? [y/N/a(总是)/s(保存)]: ").strip().lower()

                if response == 'y':
                    agent.confirm_tool(True)
                    break
                elif response == 'a':
                    # Add to memory whitelist (session only)
                    agent.add_tool_to_whitelist(tool_name)
                    agent.confirm_tool(True)
                    print(f"   已添加到本次会话白名单")
                    break
                elif response == 's':
                    # Persist whitelist to config file
                    agent.add_tool_to_whitelist(tool_name)
                    _save_whitelist_to_config(tool_name, config)
                    agent.confirm_tool(True)
                    print(f"   已保存到配置文件白名单")
                    break
                elif response in ('n', ''):
                    agent.confirm_tool(False)
                    print("   已取消")
                    break
                else:
                    print("   无效输入，请输入 y/N/a/s")

        agent.events.on(AgentEvent.CONFIRMATION_REQUIRED, handle_confirmation)

    def _setup_git_handler(agent, git_manager, config):
        """Set up Git event handlers for automatic commits."""
        if config.git.commit_mode == "step":
            # Commit after each tool execution
            def handle_tool_result(event, data):
                if config.git.auto_commit:
                    tool_name = data.get("tool", "unknown")
                    git_manager.auto_commit(
                        f"Tool: {tool_name}",
                        step_info={"tool": tool_name}
                    )
            agent.events.on(AgentEvent.TOOL_RESULT, handle_tool_result)

        elif config.git.commit_mode == "round":
            # Collect changes and commit at RUN_END
            round_tools = []

            def handle_tool_result(event, data):
                tool_name = data.get("tool", "unknown")
                round_tools.append(tool_name)

            def handle_run_end(event, data):
                if round_tools and config.git.auto_commit:
                    tools = ", ".join(set(round_tools))
                    git_manager.auto_commit(f"Round: {tools}")
                    round_tools.clear()

            agent.events.on(AgentEvent.TOOL_RESULT, handle_tool_result)
            agent.events.on(AgentEvent.RUN_END, handle_run_end)

    _setup_confirmation_handler()

    # Set up name update handler (CLI-specific state management)
    # This replaces the _pending_name_updates and _prev_name_values from ReActAgent
    name_update_state = {
        "pending_updates": [],  # list of (name_type, name_value)
        "prev_values": {}       # dict of name_type -> previous value
    }

    def _setup_name_update_handler():
        """Set up event handler for name updates from memorize tool."""
        def handle_tool_result(event, data):
            """Handle tool result to detect name updates."""
            tool_name = data.get("tool", "unknown")
            result = data.get("result")

            # Detect name update from memorize tool
            if tool_name == "memorize" and result and result.success and result.metadata:
                name_type = result.metadata.get("name_type")
                name_value = result.metadata.get("name_value")
                if name_type and name_value:
                    name_update_state["pending_updates"].append((name_type, name_value))

        agent.events.on(AgentEvent.TOOL_RESULT, handle_tool_result)

    _setup_name_update_handler()

    # Set up Git handler
    git_manager = None
    if config.git.enabled:
        from ..agent.git_manager import GitManager
        git_manager = GitManager()
        if git_manager.is_enabled():
            _setup_git_handler(agent, git_manager, config)
            Console.print("Git integration enabled", style="info")

    # Load project context at startup and add to system prompt
    project_context = _load_project_context(config)

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
    if hasattr(orchestrator, '_config_source'):
        Console.print(f"Config: {orchestrator._config_source}", style="info")

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

    # Check long-term memory for stored names (fallback if config not updated)
    stored_user, stored_agent = _check_names_in_memory(agent.memory)
    if stored_user and stored_user != user_display:
        user_display = stored_user
        config.agent.user_name = stored_user
    if stored_agent and stored_agent != agent_display:
        agent_display = stored_agent
        config.agent.agent_name = stored_agent

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

            if user_input.lower() == "/undo":
                # Prefer Git undo if available
                if git_manager and git_manager.is_enabled():
                    history = git_manager.get_history(limit=5)
                    if history:
                        print("\n可回退的操作：")
                        for i, commit in enumerate(history):
                            time_str = commit.time.strftime("%m-%d %H:%M")
                            print(f"  {i+1}. {commit.hash} [{time_str}] {commit.message}")

                        choice = input("\n选择要回退的步骤 (1-5)，或按回车使用普通撤销: ").strip()
                        if choice.isdigit() and 1 <= int(choice) <= 5:
                            steps = int(choice)
                            if git_manager.undo(steps):
                                Console.print(f"已回退 {steps} 步", style="success")
                            else:
                                Console.print("回退失败", style="error")
                            continue

                # Fallback to original undo
                restored = _handle_undo(agent, config, name_update_state)
                # Update local display variables
                if "user_name" in restored:
                    user_display = restored["user_name"]
                if "agent_name" in restored:
                    agent_display = restored["agent_name"]
                continue

            if user_input.lower() == "/history":
                if git_manager and git_manager.is_enabled():
                    history = git_manager.get_history(limit=10)
                    if history:
                        print("\n操作历史：")
                        for commit in history:
                            time_str = commit.time.strftime("%m-%d %H:%M")
                            print(f"  {commit.hash} [{time_str}] {commit.message}")
                    else:
                        Console.print("暂无操作历史", style="info")
                else:
                    Console.print("Git 未启用或不在 Git 仓库中", style="warning")
                continue

            if user_input.lower() == "/tools":
                tools = agent.tool_registry.list_tools()
                Console.print(f"Available tools: {', '.join(tools)}", style="info")
                continue

            # Plan commands
            if user_input.lower() == "/plans":
                from .plan_mode import list_plans
                print(list_plans())
                continue

            if user_input.lower().startswith("/plan "):
                from .plan_mode import run_plan_mode_interactive
                task = user_input[6:].strip()
                if task:
                    result = run_plan_mode_interactive(agent.llm, config, task)
                    print(result)
                else:
                    Console.print("用法: /plan <任务描述>", style="info")
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

            # /setname command - set user/agent display names
            if user_input.lower().startswith("/setname"):
                args = user_input[8:].strip().split()
                if len(args) == 0:
                    # Show current names
                    Console.print(f"当前设置: 用户名={user_display}, Agent名={agent_display}", style="info")
                elif len(args) == 1:
                    # Set user name only
                    user_display = args[0]
                    config.agent.user_name = args[0]
                    # Store in long-term memory
                    if hasattr(agent.memory, 'memorize'):
                        agent.memory.memorize(
                            content=f"用户的名字是{args[0]}",
                            category="preference",
                            metadata={"type": "user_name", "value": args[0]}
                        )
                    Console.print(f"用户名已更新: {args[0]}", style="success")
                elif len(args) >= 2:
                    if args[0].lower() in ["user", "agent"]:
                        # Explicit type: /setname user 天宇 or /setname agent Nano
                        if args[0].lower() == "user":
                            user_display = args[1]
                            config.agent.user_name = args[1]
                            if hasattr(agent.memory, 'memorize'):
                                agent.memory.memorize(
                                    content=f"用户的名字是{args[1]}",
                                    category="preference",
                                    metadata={"type": "user_name", "value": args[1]}
                                )
                            Console.print(f"用户名已更新: {args[1]}", style="success")
                        else:
                            agent_display = args[1]
                            config.agent.agent_name = args[1]
                            if hasattr(agent.memory, 'memorize'):
                                agent.memory.memorize(
                                    content=f"Agent的名字是{args[1]}",
                                    category="preference",
                                    metadata={"type": "agent_name", "value": args[1]}
                                )
                            Console.print(f"Agent名已更新: {args[1]}", style="success")
                    else:
                        # Set both: /setname 天宇 Nano
                        user_display, agent_display = args[0], args[1]
                        config.agent.user_name = args[0]
                        config.agent.agent_name = args[1]
                        if hasattr(agent.memory, 'memorize'):
                            agent.memory.memorize(
                                content=f"用户的名字是{args[0]}",
                                category="preference",
                                metadata={"type": "user_name", "value": args[0]}
                            )
                            agent.memory.memorize(
                                content=f"Agent的名字是{args[1]}",
                                category="preference",
                                metadata={"type": "agent_name", "value": args[1]}
                            )
                        Console.print(f"名字已更新: 用户={args[0]}, Agent={args[1]}", style="success")

                # Save config
                config_file, _ = _find_config_file()
                if config_file:
                    ConfigLoader.save(config, config_file)
                continue

            # 重置 Ctrl+C 计数
            GracefulExitManager.ctrl_c_count = 0

            # Run agent through orchestrator
            print(f"\n[{agent_display}]:")
            result = orchestrator.run(user_input)
            # Sanitize response for printing
            response = result.response
            try:
                response = response.encode('utf-8', errors='replace').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            print(f"> {response}")

            # Check for pending name updates from memorize tool (may be multiple)
            if name_update_state["pending_updates"]:
                # Clear previous name values at the start of each round
                name_update_state["prev_values"] = {}

                for name_type, name_value in name_update_state["pending_updates"]:
                    # Sanitize name_value to remove invalid Unicode characters
                    try:
                        name_value = name_value.encode('utf-8', errors='replace').decode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        name_value = "User" if name_type == "user_name" else "Agent"

                    # Save previous value for undo (only save the original value, not overwrite)
                    if name_type not in name_update_state["prev_values"]:
                        if name_type == "user_name":
                            name_update_state["prev_values"][name_type] = config.agent.user_name
                        elif name_type == "agent_name":
                            name_update_state["prev_values"][name_type] = config.agent.agent_name

                    if name_type == "user_name":
                        user_display = name_value
                        config.agent.user_name = name_value
                    elif name_type == "agent_name":
                        agent_display = name_value
                        config.agent.agent_name = name_value
                    Console.print(f"名字已更新: {name_type.replace('_', ' ')} = {name_value}", style="success")

                # Save config once after all updates
                config_file, _ = _find_config_file()
                if config_file:
                    ConfigLoader.save(config, config_file)
                name_update_state["pending_updates"] = []

            # Show monitoring stats after each run
            _show_run_stats(agent, config)

            # Show undo hint if there are undoable operations
            if hasattr(agent, 'has_undoable_operations') and agent.has_undoable_operations():
                Console.print("💡 输入 /undo 可撤销本轮操作", style="info")

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
  nano-agent                          Resume most recent session (default)
  nano-agent -n                       Start a new session
  nano-agent -c ~/.nano_agent/config.yaml    Use global config
  nano-agent --report                 Export report after session
  nano-agent -l                       List saved sessions
  nano-agent -r session_xxx           Resume a specific session
  nano-agent -s session_xxx           Show session details
  nano-agent -d session_xxx           Delete a session
  nano-agent --clean-sessions         Auto-clean low-value sessions
  nano-agent --clean-threshold 5      Set clean threshold to 5

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
        "-s", "--show-session",
        type=str,
        metavar="ID",
        default=None,
        help="[s]how a specific session"
    )
    parser.add_argument(
        "-r", "--resume-session",
        type=str,
        metavar="ID",
        default=None,
        help="[r]esume an existing session"
    )
    parser.add_argument(
        "-n", "--new-session",
        action="store_true",
        help="Start a [n]ew session (default: resume most recent)"
    )
    parser.add_argument(
        "-d", "--delete-session",
        type=str,
        metavar="ID",
        default=None,
        help="[d]elete a specific session by ID"
    )
    parser.add_argument(
        "--clean-sessions",
        action="store_true",
        help="Auto-clean low-value sessions (using config threshold)"
    )
    parser.add_argument(
        "--clean-threshold",
        type=int,
        metavar="N",
        default=None,
        help="Set clean threshold in config (requires value)"
    )
    parser.add_argument(
        "--migrate-sessions",
        action="store_true",
        help="Migrate sessions from file storage to SQLite"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run for migration (show what would be migrated)"
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

    # Handle --show-session
    if args.show_session:
        _show_session(args.show_session, args.config)
        return

    # Handle --delete-session
    if args.delete_session:
        _delete_session(args.delete_session, args.config)
        return

    # Handle --clean-threshold (set config)
    if args.clean_threshold is not None:
        _set_clean_threshold(args.config, args.clean_threshold)
        return

    # Handle --clean-sessions
    if args.clean_sessions:
        config_file, _ = _find_config_file(args.config)
        if config_file:
            config = ConfigLoader.load(config_file)
        else:
            config = ConfigLoader.load()
        _cleanup_sessions(args.config, config.memory.clean_threshold)
        return

    # Handle --migrate-sessions
    if args.migrate_sessions:
        _migrate_sessions(args.config, dry_run=args.dry_run)
        return

    # Default behavior: resume most recent session (unless --new-session specified)
    if not args.new_session and not args.resume_session:
        config_file, _ = _find_config_file(args.config)
        if config_file:
            config = ConfigLoader.load(config_file)
        else:
            config = ConfigLoader.load()
        storage = _get_storage(config)
        recent_session = storage.get_most_recent_session()
        if recent_session:
            args.resume_session = recent_session
            Console.print(f"Resuming most recent session: {recent_session}", style="info")
        else:
            Console.print("No existing sessions found. Starting new session.", style="info")

    # Create agent
    agent = create_agent(args.config)

    # Handle --new-session: explicitly create a new empty session
    if args.new_session:
        if hasattr(agent.memory, 'new_session'):
            new_sid = agent.memory.new_session()
            Console.print(f"Started new session: {new_sid}", style="success")
        # else: short_term memory doesn't need explicit new_session

    # Handle --resume-session
    if args.resume_session:
        if hasattr(agent.memory, 'load_session'):
            success = agent.memory.load_session(args.resume_session)
            if not success:
                Console.print(f"Session '{args.resume_session}' not found", style="error")
                sys.exit(1)
            Console.print(f"Resumed session: {args.resume_session}", style="success")
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


def _check_names_in_memory(memory) -> tuple[str | None, str | None]:
    """
    Check long-term memory for stored user/agent names.

    Args:
        memory: Memory instance to check

    Returns:
        Tuple of (user_name, agent_name) or (None, None) if not found
    """
    import re

    if not hasattr(memory, 'recall'):
        return None, None

    try:
        entries = memory.recall("名字 用户名 Agent名", limit=10)
        user_name = None
        agent_name = None

        # Patterns for extracting names from content (stop at punctuation)
        # NOTE: memorize content is generated by the Agent (LLM), so:
        # - "我的名字" (my name) refers to the Agent's name
        # - "用户的名字" (user's name) refers to the user's name
        user_patterns = [
            r"用户名[是为]\s*([^，。！,.]+)",
            r"用户的名字[是为]\s*([^，。！,.]+)",
            r"用户叫\s*([^，。！,.]+)",
        ]
        agent_patterns = [
            r"Agent名[是为]\s*([^，。！,.]+)",
            r"Agent的名字[是为]\s*([^，。！,.]+)",
            r"你的名字[是为叫]\s*([^，。！,.]+)",
            r"你叫\s*([^，。！,.]+)",
            r"我的名字[是为]\s*([^，。！,.]+)",
            r"我叫\s*([^，。！,.]+)",
        ]

        for entry in entries:
            # First check metadata (new format)
            if entry.metadata:
                if entry.metadata.get("type") == "user_name":
                    user_name = entry.metadata.get("value")
                elif entry.metadata.get("type") == "agent_name":
                    agent_name = entry.metadata.get("value")

            # Fallback: check content patterns (old format compatibility)
            if not user_name:
                for pattern in user_patterns:
                    match = re.search(pattern, entry.content)
                    if match:
                        user_name = match.group(1).strip()
                        break

            if not agent_name:
                for pattern in agent_patterns:
                    match = re.search(pattern, entry.content)
                    if match:
                        agent_name = match.group(1).strip()
                        break

        return user_name, agent_name
    except Exception:
        return None, None


def _migrate_sessions(config_path: str | None = None, dry_run: bool = False) -> None:
    """Migrate sessions from file storage to SQLite."""
    from ..memory.migration import migrate_file_to_sqlite, list_all_sessions

    # Find config file
    config_file, _ = _find_config_file(config_path)
    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()

    # Determine storage paths
    file_dir = ".nano_agent/memory"
    db_path = config.memory.storage_path
    if not db_path.endswith(".db"):
        db_path = db_path + ".db"

    Console.print_header("Session Migration")

    # First show current status
    all_sessions = list_all_sessions(file_dir=file_dir, db_path=db_path)

    print(f"\nFile storage ({file_dir}): {len(all_sessions['file_storage']['sessions'])} sessions")
    print(f"SQLite storage ({db_path}): {len(all_sessions['sqlite_storage']['sessions'])} sessions")
    print(f"Total unique sessions: {all_sessions['total_unique_sessions']}")

    if dry_run:
        print("\n[DRY RUN] Would migrate the following sessions:")
        for session_id in all_sessions['file_storage']['sessions']:
            if session_id not in all_sessions['sqlite_storage']['sessions']:
                info = all_sessions['file_storage']['info'].get(session_id, {})
                print(f"  - {session_id} ({info.get('message_count', 0)} messages)")
        return

    # Perform migration
    print("\nMigrating sessions...")
    report = migrate_file_to_sqlite(file_dir=file_dir, db_path=db_path, dry_run=False)

    print(f"\nMigration Report:")
    print(f"  Total file sessions: {report['total_file_sessions']}")
    print(f"  Already in SQLite: {len(report['already_in_sqlite'])}")
    print(f"  Successfully migrated: {len(report['migrated'])}")

    if report['errors']:
        print(f"  Errors: {len(report['errors'])}")
        for error in report['errors']:
            print(f"    - {error['session_id']}: {error['error']}")

    if report['migrated']:
        Console.print(f"\nSuccessfully migrated {len(report['migrated'])} sessions!", style="success")


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


def _delete_session(session_id: str, config_path: str | None = None) -> None:
    """Delete a specific session and its summary.

    Args:
        session_id: The session ID to delete
        config_path: Optional config file path
    """
    config_file, _ = _find_config_file(config_path)

    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()

    storage = _get_storage(config)

    if not storage.session_exists(session_id):
        Console.print(f"Session '{session_id}' not found", style="error")
        sys.exit(1)

    # Delete session and summary
    storage.delete_session(session_id)
    storage.delete_summary(session_id)

    Console.print(f"Session '{session_id}' deleted successfully", style="success")


def _cleanup_sessions(config_path: str | None = None, threshold: int = 3) -> None:
    """Remove low-value sessions with fewer than threshold messages.

    Args:
        config_path: Optional config file path
        threshold: Minimum message count threshold
    """
    config_file, _ = _find_config_file(config_path)

    if config_file:
        config = ConfigLoader.load(config_file)
    else:
        config = ConfigLoader.load()

    storage = _get_storage(config)
    low_value_sessions = storage.get_sessions_below_threshold(threshold)

    if not low_value_sessions:
        Console.print(f"No sessions with fewer than {threshold} messages found.", style="info")
        return

    Console.print(f"Found {len(low_value_sessions)} session(s) with fewer than {threshold} messages:", style="info")
    for session_id in low_value_sessions:
        info = storage.get_session_info(session_id)
        print(f"  {session_id} ({info['message_count']} messages)")

    # Delete sessions
    deleted_count = 0
    for session_id in low_value_sessions:
        storage.delete_session(session_id)
        storage.delete_summary(session_id)
        deleted_count += 1

    Console.print(f"Cleaned up {deleted_count} low-value session(s)", style="success")


def _set_clean_threshold(config_path: str | None, threshold: int) -> None:
    """Set clean threshold in config file.

    Args:
        config_path: Optional config file path
        threshold: New threshold value
    """
    import yaml

    config_file, _ = _find_config_file(config_path)

    if not config_file:
        # Create default config file
        config_file = Path.cwd() / ".nano_agent" / "config.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config = ConfigLoader.load()
    else:
        config = ConfigLoader.load(config_file)

    # Update threshold
    config.memory.clean_threshold = threshold

    # Save config
    ConfigLoader.save(config, config_file)
    Console.print(f"Clean threshold set to {threshold}", style="success")
    Console.print(f"Config saved to: {config_file}", style="info")


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


def _save_whitelist_to_config(tool_name: str, config) -> None:
    """
    Save tool to confirmation whitelist in config file.

    Args:
        tool_name: Tool name to add to whitelist
        config: Config object
    """
    from ..config.loader import ConfigLoader

    # Find config file
    config_file, _ = _find_config_file()

    if not config_file:
        # Create project config file if it doesn't exist
        config_file = Path(".nano_agent/config.yaml")

    # Add to whitelist
    if tool_name not in config.confirmation.whitelist:
        config.confirmation.whitelist.append(tool_name)

    # Save config
    ConfigLoader.save(config, config_file)


def _handle_undo(agent, config=None, name_update_state: dict | None = None) -> dict:
    """Handle /undo command to revert all operations in current round.

    Args:
        agent: Agent instance
        config: Config object (optional, for reverting name changes)
        name_update_state: State dict for name updates (optional)

    Returns:
        Dict with restored values: {"user_name": ..., "agent_name": ...}
    """
    restored = {}

    if not hasattr(agent, 'has_undoable_operations') or not agent.has_undoable_operations():
        Console.print("没有可撤销的操作", style="info")
        return restored

    # Build context for undo
    context = {
        "memory": agent.memory,
        "config": config,
        "tool_registry": agent.tool_registry
    }

    # Perform undo
    undone = agent.undo_current_round(context)

    if undone:
        Console.print(f"已撤销: {', '.join(undone)}", style="success")

        # Handle name updates - restore previous values
        prev_values = name_update_state.get("prev_values", {}) if name_update_state else {}
        if config and prev_values:
            for name_type, prev_value in prev_values.items():
                if name_type == "user_name":
                    config.agent.user_name = prev_value
                    restored["user_name"] = prev_value
                    Console.print(f"已恢复用户名: {prev_value}", style="info")
                elif name_type == "agent_name":
                    config.agent.agent_name = prev_value
                    restored["agent_name"] = prev_value
                    Console.print(f"已恢复Agent名: {prev_value}", style="info")
            # Save config
            config_file, _ = _find_config_file()
            if config_file:
                ConfigLoader.save(config, config_file)
            if name_update_state:
                name_update_state["prev_values"] = {}
    else:
        Console.print("撤销失败", style="error")

    return restored


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

    # 获取详细 usage 数据
    detailed_usage = agent.tracker.get_detailed_usage()

    if not detailed_usage:
        # 没有详细数据时，显示简化版本
        current_summary = agent.tracker.get_summary()
        session_summary = agent.tracker.get_session_summary()
        if current_summary and session_summary:
            current_duration = current_summary.get('duration_ms', 0) / 1000
            current_tokens = current_summary.get('total_tokens', 0)
            session_tokens = session_summary.get('total_tokens', 0)
            print(f"\n📊 本轮: {current_tokens} tokens | {current_duration:.2f}s")
            print(f"📊 总计: {session_tokens} tokens")
        return

    # 按11列格式显示：【ID】【轮次】【迭代】【工具】【系统】【技能】【消息】【输出】【总和】【简要描述】
    print("\n📊 Token Usage:")
    print("─" * 100)
    print(f"  {'ID':<4} {'轮次':<4} {'迭代':<4} {'工具':<6} {'系统':<6} {'技能':<6} {'消息':<6} {'输出':<6} {'总和':<6} {'简要描述'}")
    print("─" * 100)

    for entry in detailed_usage:
        print(f"  {entry['id']:<4} {entry['run_number']:<4} {entry['iteration_number']:<4} "
              f"{entry['tool_tokens']:<6} {entry['system_tokens']:<6} {entry['skill_tokens']:<6} "
              f"{entry['message_tokens']:<6} {entry['output_tokens']:<6} {entry['total_tokens']:<6} "
              f"{entry['description']}")

    print("─" * 100)

    # 会话总计
    session_summary = agent.tracker.get_session_summary()
    if session_summary:
        total_tokens = session_summary.get('total_tokens', 0)
        total_llm_calls = session_summary.get('total_llm_calls', 0)
        print(f"\n📊 总计: {total_tokens} tokens | LLM调用: {total_llm_calls} 次")

        # 上下文使用率
        if config and hasattr(config, 'llm'):
            context_length = config.llm.get_context_length()
            if context_length > 0:
                usage_percent = (total_tokens / context_length) * 100
                context_info = f"上下文: {usage_percent:.1f}% ({total_tokens}/{context_length})"
                if usage_percent >= 80:
                    context_info = f"⚠️ 上下文: {usage_percent:.1f}% (接近上限!)"
                print(f"📊 {context_info}")


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
    print(format_line("Clean Threshold:", str(config.memory.clean_threshold)))
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

    # Output Style 配置
    print("\n## Output Style")
    print(format_line("Style:", config.output_style.style))
    print(format_line("Max Tool Output:", f"{config.output_style.tool_output_max_tokens} tokens"))

    # Prompt 配置 (v0.7.6)
    print("\n## Prompt Settings")
    print(format_line("Source:", config.prompt.source))
    print(format_line("Style:", config.prompt.style))
    print(format_line("Token Budget:", f"{config.prompt.token_budget} tokens"))
    print(format_line("Include Environment:", str(config.prompt.include_environment)))
    print(format_line("Include Git Status:", str(config.prompt.include_git_status)))
    print(format_line("Enable Caching:", str(config.prompt.enable_caching)))
    if hasattr(agent, '_prompt_builder') and agent._prompt_builder:
        stable_names = agent._prompt_builder.get_stable_module_names()
        if stable_names:
            print(format_line("Stable Modules:", ', '.join(stable_names)))
        else:
            print(format_line("Stable Modules:", 'None'))

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
        # 显示当前会话统计（完整）
        _show_stats_status(agent, config)
    elif parts[0].lower() == "context":
        # 显示当前上下文组成
        _show_context_composition(agent, config)
    elif parts[0].lower() == "breakdown":
        # 显示各轮 Token 消耗趋势
        _show_iteration_breakdown(agent)
    elif parts[0].lower() == "on":
        _enable_run_stats()
    elif parts[0].lower() == "off":
        _disable_run_stats()
    else:
        Console.print(f"Unknown subcommand: {parts[0]}", style="error")
        Console.print("Available: status, context, breakdown, on, off", style="info")


def _show_stats_status(agent, config) -> None:
    """显示当前会话统计状态"""
    print("\n" + "=" * 50)
    print("📊 会话统计")
    print("=" * 50)

    def format_line(label: str, value: str, width: int = 18) -> str:
        return f"  {label:<{width}} {value}"

    # 显示会话统计
    if hasattr(agent, 'tracker'):
        session_summary = agent.tracker.get_session_summary()
        iteration_list = agent.tracker.get_iteration_token_list()

        if session_summary:
            # 消耗概览
            print("\n## 消耗概览")
            total_tokens = session_summary.get('total_tokens', 0)
            total_llm_calls = session_summary.get('total_llm_calls', 0)

            print(format_line("总 Token:", str(total_tokens)))
            print(format_line("总 LLM 调用:", str(total_llm_calls)))

            # 当前 run 的轮次（更直观）
            current_run_iterations = len(iteration_list)
            if current_run_iterations > 0:
                print(format_line("本轮迭代:", str(current_run_iterations)))
                avg_per_iteration = total_tokens / current_run_iterations
                print(format_line("平均每轮:", f"{avg_per_iteration:.0f} tokens"))

            # 上下文状态（使用最后一轮的 prompt_tokens）
            print("\n## 上下文状态")
            last_tokens = agent.tracker.get_last_iteration_tokens()
            if last_tokens:
                current_context = last_tokens.get('prompt_tokens', 0)
                print(format_line("当前上下文:", f"{current_context} tokens"))

                if config and hasattr(config, 'llm'):
                    context_length = config.llm.get_context_length()
                    if context_length > 0:
                        usage_percent = (current_context / context_length) * 100
                        print(format_line("上下文限制:", f"{context_length} tokens"))
                        print(format_line("使用率:", f"{usage_percent:.1f}%"))
            else:
                print("  当前上下文: 无数据")

            # 工具调用
            print("\n## 工具调用")
            print(format_line("总调用:", str(session_summary.get('total_tool_calls', 0))))
            print(format_line("成功:", str(session_summary.get('successful_tool_calls', 0))))
            print(format_line("失败:", str(session_summary.get('failed_tool_calls', 0))))
        else:
            print("\n## 会话统计")
            print("  无数据。请先运行查询。")

    # 命令说明
    print("\n## 命令")
    print("  /stats          - 显示完整统计")
    print("  /stats context  - 显示当前上下文组成")
    print("  /stats breakdown - 显示各轮消耗趋势")
    print("  /stats on       - 启用每次对话后自动显示")
    print("  /stats off      - 禁用自动显示")

    print("\n" + "=" * 50 + "\n")


def _show_context_composition(agent, config) -> None:
    """显示当前上下文组成（按轮次分组）"""
    if not hasattr(agent, 'memory'):
        Console.print("Memory not available", style="warning")
        return

    messages = agent.memory.get_all()
    if not messages:
        Console.print("No messages in memory", style="info")
        return

    print("\n📊 当前上下文组成 (准备发送给 LLM 的内容):")
    print("─" * 70)

    # 按轮次分组消息
    # 轮次定义: user + assistant(tool_calls) + tool(s) = 一轮
    rounds = []
    current_round = {"messages": [], "chars": 0, "tokens": 0}

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        chars = len(content) if isinstance(content, str) else 0
        tokens = estimate_text_tokens(content) if content else 0

        current_round["messages"].append({
            "role": role,
            "content": content,
            "chars": chars,
            "tokens": tokens,
        })
        current_round["chars"] += chars
        current_round["tokens"] += tokens

        # 一轮结束的判断：
        # - user 消息后遇到 assistant（无 tool_calls）或新的 user
        # - assistant(tool_calls) + 所有 tool 结果后遇到新的 user 或 assistant
        if role == "user":
            # 如果当前轮已有内容，保存并开始新轮
            if len(current_round["messages"]) > 1:
                rounds.append(current_round)
                current_round = {"messages": [], "chars": 0, "tokens": 0}

    # 保存最后一轮
    if current_round["messages"]:
        rounds.append(current_round)

    # 显示按轮次分组的统计
    print(f"\n  共 {len(rounds)} 轮对话，{len(messages)} 条消息")
    print("─" * 70)

    total_chars = 0
    total_tokens = 0

    for i, round_data in enumerate(rounds, 1):
        round_chars = round_data["chars"]
        round_tokens = round_data["tokens"]
        msg_count = len(round_data["messages"])

        total_chars += round_chars
        total_tokens += round_tokens

        # 显示该轮摘要
        roles = [m["role"] for m in round_data["messages"]]
        role_summary = " → ".join(roles)

        print(f"  轮次 {i}: {msg_count} 条消息 ({role_summary})")
        print(f"         {round_chars} chars, {round_tokens} tokens")

        # 显示该轮的消息详情
        for j, msg in enumerate(round_data["messages"], 1):
            role = msg["role"]
            chars = msg["chars"]
            tokens = msg["tokens"]
            content = msg["content"]

            # 内容预览
            preview = content[:25] + "..." if len(content) > 25 else content
            preview = preview.replace("\n", " ")

            indent = "    " if j > 1 else "    "
            print(f"{indent}{j}. {role:<10} {chars:>6} chars, {tokens:>4} tokens  {preview}")

        print()

    print("─" * 70)
    print(f"  总计: {total_chars} chars, {total_tokens} tokens")

    # 上下文使用率
    if config and hasattr(config, 'llm'):
        context_length = config.llm.get_context_length()
        if context_length > 0:
            usage_percent = (total_tokens / context_length) * 100
            print(f"\n  上下文使用率: {usage_percent:.1f}% ({total_tokens} / {context_length})")

    print()


def _show_iteration_breakdown(agent) -> None:
    """显示各轮 Token 消耗趋势"""
    if not hasattr(agent, 'tracker'):
        Console.print("Tracker not available", style="warning")
        return

    iterations = agent.tracker.get_iteration_token_list()

    if not iterations:
        Console.print("No iteration data yet. Run a query first.", style="info")
        return

    print("\n📊 各轮 Token 消耗趋势:")
    print("─" * 60)

    # 找出最大值用于趋势条
    max_total = max(i['total_tokens'] for i in iterations) if iterations else 1

    # 表头
    print(f"  {'轮次':<6} {'输入':<8} {'输出':<8} {'总计':<8} 趋势")
    print("─" * 60)

    # 各轮数据
    for iter_data in iterations:
        i = iter_data['iteration_number']
        prompt = iter_data['prompt_tokens']
        completion = iter_data['completion_tokens']
        total = iter_data['total_tokens']

        # 趋势条（每个 █ 代表 max_total 的 5%）
        bar_len = int(total / max_total * 20) if max_total > 0 else 0
        bar = "█" * bar_len + "░" * (20 - bar_len)

        print(f"  {i:<6} {prompt:<8} {completion:<8} {total:<8} {bar}")

    print("─" * 60)

    # 统计摘要
    total_all = sum(i['total_tokens'] for i in iterations)
    avg = total_all / len(iterations) if iterations else 0
    max_iter = max(iterations, key=lambda x: x['total_tokens'])
    min_iter = min(iterations, key=lambda x: x['total_tokens'])

    print(f"  平均每轮: {avg:.0f} tokens")
    print(f"  最大: {max_iter['total_tokens']} (轮次 {max_iter['iteration_number']})")
    print(f"  最小: {min_iter['total_tokens']} (轮次 {min_iter['iteration_number']})")
    print()


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
    print("  /undo             撤销操作（支持 Git 回退）")
    print("  /history          查看操作历史（需要 Git）")
    print("  /?, help          显示帮助")

    print("\n## 查看信息")
    print("  /config           查看配置")
    print("  /memory           查看记忆状态")
    print("  /stats            查看统计")
    print("  /tools            查看工具列表")
    print("  /skills           查看技能列表")
    print("  /sessions         查看会话列表")
    print("  /plans            查看已保存的计划")

    print("\n## 项目管理")
    print("  /init             初始化项目")
    print("  /config init      生成配置文件（合并）")
    print("  /config init -f   强制覆盖配置文件")
    print("  /memory on        启用长期记忆")
    print("  /memory off       禁用长期记忆")
    print("  /stats on         启用统计自动显示")
    print("  /stats off        禁用统计自动显示")
    print("  /stats context    显示当前上下文组成")
    print("  /stats breakdown  显示各轮消耗趋势")

    print("\n## 规划模式")
    print("  /plan <任务>      进入规划模式，制定分阶段计划")
    print("  /plans            列出所有已保存的计划")

    print("\n## 个性化设置")
    print("  /setname                    查看当前名字")
    print("  /setname <用户名>           设置用户名")
    print("  /setname user <用户名>      设置用户名")
    print("  /setname agent <Agent名>    设置Agent名")
    print("  /setname <用户名> <Agent名> 同时设置两个")

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
            "clean_threshold": config.memory.clean_threshold,
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
        "output_style": {
            "style": config.output_style.style,
            "tool_output_max_tokens": config.output_style.tool_output_max_tokens,
        },
        "prompt": {
            "source": config.prompt.source,
            "style": config.prompt.style,
            "token_budget": config.prompt.token_budget,
            "include_environment": config.prompt.include_environment,
            "include_git_status": config.prompt.include_git_status,
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
    """扫描项目并使用 LLM 生成或更新 NANOPROJECT.md

    如果 NANOPROJECT.md 已存在，会智能合并更新：
    - 保留用户手动添加的内容（在特定标记区域外）
    - 更新自动生成的部分

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

        # 检查是否已存在 NANOPROJECT.md
        output_path = Path.cwd() / "NANOPROJECT.md"
        existing_content = None
        user_notes = ""

        if output_path.exists():
            existing_content = output_path.read_text(encoding="utf-8")
            # 提取用户手动添加的内容（在 <!-- user-notes --> 标记区域）
            user_notes_match = re.search(r'<!-- user-notes -->(.*?)<!-- /user-notes -->', existing_content, re.DOTALL)
            if user_notes_match:
                user_notes = user_notes_match.group(1).strip()
            Console.print("Updating existing NANOPROJECT.md...", style="info")
        else:
            Console.print("Creating NANOPROJECT.md...", style="info")

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

        # 添加头部信息
        header = f"""# {info['project_name']} - 项目摘要

> 由 NanoAgent 生成于 {info['scan_time'][:19]}
> 基于 LLM 分析
> 使用 /init 命令可更新此文件

---

"""

        # 添加用户笔记区域（如果存在用户笔记则保留）
        user_notes_section = ""
        if user_notes:
            user_notes_section = f"""
---

## 用户笔记

<!-- user-notes -->
{user_notes}
<!-- /user-notes -->

"""
        else:
            # 提供空的用户笔记区域供用户填写
            user_notes_section = """
---

## 用户笔记

<!-- user-notes -->
在此处添加你的项目笔记，/init 更新时会保留此区域内容。
<!-- /user-notes -->

"""

        full_content = header + response + user_notes_section

        output_path.write_text(full_content, encoding="utf-8")

        if existing_content:
            Console.print(f"\nNANOPROJECT.md updated at: {output_path}", style="success")
            if user_notes:
                Console.print("User notes preserved.", style="info")
        else:
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