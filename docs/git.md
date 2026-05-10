# Git

Git operations for Python scripts. Each helper shells out to the `git` binary through `nclutils.sh.run_command`, so a working `git` install is the only runtime requirement. There is no third-party git library, no in-process libgit2 binding, and no global state.

```python
from nclutils.git import get_repo_state, sync_branch

state = get_repo_state()
if state.behind > 0 and not state.is_dirty:
    result = sync_branch()
    print(result.action)  # "up_to_date", "fast_forwarded", "rebased", or "aborted"
```

## When to use this module

You probably already use the `git` binary or a library like `GitPython`. This module is aimed at scripts that need a handful of common operations without the weight of a full git library:

- Checking repo state (current branch, dirty, ahead/behind, stash count) in a way that's easy to act on.
- Running everyday workflows (fetch then rebase, stash around a risky operation, clean up merged branches) as a single call.
- Driving git worktrees from Python with structured results.
- Calling arbitrary git subcommands when the helpers don't fit, with the same logging and error handling as everything else.

Process semantics match `git` on the command line. Hooks fire, configuration loads the same way, and `GIT_*` environment variables work as documented. The cost is that parsing porcelain output is on the caller for anything the composites don't already cover. The composites in this module do that parsing for the workflows that come up most often.

Errors come back as `ShellCommandError` (from `nclutils.sh`), `NotARepoError`, or `ValueError`. The exception hierarchy is small on purpose; there's nothing new to learn beyond what `nclutils.sh` already exposes.

## Conventions

A few conventions apply across every helper.

### Short names everywhere

Every helper that takes or returns a branch uses the short name: `"main"`, not `"refs/heads/main"`; `("origin", "main")`, not `("origin", "refs/heads/main")`. Remote names are short too (`"origin"`, not a URL).

The one exception is `ahead_behind`, which accepts anything `git rev-parse` accepts: branch names, SHAs (full or short), tags, or expressions like `HEAD~3` or `origin/main`.

### `cwd`, `stream`, and `env` are uniform

Every helper accepts the same three forwarding arguments, with the same meaning everywhere:

- `cwd: Path | str | None = None`. The repo to operate on. The default `None` uses the process's current working directory. `~` is expanded.
- `stream: bool = False`. When `True`, tees git's stdout/stderr to the parent streams in real time. Useful for long-running operations like fetch, clone, or rebase where progress matters.
- `env: Mapping[str, str] | None = None`. Replaces the child environment. The usual pattern is `{**os.environ, "GIT_SSH_COMMAND": "..."}` so the rest of the environment is preserved.

These pass straight through to `run_git`, which forwards them to `nclutils.sh.run_command`.

```python
from nclutils.git import current_branch, fetch

current_branch(cwd="~/projects/my-app")
fetch(cwd="/srv/repo", stream=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
```

### Outside a repo

Helpers split into two categories when `cwd` is not inside a git repo:

- "Absent to empty" helpers return a falsy or empty value: `is_git_repo()` returns `False`, `all_local_branches()` returns an empty frozenset. Safe to use as guards.
- Everything else raises `NotARepoError`. The exception name is intentional; `git` itself returns a generic "not a git repository" error, and `NotARepoError` lifts that into a class you can catch.

## Composites

Composites wrap multi-step workflows behind a single call. Reach for these first; drop down to the primitives below only when no composite fits.

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

`RepoState` is a frozen dataclass:

| Field                | Type             | Description                                                                                                                        |
| -------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `root`               | `Path`           | Absolute path to the working tree root.                                                                                            |
| `branch`             | `str \| None`    | Short branch name; `None` on detached HEAD.                                                                                        |
| `upstream`           | `str \| None`    | Upstream as `<remote>/<branch>` (e.g., `"origin/main"`); `None` if no upstream is configured.                                      |
| `primary_remote`     | `Remote \| None` | The first configured remote (alphabetical, usually `"origin"`); `None` if no remotes are configured. See the `Remote` table below. |
| `ahead`              | `int`            | Commits on the local branch not on the upstream. `0` if there is no upstream.                                                      |
| `behind`             | `int`            | Commits on the upstream not on the local branch. `0` if there is no upstream.                                                      |
| `is_dirty`           | `bool`           | `True` if any of the file counts below are nonzero.                                                                                |
| `staged`             | `int`            | Count of files with index changes.                                                                                                 |
| `modified`           | `int`            | Count of files with worktree changes (not yet staged).                                                                             |
| `untracked`          | `int`            | Count of files not under version control.                                                                                          |
| `unmerged`           | `int`            | Count of files with merge conflicts.                                                                                               |
| `stash_count`        | `int`            | Stash entries created on the current branch (filtered from `git stash list`).                                                      |
| `rebase_in_progress` | `bool`           | `True` if `.git/rebase-merge/` or `.git/rebase-apply/` exists.                                                                     |

