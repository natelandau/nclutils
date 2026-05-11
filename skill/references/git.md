# `nclutils.git` reference

Git operations through the `git` binary via `nclutils.sh.run_command`. No third-party git library, no in-process libgit2 binding, no global state. Process semantics match command-line `git`: hooks fire, config loads normally, `GIT_*` env vars work.

## Conventions

- **Short names everywhere.** Branch helpers take and return short names (`"main"`, NOT `"refs/heads/main"`). Remotes are short too (`"origin"`). Exception: `ahead_behind` accepts anything `git rev-parse` accepts (SHAs, tags, expressions like `HEAD~3` or `origin/main`).
- **Uniform `cwd`, `stream`, `env`.** EVERY helper (composite and primitive) accepts these three with identical meaning:
    - `cwd: Path | str | None = None` — repo to operate on. `None` uses process cwd. `~` is expanded.
    - `stream: bool = False` — tees git's stdout/stderr to parent streams in real time. Useful for long fetches/clones/rebases.
    - `env: Mapping[str, str] | None = None` — REPLACES child env. Usual pattern: `{**os.environ, "GIT_SSH_COMMAND": "..."}`.
- **Outside a repo.** Two categories:
    - "Absent to empty" helpers return falsy/empty (`is_git_repo()` → `False`; `all_local_branches()` → empty `frozenset`). Safe as guards.
    - Everything else raises `NotARepoError`.
- **All keyword args after `cwd` are keyword-only** (every function in this module uses `*` to separate positional from keyword args). The function signatures below match the real source exactly.

## Errors

| Exception                                      | When raised                                                                                                                                                                                                                   |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `NotARepoError`                                | Operation requires a repo, but `cwd` (or process cwd) is not inside one. Raised by `repo_root`, `is_dirty`, `is_rebase_in_progress`, `get_repo_state`, `fetch`, `stashed`, and `sync_branch` (transitively via `fetch`).      |
| `ValueError`                                   | Operation not well-defined: detached HEAD where a branch was needed, missing upstream, missing default branch, `start_point` without `new_branch=True`, `branch=` mismatch in `sync_branch`.                                  |
| `RuntimeError`                                 | Raised only by `add_worktree` when the new worktree is missing from the subsequent `git worktree list` (silent-bug guard).                                                                                                    |
| `nclutils.sh.ShellCommandError` and subclasses | Any subprocess failure (`git` not on PATH → `ShellCommandNotFoundError`; non-zero exit → `ShellCommandFailedError`; timeout → `ShellCommandTimeoutError`). Catch the base class to handle all uniformly.                      |

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

### `get_repo_state`

```python
get_repo_state(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> RepoState
```

Snapshot a repo in one call. Issues these subprocess calls under the hood:

1. `git rev-parse --show-toplevel` (via `repo_root`) — for the root path; surfaces `NotARepoError` cleanly before anything else runs.
2. `git status --branch --porcelain=v2` — for branch, upstream, ahead/behind, and the four file counts.
3. `git stash list` — filtered to entries created on the current branch.
4. `git rev-parse --absolute-git-dir` (via `is_rebase_in_progress`) — to check for `rebase-merge/` and `rebase-apply/`.
5. `git remote` and `git remote get-url` (via `primary_remote`) — only when at least one remote is configured.

Raises `NotARepoError` outside a repo.

```python
state = get_repo_state()
print(f"on {state.branch} ({state.ahead} ahead, {state.behind} behind)")
if state.rebase_in_progress:
    print("rebase paused")
```

`RepoState` (frozen dataclass, `slots=True`):

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
| `stash_count`        | `int`            | Stash entries created on the current branch (filtered from `git stash list`).              |
| `rebase_in_progress` | `bool`           | `True` if `.git/rebase-merge/` or `.git/rebase-apply/` exists.                             |

The four file-count fields are counts only. For paths, use `run_git("status", "--porcelain=v2")` or `run_git("diff", "--name-only", ...)`.

`Remote` (frozen dataclass, `slots=True`):

