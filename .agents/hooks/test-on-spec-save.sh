#!/bin/bash
# Runs uv run pytest on the changed test file after every Edit or Write to a test_*.py file.
# ==============================================================================
# Script: test-on-spec-save.sh
#
# What it does:
#   Executes an isolated, highly verbose test run using uv run pytest on ONLY the
#   specific test file that was just modified or saved.
#
# Key Features & Robustness:
#   1. Strict Path Matching: Uses an optimized regular expression to guarantee
#      it matches 'test_*.py' files specifically, preventing false positives
#      from folder names containing the word "test".
#   2. Root-Safe Directory Navigation: Uses Git to discover the repository's
#      top-level root directory and changes to it (`cd`). This completely fixes
#      any `ModuleNotFoundError` issues by normalizing Python's search paths.
#   3. uv Invocation (`uv run pytest`): Ensures that pytest uses the project's
#      managed environment regardless of shell PATH.
#   4. Verbose Failure Summaries (`-v`): Prints every executed test function's
#      individual name and outcome so the Agent has instant, structured context on
#      exactly which assertion needs to be fixed.

# test:
# target test file: scbatch/pp/tests/test_batch_correction.py

# cli command to test:
# echo '{"tool_input": {"file_path": "scbatch/pp/tests/test_batch_correction.py"}}' | ./test-on-spec-save.sh
# ==============================================================================

INPUT=$(cat)
PROJECT_ROOT=$(git rev-parse --show-toplevel) || exit 0
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PROJECT_ROOT/.cache/uv}"
FILE_PATHS=$(
  {
    printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null
    printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null \
      | sed -nE 's/^\*\*\* (Update|Add) File: (.+)$/\2/p'
  } | sort -u
)

# Guard: Exit if the file path is blank or the file no longer exists on disk
[ -z "$FILE_PATHS" ] && exit 0

while IFS= read -r FILE_PATH; do
# Guard: Confirm the modified file is an actual test file starting with 'test_'
# (^|/) ensures 'test_' is either at the beginning of the path or right after a slash
[[ ! "$FILE_PATH" =~ (^|/)test_[^/]+\.py$ ]] && continue

if [[ "$FILE_PATH" != /* ]]; then
  if [[ -f "$FILE_PATH" ]]; then
    FILE_DIRECTORY=$(cd "$(dirname "$FILE_PATH")" && pwd) || continue
    FILE_PATH="$FILE_DIRECTORY/$(basename "$FILE_PATH")"
  else
    REPOSITORY_ROOT=$(git rev-parse --show-toplevel) || continue
    FILE_PATH="$REPOSITORY_ROOT/$FILE_PATH"
  fi
fi
[ ! -f "$FILE_PATH" ] && continue

echo "Running tests: $FILE_PATH"

# 1. Navigate to the top-level directory of the Git repo for stable path resolution
# 2. Run uv run pytest (resolves the project's venv regardless of shell PATH) in verbose mode
cd "$PROJECT_ROOT" || exit 1
OUTPUT=$(uv run pytest "$FILE_PATH" -v 2>&1)
STATUS=$?

# Exit code 2 is what makes the Agent surface stderr back to the Agent automatically
# (PostToolUse: exit 0 -> stdout only goes to the debug log; exit 2 -> stderr is
# shown to the Agent next to the tool result). Plain non-zero (e.g. pytest's exit 1)
# only reaches the human transcript, not the Agent.
if [ "$STATUS" -ne 0 ]; then
  echo "$OUTPUT" >&2
  exit 2
fi

echo "$OUTPUT"
done <<< "$FILE_PATHS"
exit 0