`Remote` is a frozen dataclass with three fields:

| Field     | Type          | Description                                                                                                                                                                                                                                                                                                       |
| --------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`    | `str`         | Short remote name (e.g., `"origin"`).                                                                                                                                                                                                                                                                             |
| `url`     | `str`         | Configured fetch URL (e.g., `"git@github.com:org/repo.git"`).                                                                                                                                                                                                                                                     |
| `web_url` | `str \| None` | Best-effort browser URL inferred from `url`: an `https://<host>/<owner>/<repo>` rewrite that works for hosts following the common forge layout (GitHub, GitLab, Bitbucket, Gitea, Forgejo, Codeberg, sourcehut). `None` for local paths, `file://` URLs, or anything without a recognizable host. |

`get_repo_state` issues a small number of subprocess calls under the hood: `rev-parse --show-toplevel`, `status --branch --porcelain=v2`, `stash list`, `rev-parse --absolute-git-dir`, plus `git remote` and `git remote get-url` for `primary_remote` (the last one runs only when at least one remote is configured). It still beats assembling those primitive calls by hand because callers don't have to parse the porcelain output themselves. Raises `NotARepoError` outside a repo.

> [!NOTE]
> The four file-count fields are counts, not lists. If you need the actual paths, use `run_git("status", "--porcelain=v2", ...)` and parse it yourself, or `run_git("diff", "--name-only", ...)` for a specific filter.

### `fetch`

Fetch from a remote with prune-by-default behavior. Returns `None`.

```python
from nclutils.git import fetch

# Fetch the current branch's upstream remote (falls back to primary_remote)
fetch()

# Fetch a specific remote
fetch(remote="upstream")

# Fetch every remote (git fetch --all)
fetch(all_remotes=True)

# Skip tags
fetch(tags=False)

# Stream progress to the terminal
fetch(stream=True)
```

When `remote` is `None` and `all_remotes` is `False`, the remote is resolved in this order: the upstream of the current branch, then `primary_remote()`, then a `ShellCommandFailedError` if neither exists.

`prune=True` (the default) removes stale remote-tracking refs. This is almost always what you want; without it, branches deleted on the remote keep showing up locally as `origin/<branch>`.

Raises `NotARepoError` outside a repo, and `ShellCommandFailedError` if no remote can be resolved or the fetch itself fails.

### `stashed`

Context manager that stashes uncommitted changes on entry and pops on exit. Yields `True` if a stash was created, `False` if the tree was already clean.

```python
from nclutils.git import stashed, run_git

with stashed() as did_stash:
    run_git("checkout", "main")
    run_git("merge", "feature-branch")
# Stash is popped here, even if the block raised.
```

Behavior:

- If the tree is clean on entry, no stash is created and the context manager yields `False`. The exit step does nothing.
- If the tree is dirty, `git stash push -u` runs (the `-u` includes untracked files).
- On exit, the stash is popped unconditionally.
- If the pop conflicts, the stash is left on the stack and `ShellCommandFailedError` is raised. A pop failure supersedes any exception raised inside the block, since the stash is the more recoverable artifact.

`include_untracked=True` (the default) passes `-u` to `git stash push`. Pass `message="..."` to set a stash message visible in `git stash list`.

Raises `NotARepoError` outside a repo, and `ShellCommandFailedError` if either the push or the pop fails.

### `sync_branch`

The opinionated workflow composite. Fetches the upstream, optionally stashes a dirty tree, then either fast-forwards or rebases the current branch. Returns a `SyncResult` describing what happened.

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

`sync_branch` is more opinionated than `git pull`, not more flexible. It refuses detached HEAD, requires an upstream, never merges (only fast-forwards or rebases), auto-stashes by default, and gives you a structured result. In exchange, you lose the merge strategy.

