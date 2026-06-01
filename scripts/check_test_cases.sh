#!/bin/bash
# check_test_cases.sh
# When new test files are added, check that test_cases.xlsx is also updated

set -e

XLSX_FILE="tests/test_cases.xlsx"

# Find newly staged test files (files that didn't exist in HEAD)
NEW_TEST_FILES=()
for file in $(git diff --cached --name-only --diff-filter=A -- 'tests/test_*.py' 2>/dev/null); do
    NEW_TEST_FILES+=("$file")
done

if [ ${#NEW_TEST_FILES[@]} -eq 0 ]; then
    # No new test files, skip check
    exit 0
fi

# New test files found - check if test_cases.xlsx is also staged
STAGED_XLSX=$(git diff --cached --name-only | grep -F "$XLSX_FILE" || true)

if [ -z "$STAGED_XLSX" ]; then
    echo "❌ New test files were added but $XLSX_FILE was not updated:"
    for file in "${NEW_TEST_FILES[@]}"; do
        echo "   - $file"
    done
    echo "   Fix: add test cases to $XLSX_FILE and stage it with 'git add'"
    exit 1
fi

echo "✅ Test cases update check passed"
exit 0
