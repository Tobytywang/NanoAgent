#!/bin/bash
# check_interface_implementation.sh
# When a base class adds new @abstractmethod, check that all subclasses implement it
# Triggers on: changes to base class files

set -e

# Only run when base class files have staged changes
STAGED_BASES=$(git diff --cached --name-only | grep -E '(agent/base\.py|llm/base\.py|memory/base\.py|tools/base\.py|memory/storage/base\.py|llm/embedding\.py)' || true)

if [ -z "$STAGED_BASES" ]; then
    exit 0
fi

ERRORS=()

check_base() {
    local base_file="$1"
    shift
    local subclass_files="$@"

    # Extract newly added @abstractmethod names from the diff
    # Pattern: +    @abstractmethod followed by +    def method_name
    NEW_METHODS=$(git diff --cached -- "$base_file" | grep -A1 '^+.*@abstractmethod' | grep '^+.*def ' | sed 's/^+.*def \([a-zA-Z_][a-zA-Z0-9_]*\).*/\1/' || true)

    if [ -z "$NEW_METHODS" ]; then
        return
    fi

    for method in $NEW_METHODS; do
        for subclass in $subclass_files; do
            # Skip if subclass is the same file as base
            if [ "$subclass" = "$base_file" ]; then
                continue
            fi

            if [ ! -f "$subclass" ]; then
                continue
            fi

            # Check if subclass implements the method
            METHOD_IMPL=$(grep -E "^\s+def ${method}\s*\(" "$subclass" 2>/dev/null || true)
            STAGED_IMPL=$(git diff --cached -- "$subclass" 2>/dev/null | grep "^+.*def ${method}\s*(" || true)

            if [ -z "$METHOD_IMPL" ] && [ -z "$STAGED_IMPL" ]; then
                BASE_NAME=$(basename "$base_file" .py)
                SUBCLASS_NAME=$(basename "$subclass" .py)
                ERRORS+=("$SUBCLASS_NAME missing implementation of ${method}() from ${BASE_NAME}")
            fi
        done
    done
}

# Check each changed base class
for base in $STAGED_BASES; do
    case "$base" in
        nano_agent/agent/base.py)
            check_base "$base" "nano_agent/agent/react.py"
            ;;
        nano_agent/llm/base.py)
            check_base "$base" "nano_agent/llm/ollama.py nano_agent/llm/openai_compatible.py nano_agent/llm/anthropic.py"
            ;;
        nano_agent/memory/base.py)
            check_base "$base" "nano_agent/memory/short_term.py nano_agent/memory/persistent.py nano_agent/memory/hybrid.py"
            ;;
        nano_agent/tools/base.py)
            check_base "$base" "nano_agent/tools/builtin/file_ops.py nano_agent/tools/builtin/memory_tools.py nano_agent/tools/builtin/monitoring_tools.py nano_agent/tools/builtin/plan_tools.py nano_agent/tools/builtin/python_executor.py nano_agent/tools/builtin/shell.py nano_agent/tools/builtin/web_search.py"
            ;;
        nano_agent/memory/storage/base.py)
            check_base "$base" "nano_agent/memory/storage/file_storage.py nano_agent/memory/storage/sqlite_storage.py"
            ;;
        nano_agent/llm/embedding.py)
            # EmbeddingClient subclasses are in the same file, skip
            ;;
    esac
done

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo "❌ Subclasses missing newly added abstract method implementations:"
    for err in "${ERRORS[@]}"; do
        echo "   - $err"
    done
    echo "   Fix: Implement the missing methods in all subclasses"
    echo "   See: CLAUDE.md - 接口扩展检查清单"
    exit 1
fi

echo "✅ All subclasses implement new abstract methods"
exit 0