The sequence:

1. Resolve the current branch via `current_branch(cwd)`. Detached HEAD raises `ValueError`.
2. If `branch=` was passed, assert it equals the current branch (otherwise `ValueError`). This is a safety check, not a way to sync a different branch; `git pull` always operates on the checked-out branch and so does `sync_branch`.
3. Resolve the upstream via `tracking_branch(current, cwd)`. No upstream raises `ValueError`.
4. `fetch()` the upstream's remote.
5. Compute ahead/behind via `ahead_behind(current, upstream_ref)`. If behind is `0`, return `action="up_to_date"`.
6. If the tree is dirty:
   - `stash=True` (default): wrap the pull in `stashed()`.
   - `stash=False`: raise `ShellCommandFailedError` before touching anything.
7. If ahead is `0`, try `git pull --ff-only`. On success, return `action="fast_forwarded"`.
8. Otherwise (or if `--ff-only` failed), run `git pull --rebase` when `allow_rebase=True`. On success, return `action="rebased"`. With `allow_rebase=False` and ff-only unavailable, raise `ShellCommandFailedError`.
9. On rebase conflict:
   - `on_conflict="abort"` (default): run `git rebase --abort`, restore the stash, return `action="aborted"` with `conflicts` populated.
   - `on_conflict="leave"`: leave the rebase paused with the stash unpopped and raise `ShellCommandFailedError`.

Inputs:

| Parameter      | Type                        | Default   | Description                                                                                          |
| -------------- | --------------------------- | --------- | ---------------------------------------------------------------------------------------------------- |
| `cwd`          | `Path \| str \| None`       | `None`    | Repo to operate on. `None` uses the process cwd.                                                     |
| `branch`       | `str \| None`               | `None`    | Optional safety check. Must equal the checked-out branch when set; otherwise `ValueError`.           |
| `stash`        | `bool`                      | `True`    | Auto-stash a dirty tree before pulling. With `False`, a dirty tree raises `ShellCommandFailedError`. |
| `allow_rebase` | `bool`                      | `True`    | Allow `git pull --rebase` when fast-forward isn't possible. With `False`, raise instead of rebasing. |
| `on_conflict`  | `Literal["abort", "leave"]` | `"abort"` | What to do on rebase conflict. `"abort"` rolls back; `"leave"` keeps the rebase paused and raises.   |

`SyncResult` is a frozen dataclass:

| Field           | Type                                                            | Description                                                                          |
| --------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `action`        | `Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]` | What the sync ended up doing.                                                        |
| `ahead_before`  | `int`                                                           | Commits ahead of upstream before the pull.                                           |
| `behind_before` | `int`                                                           | Commits behind upstream before the pull.                                             |
| `conflicts`     | `tuple[Path, ...]`                                              | Paths with conflicts, relative to the repo root. Empty unless `action == "aborted"`. |
| `stashed`       | `bool`                                                          | `True` if a stash was created and (for non-`"aborted"` actions) popped.              |

> [!NOTE]
> When `sync_branch` returns `action="fast_forwarded"` or `action="rebased"`, the local branch contains the remote's commits. When it returns `action="aborted"`, the local branch is exactly where it started; the remote commits are still in `origin/<branch>` after the fetch but were not integrated.

### `prunable_branches` and `delete_branches`

Find local branches that are safe to delete, then delete them. The two helpers are split so callers can review the list before pulling the trigger.

```python
from nclutils.git import delete_branches, prunable_branches

candidates = prunable_branches()
print(f"prunable: {candidates}")  # e.g. ['feat/old-thing', 'fix/typo']

deleted = delete_branches(candidates)
print(f"deleted {len(deleted)} branches")
```

`prunable_branches` returns a sorted `list[str]` of short local branch names. It combines two sources, each gated by a keyword:

- `merged=True` (default): branches merged into `target`. This is the same set as branches with zero commits ahead of `target`.
- `gone=True` (default): branches whose upstream-tracking ref has been deleted on the remote (the `[gone]` marker in `git branch -vv`).

The current branch, the resolved `target` branch, and any name in `exclude` are filtered out before returning. Defaults: `target=None` defers to `default_branch()` (which reads `<remote>/HEAD`); `exclude=("main", "master", "develop")`. If `target=None` and `default_branch()` returns `None`, `ValueError` is raised.

