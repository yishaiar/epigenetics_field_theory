#!/bin/bash
# Runs Ruff's linter on only the changed file after every Edit or Write.
# If lint fails, the Agent will see the errors and fix them.
# ==============================================================================
# Script: lint-on-save.sh
#
# What it does:
#   Runs Ruff's linter on saved Python files, Markdown documents, and Jupyter
#   notebook code cells to surface code quality issues and unused imports.
#
# How it handles Markdown (.md) files:
#   Ruff does NOT lint your English text. Instead, it extracts blocks of code
#   wrapped inside \`\`\`python ... \`\`\` fences and treats them as isolated
#   Python code snippets. It validates them to ensure documentation examples
#   are free of syntax errors, broken logic, typos, or stale/unused imports.
#
# How it handles Jupyter notebooks (.ipynb):
#   Ruff natively extracts and lints code cells while preserving notebook
#   structure. This is static analysis only, not notebook execution.
#
# Crucial Execution Notes:
#   1. NO '--fix' Flag: Per constraints, it only surfaces/raises errors so that
#      the Agent can observe and fix them in the context window.
#   2. NO Project-Mapping Block: Unlike Nx, Ruff natively traverses directory
#      trees upwards from the target file to locate local pyproject.toml
#      configurations automatically. No explicit 'if/elif' project maps are needed.


# test:
# save in file "test_ruff.py":
# def foo(a, b):
#     return a + b

# # 'x' is not defined, which will trigger a linting error!
# result = foo(x, 3)

#cli command to test:
#echo '{"tool_input": {"file_path": "test_ruff.py"}}' | ./lint-on-save.sh
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

# Exit if no path, if the file doesn't exist, or if it isn't an extension Ruff checks
[ -z "$FILE_PATHS" ] && exit 0

while IFS= read -r FILE_PATH; do
[[ ! "$FILE_PATH" =~ \.(py|md|ipynb)$ ]] && continue

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

# grounding context for the Agent
echo "Linting $FILE_PATH"

# Run ruff check. We explicitly omit '--fix' so it only surfaces errors.
# Invoked via uv so it resolves regardless of the calling shell's PATH.
OUTPUT=$(uv run --project "$PROJECT_ROOT" ruff check "$FILE_PATH" 2>&1)
STATUS=$?

# Exit code 2 is what makes the Agent surface stderr back to the Agent automatically
# (PostToolUse: exit 0 -> stdout only goes to the debug log; exit 2 -> stderr is
# shown to the Agent next to the tool result). Plain non-zero (e.g. ruff's exit 1)
# only reaches the human transcript, not the Agent.
if [ "$STATUS" -ne 0 ]; then
  echo "$OUTPUT" >&2
  exit 2
fi

echo "$OUTPUT"
done <<< "$FILE_PATHS"
exit 0
