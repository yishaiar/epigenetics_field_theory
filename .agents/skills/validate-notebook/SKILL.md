---
name: validate-notebook
description: Run a target Jupyter notebook in its intended kernel and report whether every intended cell executes without errors. Use after notebook creation or when validating a notebook.
---

# Validate Notebook

Validate a notebook like a focused test target after notebook work is ready.
Invoke this skill deliberately, never after every edit. The acceptance bar is
a fresh, complete execution in the intended Jupyter kernel with outputs saved
from that run. Never infer success from JSON, source text, a partial cell run,
or a server health check.

1. Identify the notebook named by the user or changed by the current work.
   Run only that notebook unless the user explicitly requests broader coverage.
2. Determine the intended checkout, virtual environment, server URL, and
   kernel. In a worktree, identify the exact expected worktree path before
   execution.
3. Confirm the notebook contains a runtime-provenance cell before its feature
   imports. That cell must print the kernel executable, current working
   directory, and imported local-package path. For a worktree, it must assert
   that the imported path belongs to the intended worktree. If it is absent,
   fail validation and return it to `/execute-new-notebook-code`; do not treat an
   external shell import as a substitute.
4. Open the target notebook in the intended Jupyter server, restart its kernel,
   and use **Run All**. Wait until execution is complete and the kernel is
   idle. Do not rely on existing outputs, an individual cell run, or a command
   that executes notebook source outside Jupyter.
5. Inspect the outputs produced by that run, including the provenance cell and
   every feature cell. Confirm the reported kernel, working directory, and
   imported package path match the intended environment. Inspect every error
   output and traceback before declaring a result.
6. On failure, save the failing notebook state when it contains useful output,
   then report the failing cell, full relevant traceback, intended checkout,
   source tree, working directory, and kernel details to the calling flow. Do
   not invoke other skills from this skill. Do not call the notebook successful.
7. On success, save the notebook. Confirm every intended code cell has a new
   execution count from the Run All session and no error output. Never leave
   stale failed output in the notebook.
8. After saving, validate the persisted notebook with `nbformat` and run
   `git diff --check`. These are post-execution artifact checks only. They
   cannot replace steps 4 through 7.
9. Never report notebook work as complete after source-level execution,
   notebook-JSON inspection, or a subset of cells succeeds. A completion
   claim requires the fresh full-kernel execution in steps 4 through 7. If
   that execution is unavailable or fails, state that the notebook remains
   unvalidated or failing, name the blocking cell and traceback, and continue
   debugging when authorized.
10. In a worktree, explicitly verify that the provenance output names the
    intended checkout. When a new public package export was added, clear any
    cached package modules before that import or restart the kernel; otherwise
    a stale sibling checkout can produce a false failure.

Report success only with the notebook path, server URL, kernel executable,
imported package path, and confirmation that a fresh Run All completed without
cell errors.
