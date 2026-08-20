#!/bin/bash
# Scans the staged diff for hardcoded secrets before a `git commit` runs.
# If anything matches, the commit is BLOCKED — not just flagged after the fact.
# ==============================================================================
# Script: secret-scan-on-commit.sh
#
# What it does:
#   Fires as a PreToolUse hook on every Bash call. If (and only if) the
#   command being run is a `git commit`, it scans `git diff --cached` for
#   patterns that look like hardcoded credentials:
#     - AWS access key IDs (`AKIA...`)
#     - MongoDB URIs with an embedded username:password
#     - Private key headers (`-----BEGIN ... PRIVATE KEY-----`)
#     - Generic `api_key`/`secret`/`token`/`password` assigned to a quoted
#       literal (not a variable reference or `os.getenv(...)` call)
#
# Why PreToolUse, not PostToolUse (unlike this repo's other hooks):
#   Every other hook here (format/lint/pyright/test-on-save) is PostToolUse —
#   the action already happened, and the hook just surfaces feedback so
#   the Agent fixes it on the next turn. That's wrong for secrets: by the time
#   a PostToolUse hook could react, the credential is already in git history.
#   PreToolUse + exit code 2 blocks the commit from running at all.
#
# Crucial Execution Notes:
#   1. Only acts on `git commit` — every other Bash command exits 0 immediately.
#   2. Only scans ADDED lines (`^+`) in the staged diff, not the whole repo —
#      keeps it fast and avoids flagging pre-existing (already-committed) code.
#   3. Per org policy: never echo the matched secret value itself back into
#      the transcript — only the file/line and pattern name. If this fires,
#      the value must be removed and the credential rotated, not just deleted
#      from the diff (see Heka's secret-exposure playbook).


# test:
# echo '{"tool_input": {"command": "git commit -m test"}}' | ./secret-scan-on-commit.sh
# (run with something staged that matches, e.g. `git add` a file containing
#  <some-secret>, then run the command above)
# ==============================================================================

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only act on git commit invocations — everything else passes through untouched
[ -z "$COMMAND" ] && exit 0
[[ ! "$COMMAND" =~ git[[:space:]]+commit ]] && exit 0

DIFF=$(git diff --cached -U0 2>/dev/null)
[ -z "$DIFF" ] && exit 0

# Only look at added lines, and never print the matched value itself
ADDED=$(echo "$DIFF" | grep -E '^\+' | grep -vE '^\+\+\+')

FOUND=""

if echo "$ADDED" | grep -qE 'AKIA[0-9A-Z]{16}'; then
  FOUND="${FOUND}- AWS access key ID pattern (AKIA...)\n"
fi

if echo "$ADDED" | grep -qE 'mongodb(\+srv)?://[^/@[:space:]]+:[^/@[:space:]]+@'; then
  FOUND="${FOUND}- MongoDB URI with embedded username:password\n"
fi

if echo "$ADDED" | grep -qE -- '-----BEGIN[A-Z ]*PRIVATE KEY-----'; then
  FOUND="${FOUND}- Private key block (-----BEGIN ... PRIVATE KEY-----)\n"
fi

if echo "$ADDED" | grep -qiE '(api[_-]?key|secret[_-]?key|access[_-]?key|password|passwd|token)[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9/+=_.-]{8,}["'"'"']'; then
  FOUND="${FOUND}- api_key/secret/token/password assigned to a quoted literal\n"
fi

if [ -n "$FOUND" ]; then
  echo "COMMIT BLOCKED: possible hardcoded secret(s) in the staged diff:" >&2
  echo -e "$FOUND" >&2
  echo "Do not commit. Remove the value, rotate the credential if it's real, and follow Heka's secret-exposure playbook." >&2
  exit 2
fi

exit 0
