#!/usr/bin/env python3
"""
Automated token consumption test for NanoAgent.
Tests until 10 consecutive rounds meet <8k tokens requirement.
"""

import subprocess
import json
import sys
import time
from pathlib import Path

NANO_AGENT_REPO = "/Users/tobytywang/Repositories/NanoAgent"
TYNOTE_REPO = "/Users/tobytywang/Repositories/TYNote"
TARGET_TOKENS = 8000
REQUIRED_CONSECUTIVE = 10


def run_command(cmd, cwd=None, capture=True):
    """Run a shell command."""
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=capture, text=True)
    return result


def update_nano_agent():
    """Step 2: Update nano-agent in TYNote."""
    print("Step 2: Updating nano-agent...")
    # Activate venv and install
    run_command(
        f"source {TYNOTE_REPO}/.env/bin/activate && pip install -e {NANO_AGENT_REPO} -q"
    )
    print("  Done")


def list_sessions():
    """Step 3: List sessions."""
    print("Step 3: Listing sessions...")
    result = run_command(f"cd {TYNOTE_REPO} && python3 -m nano_agent.cli.main -l")
    sessions = []
    for line in result.stdout.split("\n"):
        if "session_" in line:
            # Extract session ID
            import re

            match = re.search(r"session_[a-f0-9]+", line)
            if match:
                sessions.append(match.group())
    print(f"  Found sessions: {sessions}")
    return sessions


def delete_session(session_id):
    """Step 4: Delete a session."""
    print(f"Step 4: Deleting session {session_id}...")
    run_command(f"cd {TYNOTE_REPO} && python3 -m nano_agent.cli.main -d {session_id}")
    print("  Done")


def run_conversation_test():
    """Step 5-8: Run two rounds of conversation and get token count."""
    print("Step 5-8: Running conversation test...")

    # Create test script
    test_script = f"""
import sys
sys.path.insert(0, "{NANO_AGENT_REPO}")

from nano_agent.cli.main import create_agent
from nano_agent.config.loader import ConfigLoader
from pathlib import Path

config_path = Path("{TYNOTE_REPO}/.nano_agent/config.yaml")
config = ConfigLoader.load(str(config_path))

orchestrator = create_agent(config)

# Round 1
print("Round 1: 请帮我总结当前会话的上下文信息")
result1 = orchestrator.run("请帮我总结当前会话的上下文信息")
print(f"Response 1: {{result1.response[:100]}}...")

# Round 2
print("Round 2: 请帮我查看当前项目的plan")
result2 = orchestrator.run("请帮我查看当前项目的plan")
print(f"Response 2: {{result2.response[:100]}}...")

# Get total tokens from tracker
agent = orchestrator.agent
if hasattr(agent, 'tracker') and hasattr(agent.tracker, 'run_metrics'):
    metrics = agent.tracker.run_metrics
    total_tokens = getattr(metrics, 'total_tokens', 0)
    print(f"TOTAL_TOKENS:{{total_tokens}}")
"""

    # Write and run test
    test_file = "/tmp/nano_test_run.py"
    with open(test_file, "w") as f:
        f.write(test_script)

    result = run_command(f"cd {TYNOTE_REPO} && python3 {test_file}")

    # Parse output
    print(result.stdout)

    # Extract token count
    total_tokens = None
    for line in result.stdout.split("\n"):
        if "TOTAL_TOKENS:" in line:
            total_tokens = int(line.split(":")[1])
            break

    # Fallback: read report.json
    if total_tokens is None:
        report_path = Path(f"{TYNOTE_REPO}/.nano_agent/report.json")
        if report_path.exists():
            with open(report_path) as f:
                data = json.load(f)
                total_tokens = data.get("total_tokens", 99999)

    return total_tokens or 99999


def check_report_tokens():
    """Check tokens from report.json."""
    report_path = Path(f"{TYNOTE_REPO}/.nano_agent/report.json")
    if report_path.exists():
        with open(report_path) as f:
            data = json.load(f)
            return data.get("total_tokens", 99999)
    return 99999


def main():
    print("=" * 60)
    print("NanoAgent Token Consumption Automated Test")
    print(f"Target: <{TARGET_TOKENS} tokens for 2 rounds")
    print(f"Required: {REQUIRED_CONSECUTIVE} consecutive passes")
    print("=" * 60)
    print()

    consecutive_passes = 0
    total_tests = 0
    results = []

    while consecutive_passes < REQUIRED_CONSECUTIVE:
        total_tests += 1
        print(f"\n{'='*60}")
        print(f"Test #{total_tests}")
        print("=" * 60)

        try:
            # Step 2: Update
            update_nano_agent()

            # Step 3-4: Clean up old sessions
            sessions = list_sessions()
            for session in sessions[:1]:  # Only delete most recent
                delete_session(session)

            # Step 5-8: Run test
            tokens = run_conversation_test()

            # Check result
            passed = tokens < TARGET_TOKENS
            results.append({"test": total_tests, "tokens": tokens, "passed": passed})

            print(f"\nResult: {tokens} tokens - {'PASS ✓' if passed else 'FAIL ✗'}")

            if passed:
                consecutive_passes += 1
                print(
                    f"Consecutive passes: {consecutive_passes}/{REQUIRED_CONSECUTIVE}"
                )
            else:
                consecutive_passes = 0
                print(f"Consecutive passes reset to 0")
                print("Step 9: Optimization needed...")

                # For now, we'll stop and report
                # In a full implementation, this would trigger code optimization
                print("\nNote: Manual optimization may be required.")
                print("Current configuration:")
                config_path = Path(f"{TYNOTE_REPO}/.nano_agent/config.yaml")
                if config_path.exists():
                    print(config_path.read_text()[:500])

        except Exception as e:
            print(f"Error: {e}")
            consecutive_passes = 0

        # Small delay between tests
        time.sleep(1)

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print(f"All {REQUIRED_CONSECUTIVE} consecutive tests passed!")
    print("=" * 60)

    # Print summary
    print("\nTest Summary:")
    for r in results:
        status = "✓" if r["passed"] else "✗"
        print(f"  Test {r['test']}: {r['tokens']} tokens {status}")


if __name__ == "__main__":
    main()
