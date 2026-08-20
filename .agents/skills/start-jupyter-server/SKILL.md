---
name: start-jupyter-server
description: |
  Ensure the local Jupyter MCP connection is live before work that requires a
  Jupyter kernel. Use when the user asks to "start jupyter", "check the
  jupyter connection", or similar.
---

# Start Jupyter Server

Run this before Jupyter MCP work. Do not wait for a Jupyter tool call to fail.

1. Check whether the MCP connection is already live. If the current Codex
   session exposes `jupyter` MCP tools, stop here.
2. If the tools are not exposed, check whether a JupyterLab server is already
   running and only a fresh Codex session is needed for the MCP connection:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8888/api/status
   ```
   Run this with host access. A restricted Codex shell can falsely return
   `000` for a host-loopback server. `200` means the server is running.
3. If nothing is running, start it detached so it survives Codex restarts. Run
   this command from the repository that should be the Jupyter server root:
   ```bash
   nohup uv run jupyter lab --port 8888 --ip 127.0.0.1 --no-browser > /tmp/jupyterlab-codex.log 2>&1 < /dev/null &
   disown
   ```
   Bind to `127.0.0.1`, never `0.0.0.0`, because the kernel executes arbitrary
   code. Do not add a token to this command: local server authentication is
   controlled by its Jupyter configuration.
4. If the `jupyter` MCP is absent, verify the configuration with:
   ```bash
   codex mcp get jupyter
   ```
   If this command fails, stop and report that the Jupyter MCP is not
   configured. Do not modify Codex MCP configuration without an explicit
   request.
5. Confirm the connection, not merely the HTTP server: start a fresh Codex
   session and verify that `jupyter` MCP tools are exposed. Do not create a
   notebook or execute code as part of this skill. Report success, or the
   specific failure.
