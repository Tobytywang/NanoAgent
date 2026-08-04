#!/usr/bin/env bash
# Check that BUGLIST.md is considered when code and tests change together.
#
# Trigger: staged changes in BOTH nano_agent/** and tests/** (typical bug-fix
# pattern: fix code + add regression test).
# Behavior: WARNING only, never blocks — the same file combination also
# matches normal feature work, so blocking would break the daily flow.
# pre-commit runs before the commit message exists, so we cannot look at
# "fix: ..." messages; file-combination matching is the only signal here.

set -e

STAGED=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)
[ -z "$STAGED" ] && exit 0

STAGED_CODE=$(echo "$STAGED" | grep '^nano_agent/' | grep -v '__pycache__' || true)
STAGED_TESTS=$(echo "$STAGED" | grep '^tests/test_.*\.py$' || true)

# Code + tests changed together: the bug-fix pattern
if [ -n "$STAGED_CODE" ] && [ -n "$STAGED_TESTS" ]; then
    STAGED_BUGLIST=$(echo "$STAGED" | grep -F 'BUGLIST.md' || true)
    if [ -z "$STAGED_BUGLIST" ]; then
        echo ""
        echo "⚠️  Code + test changes detected, but BUGLIST.md is not updated."
        echo "   If this change fixes a bug, add a BUGLIST.md entry (see BUGLIST 格式说明)."
        echo "   If this is a normal feature, ignore this reminder."
        echo ""
    fi
fi

exit 0
