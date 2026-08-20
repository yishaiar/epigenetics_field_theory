#!/bin/bash
# notify-on-stop.sh
# Fires on the Stop event, when Claude Code finishes responding.
# Sends a macOS notification identifying which repo and worktree the session ran in.

# cli command to test:
# echo "{\"cwd\": \"$(pwd)\"}" | bash .claude/hooks/notify-on-stop.sh

# Claude Code passes event JSON on stdin. Read it once into a variable.
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

# -e passes an AppleScript expression directly. Requires Script Editor to have
# notification permission (System Settings, Notifications, Script Editor).
osascript -e "display notification \"$MESSAGE\" with title \"Claude Code finished\""

# Exit 0 so Claude Code treats this as no objection, the Stop event proceeds normally.
exit 0