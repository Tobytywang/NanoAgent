#!/bin/bash
# check_doc_updates.sh
# When core files change, check that related docs are also updated
# Triggers on: schema.py, agent/*.py, memory/*.py changes

set -e

# Core files that require doc updates
SCHEMA_FILE="nano_agent/config/schema.py"
AGENT_FILES=("nano_agent/agent/base.py" "nano_agent/agent/react.py" "nano_agent/agent/orchestrator.py")
MEMORY_FILES=("nano_agent/memory/base.py" "nano_agent/memory/short_term.py" "nano_agent/memory/hybrid.py")

# Doc files to check based on trigger type
SCHEMA_DOCS=("docs/api.md" "docs/constraints.md" "docs/architecture.md")
FEATURE_DOCS=("docs/api.md" "docs/tutorial.md")

# Check what type of files changed
STAGED_SCHEMA=$(git diff --cached --name-only | grep -F "$SCHEMA_FILE" || true)
STAGED_AGENT=$(git diff --cached --name-only | grep -Ff <(printf '%s\n' "${AGENT_FILES[@]}") || true)
STAGED_MEMORY=$(git diff --cached --name-only | grep -Ff <(printf '%s\n' "${MEMORY_FILES[@]}") || true)

# If nothing relevant changed, skip
if [ -z "$STAGED_SCHEMA" ] && [ -z "$STAGED_AGENT" ] && [ -z "$STAGED_MEMORY" ]; then
    exit 0
fi

# Determine which docs to check based on what changed
MISSING_DOCS=()

if [ -n "$STAGED_SCHEMA" ]; then
    # schema.py changed - check all schema-related docs
    for doc in "${SCHEMA_DOCS[@]}"; do
        STAGED_DOC=$(git diff --cached --name-only | grep -F "$doc" || true)
        if [ -z "$STAGED_DOC" ]; then
            MISSING_DOCS+=("$doc (triggered by $SCHEMA_FILE)")
        fi
    done
fi

if [ -n "$STAGED_AGENT" ] || [ -n "$STAGED_MEMORY" ]; then
    # Agent or memory files changed - check feature docs
    for doc in "${FEATURE_DOCS[@]}"; do
        STAGED_DOC=$(git diff --cached --name-only | grep -F "$doc" || true)
        if [ -z "$STAGED_DOC" ]; then
            # Avoid duplicate entries
            if ! echo "${MISSING_DOCS[*]}" | grep -q "$doc"; then
                TRIGGER=$(echo "$STAGED_AGENT $STAGED_MEMORY" | head -1)
                MISSING_DOCS+=("$doc (triggered by $TRIGGER)")
            fi
        fi
    done
fi

if [ ${#MISSING_DOCS[@]} -gt 0 ]; then
    echo "❌ Core files modified but docs not updated:"
    for doc in "${MISSING_DOCS[@]}"; do
        echo "   - $doc"
    done
    echo "   Fix: update the relevant docs and stage them with 'git add'"
    exit 1
fi

echo "✅ Documentation update check passed"
exit 0
