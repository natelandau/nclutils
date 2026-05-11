# `nclutils.git` reference

Git operations through the `git` binary via `nclutils.sh.run_command`. No third-party git library. Process semantics match command-line `git`: hooks fire, config loads normally, `GIT_*` env vars work.

## Conventions

- **Short names everywhere.** Branch helpers take and return short names (`"main"`, NOT `"refs/heads/main"`). Remotes are short too (`"origin"`). Exception: `ahead_behind` accepts anything `git rev-parse` accepts (SHAs, tags, expressions like `HEAD~3` or `origin/main`).
- **Uniform `cwd`, `stream`, `env`.** Every helper accepts these three with identical meaning:
    - `cwd: Path | str | None = None` — repo to operate on. `None` uses process cwd. `~` is expanded.
    - `stream: bool = False` — tees git's stdout/stderr to parent streams in real time. Useful for long fetches/clones/rebases.
    - `env: Mapping[str, str] | None = None` — REPLACES child env. Usual pattern: `{**os.environ, "GIT_SSH_COMMAND": "..."}`.
- **Outside a repo.** Two categories:
    - "Absent to empty" helpers return falsy/empty (`is_git_repo()` → `False`; `all_local_branches()` → empty `frozenset`). Safe as guards.
    - Everything else raises `NotARepoError`.

## Errors

| Exception                                      | When raised                                                                                                                                                                                                                   |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `NotARepoError`                                | Operation requires a repo, but `cwd` (or process cwd) is not inside one. Raised by `repo_root`, `is_dirty`, `is_rebase_in_progress`, `get_repo_state`, `fetch`, `stashed`, and `sync_branch` (transitively via `fetch`).      |
| `ValueError`                                   | Operation not well-defined: detached HEAD where a branch was needed, missing upstream, missing default branch, `start_point` without `new_branch=True`.                                                                       |
| `RuntimeError`                                 | Raised only by `add_worktree` when the new worktree is missing from the subsequent `git worktree list` (silent-bug guard).                                                                                                    |
| `nclutils.sh.ShellCommandError` and subclasses | Any subprocess failure (`git` not on PATH, non-zero exit, timeout). Catch the base class to handle all uniformly.                                                                                                             |

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

## Composites — reach for these first

### `get_repo_state(cwd=None) -> RepoState`

Snapshot a repo in one call. Issues a small number of subprocess calls (`rev-parse`, `status --porcelain=v2`, `stash list`, `rev-parse --absolute-git-dir`, plus `git remote` calls when at least one remote exists).

```python
state = get_repo_state()
print(f"on {state.branch} ({state.ahead} ahead, {state.behind} behind)")
if state.rebase_in_progress:
    print("rebase paused")
```

`RepoState` (frozen dataclass):

| Field                | Type             | Description                                                                                |
| -------------------- | ---------------- | ------------------------------------------------------------------------------------------ |
| `root`               | `Path`           | Absolute path to working tree root.                                                        |
| `branch`             | `str \| None`    | Short branch name; `None` on detached HEAD.                                                |
| `upstream`           | `str \| None`    | `<remote>/<branch>` (e.g. `"origin/main"`); `None` if no upstream.                         |
| `primary_remote`     | `Remote \| None` | First remote alphabetically (usually `"origin"`); `None` if no remotes.                    |
| `ahead`              | `int`            | Commits on local not on upstream. `0` if no upstream.                                      |
| `behind`             | `int`            | Commits on upstream not on local. `0` if no upstream.                                      |
| `is_dirty`           | `bool`           | `True` if any file count below is nonzero.                                                 |
| `staged`             | `int`            | Index changes.                                                                             |
| `modified`           | `int`            | Worktree changes (not yet staged).                                                         |
| `untracked`          | `int`            | Files not under version control.                                                           |
| `unmerged`           | `int`            | Files with merge conflicts.                                                                |
| `stash_count`        | `int`            | Stash entries for the current branch (filtered from `git stash list`).                     |
| `rebase_in_progress` | `bool`           | `True` if `.git/rebase-merge/` or `.git/rebase-apply/` exists.                             |

The four file-count fields are counts only. For paths, use `run_git("status", "--porcelain=v2")` or `run_git("diff", "--name-only", ...)`.

`Remote` (frozen dataclass): `name: str`, `url: str`, `web_url: str | None` (best-effort `https://<host>/<owner>/<repo>` rewrite for GitHub/GitLab/Bitbucket/Gitea/Forgejo/Codeberg/sourcehut; `None` for local paths or unrecognized hosts).

### `fetch(cwd=None, *, remote=None, prune=True, all_remotes=False, tags=True) -> None`

When `remote` is `None` and `all_remotes` is `False`, resolution order: current branch's upstream → `primary_remote()` → `ShellCommandFailedError`.