| Field     | Type          | Description                                                                                                                                                                                          |
| --------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`    | `str`         | Short remote name (e.g. `"origin"`).                                                                                                                                                                 |
| `url`     | `str`         | Configured fetch URL exactly as `git remote get-url` returns it.                                                                                                                                     |
| `web_url` | `str \| None` | Best-effort `https://<host>/<owner>/<repo>` rewrite covering GitHub/GitLab/Bitbucket/Gitea/Forgejo/Codeberg/sourcehut and similar forges. Strips trailing `.git`, drops user/port, rewrites scheme to `https`. `None` for local paths, `file://` URLs, or anything without a recognizable host. |

### `fetch`

```python
fetch(
    cwd: Path | str | None = None,
    *,
    remote: str | None = None,
    prune: bool = True,
    all_remotes: bool = False,
    tags: bool = True,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> None
```

When `remote` is `None` and `all_remotes` is `False`, resolution order: current branch's upstream remote → `primary_remote()` → `ShellCommandFailedError` if neither exists. `prune=True` (default) removes stale remote-tracking refs (almost always what you want). `tags=False` adds `--no-tags`. `all_remotes=True` runs `git fetch --all` and ignores `remote`/`tags`/the upstream resolution.

Validates the repo via `repo_root(cwd)` before issuing the fetch, so non-repo cwd raises `NotARepoError` (not `ShellCommandFailedError`).

### `stashed` (context manager)

```python
@contextmanager
def stashed(
    cwd: Path | str | None = None,
    *,
    message: str | None = None,
    include_untracked: bool = True,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> Iterator[bool]
```

```python
with stashed() as did_stash:
    run_git("checkout", "main")
    run_git("merge", "feature-branch")
# Stash popped here, even if the block raised.
```

- Yields `True` if a stash was created, `False` if tree was already clean (no-op on both entry and exit).
- `include_untracked=True` (default) passes `-u` to `git stash push`. `message=` passes `-m <message>`.
- On exit, pops unconditionally. If the pop conflicts, the stash is LEFT on the stack and `ShellCommandFailedError` is raised — a pop failure supersedes any exception raised inside the block (the stash is the more recoverable artifact).
- Raises `NotARepoError` outside a repo (via the `is_dirty` check on entry).

### `sync_branch`

```python
sync_branch(
    cwd: Path | str | None = None,
    *,
    branch: str | None = None,
    stash: bool = True,
    allow_rebase: bool = True,
    on_conflict: Literal["abort", "leave"] = "abort",
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> SyncResult
```

Opinionated workflow: refuses detached HEAD, requires an upstream, never merges (only fast-forwards or rebases), auto-stashes by default. The `branch=` parameter is a safety check (must equal the current branch when set); it does NOT sync a non-checked-out branch.

```python
result = sync_branch()
match result.action:
    case "up_to_date":     print("nothing to do")
    case "fast_forwarded": print(f"ff'd {result.behind_before} commits")
    case "rebased":        print(f"rebased {result.ahead_before} locals over upstream")
    case "aborted":        print("conflicts; aborted")
```

Sequence (in order):

1. `repo_root(cwd)` → raise `NotARepoError` if not a repo.
2. `current_branch(cwd)` → raise `ValueError` if detached HEAD.
3. If `branch=` was passed and doesn't match the current branch → raise `ValueError`.
4. `tracking_branch(current, cwd)` → raise `ValueError` if no upstream.
5. `fetch(cwd, remote=<upstream remote>)`.
6. `ahead_behind(current, upstream_ref)`. If behind == 0 → return `action="up_to_date"`.
7. If dirty and `stash=False` → raise `ShellCommandFailedError`. If dirty and `stash=True` → wrap rest in `stashed(cwd)`.
8. If ahead == 0 → try `git pull --ff-only`. On success → return `action="fast_forwarded"`.
9. Otherwise (or if ff-only failed), and `allow_rebase=True` → `git pull --rebase`. On success → return `action="rebased"`. With `allow_rebase=False` → raise `ShellCommandFailedError`.
10. On rebase conflict:
    - `on_conflict="abort"` (default) → `git rebase --abort`, restore stash, return `action="aborted"` with `conflicts` populated (paths relative to repo root, from `git diff --name-only --diff-filter=U`).
    - `on_conflict="leave"` → leave rebase paused, stash unpopped, raise `ShellCommandFailedError`.

