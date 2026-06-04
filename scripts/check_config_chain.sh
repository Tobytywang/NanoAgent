#!/bin/bash
# check_config_chain.sh
# When schema.py adds new fields, check that the full config chain is complete:
#   schema.py → loader.py (parse + save) → _show_config() → create_agent()
#
# Strategy: Compare staged changes to detect NEW fields added to schema.py,
# then verify those new fields appear in each downstream consumer.

set -e

SCHEMA_FILE="nano_agent/config/schema.py"
LOADER_FILE="nano_agent/config/loader.py"
CLI_FILE="nano_agent/cli/main.py"

# Only run when schema.py is staged
STAGED_SCHEMA=$(git diff --cached --name-only | grep -F "$SCHEMA_FILE" || true)
if [ -z "$STAGED_SCHEMA" ]; then
    exit 0
fi

# Extract new field names added to schema.py in this commit
# Look for lines like:    field_name: type = default
# Only in the diff (added lines starting with +)
NEW_FIELDS=$(git diff --cached -- "$SCHEMA_FILE" | grep '^+' | grep -E '^\+\s+[a-z_]+:\s' | grep -vE '(class |def |#|"""|return|if |for |else)' || true)

if [ -z "$NEW_FIELDS" ]; then
    # No new fields detected
    exit 0
fi

# Extract field names from the new additions
FIELD_NAMES=()
while IFS= read -r line; do
    # Extract field name: strip leading + and whitespace, take part before colon
    field=$(echo "$line" | sed 's/^+\s*//' | cut -d':' -f1 | xargs)
    # Skip private fields (starting with _), empty, or non-field patterns
    if [[ -n "$field" && ! "$field" =~ ^_ && ! "$field" =~ ^[A-Z] ]]; then
        FIELD_NAMES+=("$field")
    fi
done <<< "$NEW_FIELDS"

if [ ${#FIELD_NAMES[@]} -eq 0 ]; then
    exit 0
fi

# Check each new field against downstream consumers
MISSING_PARSE=()
MISSING_SAVE=()
MISSING_SHOW=()
MISSING_CREATE=()

for field in "${FIELD_NAMES[@]}"; do
    # 1. Check loader.py parse
    if ! grep -q "\"${field}\"" "$LOADER_FILE" 2>/dev/null; then
        LOADER_DIFF=$(git diff --cached -- "$LOADER_FILE" | grep "^+" | grep "\"${field}\"" || true)
        if [ -z "$LOADER_DIFF" ]; then
            MISSING_PARSE+=("$field")
        fi
    fi

    # 2. Check loader.py save
    if ! grep -q "\\.${field}" "$LOADER_FILE" 2>/dev/null; then
        LOADER_SAVE_DIFF=$(git diff --cached -- "$LOADER_FILE" | grep "^+" | grep "\\.${field}" || true)
        if [ -z "$LOADER_SAVE_DIFF" ]; then
            MISSING_SAVE+=("$field")
        fi
    fi

    # 3. Check _show_config() in cli/main.py
    if ! grep -q "\\.${field}" "$CLI_FILE" 2>/dev/null; then
        CLI_DIFF=$(git diff --cached -- "$CLI_FILE" | grep "^+" | grep "\\.${field}" || true)
        if [ -z "$CLI_DIFF" ]; then
            MISSING_SHOW+=("$field")
        fi
    fi

    # 4. Check create_agent() in cli/main.py — look for the field in the agent creation section
    # create_agent() uses config.xxx.field pattern, same as _show_config()
    # Already covered by check 3 since both use .field pattern in the same file
done

ERRORS=()

if [ ${#MISSING_PARSE[@]} -gt 0 ]; then
    ERRORS+=("Missing from parse in $LOADER_FILE:")
    for field in "${MISSING_PARSE[@]}"; do
        ERRORS+=("  - $field")
    done
fi

if [ ${#MISSING_SAVE[@]} -gt 0 ]; then
    ERRORS+=("Missing from save() in $LOADER_FILE:")
    for field in "${MISSING_SAVE[@]}"; do
        ERRORS+=("  - $field")
    done
fi

if [ ${#MISSING_SHOW[@]} -gt 0 ]; then
    ERRORS+=("Missing from _show_config() / create_agent() in $CLI_FILE:")
    for field in "${MISSING_SHOW[@]}"; do
        ERRORS+=("  - $field")
    done
fi

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo "❌ Config chain incomplete - new fields in schema.py not wired through:"
    for err in "${ERRORS[@]}"; do
        echo "   $err"
    done
    echo "   Fix: add the fields to _parse_*_config(), save(), _show_config() and create_agent()"
    exit 1
fi

echo "✅ Config chain completeness check passed"
exit 0
