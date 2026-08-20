# Local Development (using worktrees)


## Install dependencies

Install all dependencies including dev tools:

```bash
cd <path-to-repo>/ML
uv sync
```

This installs everything equivalent to `pip install -r requirements/dev.txt`.

## Creating Claude Code Worktrees

Each feature should be developed in an isolated git worktree. This prevents parallel sessions from conflicting.

**Create a worktree for a new feature:**

```bash
cd <path-to-repo>/ML
claude --worktree <feature-name> #both creates an auto-generated branch and an isolated working directory
git branch -m worktree-<feature-name> <feature-name>   # rename branch (worktree-<feature-name>) to clean name 
```

This creates `.claude/worktrees/<feature-name>/` on a new branch `worktree-<feature-name>` and launches Claude Code scoped to that directory. Open your IDE in this directory as well.

**List active worktrees:**

```bash
git worktree list
```

## Personal Claude Code config (`.claude` symlink)

`.claude` is never committed directly — it's a personal symlink to your own
tracked folder, `.claude-<your-name>/` (e.g. `.claude-yishaiar/`). This lets
each teammate keep their own `CLAUDE.md`, skills (`commands/`), hooks, and
settings, versioned and backed up in git, without clashing with anyone
else's. Only `apps/*/CLAUDE.md` with shared
domain conventions, (not personal workflow) live outside this scheme.

Because `.claude` is gitignored, a fresh worktree checkout has your tracked
`.claude-<your-name>/` folder on disk but no `.claude` symlink pointing to
it yet — **recreate the symlink after every worktree creation (or any
fresh clone):**

```bash
cd <path-to-repo>/ML/.claude/worktrees/<feature-name>   # or repo root
ln -s .claude-<your-name> .claude
```

Verify it resolved correctly with `ls -la .claude`.



## Working with Worktrees

**Navigate to an existing worktree (working directory) and install dependencies\continue work:**

```bash
cd <path-to-repo>/ML/.claude/worktrees/<feature-name>
cp <path-to-repo>/ML/.env .env
UV_PROJECT_ENVIRONMENT=$(pwd)/.venv uv sync --project <path-to-repo>/ML # or use: UV_PROJECT_ENVIRONMENT=$(pwd)/.venv uv sync --project $(pwd)/../../..

claude --resume #resuming must be run from inside the worktree directory
```

Note: `.env` is not copied automatically into worktrees since it is gitignored. Copy it manually as shown above.

**Clean up after a feature branch is merged or discarded:**

```bash
git worktree remove --force <path-to-repo>/ML/.claude/worktrees/<feature-name>
git branch -d <feature-name>
```

Note: `--force` is required because `git worktree remove` only removes clean
worktrees (no untracked files, no modified tracked files) — the untracked `.venv`,
`.claude` symlink (and anything else uncommitted) would otherwise block it.
Worktree removal deletes the whole directory, so the symlink goes with it.
