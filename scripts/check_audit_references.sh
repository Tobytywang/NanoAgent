#!/usr/bin/env bash
# check_audit_references.sh
# When agent-control-audit.md is staged, verify that code references
# (backtick-wrapped identifiers like `ClassName.method()` and `file.py`)
# point to real symbols in the nano_agent/ codebase.
#
# This catches fictional class names, non-existent files, and stale
# method references that broke after refactors.
#
# WARNING only — many references are concept names rather than literal
# code identifiers, so we flag mismatches but don't block the commit.
# EXCEPTION: a .py file reference that doesn't exist IS a hard block.
#
# Whitelist (KNOWN_CONCEPTS): terms that look like code refs but are
# actually architectural concepts or planned features.

set -e

STAGED=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)
[ -z "$STAGED" ] && exit 0

AUDIT_STAGED=$(echo "$STAGED" | grep 'docs/agent-control-audit.md' || true)
[ -z "$AUDIT_STAGED" ] && exit 0

# Architectural concepts that are NOT literal code identifiers
KNOWN_CONCEPTS="\
SubTask|decompose|schedule|execute|verify|complete|blocked|adjust_dependencies|\
clarification|conversational|tool_call|planning|dangerous|early stop|continuous decline|\
blacklist|whitelist|topological|middleware|Middleware|ToolMiddleware|\
SensitiveOutputMiddleware|HarmfulContentMiddleware|/middleware.py|auto_plan.py|\
/sandbox.py|undo_all"

MISSING_FILES=0
MISSING_SYMBOLS=0

# Check .py file references (e.g. `xxx.py`)
check_file_refs() {
    local FILE_REFS
    FILE_REFS=$(grep -oE '`[a-zA-Z0-9_/.-]+\.py`' "docs/agent-control-audit.md" 2>/dev/null | tr -d '`' | sort -u || true)

    for ref in $FILE_REFS; do
        [ -z "$ref" ] && continue
        # Skip known concept files
        echo "$ref" | grep -qE "$KNOWN_CONCEPTS" 2>/dev/null && continue

        # Check relative to nano_agent/ (most common form)
        local base_name
        base_name=$(basename "$ref" .py)
        if ! find nano_agent/ -name "${base_name}.py" 2>/dev/null | grep -q . ; then
            # Try without nano_agent/ prefix
            if [ ! -f "$ref" ] && [ ! -f "nano_agent/$ref" ]; then
                echo "❌ audit.md references non-existent file: $ref"
                MISSING_FILES=$((MISSING_FILES + 1))
            fi
        fi
    done
}

# Check class references (PascalCase identifiers in backticks)
check_class_refs() {
    local CLASS_REFS
    # Extract PascalCase class names from backtick-quoted code spans
    # Pattern: `ClassName` or `ClassName.method()` or `ClassName.attr`
    CLASS_REFS=$(grep -oE '`[A-Z][a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)?(\()?[^`]*`' "docs/agent-control-audit.md" 2>/dev/null | tr -d '`()' | sort -u || true)

    for ref in $CLASS_REFS; do
        [ -z "$ref" ] && continue
        # Skip known concepts
        echo "$ref" | grep -qE "$KNOWN_CONCEPTS" 2>/dev/null && continue

        local class_name="${ref%%.*}"
        # Search for class definition in nano_agent/
        if ! grep -rq "^class ${class_name}\b" nano_agent/ 2>/dev/null; then
            # Also check for re-exports or aliases
            if ! grep -rq "\b${class_name}\b" nano_agent/ 2>/dev/null; then
                echo "⚠️  audit.md references unknown class: \`$ref\`"
                MISSING_SYMBOLS=$((MISSING_SYMBOLS + 1))
            fi
        fi
    done
}

check_file_refs
check_class_refs

if [ "$MISSING_FILES" -gt 0 ]; then
    echo ""
    echo "❌ $MISSING_FILES file reference(s) in audit.md point to non-existent files."
    echo "   Fix: update the audit document to reference correct file paths."
    exit 1
fi

if [ "$MISSING_SYMBOLS" -gt 0 ]; then
    echo ""
    echo "⚠️  $MISSING_SYMBOLS symbol(s) in audit.md not found in codebase."
    echo "   These may be concept names rather than literal identifiers."
    echo "   Verify manually and add to KNOWN_CONCEPTS if they are intentional."
    exit 0
fi

echo "✅ audit.md code references verified"
exit 0
