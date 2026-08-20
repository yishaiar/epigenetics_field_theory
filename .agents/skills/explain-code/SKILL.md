---
name: explain-code
description: |
  Explain how a piece of code works — its purpose, flow, and design.
  Use when the user asks what something does, how it works, or wants
  to understand code before modifying it.
---

# Code Explainer

## Process
1. **Read the full file or function** before explaining anything
2. **Identify the level of explanation needed**:
   - High-level — what does this module/service do and why does it exist?
   - Flow — how does data move through this code step by step?
   - Deep dive — what does this specific line or pattern do and why?
3. **Trace dependencies** — if the code calls other services or utilities, follow them

## Explanation Structure
1. **Purpose** — what problem does this code solve?
2. **Inputs & Outputs** — what goes in, what comes out
3. **Step-by-step flow** — walk through the logic in plain English
4. **Key decisions** — explain any non-obvious patterns or why something was done this way
5. **Gotchas** — anything that could surprise someone modifying this code

## Rules
- Use plain language first, then reference code — not the other way around
- If something is unclear even after reading, say so — don't fabricate intent
- Point to specific line numbers when referencing code
- If the code has a bug or smell, note it separately after the explanation — don't mix concerns
- Tailor depth to the question: a "what does this do?" needs a summary, not a line-by-line breakdown