`SyncResult` (frozen dataclass, `slots=True`):

| Field           | Type                                                            | Description                                                                          |
| --------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `action`        | `Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]` | What the sync ended up doing.                                                        |
| `ahead_before`  | `int`                                                           | Commits ahead of upstream before the pull.                                           |
| `behind_before` | `int`                                                           | Commits behind upstream before the pull.                                             |
| `conflicts`     | `tuple[Path, ...]`                                              | Paths with conflicts, relative to repo root. Empty unless `action == "aborted"`.     |
| `stashed`       | `bool`                                                          | `True` if a stash was created (and popped for non-aborted actions).                  |

When `action="fast_forwarded"` or `"rebased"`, local branch contains remote commits. When `"aborted"`, local branch is exactly where it started; remote commits are still in `origin/<branch>` after the fetch but not integrated.

### `prunable_branches`

```python
prunable_branches(
    cwd: Path | str | None = None,
    *,
    merged: bool = True,
    gone: bool = True,
    include_empty: bool = False,
    target: str | None = None,
    exclude: tuple[str, ...] = ("main", "master", "develop"),
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> list[PrunableBranch]
```

Sorted list of branches safe to delete, with the reason each qualifies. Each item is a `PrunableBranch(name: str, reason: PruneReason)` frozen dataclass. `PruneReason` is `Literal["merged", "gone", "empty"]`.

When a branch qualifies under more than one criterion, the highest-precedence reason wins: `"gone"` > `"merged"` > `"empty"`. Results are sorted alphabetically by name.

Sources (each gated by a keyword):

- `merged=True` (default): branches fully merged into `target` (per `git branch --merged <target>`).
- `gone=True` (default): branches whose upstream-tracking ref shows `[gone]` (parsed from `git branch -vv`; appears after `git fetch --prune`).
- `include_empty=False`: when `True`, also surfaces branches with zero commits ahead of `target` that are not already classified as merged or gone. Catches placeholder branches that were created but never written to.

The current branch, the resolved `target`, and any name in `exclude` are filtered out. `target=None` defers to `default_branch(cwd)`; if that also returns `None` AND `merged` or `include_empty` is enabled, raises `ValueError`. (When both `merged=False` and `include_empty=False`, `target` is not needed and `gone_branches` alone is used.)

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

### `delete_branches`

```python
delete_branches(
    branches: Sequence[str],
    cwd: Path | str | None = None,
    *,
    force: bool = False,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> DeleteOutcome
```

Takes a sequence of short names; returns a `DeleteOutcome` frozen dataclass describing what happened per branch. Skips (does not attempt) the current branch and branches that do not exist locally. `force=True` uses `git branch -D` (deletes regardless of merge state) instead of `git branch -d`.

`DeleteOutcome` fields (`slots=True`):

| Field     | Type               | Description                                                                             |
| --------- | ------------------ | --------------------------------------------------------------------------------------- |
| `deleted` | `tuple[str, ...]`  | Branches actually deleted, in input order.                                              |
| `skipped` | `tuple[str, ...]`  | Branches skipped (current branch or not present locally).                               |
| `failed`  | `dict[str, str]`   | Branches whose `git branch -d/-D` failed. Value is the captured stderr message (or `"git branch failed (exit N)"` if stderr was empty). |

Per-branch failures are captured in `failed`, not raised. Only infrastructural errors (git missing, not a repo) propagate.

```python
outcome = delete_branches([pb.name for pb in prunable_branches()])
print(f"deleted={outcome.deleted} skipped={outcome.skipped}")
if outcome.failed:
    for branch, msg in outcome.failed.items():
        print(f"FAILED {branch}: {msg}")
```

> [!WARNING]
> `delete_branches` returns a `DeleteOutcome` dataclass, not `list[str]`. Read results via `outcome.deleted`, `outcome.skipped`, `outcome.failed`. Per-branch failures land in `outcome.failed[name]` (stderr) rather than raising.

### `add_worktree`

