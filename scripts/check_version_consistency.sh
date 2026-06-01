#!/bin/bash
# check_version_consistency.sh
# Verify that version numbers in pyproject.toml and nano_agent/__init__.py match

set -e

PYPROJECT="pyproject.toml"
INIT_FILE="nano_agent/__init__.py"

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
exit 0
