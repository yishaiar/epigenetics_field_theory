#!/bin/bash
# Runs ruff format on the saved file after every Edit or Write
# ==============================================================================
# Script: format-on-save.sh
# 
# What it does:
#   Automatically reformats the saved Python file to adhere strictly to PEP 8 
#   style guidelines using Ruff (a high-performance, Rust-backed formatter; similar to prettier but supports only *.py).
#
# Specific actions performed:
#   1. Indentation & Spacing: Forces 4-space indentation and normalizes 
#      whitespace around operators (e.g., changing 'x=1' to 'x = 1').
#   2. Line Wrapping: Automatically wraps lines longer than 88 characters into 
#      clean, multi-line structures with trailing commas.
#   3. Code Structure: Standardizes quotes (preferring double-quotes) and cleans 
#      up redundant vertical spacing (blank lines between functions/classes).
#
# Note: This is a purely cosmetic formatter (similar to Black). It will NOT change 
# the behavior of your code, sort imports, or fix code logic errors.


# test:
# save in file "test_ruff.py":
# def foo(a, b):
#     return a + b 
# result = foo(x, 3)

#cli command to test:
#echo '{"tool_input": {"file_path": "test_ruff.py"}}' | ./format-on-save.sh
# ==============================================================================

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Exit if no path, if it's not a Python file, or if the file doesn't exist
[ -z "$FILE_PATH" ] && exit 0
[[ ! "$FILE_PATH" =~ \.py$ ]] && exit 0
# [[ ! "$FILE_PATH" =~ \.(py|json|md)$ ]] && exit 0

[ ! -f "$FILE_PATH" ] && exit 0

# Run Ruff's formatter on just this file (via uv so it resolves regardless of shell PATH)
OUTPUT=$(uv run --project "$(git rev-parse --show-toplevel)" ruff format "$FILE_PATH" 2>&1)
STATUS=$?

# Exit code 2 is what makes Claude Code surface stderr back to Claude automatically
# (PostToolUse: exit 0 -> stdout only goes to the debug log; exit 2 -> stderr is
# shown to Claude next to the tool result).
if [ "$STATUS" -ne 0 ]; then
  echo "$OUTPUT" >&2
  exit 2
fi

echo "$OUTPUT"
exit 0