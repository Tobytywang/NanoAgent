"""
Test script for measuring token consumption in v0.7.2.

Simulates two rounds of conversation and reports token usage.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nano_agent.config.loader import ConfigLoader
from nano_agent.llm.ollama import OllamaLLM
from nano_agent.memory.short_term import ShortTermMemory
from nano_agent.tools.registry import ToolRegistry
from nano_agent.tools.builtin import register_builtin_tools
from nano_agent.agent.react import ReActAgent
from nano_agent.monitoring import MetricsTracker
from nano_agent.config.schema import OutputStyleConfig, ToolMergeConfig


def test_token_consumption(style: str = "concise"):
    """Test token consumption with specified output style."""

    print(f"\n{'='*60}")
    print(f"Testing with output_style: {style}")
    print(f"{'='*60}\n")

    # Load config
    config = ConfigLoader.load()
    config.llm.model = "qwen3.5:9b"  # Use available model
    config.output_style = OutputStyleConfig(style=style, tool_output_max_tokens=500)
    config.tool_merge = ToolMergeConfig(enabled=True, concise_only=True)
    config.agent.verbose = True

    # Create components
    llm = OllamaLLM(
        model=config.llm.model, base_url=config.llm.base_url, timeout=config.llm.timeout
    )
    memory = ShortTermMemory(max_messages=config.memory.max_messages)
    tool_registry = ToolRegistry()
    register_builtin_tools(tool_registry, config)

    tracker = MetricsTracker()

    # Create agent
    agent = ReActAgent(
        llm=llm,
        memory=memory,
        tool_registry=tool_registry,
        max_iterations=config.agent.max_iterations,
        verbose=config.agent.verbose,
        tracker=tracker,
        output_style_config=config.output_style,
        tool_merge_config=config.tool_merge,
    )

    # Round 1: Simple file search
    print("\n--- Round 1: File search ---")
    result1 = agent.run("查找当前目录下的 Python 文件", session_id="test_session")
    print(f"Response: {result1.response[:100]}...")

    # Round 2: Another search
    print("\n--- Round 2: Another search ---")
    result2 = agent.run("查找当前目录下的 Markdown 文件", session_id="test_session")
    print(f"Response: {result2.response[:100]}...")

    # Get metrics
    metrics = tracker.run_metrics

    print(f"\n{'='*60}")
    print(f"Token Consumption Report ({style} mode)")
    print(f"{'='*60}")
    if metrics:
        print(f"Total tokens: {metrics.total_tokens}")
        print(f"LLM calls: {metrics.total_iterations}")
        print(f"Tool calls: {metrics.total_tool_calls}")
    else:
        print("No metrics available")
    print(f"Iterations: {result1.iterations + result2.iterations}")

    # Save report
    report_path = Path(f".nano_agent/test_report_{style}.json")
    report = {
        "style": style,
        "total_tokens": metrics.total_tokens if metrics else 0,
        "llm_calls": metrics.total_iterations if metrics else 0,
        "tool_calls": metrics.total_tool_calls if metrics else 0,
        "iterations": result1.iterations + result2.iterations,
        "round1": {
            "response": result1.response,
            "iterations": result1.iterations,
            "tool_calls": len(result1.tool_calls),
        },
        "round2": {
            "response": result2.response,
            "iterations": result2.iterations,
            "tool_calls": len(result2.tool_calls),
        },
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nReport saved to: {report_path}")

    return metrics.total_tokens if metrics else 0


def main():
    """Run tests with different output styles."""

    print("\n" + "=" * 60)
    print("v0.7.2 Token Consumption Test")
    print("Goal: Two rounds < 8k tokens in concise mode")
    print("=" * 60)

    # Test concise mode
    concise_tokens = test_token_consumption("concise")

    # Test standard mode for comparison
    standard_tokens = test_token_consumption("standard")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Concise mode: {concise_tokens} tokens")
    print(f"Standard mode: {standard_tokens} tokens")
    print(f"Target: < 8000 tokens")
    print(f"Concise achieved: {concise_tokens < 8000}")

    if concise_tokens < 8000:
        print("\n✅ v0.7.2 goal achieved!")
    else:
        print(
            f"\n❌ Goal not achieved. Need {concise_tokens - 8000} more tokens reduction."
        )


if __name__ == "__main__":
    main()
