# Git

Git utilities built on top of `nclutils.sh`. Imported from `nclutils.git`.

The module wraps `git` subprocess calls in typed Python helpers, ranging from one-shot primitives (`current_branch`, `is_dirty`) to full workflow composites (`sync_branch`, `add_worktree`). Every helper goes through `nclutils.sh.run_command`, so failures surface as `ShellCommandError` subclasses with structured `CompletedCommand` output attached.

```python
from nclutils.git import get_repo_state, sync_branch

state = get_repo_state()
if state.behind > 0 and not state.is_dirty:
    result = sync_branch()
    print(result.action)  # "fast_forwarded" or "rebased"
```

## Design rationale

`nclutils.git` calls `git` directly through `nclutils.sh.run_command` rather than wrapping a third-party library like `GitPython` or `pygit2`. The trade-offs:

- A working `git` binary is the only runtime requirement.
- Every error is a `ShellCommandError`, `NotARepoError`, or `ValueError`, so there is no separate exception hierarchy to learn.
- Process semantics match `git` on the command line: output matches what you would see in a terminal, hooks fire, configuration is loaded the same way, and `GIT_*` environment variables work as documented.

The cost is that parsing porcelain output is the user's problem. The composites in this module do that work for the cases that come up most often.

## Composites

These wrap multi-step workflows behind a single call. They are the reason this module exists: most callers should reach for a composite first and drop down to primitives only when the composite does not fit.

### `get_repo_state`

Snapshot a repo in one call. Returns a `RepoState` with the current branch, upstream, ahead/behind counts, file counts by category, stash count for the branch, and whether a rebase is paused.

```python
from nclutils.git import get_repo_state

state = get_repo_state()
print(f"on {state.branch} ({state.ahead} ahead, {state.behind} behind)")
print(f"  staged={state.staged} modified={state.modified} untracked={state.untracked}")
if state.rebase_in_progress:
    print("  rebase paused")
```

`RepoState` fields:

| Field                | Type        | Description                                                    |
| -------------------- | ----------- | -------------------------------------------------------------- |
| `root`               | `Path`      | Absolute path to the working tree root.                        |
| `branch`             | `str \| None` | Current branch name; `None` on detached HEAD.                |
| `upstream`           | `str \| None` | Upstream ref (e.g., `origin/main`); `None` if none configured. |
| `ahead`              | `int`       | Commits on the local branch not on the upstream.               |
| `behind`             | `int`       | Commits on the upstream not on the local branch.               |
| `is_dirty`           | `bool`      | True if any of the file counts below are nonzero.              |
| `staged`             | `int`       | Files with index changes.                                      |
| `modified`           | `int`       | Files with worktree changes.                                   |
| `untracked`          | `int`       | Files not under version control.                               |
| `unmerged`           | `int`       | Files with merge conflicts.                                    |
| `stash_count`        | `int`       | Stash entries created on the current branch.                   |
| `rebase_in_progress` | `bool`      | True if `.git/rebase-merge/` or `.git/rebase-apply/` exists.   |

`get_repo_state` issues four subprocess calls (`rev-parse --show-toplevel`, `status --branch --porcelain=v2`, `stash list`, `rev-parse --absolute-git-dir`). It still beats assembling six or more primitive calls and parsing status output by hand.

### `fetch`

Fetch from a remote with prune-by-default behavior. `prune=True` removes stale remote tracking refs; this is almost always what you want.

```python
from nclutils.git import fetch

# Fetch the upstream's remote (or primary remote if no upstream)
fetch()

# Fetch a specific remote
fetch(remote="upstream")

# Fetch every remote
fetch(all_remotes=True)

# Skip tags
fetch(tags=False)
```

When `remote` is `None` and `all_remotes` is `False`, `fetch` resolves the remote in this order: the upstream of the current branch, then `primary_remote()`, then raises `ShellCommandFailedError` if neither resolves.

### `stashed`

Context manager that stashes uncommitted changes on entry and pops on exit. Yields `True` if a stash was created, `False` if the tree was already clean.

```python
from nclutils.git import stashed, run_git

with stashed() as did_stash:
    run_git("checkout", "main")
    run_git("merge", "feature-branch")
# Stash is popped automatically here, even if the block raised.
```

