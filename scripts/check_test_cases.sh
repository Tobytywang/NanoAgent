#!/usr/bin/env bash
# Check that test_cases.xlsx is updated when test files change
# Triggers on: new test files OR modified test files with new classes/methods

set -e

STAGED_TEST_FILES=$(git diff --cached --name-only --diff-filter=ACM -- 'tests/test_*.py' 'tests/**/test_*.py' 2>/dev/null || true)

if [ -z "$STAGED_TEST_FILES" ]; then
    exit 0
fi

# Check if test_cases.xlsx is also staged
XLSX_STAGED=$(git diff --cached --name-only -- 'tests/test_cases.xlsx' 2>/dev/null || true)

if [ -n "$XLSX_STAGED" ]; then
    exit 0
fi

# For new files (diff-filter=A), always require xlsx update
NEW_TEST_FILES=$(git diff --cached --name-only --diff-filter=A -- 'tests/test_*.py' 'tests/**/test_*.py' 2>/dev/null || true)
if [ -n "$NEW_TEST_FILES" ]; then
    echo "ERROR: New test file(s) staged but tests/test_cases.xlsx not updated:"
    echo "$NEW_TEST_FILES"
    echo ""
    echo "Please update tests/test_cases.xlsx with the new test cases."
    exit 1
fi

# For modified files (diff-filter=M), check if new test classes/methods were added
MODIFIED_TEST_FILES=$(git diff --cached --name-only --diff-filter=M -- 'tests/test_*.py' 'tests/**/test_*.py' 2>/dev/null || true)
if [ -n "$MODIFIED_TEST_FILES" ]; then
    HAS_NEW_TESTS=false
    for file in $MODIFIED_TEST_FILES; do
        # Check if diff contains new test class or method definitions
        NEW_CLASSES=$(git diff --cached --diff-filter=M -- "$file" 2>/dev/null | grep '^+.*class Test' || true)
        NEW_METHODS=$(git diff --cached --diff-filter=M -- "$file" 2>/dev/null | grep '^+.*def test_' || true)
        if [ -n "$NEW_CLASSES" ] || [ -n "$NEW_METHODS" ]; then
            HAS_NEW_TESTS=true
            echo "New test classes/methods detected in $file:"
            [ -n "$NEW_CLASSES" ] && echo "$NEW_CLASSES"
            [ -n "$NEW_METHODS" ] && echo "$NEW_METHODS"
        fi
    done

    if [ "$HAS_NEW_TESTS" = true ]; then
        echo ""
        echo "ERROR: New test classes/methods added but tests/test_cases.xlsx not updated."
        echo "Please update tests/test_cases.xlsx with the new test cases."
        exit 1
    fi
fi

exit 0