```python
add_worktree(
    path: Path | str,
    branch: str,
    *,
    cwd: Path | str | None = None,
    new_branch: bool = False,
    start_point: str | None = None,
    track: bool | None = None,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> Worktree
```

Composes `create_worktree` (the actual `git worktree add`) and `list_worktrees` (to read back the resolved record, including HEAD SHA). Raises `RuntimeError` if the new worktree is missing from the subsequent listing (silent-bug guard; should not fire in practice).

Arguments:

- `path` (positional): filesystem path for the new worktree.
- `branch` (positional): branch to check out, OR (with `new_branch=True`) branch to create.
- `cwd` (kw): working directory of the SOURCE repo; `None` inherits process cwd. The new worktree lives at `path`, independent of `cwd`.
- `new_branch=True`: passes `-b` to `git worktree add` to create the branch as part of the operation.
- `start_point`: commit/ref the new branch starts from. Requires `new_branch=True`; raises `ValueError` otherwise.
- `track`: tri-state upstream tracking control.
    - `None` (default) → no flag; git's default applies.
    - `True` → `--track` (force tracking even against a non-remote ref).
    - `False` → `--no-track` (suppress automatic tracking even when start point is a remote-tracking ref). Use for short-lived feature branches.

`Worktree` (frozen dataclass, `slots=True`):

| Field         | Type          | Description                                                                                  |
| ------------- | ------------- | -------------------------------------------------------------------------------------------- |
| `path`        | `Path`        | Filesystem path as reported by `git worktree list` (NOT necessarily resolved/absolute).      |
| `branch`      | `str \| None` | Short branch name checked out; `None` on detached HEAD.                                      |
| `head`        | `str`         | Full commit SHA at HEAD.                                                                     |
| `is_bare`     | `bool`        | `True` for the bare worktree of a bare repo.                                                 |
| `is_detached` | `bool`        | `True` if HEAD is detached.                                                                  |
| `is_locked`   | `bool`        | `True` if the worktree is locked.                                                            |

## Primitives

When composites don't fit, drop down. Every primitive accepts `cwd=`, `stream=`, `env=`.

### Repo primitives

```python
is_git_installed() -> bool
```
`True` if `git` is on PATH. Uses `nclutils.sh.which`; no subprocess.

```python
is_git_repo(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool
```
`True` if cwd is inside a working tree (`git rev-parse --is-inside-work-tree`). Never raises.

```python
repo_root(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> Path
```
Absolute path to working tree root (from `git rev-parse --show-toplevel`). Raises `NotARepoError` outside a repo.

```python
primary_remote(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> Remote | None
```
First configured remote (`git remote`, alphabetical), populated via `git remote get-url`. `None` if no remotes. Returns the same `Remote` shape as `RepoState.primary_remote`.

```python
is_dirty(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool
```
`True` if `git status --porcelain` produces any output (counts both index changes and untracked files). Raises `NotARepoError` outside a repo.

```python
is_rebase_in_progress(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool
```
`True` if `<git-dir>/rebase-merge/` (interactive) or `<git-dir>/rebase-apply/` (non-interactive) exists. Raises `NotARepoError` outside a repo.

```python
stash_counts(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, int]
```
Per-branch stash counts across the whole repo, parsed from `git stash list`. Detached-HEAD stashes (where the line shows `(no branch)`) are excluded — they have no branch key. Use when you need counts beyond just the current branch (which `RepoState.stash_count` already provides).

### Branch primitives (all short names)

```python
current_branch(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> str | None
```
`None` on detached HEAD. Implemented via `git symbolic-ref --short HEAD`. Outside a repo, returns `None` (the call uses `check=False`).

```python
default_branch(
    cwd: Path | str | None = None,
    *,
    remote: str = "origin",
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> str | None
```
Short name of `<remote>/HEAD` (from `git symbolic-ref refs/remotes/<remote>/HEAD`), or `None` if unset. The symref is configured automatically by `git clone` and can be re-resolved with `git remote set-head <remote> -a`.

```python
branch_exists(
    branch: str,
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool
```
`True` if `branch` exists locally (`git rev-parse --verify refs/heads/<branch>`). Does NOT check remote-tracking branches.

