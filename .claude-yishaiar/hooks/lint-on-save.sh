#!/bin/bash
# Runs Ruff's linter on only the changed file after every Edit or Write.
# If lint fails, Claude will see the errors and fix them.
# ==============================================================================
# Script: lint-on-save.sh
# 
# What it does:
#   Runs Ruff's linter on the saved Python file or Markdown document to
#   surface code quality issues, logical bugs, and unused imports.
#
# How it handles Markdown (.md) files:
#   Ruff does NOT lint your English text. Instead, it extracts blocks of code
#   wrapped inside \`\`\`python ... \`\`\` fences and treats them as isolated 
#   Python code snippets. It validates them to ensure documentation examples 
#   are free of syntax errors, broken logic, typos, or stale/unused imports.
#
# Crucial Execution Notes:
#   1. NO '--fix' Flag: Per constraints, it only surfaces/raises errors so that 
#      Claude can observe and fix them in the context window.
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
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Exit if no path, if the file doesn't exist, or if it isn't an extension Ruff checks
[ -z "$FILE_PATH" ] && exit 0
[ ! -f "$FILE_PATH" ] && exit 0
[[ ! "$FILE_PATH" =~ \.(py|md)$ ]] && exit 0

# grounding context for claude
echo "Linting $FILE_PATH"

# Run ruff check. We explicitly omit '--fix' so it only surfaces errors.
# Invoked via uv so it resolves regardless of the calling shell's PATH.
OUTPUT=$(uv run --project "$(git rev-parse --show-toplevel)" ruff check "$FILE_PATH" 2>&1)
STATUS=$?

# Exit code 2 is what makes Claude Code surface stderr back to Claude automatically
# (PostToolUse: exit 0 -> stdout only goes to the debug log; exit 2 -> stderr is
# shown to Claude next to the tool result). Plain non-zero (e.g. ruff's exit 1)
# only reaches the human transcript, not Claude.
if [ "$STATUS" -ne 0 ]; then
  echo "$OUTPUT" >&2
  exit 2
fi

echo "$OUTPUT"
exit 0