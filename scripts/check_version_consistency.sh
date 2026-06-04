#!/bin/bash
# check_version_consistency.sh
# 1. Verify that version numbers in pyproject.toml and nano_agent/__init__.py match
# 2. Verify that ROADMAP.md marks the current version as complete (✅)

set -e

PYPROJECT="pyproject.toml"
INIT_FILE="nano_agent/__init__.py"
ROADMAP="ROADMAP.md"

# --- Check 1: pyproject.toml vs __init__.py ---

if [ ! -f "$PYPROJECT" ]; then
    echo "❌ $PYPROJECT not found"
    exit 1
fi

if [ ! -f "$INIT_FILE" ]; then
    echo "❌ $INIT_FILE not found"
    exit 1
fi

PY_VER=$(grep '^version' "$PYPROJECT" | head -1 | sed 's/version *= *["'\'']\([^"'\'']*\)["'\'']/\1/')
INIT_VER=$(grep '__version__' "$INIT_FILE" | sed 's/.*__version__ *= *["'\'']\([^"'\'']*\)["'\'']/\1/')

if [ -z "$PY_VER" ]; then
    echo "❌ Could not extract version from $PYPROJECT"
    exit 1
fi

if [ -z "$INIT_VER" ]; then
    echo "❌ Could not extract version from $INIT_FILE"
    exit 1
fi

if [ "$PY_VER" != "$INIT_VER" ]; then
    echo "❌ Version mismatch: pyproject.toml=$PY_VER, __init__.py=$INIT_VER"
    echo "   Fix: update both files to the same version"
    exit 1
fi

echo "✅ Version consistent: $PY_VER"

# --- Check 2: ROADMAP.md version mark ---

if [ ! -f "$ROADMAP" ]; then
    exit 0
fi

VERSION_LINE=$(grep -E "^### v${PY_VER}" "$ROADMAP" || true)

if [ -z "$VERSION_LINE" ]; then
    echo "⚠️  Version $PY_VER not found in ROADMAP.md"
    echo "   If this is a new release, add a section to ROADMAP.md"
    exit 0
fi

if echo "$VERSION_LINE" | grep -q '✅'; then
    echo "✅ ROADMAP version marked complete: $VERSION_LINE"
else
    echo "❌ Version $PY_VER in ROADMAP.md is NOT marked as complete (missing ✅)"
    echo "   Found: $VERSION_LINE"
    echo "   Fix: Add ✅ to the version heading"
    echo "   Example: ### v${PY_VER} - 描述 ✅"
    exit 1
fi

exit 0