`delete_branches` takes a sequence of short branch names and returns a `list[str]` of the names actually deleted (in input order). It silently skips:

- the current branch (`git branch -d` would fail anyway), and
- any name not present locally.

Pass `force=True` to use `git branch -D` instead of `git branch -d`, which deletes regardless of merge state.

```python
# Delete only branches you've reviewed
delete_branches(["feat/abandoned"], force=True)

# Or pipe directly from prunable_branches
delete_branches(prunable_branches(gone=False))  # only merged ones
```

### `add_worktree`

Create a worktree and return its `Worktree` record. Composes `create_worktree` and `list_worktrees`: the worktree is created, then looked up in `git worktree list --porcelain` so the caller gets back a populated record (including the resolved HEAD SHA).

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

Inputs:

- `path`: `Path | str` where the worktree should be created.
- `branch`: short branch name to check out (or create when `new_branch=True`).
- `new_branch=True`: pass `-b` to create the branch as part of `git worktree add`.
- `start_point`: optional commit/ref the new branch starts from. Requires `new_branch=True`; raises `ValueError` otherwise.

Returns the `Worktree` record. Raises `RuntimeError` if the new worktree is missing from the subsequent listing (a guard against silent bugs; should not fire in practice).

`Worktree` is a frozen dataclass:

| Field         | Type          | Description                                                                                     |
| ------------- | ------------- | ----------------------------------------------------------------------------------------------- |
| `path`        | `Path`        | Filesystem path of the worktree (as reported by `git worktree list`, not necessarily resolved). |
| `branch`      | `str \| None` | Short branch name checked out; `None` on detached HEAD.                                         |
| `head`        | `str`         | Full commit SHA at HEAD.                                                                        |
| `is_bare`     | `bool`        | `True` for the bare worktree of a bare repo.                                                    |
| `is_detached` | `bool`        | `True` if HEAD is detached.                                                                     |
| `is_locked`   | `bool`        | `True` if the worktree is locked.                                                               |

## Primitives

The composites cover the common workflows. When they don't fit, drop down to the primitives. Every primitive accepts `cwd=`, `stream=`, and `env=`; the examples below omit those and operate on the process cwd.

### Repo

`is_git_installed() -> bool`. `True` if the `git` binary is on PATH. Use this when `git` is optional in your code path. The check is via `nclutils.sh.which`, so no subprocess runs.

`is_git_repo(cwd=None) -> bool`. `True` if `cwd` is inside a git working tree. Returns `False` (rather than raising) outside a repo, so it's safe to use as a guard.

`repo_root(cwd=None) -> Path`. Absolute path to the working tree root (resolved from `git rev-parse --show-toplevel`). Raises `NotARepoError` outside a repo.

