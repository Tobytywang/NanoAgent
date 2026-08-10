"""
CLI entry point for NanoAgent.
"""

import argparse

from nano_agent import __version__
import asyncio
import os
import signal
import sys
import re
from datetime import datetime
from pathlib import Path

from ..llm import create_llm_from_config
from ..memory import (
    ShortTermMemory,
    PersistentMemory,
    HybridMemory,
    FileStorage,
    SQLiteStorage,
    LongTermMemory,
)
from ..tools import ToolRegistry
from ..tools.builtin import register_builtin_tools
from ..agent import (
    ReActAgent,
    AgentOrchestrator,
    AgentEvent,
    TerminationReason,
    ExecutionMode,
)
from ..agent.types import ExecutionEventType
from ..agent.token_utils import estimate_text_tokens
from ..output import Verbosity
from ..config.loader import ConfigLoader
from ..skills import SkillRegistry, SkillLoader
from ..monitoring.reporter import ReportGenerator
from ..monitoring.tracker import MetricsTracker
from .console import Console
from .constants import Commands, CommandPrefix
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
)
from .scanner import ProjectScanner

# Prompt_toolkit session for bracketed paste + history support.
# Falls back to built-in input() if prompt_toolkit is unavailable or fd is
# not a terminal (e.g. tests, piped input, non-interactive mode).
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    _HAS_PROMPT_TOOLKIT = False

_input_session = None