`prune=True` (default) removes stale remote-tracking refs. Almost always what you want.

### `stashed(cwd=None, *, message=None, include_untracked=True)` — context manager

```python
with stashed() as did_stash:
    run_git("checkout", "main")
    run_git("merge", "feature-branch")
# Stash popped here, even if the block raised.
```

- Yields `True` if a stash was created, `False` if tree was already clean.
- `include_untracked=True` (default) passes `-u` to `git stash push`.
- On exit, pops unconditionally. If the pop conflicts, the stash is LEFT on the stack and `ShellCommandFailedError` is raised — a pop failure supersedes any exception raised inside the block (the stash is the more recoverable artifact).

### `sync_branch(cwd=None, *, branch=None, stash=True, allow_rebase=True, on_conflict="abort") -> SyncResult`

Opinionated: refuses detached HEAD, requires an upstream, never merges (only fast-forwards or rebases), auto-stashes by default.

```python
result = sync_branch()
match result.action:
    case "up_to_date":     print("nothing to do")
    case "fast_forwarded": print(f"ff'd {result.behind_before} commits")
    case "rebased":        print(f"rebased {result.ahead_before} locals over upstream")
    case "aborted":        print("conflicts; aborted")
```

Sequence: resolve current branch → optional safety check vs `branch=` → resolve upstream → `fetch()` → compute ahead/behind → if behind 0, return `up_to_date` → if dirty and `stash=True`, wrap in `stashed()` → if ahead 0, try `git pull --ff-only` → otherwise `git pull --rebase` (if `allow_rebase=True`) → on conflict, abort+restore (default) or leave paused and raise.

`SyncResult` (frozen dataclass):

| Field           | Type                                                            | Description                                                                          |
| --------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `action`        | `Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]` | What the sync ended up doing.                                                        |
| `ahead_before`  | `int`                                                           | Commits ahead of upstream before the pull.                                           |
| `behind_before` | `int`                                                           | Commits behind upstream before the pull.                                             |
| `conflicts`     | `tuple[Path, ...]`                                              | Paths with conflicts, relative to repo root. Empty unless `action == "aborted"`.     |
| `stashed`       | `bool`                                                          | `True` if a stash was created (and popped for non-aborted actions).                  |

When `action="fast_forwarded"` or `"rebased"`, local branch contains remote commits. When `"aborted"`, local branch is exactly where it started; remote commits are still in `origin/<branch>` after the fetch but not integrated.

### `prunable_branches(*, merged=True, gone=True, include_empty=False, target=None, exclude=("main","master","develop")) -> list[PrunableBranch]`

Sorted list of branches safe to delete, with the reason each qualifies. Each item is a `PrunableBranch(name: str, reason: PruneReason)` frozen dataclass. `PruneReason` is `Literal["merged", "gone", "empty"]`.

When a branch qualifies under more than one criterion, the highest-precedence reason wins: `"gone"` > `"merged"` > `"empty"`. Results are sorted alphabetically by name.

Sources (each gated by a keyword):
- `merged=True`: branches fully merged into `target`.
- `gone=True`: branches whose upstream-tracking ref is `[gone]`.
- `include_empty=False`: when `True`, also surfaces branches with zero commits ahead of `target` that are not already classified as merged or gone (useful for catching placeholder branches that were created but never written to).

Current branch, the resolved `target`, and any name in `exclude` are filtered out. `target=None` defers to `default_branch()`; if that also returns `None`, `ValueError`.

```python
from nclutils.git import prunable_branches, delete_branches

candidates = prunable_branches()
for pb in candidates:
    print(f"{pb.name}: {pb.reason}")

# Extract names before passing to delete_branches
outcome = delete_branches([pb.name for pb in candidates])
```

> [!WARNING]
> `prunable_branches` returns `list[PrunableBranch]`, not `list[str]`. Passing its result directly to `delete_branches` is a type error. Always extract `.name` first.

### `delete_branches(branches, *, force=False) -> DeleteOutcome`

Takes a sequence of short names; returns a `DeleteOutcome` frozen dataclass describing what happened per branch.

`DeleteOutcome` fields:

| Field     | Type               | Description                                                                             |
| --------- | ------------------ | --------------------------------------------------------------------------------------- |
| `deleted` | `tuple[str, ...]`  | Branches actually deleted, in input order.                                               |
| `skipped` | `tuple[str, ...]`  | Branches skipped (current branch or not present locally).                               |
| `failed`  | `dict[str, str]`   | Branches whose `git branch -d/-D` failed. Value is the captured stderr message.         |

Per-branch failures are captured in `failed`, not raised. Only infrastructural errors (git missing, not a repo) propagate. `force=True` uses `git branch -D` (deletes regardless of merge state).

