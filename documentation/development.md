# Local Development Using Worktrees


## Creating Git worktrees

Each feature should use an isolated Git worktree. This prevents parallel Codex
sessions and IDE windows from modifying the same checkout.

Create a worktree from the main checkout:

```bash
cd <path-to-repo>/scbatch
git worktree add -b <feature-name> ../scbatch-<feature-name>
```

This creates `../scbatch-<feature-name>/` on branch `<feature-name>`. Open the
IDE and start Codex from that directory.

List active worktrees:

```bash
git worktree list
```

## Agent configuration in worktrees

The repository's `.agents/` skills and `.codex/` hook configuration must be
committed repository files. Git includes committed configuration in every
worktree automatically. Until those directories are committed, a new worktree
will not contain them. Do not create symlinks, copy agent configuration, or run
a bootstrap script.

Each Codex installation must trust the project hooks through `/hooks` before
the configured hooks run.

## Working with a worktree

Navigate to the worktree and create an environment inside it:

```bash
cd <path-to-repo>/scbatch-<feature-name>
UV_PROJECT_ENVIRONMENT=$(pwd)/.venv uv sync --project <path-to-repo>/scbatch-<feature-name>
codex
```

`UV_PROJECT_ENVIRONMENT=$(pwd)/.venv` ensures that each worktree has its own
virtual environment. Do not share `.venv` directories between worktrees.

`scbatch` currently does not require an environment file. If later work adds a
gitignored `.env`, copy it manually into each worktree. Git worktrees never
copy ignored local files.

## Clean up a worktree

After merging or discarding a feature branch, remove its worktree from the main
checkout:

```bash
cd <path-to-repo>/scbatch
git worktree remove --force ../scbatch-<feature-name>
git branch -d <feature-name>
```

`--force` is necessary when the worktree contains an untracked `.venv`, local
notebooks, or other uncommitted files. Removing a worktree deletes that
directory, including its local environment and ignored files.


## Local checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest scbatch/pp/tests
uv run pytest scbatch/pl/tests
uv run pytest scbatch/datasets/tests
uv run pytest scbatch/tl/tests
uv run pytest
uv build
```

## Notebooks

Notebooks under `documentation/` and `examples/` are exploratory and research
artifacts. Package behavior must be implemented and tested in Python modules;
notebook results alone are not a verification boundary.

Use the `start-jupyter-server` skill only when a live Jupyter kernel is needed.
It checks local Jupyter availability and does not replace package tests.
