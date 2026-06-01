#!/bin/bash
# check_doc_updates.sh
# When schema.py has changes, check that related docs are also updated

set -e

SCHEMA_FILE="nano_agent/config/schema.py"
DOC_FILES=("docs/api.md" "docs/constraints.md" "docs/architecture.md")

# Check if schema.py is in staged files
STAGED_SCHEMA=$(git diff --cached --name-only | grep -F "$SCHEMA_FILE" || true)

if [ -z "$STAGED_SCHEMA" ]; then
    # schema.py not changed, skip check
    exit 0
fi

# schema.py has changes - check if any docs are also staged
MISSING_DOCS=()
for doc in "${DOC_FILES[@]}"; do
    STAGED_DOC=$(git diff --cached --name-only | grep -F "$doc" || true)
    if [ -z "$STAGED_DOC" ]; then
        MISSING_DOCS+=("$doc")
    fi
done

if [ ${#MISSING_DOCS[@]} -gt 0 ]; then
    echo "❌ schema.py was modified but the following docs were not updated:"
    for doc in "${MISSING_DOCS[@]}"; do
        echo "   - $doc"
    done
    echo "   Fix: update the relevant docs and stage them with 'git add'"
    exit 1
fi

echo "✅ Documentation update check passed"
exit 0