def _read_user_input(prompt_text: str) -> str:
    """Read user input with bracketed paste handling.

    Prompt_toolkit auto-detects pasted multi-line content via bracketed
    paste mode (ANSI \e[200~ / \e[201~), preserving embedded newlines
    within the returned string.  Falls back to built-in input() if
    prompt_toolkit is not installed or stdin is not a terminal.
    """
    global _input_session

    try:
        if not _HAS_PROMPT_TOOLKIT or not sys.stdin.isatty():
            return input(prompt_text).strip()

        if _input_session is None:
            history_path = Path.home() / ".nano_agent" / "history"
            history_path.parent.mkdir(parents=True, exist_ok=True)
            _input_session = PromptSession(history=FileHistory(str(history_path)))

        result = _input_session.prompt(prompt_text, multiline=False)
    except (EOFError, KeyboardInterrupt):
        return ""
    return result.strip()


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

        print("再见!")
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
            system_prompt=system_prompt,
        )

        # Create long-term memory
        long_term_memory = LongTermMemory(
            storage_path=config.memory.long_term_storage_path
        )

        # Create hybrid memory
        memory = HybridMemory(
            working_memory=working_memory,
            long_term_memory=long_term_memory,
            auto_extract=config.memory.auto_extract,
        )

    elif config.memory.type == "persistent":
        memory = PersistentMemory(
            storage=storage,
            session_id=config.memory.session_id,
            max_messages=config.memory.max_messages,
            system_prompt=system_prompt,
        )
    else:
        memory = ShortTermMemory(
            max_messages=config.memory.max_messages, system_prompt=system_prompt
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
        Console.print(f"警告: 无法更新 .gitignore: {e}", style="warning")
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
        file_path=config.logging.file,
    )

    # Auto-update .gitignore
    update_gitignore()

    # Use AgentBuilder for clean assembly
    builder = AgentBuilder(config)

    # Create LLM
    llm = create_llm_from_config(config.llm)
    config.llm.set_llm_client(llm)
    builder.with_llm_instance(llm)

    # Create memory and set LLM for auto-extraction
    memory = create_memory(config)
    if isinstance(memory, HybridMemory):
        memory.set_llm(llm)
        memory.set_memory_gc_config(config.memory_gc)
    builder.with_memory_instance(memory)

    # Create tool registry
    tool_registry = ToolRegistry()
    builder.with_tool_registry(tool_registry)

    # Build agent to get tracker for tool registration
    orchestrator = builder.build()
    agent = orchestrator.agent

    # Register built-in tools with tracker
    register_builtin_tools(
        tool_registry,
        memory=memory,
        tracker=agent.tracker,
        context_length=config.llm.get_context_length(),
    )

    # Load plugins from configuration
    from ..tools.plugin import load_plugins_from_config

    plugins_config = {
        "directories": config.plugins.directories if hasattr(config, "plugins") else [],
        "modules": config.plugins.modules if hasattr(config, "plugins") else [],
        "files": config.plugins.files if hasattr(config, "plugins") else [],
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
    if config and hasattr(config, "project_file"):
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
                memory_text = "\n".join(
                    [f"- [{m.category}] {m.content[:200]}" for m in memories[:5]]
                )
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
    lines = content.split("\n")

    current_section = None
    section_content = []

    for line in lines:
        if line.startswith("## "):
            # Save previous section
            if current_section and section_content:
                # Keep first 3 lines of section content
                condensed = "\n".join(section_content[:3])
                if len(condensed) > 200:
                    condensed = condensed[:200] + "..."
                sections.append(f"{current_section}\n{condensed}")

            current_section = line
            section_content = []
        elif current_section:
            section_content.append(line)

    # Don't forget last section
    if current_section and section_content:
        condensed = "\n".join(section_content[:3])
        if len(condensed) > 200:
            condensed = condensed[:200] + "..."
        sections.append(f"{current_section}\n{condensed}")

    # Limit total length
    result = "\n\n".join(sections[:5])  # Max 5 sections
    if len(result) > 1500:
        result = result[:1500] + "\n\n... (condensed)"

    return result


def _handle_setname_command(
    user_input: str, agent, config, user_display: str, agent_display: str
) -> tuple[str, str]:
    """Handle /setname command. Returns updated (user_display, agent_display)."""
    args = user_input[8:].strip().split()
    if len(args) == 0:
        Console.print(
            f"当前设置: 用户名={user_display}, Agent名={agent_display}",
            style="info",
        )
    elif len(args) == 1:
        user_display = args[0]
        config.agent.user_name = args[0]
        if hasattr(agent.memory, "memorize"):
            agent.memory.memorize(
                content=f"用户的名字是{args[0]}",
                category="preference",
                metadata={"type": "user_name", "value": args[0]},
            )
        Console.print(f"用户名已更新: {args[0]}", style="success")
    elif len(args) >= 2:
        if args[0].lower() in ["user", "agent"]:
            if args[0].lower() == "user":
                user_display = args[1]
                config.agent.user_name = args[1]
                if hasattr(agent.memory, "memorize"):
                    agent.memory.memorize(
                        content=f"用户的名字是{args[1]}",
                        category="preference",
                        metadata={"type": "user_name", "value": args[1]},
                    )
                Console.print(f"用户名已更新: {args[1]}", style="success")
            else:
                agent_display = args[1]
                config.agent.agent_name = args[1]
                if hasattr(agent.memory, "memorize"):
                    agent.memory.memorize(
                        content=f"Agent的名字是{args[1]}",
                        category="preference",
                        metadata={"type": "agent_name", "value": args[1]},
                    )
                Console.print(f"Agent名已更新: {args[1]}", style="success")
        else:
            user_display, agent_display = args[0], args[1]
            config.agent.user_name = args[0]
            config.agent.agent_name = args[1]
            if hasattr(agent.memory, "memorize"):
                agent.memory.memorize(
                    content=f"用户的名字是{args[0]}",
                    category="preference",
                    metadata={"type": "user_name", "value": args[0]},
                )
                agent.memory.memorize(
                    content=f"Agent的名字是{args[1]}",
                    category="preference",
                    metadata={"type": "agent_name", "value": args[1]},
                )
            Console.print(
                f"名字已更新: 用户={args[0]}, Agent={args[1]}",
                style="success",
            )

    # Save config
    config_file, _ = _find_config_file()
    if config_file:
        ConfigLoader.save(config, config_file)
    return user_display, agent_display


def _handle_auto_command(orchestrator, agent) -> None:
    """Handle /auto command — reset circuit breaker, feedback loop, rate limiter."""
    if agent.circuit_breaker:
        agent.circuit_breaker.reset()
        Console.print("[熔断器] 已恢复 AUTO 模式", style="info")
    else:
        Console.print("[熔断器] 未启用", style="warning")
    if orchestrator.feedback_loop is not None:
        orchestrator.feedback_loop.reset_all()
    if agent.tool_rate_limiter:
        agent.tool_rate_limiter.reset()


def _handle_undo_command(
    agent, config, git_manager, name_update_state
) -> tuple[str, str]:
    """Handle /undo command. Returns updated (user_display, agent_display)."""
    user_display = config.agent.user_name
    agent_display = config.agent.agent_name

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
                return user_display, agent_display

    # Fallback to original undo
    restored = _handle_undo(agent, config, name_update_state)
    if "user_name" in restored:
        user_display = restored["user_name"]
    if "agent_name" in restored:
        agent_display = restored["agent_name"]
    return user_display, agent_display


def _handle_run_result(
    result, orchestrator, agent, config, name_update_state, user_display, agent_display
) -> tuple[str, str] | None:
    """Process run result. Returns updated (user_display, agent_display) or None to continue loop."""
    # Handle input rejection from sanitizer
    if result.termination_reason == TerminationReason.INPUT_REJECTED.value:
        print(f"⚠ 输入被拒绝: {result.response}")
        return None

    # Handle output blocking from output guard
    if result.termination_reason == TerminationReason.OUTPUT_BLOCKED.value:
        print(f"⚠ 输出被拦截: {result.response}")
        return None

    # Handle harmful content blocking
    if result.termination_reason == TerminationReason.HARMFUL_CONTENT_BLOCKED.value:
        print(f"⚠ 输出被拦截: 有害内容 ({result.response})")
        return None

    # Handle validation failure blocking
    if result.termination_reason == TerminationReason.VALIDATION_FAILED.value:
        print(f"⚠ 输出被拦截: 验证失败 ({result.response})")
        return None

    # Handle self-correction exhaustion
    if result.termination_reason == TerminationReason.SELF_CORRECTION_EXHAUSTED.value:
        print(f"⚠ 自纠正失败: 验证未通过 ({result.response})")
        return None

    # Show PII desensitization notice
    if (
        orchestrator.last_sanitizer_result is not None
        and orchestrator.last_sanitizer_result.pii_matches
    ):
        from nano_agent.agent.sanitizer import summarize_pii_matches

        summary = summarize_pii_matches(orchestrator.last_sanitizer_result.pii_matches)
        print(f"[PII] 已脱敏 ({summary})")

    # Show output guard masking notice
    if (
        orchestrator.last_output_guard_result is not None
        and orchestrator.last_output_guard_result.matches
    ):
        from nano_agent.agent.output_guard import summarize_sensitive_matches

        summary = summarize_sensitive_matches(
            orchestrator.last_output_guard_result.matches
        )
        print(f"[Guard] 输出已遮蔽 ({summary})")

    # Show harmful content filter notice
    if (
        orchestrator.last_harmful_filter_result is not None
        and orchestrator.last_harmful_filter_result.matches
    ):
        from nano_agent.agent.harmful_filter import summarize_harmful_matches

        summary = summarize_harmful_matches(
            orchestrator.last_harmful_filter_result.matches
        )
        if orchestrator.last_harmful_filter_result.warned:
            print(f"[HarmfulFilter] 内容警告 ({summary})")
        else:
            print(f"[HarmfulFilter] 内容已替换 ({summary})")

    # Show result validator notice
    if (
        orchestrator.last_validator_result is not None
        and orchestrator.last_validator_result.failed_checks
    ):
        from nano_agent.agent.result_validator import summarize_validation_checks

        summary = summarize_validation_checks(
            orchestrator.last_validator_result.failed_checks
        )
        action = (
            orchestrator.last_validator_result.actions_taken[0]
            if orchestrator.last_validator_result.actions_taken
            else ""
        )
        if "validation_blocked" in action:
            print(f"[Validator] 输出被拦截 ({summary})")
        elif "validation_warning" in action:
            print(f"[Validator] 验证警告 ({summary})")
        else:
            print(f"[Validator] 验证标注 ({summary})")

    # Show self-correction notice
    if (
        orchestrator.feedback_loop is not None
        and orchestrator.feedback_loop.correction_attempts_used > 0
    ):
        print(
            f"[Self-Correction] "
            f"{orchestrator.feedback_loop.correction_attempts_used} "
            f"attempt(s) made to correct validation failures"
        )

    # Sanitize response for printing
    response = result.response
    try:
        response = response.encode("utf-8", errors="replace").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    print(f"> {response}")

    # Check for pending name updates from memorize tool (may be multiple)
    if name_update_state["pending_updates"]:
        name_update_state["prev_values"] = {}

        for name_type, name_value in name_update_state["pending_updates"]:
            try:
                name_value = name_value.encode("utf-8", errors="replace").decode(
                    "utf-8"
                )
            except (UnicodeDecodeError, UnicodeEncodeError):
                name_value = "User" if name_type == "user_name" else "Agent"

            if name_type not in name_update_state["prev_values"]:
                if name_type == "user_name":
                    name_update_state["prev_values"][name_type] = config.agent.user_name
                elif name_type == "agent_name":
                    name_update_state["prev_values"][
                        name_type
                    ] = config.agent.agent_name

            if name_type == "user_name":
                user_display = name_value
                config.agent.user_name = name_value
            elif name_type == "agent_name":
                agent_display = name_value
                config.agent.agent_name = name_value
            Console.print(
                f"名字已更新: {name_type.replace('_', ' ')} = {name_value}",
                style="success",
            )

        config_file, _ = _find_config_file()
        if config_file:
            ConfigLoader.save(config, config_file)
        name_update_state["pending_updates"] = []

    # Show monitoring stats after each run
    _show_run_stats(agent, config)

    # Show undo hint if there are undoable operations
    if hasattr(agent, "has_undoable_operations") and agent.has_undoable_operations():
        Console.print("💡 输入 /undo 可撤销本轮操作", style="info")

    return user_display, agent_display


def _handle_slash_command(
    user_input: str,
    orchestrator: AgentOrchestrator,
    agent,
    config,
    git_manager,
    name_update_state: dict,
    user_display: str,
    agent_display: str,
    report_format: str,
    report_output: str | None,
) -> tuple[str, str, str] | None:
    """Handle slash commands shared by sync and async interactive loops.

    Returns:
        - ("continue", user_display, agent_display) — skip agent execution
        - ("break", user_display, agent_display) — exit the loop
        - None — not a slash command, proceed to agent execution
    """
    lower = user_input.lower()

    if lower in Commands.HELP:
        _show_help()
        return ("continue", user_display, agent_display)

    if lower in Commands.EXIT:
        GracefulExitManager.exit_with_summary()
        return ("break", user_display, agent_display)

    if lower in Commands.EXIT_DIRECT:
        Console.print("再见!", style="success")
        return ("break", user_display, agent_display)

    if lower == Commands.CLEAR:
        agent.reset()
        Console.print("对话历史已清空", style="success")
        return ("continue", user_display, agent_display)

    if lower == Commands.UNDO:
        user_display, agent_display = _handle_undo_command(
            agent, config, git_manager, name_update_state
        )
        return ("continue", user_display, agent_display)

    if lower == Commands.HISTORY:
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
        return ("continue", user_display, agent_display)

    if lower == Commands.TOOLS:
        tools = agent.tool_registry.list_tools()
        Console.print(f"可用工具: {', '.join(tools)}", style="info")
        return ("continue", user_display, agent_display)

    if lower == Commands.PLANS:
        from .plan_mode import list_plans

        print(list_plans())
        return ("continue", user_display, agent_display)

    if lower.startswith(CommandPrefix.PLAN):
        from .plan_mode import run_plan_mode_interactive

        task = user_input[6:].strip()
        if task:
            result = run_plan_mode_interactive(agent.llm, config, task)
            print(result)
        else:
            Console.print("用法: /plan <任务描述>", style="info")
        return ("continue", user_display, agent_display)

    if lower.startswith(CommandPrefix.STATS):
        _handle_stats_command(agent, config, user_input[6:].strip())
        return ("continue", user_display, agent_display)

    if lower == Commands.USAGE:
        _show_context_composition(agent, config)
        return ("continue", user_display, agent_display)

    if lower == Commands.CONTEXT:
        _show_context_budget(agent, config)
        return ("continue", user_display, agent_display)

    if lower == Commands.INIT:
        _init_project(agent)
        return ("continue", user_display, agent_display)

    if lower == Commands.CONFIG:
        _show_config(config, agent)
        return ("continue", user_display, agent_display)

    if lower.startswith(CommandPrefix.CONFIG):
        _handle_config_command(agent, config, user_input[8:])
        return ("continue", user_display, agent_display)

    if lower.startswith(CommandPrefix.MEMORY):
        _handle_memory_command(agent, config, user_input[7:].strip())
        return ("continue", user_display, agent_display)

    if lower == Commands.REPORT:
        _export_report(agent, report_format, report_output)
        return ("continue", user_display, agent_display)

    if lower == Commands.AUTO:
        _handle_auto_command(orchestrator, agent)
        return ("continue", user_display, agent_display)

    if lower == Commands.VERBOSE or lower.startswith(Commands.VERBOSE + " "):
        parts = user_input[len(Commands.VERBOSE) :].strip().lower()
        if parts == "on":
            agent.verbose = True
            Console.print("详细输出已开启", style="success")
        elif parts == "off":
            agent.verbose = False
            Console.print("详细输出已关闭", style="info")
        else:
            Console.print(
                f"当前详细输出: {'开启' if agent.verbose else '关闭'}", style="info"
            )
            Console.print("用法: /verbose on | /verbose off", style="info")
        return ("continue", user_display, agent_display)

    if lower == Commands.EFFORT or lower.startswith(Commands.EFFORT + " "):
        parts = user_input[len(Commands.EFFORT) :].strip().lower()
        valid = {"concise", "standard", "detailed"}
        if parts in valid:
            agent.output_style_config.style = parts
            agent._setup_system_prompt()
            Console.print(f"推理强度已切换: {parts}", style="success")
            Console.print("System prompt 已重新生成，下轮对话生效", style="info")
        else:
            current = agent.output_style_config.style
            Console.print(f"当前推理强度: {current}", style="info")
            Console.print(
                "用法: /effort concise | /effort standard | /effort detailed",
                style="info",
            )
        return ("continue", user_display, agent_display)

    if lower == Commands.PROMPT:
        messages = agent.memory.get_all()
        system_msgs = [m for m in messages if m.get("role") == "system"]
        if system_msgs:
            for i, msg in enumerate(system_msgs):
                content = msg.get("content", "")
                name = msg.get("name", "")
                header = f"--- System Prompt #{i + 1}"
                if name:
                    header += f" (name: {name})"
                header += f" [{len(content)} chars] ---"
                print(header)
                print(content)
                print("--- end ---")
        else:
            Console.print("当前无 system prompt", style="warning")
        return ("continue", user_display, agent_display)

    if lower == Commands.SESSIONS:
        if hasattr(agent.memory, "list_sessions"):
            sessions = agent.memory.list_sessions()
            if not sessions:
                Console.print("暂无会话", style="info")
            else:
                Console.print(f"可用会话 ({len(sessions)}):", style="info")
                for sid in sessions:
                    print(f"  {sid}")
        else:
            Console.print(
                "当前记忆类型不支持会话列表",
                style="warning",
            )
        return ("continue", user_display, agent_display)

    if lower.startswith(CommandPrefix.SNAPSHOT):
        _handle_snapshot_command(
            orchestrator,
            config,
            user_input[len(CommandPrefix.SNAPSHOT) :].strip(),
        )
        return ("continue", user_display, agent_display)

    if lower == Commands.SKILLS:
        if hasattr(agent, "skill_loader"):
            skills = agent.skill_loader.list_loaded_skills()
            if not skills:
                Console.print("未加载技能", style="info")
            else:
                Console.print(f"已加载技能 ({len(skills)}):", style="info")
                for skill_name in skills:
                    source = agent.skill_loader.get_skill_source(skill_name)
                    print(f"  {skill_name} <- {source}")
        else:
            Console.print("技能系统不可用", style="warning")
        return ("continue", user_display, agent_display)

    if lower.startswith(CommandPrefix.SKILL):
        _handle_skill_command(agent, user_input[7:])
        return ("continue", user_display, agent_display)

    if lower.startswith(CommandPrefix.SETNAME):
        user_display, agent_display = _handle_setname_command(
            user_input, agent, config, user_display, agent_display
        )
        return ("continue", user_display, agent_display)

    # Not a slash command
    return None


def run_interactive(
    orchestrator: AgentOrchestrator,
    config,
    report_enabled: bool = False,
    report_format: str = "json",
    report_output: str | None = None,
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
            risk_icons = {"safe": "🟢", "moderate": "🟡", "dangerous": "🔴"}
            icon = risk_icons.get(risk_level, "❓")

            print(f"\n{icon} 确认执行工具: {tool_name}")
            print(f"   风险级别: {risk_level}")
            if arguments:
                args_str = str(arguments)[:100]
                print(
                    f"   参数: {args_str}{'...' if len(str(arguments)) > 100 else ''}"
                )

            while True:
                response = input("   确认执行? [y/N/a(总是)/s(保存)]: ").strip().lower()

                if response == "y":
                    agent.confirm_tool(True)
                    break
                elif response == "a":
                    # Add to memory whitelist (session only)
                    agent.add_tool_to_whitelist(tool_name)
                    agent.confirm_tool(True)
                    print(f"   已添加到本次会话白名单")
                    break
                elif response == "s":
                    # Persist whitelist to config file
                    agent.add_tool_to_whitelist(tool_name)
                    _save_whitelist_to_config(tool_name, config)
                    agent.confirm_tool(True)
                    print(f"   已保存到配置文件白名单")
                    break
                elif response in ("n", ""):
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
                        f"Tool: {tool_name}", step_info={"tool": tool_name}
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
        "prev_values": {},  # dict of name_type -> previous value
    }

    def _setup_name_update_handler():
        """Set up event handler for name updates from memorize tool."""

        def handle_tool_result(event, data):
            """Handle tool result to detect name updates."""
            tool_name = data.get("tool", "unknown")
            result = data.get("result")

            # Detect name update from memorize tool
            if (
                tool_name == "memorize"
                and result
                and result.success
                and result.metadata
            ):
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
            if agent.verbose:
                Console.print("Git 集成已启用", style="info")

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
    Console.print_title("NanoAgent - AI Assistant")

    # Show config source
    if agent.verbose and hasattr(orchestrator, "_config_source"):
        Console.print(f"Config: {orchestrator._config_source}", style="info")

    # Show project context status
    if project_context:
        # Append to system prompt
        current_prompt = agent.memory.system_prompt or ""
        agent.memory.set_system_prompt(f"{current_prompt}\n\n---\n\n{project_context}")
        if agent.verbose:
            Console.print("项目: NANOPROJECT.md 已加载", style="success")

    if agent.verbose:
        Console.print("输入 '/?' 或 'help' 查看可用命令", style="info")
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

    cwd = os.getcwd()
    while True:
        try:
            print(f"\n[{user_display}] [{cwd}]:")
            user_input = _read_user_input("> ")

            if not user_input:
                continue

            # Handle slash commands (shared with async loop)
            cmd_result = _handle_slash_command(
                user_input,
                orchestrator,
                agent,
                config,
                git_manager,
                name_update_state,
                user_display,
                agent_display,
                report_format,
                report_output,
            )
            if cmd_result is not None:
                action, user_display, agent_display = cmd_result
                if action == "break":
                    break
                continue

            # 重置 Ctrl+C 计数
            GracefulExitManager.ctrl_c_count = 0

            # Run agent through orchestrator (streaming)
            print(f"\n[{agent_display}]:")
            handle = orchestrator.run_stream(user_input)
            result = None
            try:
                for event in handle.events:
                    if event.type == ExecutionEventType.THINK_START:
                        if agent.verbose:
                            print("  [Thinking...]", end="", flush=True)
                    elif event.type == ExecutionEventType.THINK_TEXT:
                        if agent.verbose and event.text_chunk:
                            print(f"\r  {event.text_chunk[:200]}", flush=True)
                    elif event.type == ExecutionEventType.THINK_END:
                        if (
                            agent.verbose
                            and event.think_result
                            and event.think_result.tool_calls
                        ):
                            names = [tc.name for tc in event.think_result.tool_calls]
                            print(f"  [Calling: {', '.join(names)}]")
                    elif event.type == ExecutionEventType.TOOL_CALL:
                        if agent.verbose and event.tool_call:
                            print(f"  [Tool] {event.tool_call.name}")
                    elif event.type == ExecutionEventType.TOOL_RESULT:
                        if agent.verbose and event.tool_result:
                            status = "ok" if event.tool_result.success else "fail"
                            preview = (event.tool_result.output or "")[:80]
                            print(f"  [Result:{status}] {preview}")
                    elif event.type == ExecutionEventType.GUARD_SHORT_CIRCUIT:
                        if agent.verbose and event.guard_name:
                            print(f"  [Guard: {event.guard_name}]")
                    elif event.type == ExecutionEventType.CANCELLED:
                        if agent.verbose:
                            print("\n  [Cancelled]")
                    elif event.type == ExecutionEventType.RUN_END:
                        result = event.result
            except KeyboardInterrupt:
                handle.cancel()
                # Drain remaining events to completion
                try:
                    for event in handle.events:
                        if event.type == ExecutionEventType.RUN_END:
                            result = event.result
                except KeyboardInterrupt:
                    pass

            # Process run result
            updated = _handle_run_result(
                result,
                orchestrator,
                agent,
                config,
                name_update_state,
                user_display,
                agent_display,
            )
            if updated is None:
                continue
            user_display, agent_display = updated

        except KeyboardInterrupt:
            # 被 signal handler 处理，继续循环
            continue
        except Exception as e:
            Console.print(f"错误: {e}", style="error")


async def run_interactive_async(
    orchestrator: AgentOrchestrator,
    config,
    report_enabled: bool = False,
    report_format: str = "json",
    report_output: str | None = None,
) -> None:
    """
    Async interactive chat loop with token-by-token streaming.

    Like run_interactive() but uses async generators and the agent's
    run_stream_async() for true token-by-token output.

    Args:
        orchestrator: The agent orchestrator to interact with
        config: The configuration object
        report_enabled: Whether to export report on exit
        report_format: Report format (json, markdown, summary)
        report_output: Report output path
    """
    agent = orchestrator.agent

    # Set up confirmation handler (matches sync path)
    def _setup_confirmation_handler():
        def handle_confirmation(event, data):
            tool_name = data.get("tool", "unknown")
            risk_level = data.get("risk_level", "moderate")
            risk_icons = {"safe": "🟢", "moderate": "🟡", "dangerous": "🔴"}
            icon = risk_icons.get(risk_level, "❓")

            print(f"\n{icon} 确认执行工具: {tool_name}")
            print(f"   风险级别: {risk_level}")
            if arguments := data.get("arguments"):
                print(f"   参数: {str(arguments)[:100]}")

            while True:
                response = input("   确认执行? [y/N/a(总是)/s(保存)]: ").strip().lower()
                if response == "y":
                    agent.confirm_tool(True)
                    break
                elif response == "a":
                    agent.add_tool_to_whitelist(tool_name)
                    agent.confirm_tool(True)
                    print(f"   已添加到本次会话白名单")
                    break
                elif response == "s":
                    agent.add_tool_to_whitelist(tool_name)
                    _save_whitelist_to_config(tool_name, config)
                    agent.confirm_tool(True)
                    print(f"   已保存到配置文件白名单")
                    break
                elif response in ("n", ""):
                    agent.confirm_tool(False)
                    print("   已取消")
                    break
                else:
                    print("   无效输入，请输入 y/N/a/s")

        agent.events.on(AgentEvent.CONFIRMATION_REQUIRED, handle_confirmation)

    _setup_confirmation_handler()

    # Set up git handler (same as sync)
    git_manager = None
    name_update_state = {"pending_name": None, "pending_updates": []}

    if hasattr(agent, "git_manager") and agent.git_manager:
        git_manager = agent.git_manager

        def handle_git_commit(event, data):
            if event == AgentEvent.TOOL_RESULT:
                tool_name = data.get("tool", "")
                if tool_name in ["file_write", "shell_execute"]:
                    git_manager.auto_commit(
                        f"[NanoAgent] {tool_name}: {data.get('summary', 'tool execution')}"
                    )

        orchestrator.events.on(AgentEvent.TOOL_RESULT, handle_git_commit)

    # Get display names
    user_display = config.agent.user_name
    agent_display = config.agent.agent_name

    # Check for stored names in memory
    if hasattr(agent, "memory") and hasattr(agent.memory, "recall"):
        stored_user, stored_agent = _check_names_in_memory(agent.memory)
        if stored_user:
            user_display = stored_user
        if stored_agent:
            agent_display = stored_agent

    # Initialize GracefulExitManager for /exit summary
    GracefulExitManager.agent = agent
    GracefulExitManager.config = config
    GracefulExitManager.report_enabled = report_enabled
    GracefulExitManager.report_format = report_format
    GracefulExitManager.report_output = report_output

    # Set up signal handler for Ctrl+C cancellation
    loop = asyncio.get_running_loop()

    def sigint_handler(sig, frame):
        task = asyncio.current_task()
        if task and not task.done():
            task.cancel()

    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, sigint_handler)

    cwd = os.getcwd()
    try:
        while True:
            try:
                print(f"\n[{user_display}] [{cwd}]:")

                # Get user input in thread to not block event loop
                user_input = await loop.run_in_executor(
                    None, lambda: _read_user_input("> ")
                )

                if not user_input:
                    continue

                # Handle slash commands (shared with sync loop)
                cmd_result = _handle_slash_command(
                    user_input,
                    orchestrator,
                    agent,
                    config,
                    git_manager,
                    name_update_state,
                    user_display,
                    agent_display,
                    report_format,
                    report_output,
                )
                if cmd_result is not None:
                    action, user_display, agent_display = cmd_result
                    if action == "break":
                        break
                    continue

                # Reset Ctrl+C count
                GracefulExitManager.ctrl_c_count = 0

                # Run agent through orchestrator (async streaming)
                print(f"\n[{agent_display}]:")
                handle = orchestrator.run_stream_async(user_input)
                result = None
                try:
                    async for event in handle.events:
                        if event.type == ExecutionEventType.THINK_START:
                            if agent.verbose:
                                print("  [Thinking...]", end="", flush=True)
                        elif event.type == ExecutionEventType.THINK_TEXT:
                            if event.text_chunk:
                                print(event.text_chunk, end="", flush=True)
                        elif event.type == ExecutionEventType.THINK_END:
                            print()  # Newline after streaming text
                            if (
                                agent.verbose
                                and event.think_result
                                and event.think_result.tool_calls
                            ):
                                names = [
                                    tc.name for tc in event.think_result.tool_calls
                                ]
                                print(f"  [Calling: {', '.join(names)}]")
                        elif event.type == ExecutionEventType.TOOL_CALL:
                            if agent.verbose and event.tool_call:
                                print(f"  [Tool] {event.tool_call.name}")
                        elif event.type == ExecutionEventType.TOOL_RESULT:
                            if agent.verbose and event.tool_result:
                                status = "ok" if event.tool_result.success else "fail"
                                preview = (event.tool_result.output or "")[:80]
                                print(f"  [Result:{status}] {preview}")
                        elif event.type == ExecutionEventType.GUARD_SHORT_CIRCUIT:
                            if agent.verbose and event.guard_name:
                                print(f"  [Guard: {event.guard_name}]")
                        elif event.type == ExecutionEventType.CANCELLED:
                            if agent.verbose:
                                print("\n  [Cancelled]")
                        elif event.type == ExecutionEventType.RUN_END:
                            result = event.result
                except asyncio.CancelledError:
                    handle.cancel()
                    # Drain remaining events
                    try:
                        async for event in handle.events:
                            if event.type == ExecutionEventType.RUN_END:
                                result = event.result
                    except asyncio.CancelledError:
                        pass

                # Process run result
                updated = _handle_run_result(
                    result,
                    orchestrator,
                    agent,
                    config,
                    name_update_state,
                    user_display,
                    agent_display,
                )
                if updated is None:
                    continue
                user_display, agent_display = updated

            except asyncio.CancelledError:
                # Ctrl+C during input — just continue
                continue
            except Exception as e:
                Console.print(f"错误: {e}", style="error")
    finally:
        signal.signal(signal.SIGINT, original_sigint)


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
""",
    )
    parser.add_argument(
        "-h", "--help", action="help", help="Show this [h]elp message and exit"
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"nano-agent {__version__}",
        help="Show [v]ersion and exit",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        metavar="PATH",
        help="[c]onfig file path (see priority below)",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=None,
        metavar="NAME",
        help="Override [m]odel name",
    )
    parser.add_argument(
        "-l", "--list-sessions", action="store_true", help="[l]ist all saved sessions"
    )
    parser.add_argument(
        "-s",
        "--show-session",
        type=str,
        metavar="ID",
        default=None,
        help="[s]how a specific session",
    )
    parser.add_argument(
        "-r",
        "--resume-session",
        type=str,
        metavar="ID",
        default=None,
        help="[r]esume an existing session",
    )
    parser.add_argument(
        "-n",
        "--new-session",
        action="store_true",
        help="Start a [n]ew session (default: resume most recent)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity: -v (minimal), -vv (debug).  Overrides config.output.verbosity.",
    )
    parser.add_argument(
        "--output-module",
        type=str,
        default=None,
        metavar="MODULE:LEVEL",
        help="Module-level verbosity override, e.g. react:verbose,context:quiet",
    )
    parser.add_argument(
        "-d",
        "--delete-session",
        type=str,
        metavar="ID",
        default=None,
        help="[d]elete a specific session by ID",
    )
    parser.add_argument(
        "--clean-sessions",
        action="store_true",
        help="Auto-clean low-value sessions (using config threshold)",
    )
    parser.add_argument(
        "--clean-threshold",
        type=int,
        metavar="N",
        default=None,
        help="Set clean threshold in config (requires value)",
    )
    parser.add_argument(
        "--migrate-sessions",
        action="store_true",
        help="Migrate sessions from file storage to SQLite",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run for migration (show what would be migrated)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode (read from stdin)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose output ([q]uiet mode)",
    )
    parser.add_argument(
        "--report", action="store_true", help="Export monitoring report after session"
    )
    parser.add_argument(
        "--report-format",
        type=str,
        choices=["json", "markdown", "summary"],
        default="json",
        metavar="FORMAT",
        help="Report format: json, markdown, summary",
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default=None,
        metavar="PATH",
        help="Report output file path",
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
        # Don't print session messages here — they're gated by verbose after agent creation

    # Create agent
    agent = create_agent(args.config)

    # Override verbosity via CLI flags
    if args.quiet:
        agent._output.set_verbosity(Verbosity.QUIET)
    elif args.verbose:
        if args.verbose == 1:
            agent._output.set_verbosity(Verbosity.MINIMAL)
        else:
            agent._output.set_verbosity(Verbosity.VERBOSE)

    # Apply --output-module overrides (e.g. "react:verbose,context:quiet")
    if args.output_module:
        from ..output import parse_verbosity

        for override in args.output_module.split(","):
            override = override.strip()
            if ":" in override:
                module, level = override.split(":", 1)
                try:
                    agent._output.set_verbosity(
                        parse_verbosity(level.strip()), module=module.strip()
                    )
                except ValueError:
                    pass

    # Now print session info gated by verbose
    if agent.verbose:
        if args.resume_session and not args.new_session:
            Console.print(f"正在恢复会话: {args.resume_session}", style="info")
        elif not args.resume_session and not args.new_session:
            Console.print("开始新会话", style="info")

    # Handle --new-session: explicitly create a new empty session
    if args.new_session:
        if hasattr(agent.memory, "new_session"):
            new_sid = agent.memory.new_session()
            if agent.verbose:
                Console.print(f"已创建新会话: {new_sid}", style="success")
        # else: short_term memory doesn't need explicit new_session

    # Handle --resume-session
    if args.resume_session:
        if hasattr(agent.memory, "load_session"):
            success = agent.memory.load_session(args.resume_session)
            if not success:
                Console.print(f"会话 '{args.resume_session}' 未找到", style="error")
                sys.exit(1)
            if agent.verbose:
                Console.print(f"已恢复会话: {args.resume_session}", style="success")
        else:
            Console.print(
                "会话恢复不可用（需要持久化或混合记忆）",
                style="warning",
            )

    if isinstance(agent.memory, HybridMemory):
        gc_result = agent.memory.run_gc()
        if gc_result and gc_result.summary():
            Console.print(
                f"[MemoryGC] {gc_result.summary()}",
                style="info",
            )

    # Override model if specified
    if args.model:
        agent.llm.model = args.model

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

        # Use async streaming if configured
        if getattr(config, "streaming", None) and config.streaming.mode == "async":
            asyncio.run(
                run_interactive_async(
                    agent,
                    config,
                    report_enabled=args.report,
                    report_format=args.report_format,
                    report_output=args.report_output,
                )
            )
        else:
            run_interactive(
                agent,
                config,
                report_enabled=args.report,
                report_format=args.report_format,
                report_output=args.report_output,
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

    if not hasattr(memory, "recall"):
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

    Console.print_title("会话迁移")

    # First show current status
    all_sessions = list_all_sessions(file_dir=file_dir, db_path=db_path)

    print(
        f"\nFile storage ({file_dir}): {len(all_sessions['file_storage']['sessions'])} sessions"
    )
    print(
        f"SQLite storage ({db_path}): {len(all_sessions['sqlite_storage']['sessions'])} sessions"
    )
    print(f"会话总数: {all_sessions['total_unique_sessions']}")

    if dry_run:
        print("\n[预演] 将迁移以下会话:")
        for session_id in all_sessions["file_storage"]["sessions"]:
            if session_id not in all_sessions["sqlite_storage"]["sessions"]:
                info = all_sessions["file_storage"]["info"].get(session_id, {})
                print(f"  - {session_id} ({info.get('message_count', 0)} 条消息)")
        return

    # Perform migration
    print("\n正在迁移会话…")
    report = migrate_file_to_sqlite(file_dir=file_dir, db_path=db_path, dry_run=False)

    print(f"\n迁移报告:")
    print(f"  文件会话总数: {report['total_file_sessions']}")
    print(f"  已在 SQLite 中: {len(report['already_in_sqlite'])}")
    print(f"  成功迁移: {len(report['migrated'])}")

    if report["errors"]:
        print(f"  错误: {len(report['errors'])}")
        for error in report["errors"]:
            print(f"    - {error['session_id']}: {error['error']}")

    if report["migrated"]:
        Console.print(
            f"\n成功迁移 {len(report['migrated'])} 个会话!",
            style="success",
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
        Console.print("暂无会话", style="info")
        return

    Console.print(f"共有 {len(sessions)} 个会话:", style="info")
    Console.print_separator()
    for session_id in sessions:
        info = storage.get_session_info(session_id)
        print(f"  {session_id}")
        print(f"    消息数: {info['message_count']}")
        if info["last_message"]:
            print(f"    最后活动: {info['last_message'][:19]}")
        print()


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
        Console.print(f"会话 '{session_id}' 未找到", style="error")
        sys.exit(1)

    # Delete session and summary
    storage.delete_session(session_id)
    storage.delete_summary(session_id)

    Console.print(f"会话 '{session_id}' 已删除", style="success")


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
        Console.print(f"未找到低于 {threshold} 条消息的低价值会话。", style="info")
        return

    Console.print(
        f"发现 {len(low_value_sessions)} 个低于 {threshold} 条消息的低价值会话:",
        style="info",
    )
    for session_id in low_value_sessions:
        info = storage.get_session_info(session_id)
        print(f"  {session_id} ({info['message_count']} 条消息)")

    # Delete sessions
    deleted_count = 0
    for session_id in low_value_sessions:
        storage.delete_session(session_id)
        storage.delete_summary(session_id)
        deleted_count += 1

    Console.print(f"已清理 {deleted_count} 个低价值会话", style="success")


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
    Console.print(f"清理阈值已设置为 {threshold}", style="success")
    Console.print(f"配置已保存: {config_file}", style="info")


def _generate_session_summary(agent, config) -> str:
    """使用 LLM 生成会话摘要（不超过10行）"""
    messages = agent.memory.get_all()
    # 过滤掉 system 消息
    messages = [m for m in messages if m.get("role") != "system"]

    if not messages:
        return "空会话"

    # 构建对话文本
    conversation = "\n".join(
        f"[{m.get('role')}]: {m.get('content', '')[:200]}" for m in messages
    )

    prompt = f"""请用不超过10行总结以下对话的主要内容：