If the pop conflicts on exit, the stash is left on the stack and `ShellCommandFailedError` is raised. A pop failure supersedes any exception raised inside the block, since the stash is the more recoverable artifact.

`include_untracked=True` (the default) passes `-u` to `git stash push`, so untracked files are included in the stash. Pass `message="..."` to set a stash message.

### `sync_branch`

The central workflow composite. Fetches the upstream, computes divergence, optionally stashes a dirty tree, then either fast-forwards or rebases the current branch.

```python
from nclutils.git import sync_branch

result = sync_branch()
match result.action:
    case "up_to_date":
        print("nothing to do")
    case "fast_forwarded":
        print(f"fast-forwarded {result.behind_before} commits")
    case "rebased":
        print(f"rebased {result.ahead_before} local commits over upstream")
    case "aborted":
        print("rebase had conflicts; aborted and restored")
        for path in result.conflicts:
            print(f"  conflict: {path}")
```

The sequence:

1. Resolve the current branch. Detached HEAD raises `ValueError`.
2. Resolve the upstream. No upstream raises `ValueError`.
3. `fetch()` the upstream's remote.
4. Compute ahead/behind. If behind is zero, return `action="up_to_date"`.
5. If the tree is dirty and `stash=True`, wrap the pull in `stashed()`. If `stash=False`, raise `ShellCommandFailedError`.
6. If ahead is zero, try `git pull --ff-only`. If that fails (or ahead is nonzero), run `git pull --rebase` when `allow_rebase=True`. If neither path is available, raise `ShellCommandFailedError`.
7. On rebase conflict, behavior depends on `on_conflict`:
   - `"abort"` (default): run `git rebase --abort`, restore the stash, return `action="aborted"` with `conflicts` populated.
   - `"leave"`: leave the rebase paused with the stash unpopped and raise `ShellCommandFailedError`.

The optional `branch=` parameter is a safety check: if provided, it must equal the checked-out branch or `ValueError` is raised. Use it to assert you are syncing the branch you think you are.

`SyncResult` fields:

| Field            | Type                                                            | Description                                  |
| ---------------- | --------------------------------------------------------------- | -------------------------------------------- |
| `action`         | `Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]` | What the sync ended up doing.                |
| `ahead_before`   | `int`                                                           | Commits ahead before the pull.               |
| `behind_before`  | `int`                                                           | Commits behind before the pull.              |
| `conflicts`      | `tuple[Path, ...]`                                              | Conflicted paths (only when `action="aborted"`). |
| `stashed`        | `bool`                                                          | True if a stash was created during the sync. |

### `prunable_branches` + `delete_branches`

Find branches that are safe to delete, then delete them. The two helpers are split so callers can review the list before pulling the trigger.

```python
from nclutils.git import delete_branches, prunable_branches

candidates = prunable_branches()
print(f"prunable: {candidates}")

deleted = delete_branches(candidates)
print(f"deleted {len(deleted)} branches")
```

`prunable_branches` combines two sources of safe-to-delete branches; toggle each with the matching keyword:

- `merged=True`: branches merged into `target` (default `default_branch()`), which is the same set as branches with zero commits ahead of `target`.
- `gone=True`: branches whose upstream tracking ref has been deleted on the remote.

The current branch, the target branch, and any name in `exclude` (default `("main", "master", "develop")`) are always filtered out. `target=None` (the default) defers to `default_branch()`. `ValueError` is raised if a target is needed but `default_branch()` returns `None`.

`delete_branches` runs `git branch -d` on each name (or `git branch -D` with `force=True`). It silently skips the current branch and any name that does not exist locally, then returns the list of names actually deleted.

### `add_worktree`

Create a worktree and return its resolved `Worktree` record. Composes `create_worktree` and `list_worktrees`.

```python
from pathlib import Path
from nclutils.git import add_worktree

# Check out an existing branch in a new worktree
wt = add_worktree(Path("../feature-x"), branch="feature-x")

# Create a new branch as part of the operation
wt = add_worktree(
    Path("../experiment"),
    branch="experiment",
    new_branch=True,
    start_point="origin/main",
)

print(wt.path, wt.branch, wt.head)
```

`Worktree` fields:

| Field         | Type          | Description                                       |
| ------------- | ------------- | ------------------------------------------------- |
| `path`        | `Path`        | Filesystem path of the worktree.                  |
| `branch`      | `str \| None` | Checked-out branch; `None` on detached HEAD.      |
| `head`        | `str`         | Commit SHA at HEAD.                               |
| `is_bare`     | `bool`        | True for the bare worktree of a bare repo.        |
| `is_detached` | `bool`        | True if HEAD is detached.                         |
| `is_locked`   | `bool`        | True if the worktree is locked.                   |

## Primitives

The composites cover the common workflows. When they do not fit, drop down to the primitives.

### Repo

| Function                  | Returns       | Description                                                                       |
| ------------------------- | ------------- | --------------------------------------------------------------------------------- |
| `is_git_installed()`      | `bool`        | True if the `git` binary is on PATH.                                              |
| `is_git_repo(cwd=None)`   | `bool`        | True if `cwd` is inside a git working tree.                                       |
| `repo_root(cwd=None)`     | `Path`        | Absolute path to the working tree root. Raises `NotARepoError` if not a repo.    |
| `primary_remote(cwd=None)` | `tuple[str, str] \| None` | `(name, url)` of the first configured remote, or `None`.            |
| `is_dirty(cwd=None)`      | `bool`        | True if the working tree has uncommitted or untracked changes.                    |
| `is_rebase_in_progress(cwd=None)` | `bool` | True if `rebase-merge/` or `rebase-apply/` exists in `.git/`.                    |

### Branch

| Function                                       | Returns                  | Description                                                                  |
| ---------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------- |
| `current_branch(cwd=None)`                     | `str \| None`            | Current branch name, or `None` on detached HEAD.                             |
| `default_branch(cwd=None, *, remote="origin")` | `str \| None`            | Default branch as advertised by `<remote>/HEAD`, or `None` if unset.         |
| `branch_exists(branch, cwd=None)`              | `bool`                   | True if `branch` is a local branch.                                          |
| `all_local_branches(cwd=None)`                 | `frozenset[str]`         | Set of local branch names.                                                   |
| `tracking_branch(branch=None, cwd=None)`       | `tuple[str, str] \| None` | `(remote, branch_on_remote)` for the upstream of `branch`, or `None`.       |
| `ahead_behind(left, right, cwd=None)`          | `tuple[int, int]`        | Commits `(ahead, behind)` comparing `left` to `right`.                       |
| `merged_branches(target=None, cwd=None)`       | `frozenset[str]`         | Local branches merged into `target`. Includes `target` itself.               |
| `gone_branches(cwd=None)`                      | `frozenset[str]`         | Branches whose upstream tracking ref has been deleted.                       |

### Worktree

| Function                                   | Returns          | Description                                                            |
| ------------------------------------------ | ---------------- | ---------------------------------------------------------------------- |
| `list_worktrees(cwd=None)`                 | `list[Worktree]` | All registered worktrees.                                              |
| `create_worktree(path, branch, ...)`       | `None`           | Create a worktree at `path` checked out to `branch`.                   |
| `remove_worktree(path, *, cwd=None, force=False)` | `None`    | Remove the worktree at `path`. `force=True` removes a dirty worktree. |

### Runner

`run_git(*args, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,))` is the single subprocess entry point used by every other helper in the module. It prepends `git` to `args`, logs the invocation at DEBUG, and forwards every option to `nclutils.sh.run_command`.

```python
from nclutils.git import run_git

# Use run_git directly when no helper exists
result = run_git("log", "--oneline", "-5")
for line in result.stdout.splitlines():
    print(line)
```

## Error handling

Every git helper either returns a value or raises one of three exception types:

| Exception                                | When raised                                                                                                       |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `NotARepoError`                          | Operation requires a repo, but `cwd` (or the process cwd) is not inside one. Raised by `repo_root`, `is_dirty`, `is_rebase_in_progress`, `get_repo_state`, `fetch`, `stashed`, and `sync_branch` (transitively, via `fetch`). |
| `ValueError`                             | Caller asked for an operation that is not well-defined: detached HEAD where a branch was needed, missing upstream, missing default branch.     |
| `RuntimeError`                           | Raised only by `add_worktree` if the new worktree was created but does not appear in the subsequent `git worktree list` output. A guard against silent bugs; should not fire in practice. |
| `nclutils.sh.ShellCommandError` and subclasses | Any subprocess failure: `git` not on PATH, non-zero exit, timeout exceeded.                                       |

