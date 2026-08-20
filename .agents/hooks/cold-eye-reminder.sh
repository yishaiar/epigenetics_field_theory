#!/bin/bash
# cold-eye-reminder.sh
# Fires on every UserPromptSubmit event. Re-injects the cold-eye rules as
# additionalContext so the behavior survives long/compacted sessions instead
# of fading after the skill's one load-once invocation.

# cli command to test:
# echo '{"permission_mode": "default"}' | bash .agents/hooks/cold-eye-reminder.sh

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "cold-eye: name the external bar you're judged against, state the strongest counter-case, never fabricate research/facts to fill a gap (ask instead), and treat stored memory/preferences as framing, not truth."
  }
}
EOF

exit 0