{conversation}

要求：
1. 提取关键话题和结论
2. 简洁明了，不超过10行
3. 用中文回答"""

    try:
        response, _, _ = agent.llm.chat(
            messages=[{"role": "user", "content": prompt}], tools=None
        )
        return response
    except Exception:
        # 失败时返回简单摘要
        return f"共 {len(messages)} 条消息"


def _save_session_summary(agent, config, summary: str) -> None:
    """保存会话摘要"""
    # 获取 session_id
    if hasattr(agent.memory, "working_memory") and hasattr(
        agent.memory.working_memory, "session_id"
    ):
        session_id = agent.memory.working_memory.session_id
    elif hasattr(agent.memory, "session_id"):
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


def _handle_snapshot_command(orchestrator, config, command: str) -> None:
    """处理 /snapshot 子命令

    子命令:
        save [name]          - 保存当前状态快照
        list                 - 列出所有快照
        restore <id>         - 恢复到指定快照
        delete <id>          - 删除指定快照
        audit                - 查看审计日志
        rollback <audit_id>  - 从审计条目回滚
    """
    parts = command.strip().split()
    if not parts:
        Console.print(
            "用法: /snapshot <save [名称]|list|restore <id>|delete <id>"
            "|audit|rollback <audit_id>>",
            style="info",
        )
        return

    snapshot_manager = getattr(orchestrator, "snapshot_manager", None)
    if snapshot_manager is None:
        Console.print("快照管理器不可用。", style="warning")
        return

    subcommand = parts[0].lower()

    if subcommand == "save":
        name = parts[1] if len(parts) > 1 else ""
        metadata = snapshot_manager.save(orchestrator.agent, orchestrator, name=name)
        name_str = f" ({metadata.name})" if metadata.name else ""
        Console.print(
            f"快照已保存: {metadata.snapshot_id}{name_str} "
            f"(round={metadata.round_counter}, tokens={metadata.total_tokens})",
            style="success",
        )

    elif subcommand == "list":
        snapshots = snapshot_manager.list_snapshots()
        if not snapshots:
            Console.print("暂无快照。", style="info")
        else:
            Console.print(f"快照 ({len(snapshots)}):", style="info")
            for snap in snapshots:
                time_str = (
                    snap.created_at[11:16]
                    if len(snap.created_at) > 16
                    else snap.created_at
                )
                name_str = f" ({snap.name})" if snap.name else ""
                print(
                    f"  {snap.snapshot_id} [{time_str}] "
                    f"round={snap.round_counter} tokens={snap.total_tokens}{name_str}"
                )

    elif subcommand == "restore":
        if len(parts) < 2:
            Console.print("用法: /snapshot restore <id>", style="info")
            return
        snapshot_id = parts[1]
        if snapshot_manager.restore(snapshot_id, orchestrator.agent, orchestrator):
            Console.print(f"已恢复快照: {snapshot_id}", style="success")
        else:
            Console.print(f"快照未找到: {snapshot_id}", style="error")

    elif subcommand == "delete":
        if len(parts) < 2:
            Console.print("用法: /snapshot delete <id>", style="info")
            return
        snapshot_id = parts[1]
        if snapshot_manager.delete(snapshot_id):
            Console.print(f"快照已删除: {snapshot_id}", style="success")
        else:
            Console.print(f"快照未找到: {snapshot_id}", style="error")

    elif subcommand == "audit":
        entries = snapshot_manager.list_audit_entries()
        if not entries:
            Console.print("暂无审计条目。", style="info")
        else:
            Console.print(f"审计日志 ({len(entries)} entries):", style="info")
            for entry in entries:
                time_str = (
                    entry.timestamp[11:16]
                    if len(entry.timestamp) > 16
                    else entry.timestamp
                )
                print(
                    f"  {entry.audit_id} [{time_str}] {entry.operation} "
                    f"snap={entry.snapshot_id} "
                    f"trigger={entry.trigger} outcome={entry.outcome}"
                )
                if entry.reason:
                    print(f"    reason: {entry.reason}")

    elif subcommand == "rollback":
        if len(parts) < 2:
            Console.print("用法: /snapshot rollback <audit_id>", style="info")
            return
        audit_id = parts[1]
        if snapshot_manager.rollback_from_audit(
            audit_id, orchestrator.agent, orchestrator
        ):
            Console.print(f"已回滚审计条目: {audit_id}", style="success")
        else:
            Console.print(f"审计条目未找到或回滚失败: {audit_id}", style="error")

    else:
        Console.print(f"未知子命令: {subcommand}", style="error")
        Console.print(
            "可选: save [名称], list, restore <id>, delete <id>, "
            "audit, rollback <audit_id>",
            style="info",
        )


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

    if (
        not hasattr(agent, "has_undoable_operations")
        or not agent.has_undoable_operations()
    ):
        Console.print("没有可撤销的操作", style="info")
        return restored

    # Build context for undo
    context = {
        "memory": agent.memory,
        "config": config,
        "tool_registry": agent.tool_registry,
    }

    # Perform undo
    undone = agent.undo_current_round(context)

    if undone:
        Console.print(f"已撤销: {', '.join(undone)}", style="success")

        # Handle name updates - restore previous values
        prev_values = (
            name_update_state.get("prev_values", {}) if name_update_state else {}
        )
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
    if not hasattr(agent, "skill_loader"):
        Console.print("技能系统不可用", style="warning")
        return

    parts = command.strip().split()
    if not parts:
        Console.print("用法: /skill reload <名称>", style="info")
        return

    action = parts[0].lower()
    skill_name = parts[1] if len(parts) > 1 else None

    if action == "reload":
        if not skill_name:
            Console.print("用法: /skill reload <名称>", style="info")
            return

        if skill_name not in agent.skill_loader.list_loaded_skills():
            Console.print(f"技能 '{skill_name}' 未找到", style="error")
            return

        success = agent.skill_loader.reload_skill(skill_name)
        if success:
            Console.print(f"技能 '{skill_name}' 重新加载成功", style="success")
            # Update agent's tools and prompt
            _update_agent_skills(agent)
        else:
            Console.print(f"重新加载技能失败: '{skill_name}'", style="error")

    elif action == "unload":
        if not skill_name:
            Console.print("用法: /skill unload <名称>", style="info")
            return

        if skill_name not in agent.skill_loader.list_loaded_skills():
            Console.print(f"技能 '{skill_name}' 未找到", style="error")
            return

        success = agent.skill_loader.unload_skill(skill_name)
        if success:
            Console.print(f"技能 '{skill_name}' unloaded successfully", style="success")
            # Update agent's tools and prompt
            _update_agent_skills(agent)
        else:
            Console.print(f"卸载技能失败: '{skill_name}'", style="error")

    else:
        Console.print(
            f"Unknown action: {action}. Use 'reload' or 'unload'", style="error"
        )


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


def _export_report(
    agent, report_format: str = "json", report_output: str | None = None
) -> None:
    """导出监控报告

    Args:
        agent: Agent 实例
        report_format: 报告格式 (json, markdown, summary)
        report_output: 输出路径 (默认 .nano_agent/report.{format})
    """
    if not hasattr(agent, "tracker") or not agent.tracker.run_metrics:
        Console.print(
            "No monitoring data available yet. Run a query first.", style="info"
        )
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
            Console.print(f"报告已导出: {report_output}", style="success")
        elif report_format == "markdown":
            ReportGenerator.save_markdown(metrics, report_output)
            Console.print(f"报告已导出: {report_output}", style="success")
        elif report_format == "summary":
            summary = ReportGenerator.to_summary(metrics)
            print(f"\n{summary}")
        else:
            Console.print(f"未知格式: {report_format}", style="error")

    except Exception as e:
        Console.print(f"报告导出失败: {e}", style="error")


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
        Console.print(f"未知子命令: {parts[0]}", style="error")
        Console.print("可选: status, on, off", style="info")


def _enable_long_term_memory(config) -> None:
    """启用长期记忆功能"""
    import yaml
    from pathlib import Path

    # 检查当前状态
    if config.memory.type == "hybrid":
        Console.print("长期记忆已启用", style="info")
        return

    # 更新配置文件
    config_path = Path.cwd() / ".nano_agent" / "config.yaml"

    if not config_path.exists():
        # 创建配置文件
        Console.print("创建配置文件…", style="info")
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
            existing_config["memory"][
                "long_term_storage_path"
            ] = ".nano_agent/long_term_memory"

        # 写入配置
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                existing_config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        Console.print("长期记忆已启用!", style="success")
        Console.print(f"配置已更新: {config_path}", style="info")
        Console.print("记忆类型已切换为: hybrid", style="info")
        Console.print("重启 nano-agent 以应用更改。", style="warning")

    except Exception as e:
        Console.print(f"配置更新失败: {e}", style="error")


def _disable_long_term_memory(config) -> None:
    """禁用长期记忆功能"""
    import yaml
    from pathlib import Path

    # 检查当前状态
    if config.memory.type == "short_term":
        Console.print("长期记忆已禁用", style="info")
        return

    # 更新配置文件
    config_path = Path.cwd() / ".nano_agent" / "config.yaml"

    if not config_path.exists():
        Console.print("未找到配置文件。当前使用默认值。", style="info")
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
            yaml.dump(
                existing_config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        Console.print("长期记忆已禁用!", style="success")
        Console.print(f"配置已更新: {config_path}", style="info")
        Console.print("记忆类型已切换为: short_term", style="info")
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
    elif parts[0].lower() == "estimation":
        # v0.7.18: Show estimation audit data
        _show_estimation_audit(agent, config)
    else:
        Console.print(f"未知子命令: {parts[0]}", style="error")
        Console.print(
            "可选: status, context, breakdown, estimation, on, off", style="info"
        )


def _enable_run_stats() -> None:
    """启用每次对话后的统计显示"""
    if GracefulExitManager.show_run_stats:
        Console.print("自动统计显示已启用", style="info")
        return

    GracefulExitManager.show_run_stats = True
    Console.print("自动统计显示已启用!", style="success")
    Console.print("每次运行后将显示统计信息。", style="info")


def _disable_run_stats() -> None:
    """禁用每次对话后的统计显示"""
    if not GracefulExitManager.show_run_stats:
        Console.print("自动统计显示已禁用", style="info")
        return

    GracefulExitManager.show_run_stats = False
    Console.print("自动统计显示已禁用!", style="success")
    Console.print("使用 /stats 手动查看统计信息。", style="info")


def _handle_config_command(agent, config, command: str) -> None:
    """处理 /config 子命令

    Args:
        agent: Agent 实例
        config: 配置对象
        command: 子命令字符串
    """
    parts = command.strip().split()
    if not parts:
        Console.print("用法: /config <init [--force]>", style="info")
        return

    subcommand = parts[0].lower()

    if subcommand == "init":
        force = "--force" in parts or "-f" in parts
        _init_config_file(config, force=force)
    else:
        Console.print(f"未知子命令: {subcommand}", style="error")
        Console.print("可选: init [--force]", style="info")


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
            "system_prompt": config.agent.system_prompt
            or "You are a helpful AI assistant.",
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
        "smart_optimization": {
            "confidence_enabled": config.smart_optimization.confidence_enabled,
            "confidence_threshold": config.smart_optimization.confidence_threshold,
            "budget_enabled": config.smart_optimization.budget_enabled,
            "initial_budget": config.smart_optimization.initial_budget,
            "routing_enabled": config.smart_optimization.routing_enabled,
            "prejudgment_enabled": config.smart_optimization.prejudgment_enabled,
            "prejudgment_simple_prompt": config.smart_optimization.prejudgment_simple_prompt,
            "prejudgment_max_answer_tokens": config.smart_optimization.prejudgment_max_answer_tokens,
        },
        "aggressive_output": {
            "enabled": config.aggressive_output.enabled,
            "level": config.aggressive_output.level,
        },
        "standardized_output": {
            "enabled": config.standardized_output.enabled,
            "detailed": config.standardized_output.detailed,
        },
        "output": {
            "verbosity": config.output.verbosity,
            "module_overrides": config.output.module_overrides,
            "color": config.output.color,
            "tui_enabled": config.output.tui_enabled,
        },
        "retry": {
            "enabled": config.retry.enabled,
            "max_retries": config.retry.max_retries,
            "base_delay": config.retry.base_delay,
            "max_delay": config.retry.max_delay,
            "jitter": config.retry.jitter,
            "retryable_status_codes": config.retry.retryable_status_codes,
        },
        "rate_limiter": {
            "enabled": config.rate_limiter.enabled,
            "requests_per_minute": config.rate_limiter.requests_per_minute,
            "burst": config.rate_limiter.burst,
        },
        "sanitizer": {
            "enabled": config.sanitizer.enabled,
            "max_input_length": config.sanitizer.max_input_length,
            "length_action": config.sanitizer.length_action,
            "reject_null_bytes": config.sanitizer.reject_null_bytes,
            "reject_control_chars": config.sanitizer.reject_control_chars,
            "max_line_length": config.sanitizer.max_line_length,
            "pii_enabled": config.sanitizer.pii_enabled,
            "pii_mask_mode": config.sanitizer.pii_mask_mode,
            "pii_mask_char": config.sanitizer.pii_mask_char,
            "pii_types": config.sanitizer.pii_types,
        },
        "output_guard": {
            "enabled": config.output_guard.enabled,
            "action": config.output_guard.action,
            "mask_mode": config.output_guard.mask_mode,
            "mask_char": config.output_guard.mask_char,
            "sensitive_types": config.output_guard.sensitive_types,
            "block_severity": config.output_guard.block_severity,
            "custom_patterns": config.output_guard.custom_patterns,
        },
        "harmful_content_filter": {
            "enabled": config.harmful_content_filter.enabled,
            "categories": config.harmful_content_filter.categories,
            "default_action": config.harmful_content_filter.default_action,
            "category_actions": config.harmful_content_filter.category_actions,
            "replacement_text": config.harmful_content_filter.replacement_text,
            "custom_patterns": config.harmful_content_filter.custom_patterns,
        },
        "result_validator": {
            "enabled": config.result_validator.enabled,
            "checks": config.result_validator.checks,
            "on_fail": config.result_validator.on_fail,
            "on_pass": config.result_validator.on_pass,
            "custom_validators": config.result_validator.custom_validators,
        },
        "feedback_loop": {
            "deviation_feedback_enabled": config.feedback_loop.deviation_feedback_enabled,
            "deviation_feedback_threshold": config.feedback_loop.deviation_feedback_threshold,
            "deviation_feedback_cooldown": config.feedback_loop.deviation_feedback_cooldown,
            "deviation_feedback_hint_injection": config.feedback_loop.deviation_feedback_hint_injection,
            "self_correction_enabled": config.feedback_loop.self_correction_enabled,
            "self_correction_max_attempts": config.feedback_loop.self_correction_max_attempts,
        },
        "tool_resource_limiter": {
            "enabled": config.tool_resource_limiter.enabled,
            "timeout_enabled": config.tool_resource_limiter.timeout_enabled,
            "default_timeout": config.tool_resource_limiter.default_timeout,
            "timeout_overrides": config.tool_resource_limiter.timeout_overrides,
            "rate_limit_enabled": config.tool_resource_limiter.rate_limit_enabled,
            "per_tool_calls_per_minute": config.tool_resource_limiter.per_tool_calls_per_minute,
            "global_calls_per_minute": config.tool_resource_limiter.global_calls_per_minute,
        },
        "memory_gc": {
            "decay_enabled": config.memory_gc.decay_enabled,
            "decay_half_life_days": config.memory_gc.decay_half_life_days,
            "dedup_merge_enabled": config.memory_gc.dedup_merge_enabled,
            "dedup_merge_tag": config.memory_gc.dedup_merge_tag,
            "gc_enabled": config.memory_gc.gc_enabled,
            "gc_threshold": config.memory_gc.gc_threshold,
            "gc_min_age_days": config.memory_gc.gc_min_age_days,
            "eviction_enabled": config.memory_gc.eviction_enabled,
            "eviction_max_entries": config.memory_gc.eviction_max_entries,
            "eviction_protected_categories": config.memory_gc.eviction_protected_categories,
            "eviction_mention_count_threshold": config.memory_gc.eviction_mention_count_threshold,
        },
        "snapshot": {
            "enabled": config.snapshot.enabled,
            "auto_snapshot": config.snapshot.auto_snapshot,
            "max_snapshots": config.snapshot.max_snapshots,
            "snapshot_dir": config.snapshot.snapshot_dir,
            "audit_log_enabled": config.snapshot.audit_log_enabled,
            "audit_log_dir": config.snapshot.audit_log_dir,
            "max_audit_entries": config.snapshot.max_audit_entries,
            "auto_rollback_enabled": config.snapshot.auto_rollback_enabled,
            "auto_rollback_threshold": config.snapshot.auto_rollback_threshold,
            "auto_rollback_on_failure": config.snapshot.auto_rollback_on_failure,
        },
        "streaming": {
            "mode": config.streaming.mode,
        },
    }

    # 如果文件不存在或强制覆盖，直接写入
    if not config_path.exists() or force:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                default_config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
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
            yaml.dump(
                merged_config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

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
        Console.print(
            f"Files: {info['structure']['total_files']} | Dirs: {info['structure']['total_dirs']}",
            style="info",
        )

        if info["tech_stack"]:
            Console.print(f"Tech: {', '.join(info['tech_stack'])}", style="info")

        # 检查是否已存在 NANOPROJECT.md
        output_path = Path.cwd() / "NANOPROJECT.md"
        existing_content = None
        user_notes = ""

        if output_path.exists():
            existing_content = output_path.read_text(encoding="utf-8")
            # 提取用户手动添加的内容（在 <!-- user-notes --> 标记区域）
            user_notes_match = re.search(
                r"<!-- user-notes -->(.*?)<!-- /user-notes -->",
                existing_content,
                re.DOTALL,
            )
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
            messages=[{"role": "user", "content": prompt}], tools=None
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
            Console.print(
                f"\nNANOPROJECT.md updated at: {output_path}", style="success"
            )
            if user_notes:
                Console.print("User notes preserved.", style="info")
        else:
            Console.print(
                f"\nNANOPROJECT.md created at: {output_path}", style="success"
            )
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
    if not hasattr(agent.memory, "long_term_memory"):
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
            metadata={"source": "/init", "project_name": info["project_name"]},
        )

        # 保存项目摘要（截取关键部分）
        summary_preview = summary[:500] if len(summary) > 500 else summary
        ltm.add(
            content=f"项目摘要:\n{summary_preview}",
            category="project_summary",
            metadata={"source": "/init", "project_name": info["project_name"]},
        )

        Console.print("Project info saved to long-term memory.", style="success")

    except Exception as e:
        Console.print(
            f"Warning: Could not save to long-term memory: {e}", style="warning"
        )


if __name__ == "__main__":
    main()
