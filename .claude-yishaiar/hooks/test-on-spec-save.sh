#!/bin/bash
# Runs pytest on the changed test file after every Edit or Write to a test_*.py file.
# ==============================================================================
# Script: test-on-spec-save.sh
# 
# What it does:
#   Executes an isolated, highly verbose test run using pytest on ONLY the 
#   specific test file that was just modified or saved.
#
# Key Features & Robustness:
#   1. Strict Path Matching: Uses an optimized regular expression to guarantee 
#      it matches 'test_*.py' files specifically, preventing false positives 
#      from folder names containing the word "test".
#   2. Root-Safe Directory Navigation: Uses Git to discover the repository's 
#      top-level root directory and changes to it (`cd`). This completely fixes 
#      any `ModuleNotFoundError` issues by normalizing Python's search paths.
#   3. Python Module Invocation (`python -m pytest`): Ensures that pytest uses 
#      the correct local workspace context and explicitly adds the repository 
#      root to `sys.path`.
#   4. Verbose Failure Summaries (`-v`): Prints every executed test function's 
#      individual name and outcome so Claude has instant, structured context on 
#      exactly which assertion needs to be fixed.

# test:
# target test file: /Users/yishai-heka/repos/ML/apps/contactability/tests/test_endpoints.py

# cli command to test:
# echo '{"tool_input": {"file_path": "/Users/yishai-heka/repos/ML/apps/contactability/tests/test_endpoints.py"}}' | ./test-on-spec-save.sh
# ==============================================================================

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Guard: Exit if the file path is blank or the file no longer exists on disk
[ -z "$FILE_PATH" ] && exit 0
[ ! -f "$FILE_PATH" ] && exit 0

# Guard: Confirm the modified file is an actual test file starting with 'test_'
# (^|/) ensures 'test_' is either at the beginning of the path or right after a slash
[[ ! "$FILE_PATH" =~ (^|/)test_[^/]+\.py$ ]] && exit 0

echo "Running tests: $FILE_PATH"

# 1. Navigate to the top-level directory of the Git repo for stable path resolution
# 2. Run pytest via uv (resolves the project's venv regardless of shell PATH) in verbose mode
cd "$(git rev-parse --show-toplevel)" || exit 1
OUTPUT=$(uv run pytest "$FILE_PATH" -v 2>&1)
STATUS=$?

# Exit code 2 is what makes Claude Code surface stderr back to Claude automatically
# (PostToolUse: exit 0 -> stdout only goes to the debug log; exit 2 -> stderr is
# shown to Claude next to the tool result). Plain non-zero (e.g. pytest's exit 1)
# only reaches the human transcript, not Claude.
if [ "$STATUS" -ne 0 ]; then
  echo "$OUTPUT" >&2
  exit 2
fi

echo "$OUTPUT"
exit 0