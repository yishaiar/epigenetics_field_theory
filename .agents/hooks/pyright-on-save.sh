#!/bin/bash
# Runs basedpyright's type checker on only the changed file after every Edit or Write.
# If type checking fails, the Agent will see the errors and fix them.
# ==============================================================================
# Script: pyright-on-save.sh
#
# What it does:
#   Runs basedpyright (a strict-by-default fork of pyright) on the saved Python
#   file to surface type errors: wrong argument types, incompatible return
#   types, attribute access on the wrong type, unresolved imports, etc.
#
# Crucial Execution Notes:
#   1. Python only: this does NOT also run on .md files (there's no type information)
#   2. Single-file scope: only the saved file is checked, not the whole
#      project, to keep this fast enough to run on every save.
#   3. `include`/`exclude` in `[tool.pyright]` (pyproject.toml) don't apply
#      here — those only filter whole-project directory scans.


# test:
# save in file "test_pyright.py":
# def foo(a: int, b: int) -> int:
#     return a + b
# result = foo("x", 3)  # wrong type passed for 'a'

#cli command to test:
#echo '{"tool_input": {"file_path": "test_pyright.py"}}' | ./pyright-on-save.sh
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

# Exit if no path, if the file doesn't exist, or if it isn't a Python file
[ -z "$FILE_PATHS" ] && exit 0

while IFS= read -r FILE_PATH; do
[[ ! "$FILE_PATH" =~ \.py$ ]] && continue

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
echo "Type-checking $FILE_PATH"

# Run basedpyright on just this file (via uv so it resolves regardless of shell PATH)
OUTPUT=$(uv run --project "$PROJECT_ROOT" basedpyright "$FILE_PATH" 2>&1)
STATUS=$?

# Exit code 2 is what makes the Agent surface stderr back to the Agent automatically
# (PostToolUse: exit 0 -> stdout only goes to the debug log; exit 2 -> stderr is
# shown to the Agent next to the tool result). Plain non-zero (e.g. basedpyright's
# exit 1 for reported errors) only reaches the human transcript, not the Agent.
if [ "$STATUS" -ne 0 ]; then
  echo "$OUTPUT" >&2
  exit 2
fi

echo "$OUTPUT"
done <<< "$FILE_PATHS"
exit 0
