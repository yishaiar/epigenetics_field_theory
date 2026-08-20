#!/bin/bash
# Blocks ExitPlanMode unless the plan-new-feature skill was actually invoked
# during the current plan-mode cycle.
# ==============================================================================
# Script: plan-skill-gate.sh
#
# What it does:
#   Every session starts in Plan Mode, and plan-new-feature is meant to
#   fully replace generic Plan Mode here (see plan-mode-enforce-skill.sh's
#   UserPromptSubmit nudge). But that nudge is just injected text — it can't
#   force a tool call, and Claude can (and did) ignore it in favor of the
#   harness's own generic Plan Mode instructions. This hook is the hard
#   backstop: it fires as a PreToolUse gate on ExitPlanMode and inspects the
#   session transcript for a prior `Skill` call with `plan-new-feature`
#   since the current plan-mode cycle began. If it's missing, it blocks the
#   exit and tells Claude to call the skill first.
#
# Why "since the current cycle began", not "anywhere in the transcript":
#   A long session can pass through many plan-mode cycles (or none). We only
#   want to check within the cycle that's ending right now — otherwise a
#   plan-new-feature call from an unrelated, earlier task in the same
#   session would falsely satisfy this check for a later, different plan.
#   The boundary is found by scanning the transcript's `permission-mode`
#   entries: they're logged on every turn while a mode is active, so the
#   start of the current run of `"permissionMode": "plan"` entries (the
#   first one not preceded by another `plan` entry) marks the cycle start.
#
# Crucial Execution Notes:
#   1. Fails OPEN (exit 0) on any missing/unreadable transcript, or if the
#      current plan-mode cycle can't be located — blocking on our own
#      parsing gap is worse than occasionally missing a real one.
#   2. Reads `transcript_path` from the PreToolUse stdin JSON (Claude Code
#      always includes it) rather than tracking any state file of our own —
#      no marker file to create, clean up, or go stale across sessions.
#   3. Parses the transcript with plain `python3`/stdlib json, not jq — the
#      boundary-scan + nested tool_use lookup is easier to get right in
#      Python than in a jq one-liner.

# test:
# echo '{"tool_name":"ExitPlanMode","transcript_path":"/path/to/transcript.jsonl"}' | bash .claude/hooks/plan-skill-gate.sh
# ==============================================================================

INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

[ -z "$TRANSCRIPT" ] && exit 0
[ ! -f "$TRANSCRIPT" ] && exit 0

python3 - "$TRANSCRIPT" <<'PYEOF'
import json
import sys

path = sys.argv[1]
plan_start = None
skill_called = False

with open(path) as f:
    for i, line in enumerate(f):
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if entry.get("type") == "permission-mode":
            if entry.get("permissionMode") == "plan":
                if plan_start is None:
                    plan_start = i
                    skill_called = False
            else:
                plan_start = None
            continue

        if plan_start is None:
            continue

        message = entry.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue

        for item in message.get("content", []):
            if (
                isinstance(item, dict)
                and item.get("type") == "tool_use"
                and item.get("name") == "Skill"
                and item.get("input", {}).get("skill") == "plan-new-feature"
            ):
                skill_called = True

# plan_start is None here means we never saw a "plan" permission-mode entry
# at all (shouldn't happen for an ExitPlanMode call, but fail open if it does)
sys.exit(0 if skill_called or plan_start is None else 1)
PYEOF
STATUS=$?

if [ "$STATUS" -eq 1 ]; then
  echo "plan-new-feature has not been invoked yet this plan cycle. Call the Skill tool with skill: \"plan-new-feature\" before calling ExitPlanMode again." >&2
  exit 2
fi

exit 0
