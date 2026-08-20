---
name: start-jupyter-server
description: |
  Ensure the local Jupyter MCP connection is live before any
  dev-verification-notebook work. Use when write-dev-notebook or
  verify-dev-notebook need a live kernel, or when the user asks to
  "start jupyter", "check the jupyter connection", or similar.
---

# Start Jupyter Server

Prerequisite invoked by `write-dev-notebook` and `verify-dev-notebook` —
don't wait for a failure before running it.

1. Check whether the MCP connection is already live: `claude mcp list`
   should show `jupyter: ... - ✔ Connected`. If so, stop here.
2. If not connected, check whether a JupyterLab server is already running
   and only the MCP handshake needs retrying:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:8888/api/status?token=$JUPYTER_TOKEN"
   ```
   `200` means it's up.
3. If nothing is running, start it detached so it survives Claude Code
   restarts. This requires `JUPYTER_TOKEN` to already be exported in the
   user's shell — if it isn't set, stop and tell the user to export it
   first (see `documentation/developement.md`); never invent or hardcode a
   token value yourself.
   ```bash
   nohup uv run jupyter lab --port 8888 \
     --IdentityProvider.token "$JUPYTER_TOKEN" --ip 127.0.0.1 --no-browser \
     > /tmp/jupyterlab-contactability.log 2>&1 < /dev/null &
   disown
   ```
   Bind to `127.0.0.1`, never `0.0.0.0` — this kernel executes arbitrary
   code, keep it off the network.
4. If `claude mcp list` shows no `jupyter` entry at all, the one-time
   per-worktree `.mcp.json` symlink setup hasn't been done. Tell the user
   and point at `documentation/developement.md` — don't create it
   yourself, it's a personal-dotfile step tied to their own
   `.claude-<name>/mcp.json`.
5. Confirm end-to-end, not just via the HTTP check: create or connect a
   throwaway notebook via the `jupyter` MCP tools and execute one trivial
   cell. Report success, or the specific failure — don't assume it works.
