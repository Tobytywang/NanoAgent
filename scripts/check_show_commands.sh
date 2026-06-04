#!/bin/bash
# check_show_commands.sh
# Check that interactive commands used in main.py have constant definitions in constants.py
# Triggers on: changes to main.py or constants.py

set -e

MAIN_FILE="nano_agent/cli/main.py"
CONSTANTS_FILE="nano_agent/cli/constants.py"

# Only run when relevant files change
STAGED_MAIN=$(git diff --cached --name-only | grep -F "$MAIN_FILE" || true)
STAGED_CONSTANTS=$(git diff --cached --name-only | grep -F "$CONSTANTS_FILE" || true)

if [ -z "$STAGED_MAIN" ] && [ -z "$STAGED_CONSTANTS" ]; then
    exit 0
fi

if [ ! -f "$MAIN_FILE" ]; then
    exit 0
fi

if [ ! -f "$CONSTANTS_FILE" ]; then
    exit 0
fi

# Extract command strings used in main.py conditionals
# Matches patterns like: user_input.lower() == "/xxx" or user_input.lower().startswith("/xxx")
# and: user_input == "/xxx" or user_input.startswith("/xxx")
USED_COMMANDS=$(grep -oE '(==|startswith)\s*\(\s*["'"'"'](/[a-z]+)["'"'"']' "$MAIN_FILE" | sed "s/.*['\"]\\(.*\\)['\"].*/\\1/" | sort -u || true)

if [ -z "$USED_COMMANDS" ]; then
    exit 0
fi

# Check each command string against constants.py
MISSING=()

for cmd in $USED_COMMANDS; do
    # Extract the constant name (e.g., /history -> HISTORY, /stats -> STATS)
    # Strip leading / and convert to UPPER_SNAKE_CASE
    CMD_NAME=$(echo "$cmd" | sed 's/^\///' | tr '[:lower:]' '[:upper:]')

    # Check if the command string literal appears in constants.py
    # This handles both string assignments and set memberships
    CONSTANT_FOUND=$(grep -F "\"$cmd\"" "$CONSTANTS_FILE" || true)
    CONSTANT_FOUND_ALT=$(grep -F "'$cmd'" "$CONSTANTS_FILE" || true)

    if [ -z "$CONSTANT_FOUND" ] && [ -z "$CONSTANT_FOUND_ALT" ]; then
        MISSING+=("$cmd -> Commands.$CMD_NAME")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "❌ Commands in main.py missing constant definitions in constants.py:"
    for missing in "${MISSING[@]}"; do
        echo "   - $missing"
    done
    echo "   Fix: Add the missing constants to $CONSTANTS_FILE"
    exit 1
fi

echo "✅ All commands have corresponding constants"
exit 0