`primary_remote(cwd=None) -> Remote | None`. Returns a `Remote(name, url, web_url)` for the first remote listed by `git remote`, or `None` if no remotes are configured. "First" is alphabetical, which means `origin` in almost all repos. See the `Remote` table under [`get_repo_state`](#get_repo_state) above.

`is_dirty(cwd=None) -> bool`. `True` if `git status --porcelain` produces any output. Counts both index changes and untracked files. Raises `NotARepoError` outside a repo.

`is_rebase_in_progress(cwd=None) -> bool`. `True` if either `.git/rebase-merge/` (interactive rebase) or `.git/rebase-apply/` (non-interactive rebase) exists. Raises `NotARepoError` outside a repo.

### Branch

Every branch helper returns or accepts short branch names (no `refs/heads/` prefix).

`current_branch(cwd=None) -> str | None`. Short name of the currently checked-out branch, or `None` on detached HEAD. Implemented via `git symbolic-ref --short HEAD`. Outside a repo, the underlying call raises `ShellCommandFailedError`.

`default_branch(cwd=None, *, remote="origin") -> str | None`. Short name of the branch advertised by `<remote>/HEAD`, or `None` when the symbolic ref isn't configured. The `<remote>/HEAD` symref is set automatically by `git clone` and can be re-resolved with `git remote set-head <remote> -a`.

`branch_exists(branch, cwd=None) -> bool`. `True` if `branch` (a short name) is a local branch. Implemented via `git rev-parse --verify refs/heads/<branch>`. Does not check remote-tracking branches; use `tracking_branch` or `git ls-remote` for that.

`all_local_branches(cwd=None) -> frozenset[str]`. Set of short local branch names. Returns an empty `frozenset` outside a repo (matching the "absent to empty" pattern used by other branch primitives).

`tracking_branch(branch=None, cwd=None) -> tuple[str, str] | None`. Returns `(remote, branch_on_remote)` for the upstream of `branch`, or `None` if no upstream is configured. `branch=None` (the default) means the currently checked-out branch; if HEAD is detached, the result is `None`. Both elements are short names: `("origin", "main")`, not anything with `refs/`.

`ahead_behind(left, right, cwd=None) -> tuple[int, int]`. Returns `(ahead, behind)` commit counts comparing `left` to `right`, computed via `git rev-list --left-right --count left...right`. Both arguments accept anything `git rev-parse` accepts: branch names, SHAs, tags, `HEAD~3`, `origin/main`. Typical use is `ahead_behind("main", "origin/main")` to ask "how does my main differ from origin/main?"

`merged_branches(target=None, cwd=None) -> frozenset[str]`. Short names of local branches merged into `target` (per `git branch --merged <target>`). The result includes `target` itself, since every branch is "merged" with itself. `target=None` defers to `default_branch()`; if that also returns `None`, `ValueError` is raised. Pass a non-existent ref and you'll get `ShellCommandFailedError` from git.

`gone_branches(cwd=None) -> frozenset[str]`. Short names of local branches whose upstream-tracking ref has been deleted on the remote. Parses `git branch -vv` for the `[<upstream>: gone]` marker, which appears after a `git fetch --prune` removes the remote ref.

### Worktree

`list_worktrees(cwd=None) -> list[Worktree]`. All registered worktrees as a list of `Worktree` records, parsed from `git worktree list --porcelain`. The bare worktree of a bare repo appears with `is_bare=True`.

`create_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None) -> None`. Run `git worktree add` to create a worktree at `path` checked out to `branch`. With `new_branch=True`, pass `-b` to create the branch. `start_point` requires `new_branch=True` and raises `ValueError` otherwise. Returns `None`; use `add_worktree` (composite) if you want the resulting `Worktree` record.

`remove_worktree(path, *, cwd=None, force=False) -> None`. Run `git worktree remove`. With `force=True`, pass `--force` so removal succeeds even on dirty worktrees or those containing submodules.

### Runner

`run_git(*args, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,)) -> CompletedCommand` is the single subprocess entry point used by every other helper in the module. It prepends `git` to `args`, logs the invocation at `DEBUG`, and forwards every option to `nclutils.sh.run_command`. Returns a `CompletedCommand` (see [shell_commands.md](shell_commands.md)).

```python
from nclutils.git import run_git

# Run any git subcommand when no helper covers it
result = run_git("log", "--oneline", "-5")
for line in result.stdout.splitlines():
    print(line)

# Inspect exit code without raising
result = run_git("diff", "--quiet", check=False)
print("dirty" if result.returncode != 0 else "clean")
```

Reach for `run_git` when:

- No primitive covers the subcommand you need (`git log`, `git show`, `git tag`, and so on).
- You want options the helpers don't expose (`--no-color`, `--max-count`, custom format strings).
- You need the raw `CompletedCommand` (`stdout`, `stderr`, `returncode`, `duration`, `argv`, `cwd`).

## Error handling

Every git helper either returns a value or raises one of these exception types:

| Exception                                      | When raised                                                                                                                                                                                                                   |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `NotARepoError`                                | Operation requires a repo, but `cwd` (or the process cwd) is not inside one. Raised by `repo_root`, `is_dirty`, `is_rebase_in_progress`, `get_repo_state`, `fetch`, `stashed`, and `sync_branch` (transitively, via `fetch`). |
| `ValueError`                                   | Operation is not well-defined: detached HEAD where a branch was needed, missing upstream, missing default branch, `start_point` without `new_branch=True`.                                                                    |
| `RuntimeError`                                 | Raised only by `add_worktree` when the new worktree was created but does not appear in the subsequent `git worktree list`. A guard against silent bugs.                                                                       |
| `nclutils.sh.ShellCommandError` and subclasses | Any subprocess failure: `git` not on PATH, non-zero exit, timeout exceeded.                                                                                                                                                   |

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

`nclutils.git` emits `DEBUG` messages through stdlib `logging` under the `nclutils.git` logger. Every git invocation is logged. To see them:

```python
import logging

logging.getLogger("nclutils.git").setLevel(logging.DEBUG)
logging.basicConfig()
```

This is independent of `nclutils.pp`. The git module never writes to the console directly; for visible progress on long-running commands, pass `stream=True` to the helper instead.

## API reference

### Foundation

- `run_git(*args, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,)) -> CompletedCommand`. Run a `git` subcommand and return the captured result.
- `NotARepoError`. Raised when an operation requires a repo but `cwd` is not inside one.

### Repo

- `is_git_installed() -> bool`. `True` if `git` is on PATH.
- `is_git_repo(cwd=None, *, stream=False, env=None) -> bool`. `True` if `cwd` is inside a working tree. Never raises.
- `repo_root(cwd=None, *, stream=False, env=None) -> Path`. Absolute path to the working tree root.
- `primary_remote(cwd=None, *, stream=False, env=None) -> Remote | None`. The first configured remote, or `None`.
- `Remote`. Frozen dataclass with `name`, `url`, and `web_url`; see the field table above.
- `is_dirty(cwd=None, *, stream=False, env=None) -> bool`. `True` if `git status --porcelain` is non-empty.
- `is_rebase_in_progress(cwd=None, *, stream=False, env=None) -> bool`. `True` if a rebase is paused.
- `get_repo_state(cwd=None, *, stream=False, env=None) -> RepoState`. Snapshot a repo's state in one call.
- `RepoState`. Frozen dataclass; see the field table above.

### Branch

Every helper returns or accepts short branch names (no `refs/heads/` prefix).

- `current_branch(cwd=None, *, stream=False, env=None) -> str | None`. Short name of the current branch, or `None` on detached HEAD.
- `default_branch(cwd=None, *, remote="origin", stream=False, env=None) -> str | None`. Short name of `<remote>/HEAD`, or `None` if unset.
- `branch_exists(branch, cwd=None, *, stream=False, env=None) -> bool`. `True` if `branch` (a short name) exists locally.
- `all_local_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]`. Short names of every local branch.
- `tracking_branch(branch=None, cwd=None, *, stream=False, env=None) -> tuple[str, str] | None`. `(remote_short_name, branch_short_name_on_remote)`, or `None`.
- `ahead_behind(left, right, cwd=None, *, stream=False, env=None) -> tuple[int, int]`. `(ahead, behind)` for any two `git rev-parse`-able revisions.
- `merged_branches(target=None, cwd=None, *, stream=False, env=None) -> frozenset[str]`. Local branches merged into `target`. Includes `target`.
- `gone_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]`. Branches whose upstream-tracking ref is `[gone]`.
- `prunable_branches(cwd=None, *, merged=True, gone=True, target=None, exclude=("main", "master", "develop"), stream=False, env=None) -> list[str]`. Sorted list of short names safe to delete.
- `delete_branches(branches, cwd=None, *, force=False, stream=False, env=None) -> list[str]`. Take a sequence of short names; return the names actually deleted.

### Sync

- `fetch(cwd=None, *, remote=None, prune=True, all_remotes=False, tags=True, stream=False, env=None) -> None`. Fetch from a remote.
- `stashed(cwd=None, *, message=None, include_untracked=True, stream=False, env=None)`. Context manager. Yields `True` if a stash was created.
- `sync_branch(cwd=None, *, branch=None, stash=True, allow_rebase=True, on_conflict="abort", stream=False, env=None) -> SyncResult`. Fetch and pull (rebase) the current branch from its upstream.
- `SyncResult`. Frozen dataclass; see the field table above.

### Worktree

- `list_worktrees(cwd=None, *, stream=False, env=None) -> list[Worktree]`. All registered worktrees.
- `create_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None, stream=False, env=None) -> None`. Create a worktree.
- `remove_worktree(path, *, cwd=None, force=False, stream=False, env=None) -> None`. Remove the worktree at `path`.
- `add_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None, stream=False, env=None) -> Worktree`. Composite: create and return the resolved record.
- `Worktree`. Frozen dataclass; see the field table above.
