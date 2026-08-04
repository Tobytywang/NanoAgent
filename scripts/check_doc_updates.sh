#!/usr/bin/env bash
# check_doc_updates.sh
# When nano_agent/** code changes, check that related docs are also staged.
#
# Mapping-driven (scan-based): each code area routes to the docs it affects.
# Previously this was a hard-coded whitelist (schema.py + 3 agent/memory
# files only); now every nano_agent/ sub-module change is covered.
#
# Add/change a rule by editing the parallel RULE_PATHS / RULE_DOCS arrays.
# Note: parallel arrays are used instead of associative arrays to stay
# compatible with macOS bash 3.2 (no `declare -A` support).

set -e

RULE_PATHS=(
  "nano_agent/config/"
  "nano_agent/agent/"
  "nano_agent/memory/"
  "nano_agent/llm/"
  "nano_agent/tools/"
  "nano_agent/cli/"
  "nano_agent/monitoring/"
  "nano_agent/core/"
  "nano_agent/skills/"
)

# Space-separated docs, same index as RULE_PATHS
RULE_DOCS=(
  "docs/api.md docs/constraints.md docs/architecture.md"
  "docs/api.md docs/tutorial.md"
  "docs/api.md docs/tutorial.md"
  "docs/api.md"
  "docs/api.md"
  "docs/api.md docs/tutorial.md"
  "docs/api.md"
  "docs/api.md docs/architecture.md"
  "docs/api.md docs/skill-development.md"
)

STAGED=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)
[ -z "$STAGED" ] && exit 0

MISSING_DOCS=()

for i in "${!RULE_PATHS[@]}"; do
    prefix="${RULE_PATHS[$i]}"
    AREA_CHANGED=$(echo "$STAGED" | grep -F "$prefix" | grep -v '__pycache__' || true)
    [ -z "$AREA_CHANGED" ] && continue

    for doc in ${RULE_DOCS[$i]}; do
        STAGED_DOC=$(echo "$STAGED" | grep -F "$doc" || true)
        if [ -z "$STAGED_DOC" ]; then
            MISSING_DOCS+=("$doc (triggered by $prefix)")
        fi
    done
done

if [ ${#MISSING_DOCS[@]} -gt 0 ]; then
    # De-duplicate while keeping order
    UNIQUE_DOCS=()
    for entry in "${MISSING_DOCS[@]}"; do
        if ! echo "${UNIQUE_DOCS[*]}" | grep -qF "$entry"; then
            UNIQUE_DOCS+=("$entry")
        fi
    done

    echo "❌ Core files modified but docs not updated:"
    for entry in "${UNIQUE_DOCS[@]}"; do
        echo "   - $entry"
    done
    echo "   Fix: update the relevant docs and stage them with 'git add'"
    exit 1
fi

echo "✅ Documentation update check passed"
exit 0
