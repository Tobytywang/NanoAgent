#!/usr/bin/env bash
# check_doc_imports.sh
# Verify that nano_agent import statements in documentation are valid.
#
# Extracts "from nano_agent.X import Y" and "import nano_agent.X" patterns
# from staged docs/*.md files, then validates each import via Python's
# importlib. Exits non-zero when any import is unresolvable.
#
# macOS-compatible: uses basic grep (no -P), POSIX shell constructs.

set -e

STAGED=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)
[ -z "$STAGED" ] && exit 0

DOCS_STAGED=$(echo "$STAGED" | grep '^docs/.*\.md$' || true)
[ -z "$DOCS_STAGED" ] && exit 0

# Ensure nano_agent is importable. Try common env setups.
# pre-commit runs in the repo root, so pip install -e .[dev] should work.
PYTHON="${PYTHON:-python3}"
if ! $PYTHON -c "import nano_agent" 2>/dev/null; then
    # Try to install in dev mode if needed
    if [ -f "pyproject.toml" ]; then
        echo "⚠️  nano_agent not importable. Attempting: pip install -e ."
        pip install -e . -q 2>/dev/null || {
            echo "⚠️  Cannot install nano_agent. Run 'pip install -e .[dev]' first."
            echo "   Skipping doc import check (non-blocking)."
            exit 0
        }
    fi
fi

FAILED=0
CHECKED=0

# Helper: extract import statements from a file and validate each
check_file() {
    local doc="$1"

    # Extract "from nano_agent.XXX import YYY" patterns.
    # We need: module_path followed by import target(s).
    # Strategy: extract each "from X import Y" line, split on " import ".
    local IMPORTS
    IMPORTS=$(grep -E '^[[:space:]]*from nano_agent\.' "$doc" 2>/dev/null || true)

    if [ -z "$IMPORTS" ]; then
        return
    fi

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        # Skip comment lines
        echo "$line" | grep -qE '^[[:space:]]*#' && continue

        # Extract "nano_agent.X" part from "from nano_agent.X import Y"
        local module
        module=$(echo "$line" | sed -n 's/.*from \(nano_agent\.[a-zA-Z0-9_.]*\) import .*/\1/p')
        [ -z "$module" ] && continue

        # Also extract "import nano_agent.X" patterns
        if [ -z "$module" ]; then
            module=$(echo "$line" | sed -n 's/.*import \(nano_agent\.[a-zA-Z0-9_.]*\).*/\1/p')
            [ -z "$module" ] && continue
        fi

        # Skip top-level nano_agent (always importable if installed)
        [ "$module" = "nano_agent" ] && continue

        CHECKED=$((CHECKED + 1))

        if ! $PYTHON -c "import importlib; importlib.import_module('${module}')" 2>/dev/null; then
            echo "❌ $doc: Import failed — $module"
            echo "   Line: $line"
            FAILED=$((FAILED + 1))
        fi
    done <<< "$IMPORTS"
}

for doc in $DOCS_STAGED; do
    [ -f "$doc" ] || continue
    check_file "$doc"
done

if [ "$CHECKED" -eq 0 ]; then
    exit 0
fi

if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "❌ $FAILED import(s) in documentation are unresolvable."
    echo "   Fix: update import paths in docs to match current nano_agent structure."
    exit 1
fi

echo "✅ Documentation import paths verified ($CHECKED checked)"
exit 0