```python
all_local_branches(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> frozenset[str]
```
Set of short local branch names. Empty `frozenset` outside a repo.

```python
tracking_branch(
    branch: str | None = None,
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str] | None
```
`(remote_short, branch_on_remote_short)` for the upstream of `branch`. `branch=None` means current; detached HEAD returns `None`. Reads `branch.<name>.remote` and `branch.<name>.merge` from git config; returns `None` if either is unset.

```python
ahead_behind(
    left: str,
    right: str,
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> tuple[int, int]
```
`(ahead, behind)` commit counts from `git rev-list --left-right --count left...right`. Accepts anything `git rev-parse` accepts on both sides. Returns `(0, 0)` if the output can't be parsed (defensive).

```python
is_empty_branch(
    branch: str,
    target: str | None = None,
    *,
    cwd: Path | str | None = None,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool
```
`True` when `branch` has zero commits ahead of `target`. `target=None` defers to `default_branch(cwd)`; raises `ValueError` if that also returns `None`. Primitive behind `prunable_branches(include_empty=True)`.

```python
merged_branches(
    target: str | None = None,
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> frozenset[str]
```
Local branches merged into `target` (from `git branch --merged <target>`). INCLUDES `target` itself — callers performing cleanup should filter it. `target=None` defers to `default_branch(cwd)`; raises `ValueError` if that returns `None`. A non-existent `target` ref raises `ShellCommandFailedError`.

```python
gone_branches(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> frozenset[str]
```
Branches whose upstream tracking ref shows `[gone]`. Parses `git branch -vv --no-color` for the `[<upstream>: gone]` marker. Markers appear after `git fetch --prune` removes the remote ref.

### Worktree primitives

```python
list_worktrees(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> list[Worktree]
```
All registered worktrees parsed from `git worktree list --porcelain`. The bare worktree of a bare repo appears with `is_bare=True`.

```python
create_worktree(
    path: Path | str,
    branch: str,
    *,
    cwd: Path | str | None = None,
    new_branch: bool = False,
    start_point: str | None = None,
    track: bool | None = None,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> None
```
Runs `git worktree add`. `start_point` requires `new_branch=True` (else `ValueError`). `track`: `None` → no flag; `True` → `--track`; `False` → `--no-track`. Argument order to git: `worktree add [--track|--no-track] [-b <branch> <path> [start_point] | <path> <branch>]`.

```python
remove_worktree(
    path: Path | str,
    *,
    cwd: Path | str | None = None,
    force: bool = False,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> None
```
Runs `git worktree remove`. `force=True` adds `--force` (required for dirty worktrees or those with submodules).

### Runner — escape hatch

```python
run_git(
    *args: str,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    input: str | bytes | None = None,
    timeout: float | None = None,
    exclude_regex: str | None = None,
    stream: bool = False,
    check: bool = True,
    okay_codes: tuple[int, ...] = (0,),
) -> CompletedCommand
```

Prepends `git` to `args` and forwards every option to `nclutils.sh.run_command`. Reach for it when:

- No primitive covers the subcommand (`git log`, `git show`, `git tag`).
- You need options the helpers don't expose (`--no-color`, `--max-count`, custom formats).
- You need the raw `CompletedCommand` (`stdout`, `stderr`, `returncode`, `duration`, `argv`, `cwd`).

```python
result = run_git("log", "--oneline", "-5")
for line in result.stdout.splitlines():
    print(line)

# Inspect exit code without raising
result = run_git("diff", "--quiet", check=False)
print("dirty" if result.returncode != 0 else "clean")
```

`CompletedCommand` is the same shape returned by `nclutils.sh.run_command`. Raises `ShellCommandNotFoundError` if `git` is missing, `ShellCommandFailedError` on non-zero exit (when `check=True` and code not in `okay_codes`), `ShellCommandTimeoutError` on timeout. Note: `run_git` itself does NOT raise `NotARepoError` — only the higher-level helpers translate "not a repo" into `NotARepoError`. With `run_git`, a non-repo cwd produces a `ShellCommandFailedError` (since `git` itself exits non-zero with "fatal: not a git repository").

