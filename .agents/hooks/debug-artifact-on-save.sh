#!/bin/bash
# Checks the changed file for leftover debugger breakpoints after every Edit or Write.
# If any are found, the Agent will see them and remove them.
# ==============================================================================
# Script: debug-artifact-on-save.sh
#
# What it does:
#   Greps the saved Python file for debugger breakpoints that should never
#   ship: `pdb.set_trace()`, `breakpoint()`, and `import pdb`.
#
# Why not also flag `print(`:
#   This repo already uses `print(` pervasively as its normal output style
#   (existing scientific and notebook call sites) — it's this
#   codebase's convention, not a debug leftover. Flagging it would fire on
#   nearly every file touched and teach the Agent to ignore this hook. Only the
#   patterns below are debugger-specific and had zero existing occurrences
#   when this hook was added, so there's no false-positive risk today.
#
# Crucial Execution Notes:
#   1. Python only, same file-existence/extension guards as lint-on-save.sh.
#   2. Pattern match via grep, not an AST — cheap and fast, but blunt. It
#      won't catch a breakpoint split across lines or aliased imports
#      (`import pdb as p`). Good enough for the common case; it's not a
#      substitute for the judgment `code-reviewer` applies at PR time.


# test:
# save in file "test_debug.py":
# def foo():
#     breakpoint()
#     return 1

#cli command to test:
#echo '{"tool_input": {"file_path": "test_debug.py"}}' | ./debug-artifact-on-save.sh
# ==============================================================================

INPUT=$(cat)
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

MATCHES=$(grep -nE 'pdb\.set_trace\(\)|^\s*breakpoint\(\)|^\s*import pdb(\s|$)' "$FILE_PATH")

if [ -n "$MATCHES" ]; then
  echo "Debugger breakpoint left in $FILE_PATH — remove before continuing:" >&2
  echo "$MATCHES" >&2
  exit 2
fi

done <<< "$FILE_PATHS"
exit 0
