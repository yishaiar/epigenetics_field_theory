#!/bin/bash
# Checks the changed file for leftover debugger breakpoints after every Edit or Write.
# If any are found, Claude will see them and remove them.
# ==============================================================================
# Script: debug-artifact-on-save.sh
#
# What it does:
#   Greps the saved Python file for debugger breakpoints that should never
#   ship: `pdb.set_trace()`, `breakpoint()`, and `import pdb`.
#
# Why not also flag `print(`:
#   This repo already uses `print(` pervasively as its normal output style
#   (131+ existing call sites in apps/shared, non-test code) — it's this
#   codebase's convention, not a debug leftover. Flagging it would fire on
#   nearly every file touched and teach Claude to ignore this hook. Only the
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
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Exit if no path, if the file doesn't exist, or if it isn't a Python file
[ -z "$FILE_PATH" ] && exit 0
[ ! -f "$FILE_PATH" ] && exit 0
[[ ! "$FILE_PATH" =~ \.py$ ]] && exit 0

MATCHES=$(grep -nE 'pdb\.set_trace\(\)|^\s*breakpoint\(\)|^\s*import pdb(\s|$)' "$FILE_PATH")

if [ -n "$MATCHES" ]; then
  echo "Debugger breakpoint left in $FILE_PATH — remove before continuing:" >&2
  echo "$MATCHES" >&2
  exit 2
fi

exit 0