## Diagnostic logging

Every git invocation is logged at `DEBUG` by `nclutils.sh.run_command` (which `run_git` delegates to). Records arrive under the `nclutils.sh` logger, NOT `nclutils.git`. The git module never writes to the console directly. For visible progress, pass `stream=True`.

```python
import logging
logging.getLogger("nclutils.sh").setLevel(logging.DEBUG)
logging.basicConfig()
```

## API reference (signatures only)

Quick flat lookup. Same information as above, condensed.

### Foundation

```python
class NotARepoError(Exception): ...

run_git(*args: str, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,)) -> CompletedCommand
```

### Repo

```python
is_git_installed() -> bool
is_git_repo(cwd=None, *, stream=False, env=None) -> bool
repo_root(cwd=None, *, stream=False, env=None) -> Path
primary_remote(cwd=None, *, stream=False, env=None) -> Remote | None
is_dirty(cwd=None, *, stream=False, env=None) -> bool
is_rebase_in_progress(cwd=None, *, stream=False, env=None) -> bool
stash_counts(cwd=None, *, stream=False, env=None) -> dict[str, int]
get_repo_state(cwd=None, *, stream=False, env=None) -> RepoState

@dataclass(frozen=True, slots=True)
class Remote:
    name: str
    url: str
    web_url: str | None

@dataclass(frozen=True, slots=True)
class RepoState:
    root: Path
    branch: str | None
    upstream: str | None
    primary_remote: Remote | None
    ahead: int
    behind: int
    is_dirty: bool
    staged: int
    modified: int
    untracked: int
    unmerged: int
    stash_count: int
    rebase_in_progress: bool
```

### Branch

```python
current_branch(cwd=None, *, stream=False, env=None) -> str | None
default_branch(cwd=None, *, remote="origin", stream=False, env=None) -> str | None
branch_exists(branch, cwd=None, *, stream=False, env=None) -> bool
all_local_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]
tracking_branch(branch=None, cwd=None, *, stream=False, env=None) -> tuple[str, str] | None
ahead_behind(left, right, cwd=None, *, stream=False, env=None) -> tuple[int, int]
is_empty_branch(branch, target=None, *, cwd=None, stream=False, env=None) -> bool
merged_branches(target=None, cwd=None, *, stream=False, env=None) -> frozenset[str]
gone_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]
prunable_branches(cwd=None, *, merged=True, gone=True, include_empty=False, target=None, exclude=("main","master","develop"), stream=False, env=None) -> list[PrunableBranch]
delete_branches(branches, cwd=None, *, force=False, stream=False, env=None) -> DeleteOutcome

PruneReason = Literal["merged", "gone", "empty"]

@dataclass(frozen=True, slots=True)
class PrunableBranch:
    name: str
    reason: PruneReason

@dataclass(frozen=True, slots=True)
class DeleteOutcome:
    deleted: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: dict[str, str]
```

### Sync

```python
fetch(cwd=None, *, remote=None, prune=True, all_remotes=False, tags=True, stream=False, env=None) -> None

@contextmanager
def stashed(cwd=None, *, message=None, include_untracked=True, stream=False, env=None) -> Iterator[bool]: ...

sync_branch(cwd=None, *, branch=None, stash=True, allow_rebase=True, on_conflict="abort", stream=False, env=None) -> SyncResult

@dataclass(frozen=True, slots=True)
class SyncResult:
    action: Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]
    ahead_before: int
    behind_before: int
    conflicts: tuple[Path, ...] = ()
    stashed: bool = False
```

### Worktree

```python
list_worktrees(cwd=None, *, stream=False, env=None) -> list[Worktree]
create_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None, track=None, stream=False, env=None) -> None
remove_worktree(path, *, cwd=None, force=False, stream=False, env=None) -> None
add_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None, track=None, stream=False, env=None) -> Worktree

@dataclass(frozen=True, slots=True)
class Worktree:
    path: Path
    branch: str | None
    head: str
    is_bare: bool
    is_detached: bool
    is_locked: bool
```
