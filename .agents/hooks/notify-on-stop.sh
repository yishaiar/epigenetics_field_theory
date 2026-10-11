#!/bin/bash
# notify-on-stop.sh
# Fires on the Stop event, when the Agent finishes responding.
# Sends an optional macOS notification identifying which repo and worktree the
# session ran in. Other operating systems skip this optional notification.

# cli command to test:
# echo "{\"cwd\": \"$(pwd)\"}" | bash .agents/hooks/notify-on-stop.sh

# The Agent passes event JSON on stdin. Read it once into a variable.
INPUT=$(cat)

# "cwd" is the working directory the session was running in when Stop fired.
CWD=$(echo "$INPUT" | jq -r '.cwd')

# If cwd is missing or invalid, bail quietly rather than blocking the Stop event.
cd "$CWD" 2>/dev/null || exit 0

# --show-toplevel gives the root of the current worktree.
# Its basename is the worktree folder name, e.g. "myrepo-feature-x".
TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null)

# --git-common-dir points at the shared .git directory across all worktrees.
# Its parent directory is the main repo checkout, not the worktree.
COMMON_DIR=$(git rev-parse --git-common-dir 2>/dev/null)

if [ -n "$TOPLEVEL" ] && [ -n "$COMMON_DIR" ]; then
  WORKTREE_NAME=$(basename "$TOPLEVEL")

  # Resolve to an absolute path before taking the basename, since --git-common-dir
  # can return a relative path depending on where the command was run from.
  MAIN_REPO_DIR=$(cd "$(dirname "$COMMON_DIR")" && pwd)
  REPO_NAME=$(basename "$MAIN_REPO_DIR")

  BRANCH=$(git branch --show-current 2>/dev/null)

  # If you're in the main checkout rather than a linked worktree, repo name
  # and worktree name are the same, so don't show it twice.
  if [ "$REPO_NAME" = "$WORKTREE_NAME" ]; then
    MESSAGE="$REPO_NAME ($BRANCH)"
  else
    MESSAGE="$REPO_NAME / $WORKTREE_NAME ($BRANCH)"
  fi
else
  # Not a git repo at all, fall back to just the directory name.
  MESSAGE=$(basename "$CWD")
fi

# `display notification` is built into macOS Standard Additions. Notifications
# are optional, so an unavailable GUI service must not make the Stop hook fail.
if ! command -v osascript >/dev/null 2>&1; then
  exit 0
fi

if ! osascript -e "display notification \"$MESSAGE\" with title \"Agent finished\""; then
  echo "notify-on-stop.sh: macOS notification delivery unavailable." >&2
fi

exit 0
