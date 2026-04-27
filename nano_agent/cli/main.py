"""
CLI entry point for NanoAgent.
"""

import argparse
import sys
from pathlib import Path

from ..llm import create_llm_from_config
from ..memory import ShortTermMemory, PersistentMemory, HybridMemory, FileStorage, LongTermMemory
from ..tools.base import ToolRegistry
from ..tools.builtin import register_builtin_tools
from ..agent.react import ReActAgent
from ..config.loader import ConfigLoader
from .console import Console


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
        # Create working memory (short-term)
        working_memory = ShortTermMemory(
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
    register_builtin_tools(tool_registry, memory=memory)

    # Create agent
    agent = ReActAgent(
        llm=llm,
        memory=memory,
        tool_registry=tool_registry,
        max_iterations=config.agent.max_iterations,
        verbose=config.agent.verbose
    )

    return agent


def run_interactive(agent: ReActAgent) -> None:
    """
    Run interactive chat loop.

    Args:
        agent: The agent to interact with
    """
    import os

    Console.print_header("NanoAgent - AI Assistant")
    Console.print("Type 'exit' or 'quit' to exit", style="info")
    Console.print("Type 'clear' to clear conversation history", style="info")
    Console.print("Type 'tools' to list available tools", style="info")
    Console.print_separator()

    while True:
        try:
            cwd = os.getcwd()
            print(f"\n[User] [{cwd}]:")
            user_input = input("> ").strip()

            if not user_input:
                continue

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

            # Run agent
            Console.print("\n", style="agent", end="")
            response = agent.run(user_input)
            print(f"> {response}")

        except KeyboardInterrupt:
            Console.print("\nInterrupted", style="warning")
            break
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

    # Create agent
    agent = create_agent(args.config)

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
        # Interactive mode
        run_interactive(agent)


if __name__ == "__main__":
    main()