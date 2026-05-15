#!/bin/bash
# Automated token consumption test for NanoAgent
# Tests until 10 consecutive rounds meet <8k tokens requirement

set -e

NANO_AGENT_REPO="/Users/tobytywang/Repositories/NanoAgent"
TYNOTE_REPO="/Users/tobytywang/Repositories/TYNote"
TARGET_TOKENS=8000
REQUIRED_CONSECUTIVE=10

# Results tracking
consecutive_passes=0
total_tests=0
results_file="/tmp/nano_agent_test_results.txt"

echo "=== NanoAgent Token Consumption Automated Test ===" | tee "$results_file"
echo "Target: <$TARGET_TOKENS tokens for 2 rounds" | tee -a "$results_file"
echo "Required: $REQUIRED_CONSECUTIVE consecutive passes" | tee -a "$results_file"
echo "" | tee -a "$results_file"

# Function to run a single test
run_test() {
    local test_num=$1
    echo "--- Test #$test_num ---" | tee -a "$results_file"

    # Step 2: Update nano-agent in TYNote
    echo "Step 2: Updating nano-agent..."
    cd "$TYNOTE_REPO"
    source .env/bin/activate 2>/dev/null || python3 -m venv .env && source .env/bin/activate
    pip install -e "$NANO_AGENT_REPO" -q

    # Step 3: List sessions
    echo "Step 3: Listing sessions..."
    sessions=$(python3 -m nano_agent.cli.main -l 2>&1 | grep -o "session_[a-f0-9]*" | head -1)

    # Step 4: Delete previous session if exists
    if [ -n "$sessions" ]; then
        echo "Step 4: Deleting previous session $sessions..."
        python3 -m nano_agent.cli.main -d "$sessions" 2>/dev/null || true
    fi

    # Step 5-8: Run conversation using expect or direct Python
    echo "Step 5-8: Running conversation test..."

    # Use Python to simulate conversation
    python3 << 'PYTHON_SCRIPT'
import sys
sys.path.insert(0, "/Users/tobytywang/Repositories/NanoAgent")

from nano_agent.cli.main import create_agent
from nano_agent.config.loader import ConfigLoader
from pathlib import Path

config_path = Path("/Users/tobytywang/Repositories/TYNote/.nano_agent/config.yaml")
config = ConfigLoader.load(str(config_path))

orchestrator = create_agent(config)

# Round 1
print("Round 1: 请帮我总结当前会话的上下文信息")
result1 = orchestrator.run("请帮我总结当前会话的上下文信息")

# Round 2
print("Round 2: 请帮我查看当前项目的plan")
result2 = orchestrator.run("请帮我查看当前项目的plan")

# Get stats
agent = orchestrator.agent
if hasattr(agent, 'tracker') and hasattr(agent.tracker, 'run_metrics'):
    metrics = agent.tracker.run_metrics
    total_tokens = metrics.total_tokens if hasattr(metrics, 'total_tokens') else 0
    print(f"TOTAL_TOKENS:{total_tokens}")
else:
    # Fallback: read from report
    import json
    report_path = Path("/Users/tobytywang/Repositories/TYNote/.nano_agent/report.json")
    if report_path.exists():
        with open(report_path) as f:
            data = json.load(f)
            total_tokens = data.get("total_tokens", 0)
            print(f"TOTAL_TOKENS:{total_tokens}")
PYTHON_SCRIPT

    # Extract token count
    tokens=$(grep "TOTAL_TOKENS:" /tmp/nano_output.txt 2>/dev/null | cut -d: -f2 || echo "99999")

    # Check report.json as fallback
    if [ -z "$tokens" ] || [ "$tokens" = "99999" ]; then
        tokens=$(python3 -c "
import json
with open('$TYNOTE_REPO/.nano_agent/report.json') as f:
    data = json.load(f)
    print(data.get('total_tokens', 99999))
" 2>/dev/null || echo "99999")
    fi

    echo "Tokens used: $tokens" | tee -a "$results_file"

    # Check if passes
    if [ "$tokens" -lt "$TARGET_TOKENS" ]; then
        echo "PASS ✓" | tee -a "$results_file"
        return 0
    else
        echo "FAIL ✗" | tee -a "$results_file"
        return 1
    fi
}

# Main test loop
while [ $consecutive_passes -lt $REQUIRED_CONSECUTIVE ]; do
    total_tests=$((total_tests + 1))

    if run_test $total_tests; then
        consecutive_passes=$((consecutive_passes + 1))
    else
        consecutive_passes=0
        echo "Optimization needed..." | tee -a "$results_file"
        # Step 9: Optimize code (placeholder - would need actual optimization logic)
    fi

    echo "Consecutive passes: $consecutive_passes/$REQUIRED_CONSECUTIVE" | tee -a "$results_file"
    echo "" | tee -a "$results_file"
done

echo "=== SUCCESS ===" | tee -a "$results_file"
echo "All $REQUIRED_CONSECUTIVE consecutive tests passed with <$TARGET_TOKENS tokens!" | tee -a "$results_file"
