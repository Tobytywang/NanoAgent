#!/bin/bash
# check_config_chain.sh
# When schema.py adds new fields, check that loader.py parse+save are also updated.
#
# Strategy: Compare staged changes to detect NEW fields added to schema.py,
# then verify those new fields appear in loader.py's parse and save functions.

set -e

SCHEMA_FILE="nano_agent/config/schema.py"
LOADER_FILE="nano_agent/config/loader.py"

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

# Check each new field against loader.py
MISSING_PARSE=()
MISSING_SAVE=()

for field in "${FIELD_NAMES[@]}"; do
    # Check if field appears in any parse function in loader.py
    if ! grep -q "\"${field}\"" "$LOADER_FILE" 2>/dev/null; then
        # Also check staged version of loader.py
        LOADER_DIFF=$(git diff --cached -- "$LOADER_FILE" | grep "^+" | grep "\"${field}\"" || true)
        if [ -z "$LOADER_DIFF" ]; then
            MISSING_PARSE+=("$field")
        fi
    fi

    # Check if field appears in save() serialization in loader.py
    # save() uses config.section.field_name pattern
    if ! grep -q "\\.${field}" "$LOADER_FILE" 2>/dev/null; then
        LOADER_SAVE_DIFF=$(git diff --cached -- "$LOADER_FILE" | grep "^+" | grep "\\.${field}" || true)
        if [ -z "$LOADER_SAVE_DIFF" ]; then
            MISSING_SAVE+=("$field")
        fi
    fi
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

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo "❌ Config chain incomplete - new fields in schema.py not in loader.py:"
    for err in "${ERRORS[@]}"; do
        echo "   $err"
    done
    echo "   Fix: add the fields to _parse_*_config() and save() in $LOADER_FILE"
    exit 1
fi

echo "✅ Config chain completeness check passed"
exit 0
