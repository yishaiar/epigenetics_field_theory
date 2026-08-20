#!/bin/bash
# plan-mode-enforce-skill.sh
# Fires on every UserPromptSubmit event. Native Plan Mode can activate from
# session state alone, bypassing this project's plan-new-feature skill and
# its post-approval CURRENT_PLAN.md save. Nudge the Agent to load it when
# permission_mode is "plan".

# cli command to test:
# echo '{"permission_mode": "plan"}' | bash .agents/hooks/plan-mode-enforce-skill.sh

INPUT=$(cat)
MODE=$(echo "$INPUT" | jq -r '.permission_mode // empty')

if [ "$MODE" = "plan" ]; then
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Plan Mode active -- follow .agents/skills/plan-new-feature/SKILL.md"
  }
}
EOF
fi

exit 0