`ShellCommandError` is the base class for all shell-level failures, so a single `except` handles every subprocess error:

```python
from nclutils.git import NotARepoError, sync_branch
from nclutils.sh import ShellCommandError

try:
    result = sync_branch()
except NotARepoError:
    print("not in a git repo")
except ValueError as e:
    print(f"invalid sync request: {e}")
except ShellCommandError as e:
    print(f"git failed: {e}")
```

See [docs/shell_commands.md](shell_commands.md) for the full `ShellCommandError` hierarchy (`ShellCommandNotFoundError`, `ShellCommandFailedError`, `ShellCommandTimeoutError`).

## Diagnostic logging

`nclutils.git` emits DEBUG messages through the stdlib `logging` module under the `nclutils.git` logger name. Every `git` invocation is logged. To see them:

```python
import logging

logging.getLogger("nclutils.git").setLevel(logging.DEBUG)
logging.basicConfig()
```

This is independent of `nclutils.pp`. The git module never writes to the console directly.

## API reference

### Foundation

- `run_git(*args, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,)) -> CompletedCommand`. Run a `git` subcommand and return the captured result.
- `NotARepoError`. Raised when an operation requires a repo but `cwd` is not inside one.

### Repo

- `is_git_installed() -> bool`. True if `git` is on PATH.
- `is_git_repo(cwd=None) -> bool`. True if `cwd` is inside a git working tree.
- `repo_root(cwd=None) -> Path`. Absolute path to the working tree root.
- `primary_remote(cwd=None) -> tuple[str, str] | None`. `(name, url)` of the first configured remote.
- `is_dirty(cwd=None) -> bool`. True if the working tree has uncommitted or untracked changes.
- `is_rebase_in_progress(cwd=None) -> bool`. True if a rebase is paused.
- `get_repo_state(cwd=None) -> RepoState`. Snapshot a repo's state in one call.
- `RepoState`. Frozen dataclass; see the field table above.

### Branch

- `current_branch(cwd=None) -> str | None`. Current branch name, or `None` on detached HEAD.
- `default_branch(cwd=None, *, remote="origin") -> str | None`. Default branch as advertised by `<remote>/HEAD`.
- `branch_exists(branch, cwd=None) -> bool`. True if `branch` is a local branch.
- `all_local_branches(cwd=None) -> frozenset[str]`. Set of local branch names.
- `tracking_branch(branch=None, cwd=None) -> tuple[str, str] | None`. `(remote, branch_on_remote)` for the upstream.
- `ahead_behind(left, right, cwd=None) -> tuple[int, int]`. `(ahead, behind)` commit counts comparing `left` to `right`.
- `merged_branches(target=None, cwd=None) -> frozenset[str]`. Local branches merged into `target`.
- `gone_branches(cwd=None) -> frozenset[str]`. Branches whose upstream tracking ref has been deleted.
- `prunable_branches(cwd=None, *, merged=True, gone=True, target=None, exclude=("main", "master", "develop")) -> list[str]`. Local branches safe to delete.
- `delete_branches(branches, cwd=None, *, force=False) -> list[str]`. Delete local branches; return the names actually deleted.

### Sync

- `fetch(cwd=None, *, remote=None, prune=True, all_remotes=False, tags=True) -> None`. Fetch from a remote with prune-by-default.
- `stashed(cwd=None, *, message=None, include_untracked=True)`. Context manager: stash on enter (if dirty), pop on exit. Yields `True` if a stash was created.
- `sync_branch(cwd=None, *, branch=None, stash=True, allow_rebase=True, on_conflict="abort") -> SyncResult`. Fetch and pull (rebase) the current branch from its upstream.
- `SyncResult`. Frozen dataclass; see the field table above.

### Worktree

- `list_worktrees(cwd=None) -> list[Worktree]`. All registered worktrees.
- `create_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None) -> None`. Create a worktree at `path` checked out to `branch`.
- `remove_worktree(path, *, cwd=None, force=False) -> None`. Remove the worktree at `path`.
- `add_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None) -> Worktree`. Composite: create a worktree and return its resolved record. Raises `RuntimeError` if the new worktree is missing from the subsequent listing.
- `Worktree`. Frozen dataclass; see the field table above.