```python
outcome = delete_branches([pb.name for pb in prunable_branches()])
print(f"deleted={outcome.deleted} skipped={outcome.skipped}")
if outcome.failed:
    for branch, msg in outcome.failed.items():
        print(f"FAILED {branch}: {msg}")
```

> [!WARNING]
> `delete_branches` returns a `DeleteOutcome` dataclass, not `list[str]`. Read results via `outcome.deleted`, `outcome.skipped`, `outcome.failed`. Per-branch failures land in `outcome.failed[name]` (stderr) rather than raising.

### `add_worktree(path, branch, *, new_branch=False, start_point=None, track=None) -> Worktree`

Composes `create_worktree` and `list_worktrees`. Returns the populated `Worktree` record with the resolved HEAD SHA. Raises `RuntimeError` if the new worktree is missing from the subsequent listing.

`track: bool | None = None` controls upstream tracking for the new branch: `None` leaves git's default intact; `True` passes `--track`; `False` passes `--no-track`. Use `track=False` for short-lived feature branches that should not auto-track a remote.

`Worktree` (frozen dataclass): `path: Path`, `branch: str | None`, `head: str`, `is_bare: bool`, `is_detached: bool`, `is_locked: bool`.

## Primitives

When composites don't fit, drop down. Every primitive accepts `cwd=`, `stream=`, `env=`.

### Repo

- `is_git_installed() -> bool` — `True` if `git` is on PATH. Uses `nclutils.sh.which`; no subprocess.
- `is_git_repo(cwd=None) -> bool` — `True` if inside a working tree. Never raises.
- `repo_root(cwd=None) -> Path` — absolute path to working tree root.
- `primary_remote(cwd=None) -> Remote | None` — first remote alphabetically, or `None`.
- `is_dirty(cwd=None) -> bool` — `True` if `git status --porcelain` non-empty.
- `is_rebase_in_progress(cwd=None) -> bool` — checks for `.git/rebase-merge/` or `.git/rebase-apply/`.
- `stash_counts(cwd=None) -> dict[str, int]`: per-branch stash counts across the whole repo. Detached-HEAD stashes excluded. Use when you need counts beyond just the current branch (which `RepoState.stash_count` already provides).

### Branch (all short names)

- `current_branch(cwd=None) -> str | None` — `None` on detached HEAD. Outside a repo, underlying call raises `ShellCommandFailedError`.
- `default_branch(cwd=None, *, remote="origin") -> str | None` — short name of `<remote>/HEAD`, or `None` if unset. Set via `git remote set-head <remote> -a`.
- `branch_exists(branch, cwd=None) -> bool` — local only; does NOT check remote-tracking branches.
- `all_local_branches(cwd=None) -> frozenset[str]` — empty `frozenset` outside a repo.
- `tracking_branch(branch=None, cwd=None) -> tuple[str, str] | None` — `(remote, branch_on_remote)` or `None`. `branch=None` means current; detached HEAD returns `None`.
- `ahead_behind(left, right, cwd=None) -> tuple[int, int]` — accepts anything `git rev-parse` accepts.
- `merged_branches(target=None, cwd=None) -> frozenset[str]` — includes `target` itself.
- `gone_branches(cwd=None) -> frozenset[str]` — appears after `git fetch --prune`.
- `is_empty_branch(branch, target=None, *, cwd=None) -> bool`: `True` when `branch` has zero commits ahead of `target`. `target=None` defers to `default_branch()`; raises `ValueError` if that also returns `None`. The primitive behind `prunable_branches(include_empty=True)`.

### Worktree

- `list_worktrees(cwd=None) -> list[Worktree]` — all registered worktrees (bare repo's bare worktree has `is_bare=True`).
- `create_worktree(path, branch, *, new_branch=False, start_point=None, track=None) -> None`: `start_point` requires `new_branch=True`. `track=None` passes no flag; `True` passes `--track`; `False` passes `--no-track`.
- `remove_worktree(path, *, force=False) -> None` — `force=True` for dirty worktrees or submodules.

### Runner — escape hatch

`run_git(*args, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,)) -> CompletedCommand`

Prepends `git` to args; forwards every option to `nclutils.sh.run_command`. Reach for it when:

- No primitive covers the subcommand (`git log`, `git show`, `git tag`).
- You need options the helpers don't expose (`--no-color`, `--max-count`, custom formats).
- You need the raw `CompletedCommand`.

```python
result = run_git("log", "--oneline", "-5")
for line in result.stdout.splitlines():
    print(line)

# Inspect without raising
result = run_git("diff", "--quiet", check=False)
print("dirty" if result.returncode != 0 else "clean")
```

## Diagnostic logging

Every git invocation is logged at `DEBUG` by `nclutils.sh.run_command` (which `run_git` delegates to). Records arrive under the `nclutils.sh` logger, NOT `nclutils.git`. The git module never writes to the console directly. For visible progress, pass `stream=True`.
