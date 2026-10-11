---
name: start-jupyter-server
description: |
  Ensure the local Jupyter MCP connection is live before work that requires a
  Jupyter kernel. Use when the user asks to "start jupyter", "check the
  jupyter connection", or similar.
---

# Start Jupyter Server

Use this before Jupyter MCP work. Do not wait for a failed tool call or require
a new chat when native `jupyter` tools are absent.

## Check

- If `jupyter` MCP tools are exposed, stop.
- Otherwise check JupyterLab with host access:

  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8888/api/status
  ```

- A restricted shell can return `000` for a live loopback server.
- `200` means JupyterLab is running.

## Start

If JupyterLab is not running, run this from repository root:

```bash
nohup uv run jupyter lab --port 8888 --ip 127.0.0.1 --no-browser > /tmp/jupyterlab-codex.log 2>&1 < /dev/null &
disown
```

- Start detached so it survives Codex restarts.
- Bind to `127.0.0.1`, never `0.0.0.0`.
- Do not add a token. Jupyter configuration controls local authentication.

## Recover

After startup, recheck `/api/status` with host access. If it is not `200`:

- Inspect `/tmp/jupyterlab-codex.log`.
- Retry using the repository's existing virtual-environment launcher, if any.
- If detached children do not survive the command runner, use the platform's existing user-service configuration, if any.
- Require a `200` response and a live service PID before continuing. Otherwise, report the log and service status, then stop.
- Do not install dependencies or change configuration for a silent detached-launch failure.

## Confirm

- When MCP tools are absent, run `codex mcp get jupyter`.
- If it fails, report that Jupyter MCP is unconfigured and stop.
- Do not modify MCP configuration without an explicit request.
- When tools remain absent after the server and configuration checks, run a direct stdio MCP smoke test with the configured command: `initialize`, `notifications/initialized`, then `connect_to_jupyter` at `http://127.0.0.1:8888`.
- Success requires request `2` to contain `Successfully connected to Jupyter server:` and `"isError":false`.
- Confirm the connection, not merely the HTTP server: optionally start a fresh Codex session and verify that native `jupyter` MCP tools are exposed. This is verification only, not a prerequisite for direct stdio MCP work in the current chat.
- A successful probe proves the server and MCP work even if this chat lacks native tools. For a requested Jupyter operation, use the configured stdio MCP command directly: initialize, send `notifications/initialized`, call `connect_to_jupyter`, then the requested tool. It does not attach native tools to the chat.
- Do not create notebooks or execute kernel code for connection-only requests.
- Report success or the specific failure.
