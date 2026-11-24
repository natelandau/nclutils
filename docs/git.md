# Git

Git operations for Python scripts. Each helper runs the `git` binary through `nclutils.sh.run_command`, so a working `git` install is the only runtime requirement.

```python
from nclutils.git import get_repo_state, sync_branch

state = get_repo_state()
if state.behind > 0 and not state.is_dirty:
    result = sync_branch()
    print(result.action)  # "up_to_date", "fast_forwarded", "rebased", or "aborted"
```

## When to use this module

Use this module in scripts that need a few common git operations without a full git library:

- Read the repo state (current branch, dirty files, ahead and behind counts, stashes) as typed values.
- Run everyday workflows (fetch then rebase, stash around a risky operation, delete merged branches) in one call.
- Create, list, and delete git worktrees with structured results.
- Run any other git subcommand with the same logging and error handling.

Git behaves the same as on the command line. Hooks run, configuration loads the same way, and `GIT_*` environment variables work as git documents them. The helpers parse git output for the common workflows. For any other output, you parse it yourself.

## Conventions

These conventions apply to every helper.

### Short names everywhere

Every helper that takes or returns a branch uses the short name: `"main"`, not `"refs/heads/main"`, and `("origin", "main")`, not `("origin", "refs/heads/main")`. Remote names are short too (`"origin"`, not a URL).

The exception is `ahead_behind`, which accepts any revision that `git rev-parse` accepts: branch names, full or short SHAs, tags, or expressions such as `HEAD~3` or `origin/main`.

### `cwd`, `stream`, and `env` are uniform

Every helper except `is_git_installed` accepts the same three arguments, with the same meaning everywhere:

- `cwd: Path | str | None = None`. The repo to operate on. `None` uses the current working directory of the process. A leading `~` is expanded.
- `stream: bool = False`. If `True`, git's stdout and stderr also go to the terminal in real time. Use it to show progress for slow operations such as fetch or rebase.
- `env: Mapping[str, str] | None = None`. Replaces the environment of the git process. To keep the rest of the environment, pass `{**os.environ, "GIT_SSH_COMMAND": "..."}`.

The helpers pass these arguments to `run_git`, which passes them to `nclutils.sh.run_command`.

```python
import os

from nclutils.git import current_branch, fetch

current_branch(cwd="~/projects/my-app")
fetch(cwd="/srv/repo", stream=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
```

### Outside a repo

If `cwd` is not inside a git repo, a helper does one of three things:

- Returns an empty or falsy value, so you can use it as a guard: `is_git_repo`, `current_branch`, `default_branch`, `branch_exists`, `all_local_branches`, `tracking_branch`, and `primary_remote`. `delete_branches` puts every name in `skipped`.
- Raises `NotARepoError`: `repo_root`, `is_dirty`, `is_rebase_in_progress`, `get_repo_state`, `fetch`, `stashed`, and `sync_branch`.
- Raises an error from the git command or from the missing default branch. `ahead_behind`, `gone_branches`, `stash_counts`, `run_git`, and the worktree helpers raise `ShellCommandFailedError`. With `target=None`, `merged_branches`, `is_empty_branch`, and `prunable_branches` raise `ValueError`.

Use `is_git_repo()` first when your script can start outside a repo.

## Composites

Composites wrap a multi-step workflow in one call. Use a composite first. Use the primitives below only when no composite fits.

### `get_repo_state`

Read the state of a repo in one call. `get_repo_state` returns a `RepoState` with the current branch, upstream, ahead and behind counts, file counts by category, the stash count for the branch, and whether a rebase is paused. It raises `NotARepoError` outside a repo.

```python
from nclutils.git import get_repo_state

state = get_repo_state()
print(f"on {state.branch} ({state.ahead} ahead, {state.behind} behind)")
print(f"  staged={state.staged} modified={state.modified} untracked={state.untracked}")
if state.rebase_in_progress:
    print("  rebase paused")
```

`RepoState` is a frozen dataclass:

| Field                | Type             | Description                                                                                                                  |
| -------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `root`               | `Path`           | Absolute path to the working tree root.                                                                                      |
| `branch`             | `str \| None`    | Short branch name. `None` on detached HEAD.                                                                                  |
| `upstream`           | `str \| None`    | Upstream as `<remote>/<branch>`, for example `"origin/main"`. `None` if no upstream is configured.                           |
| `primary_remote`     | `Remote \| None` | The first configured remote, in the order `git remote` lists them. `None` if no remote is configured. See the `Remote` table. |
| `ahead`              | `int`            | Commits on the local branch that are not on the upstream. `0` if there is no upstream.                                       |
| `behind`             | `int`            | Commits on the upstream that are not on the local branch. `0` if there is no upstream.                                       |
| `is_dirty`           | `bool`           | `True` if any of the four file counts is more than zero.                                                                     |
| `staged`             | `int`            | Count of files with index changes.                                                                                           |
| `modified`           | `int`            | Count of files with working tree changes that are not staged.                                                                |
| `untracked`          | `int`            | Count of files not under version control.                                                                                    |
| `unmerged`           | `int`            | Count of files with merge conflicts.                                                                                         |
| `stash_count`        | `int`            | Stash entries created on the current branch. `0` on detached HEAD.                                                           |
| `rebase_in_progress` | `bool`           | `True` if a rebase is paused.                                                                                                |

`Remote` is a frozen dataclass:

| Field     | Type          | Description                                                                                                                                                                                                                       |
| --------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`    | `str`         | Short remote name, for example `"origin"`.                                                                                                                                                                                        |
| `url`     | `str`         | Configured fetch URL, for example `"git@github.com:org/repo.git"`.                                                                                                                                                                |
| `web_url` | `str \| None` | Browser URL inferred from `url` as `https://<host>/<owner>/<repo>`. The result is correct for hosts with the common forge layout (GitHub, GitLab, Bitbucket, Gitea, Forgejo, Codeberg, sourcehut). `None` for local paths and `file://` URLs. |

> [!NOTE]
> The four file-count fields are counts, not lists. To get the paths, run `run_git("status", "--porcelain=v2")` and parse the output, or run `run_git("diff", "--name-only")` with a filter.

### `fetch`

Fetch from a remote. `fetch` prunes stale remote-tracking refs by default and returns `None`.

```python
from nclutils.git import fetch

# Fetch the remote of the current branch's upstream (falls back to primary_remote)
fetch()

# Fetch a specific remote
fetch(remote="upstream")

# Fetch every remote (git fetch --all)
fetch(all_remotes=True)

# Skip tags
fetch(tags=False)

# Show progress in the terminal
fetch(stream=True)
```

| Parameter     | Type          | Default | Description                                                                                                         |
| ------------- | ------------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| `remote`      | `str \| None` | `None`  | Remote to fetch. If `None`, `fetch` uses the remote of the current branch's upstream, then `primary_remote()`.      |
| `prune`       | `bool`        | `True`  | Pass `--prune`. Without it, branches deleted on the remote stay visible locally as `origin/<branch>`.               |
| `all_remotes` | `bool`        | `False` | Run `git fetch --all`. `remote` is ignored.                                                                         |
| `tags`        | `bool`        | `True`  | If `False`, pass `--no-tags`.                                                                                       |

`fetch` raises `NotARepoError` outside a repo. It raises `ShellCommandFailedError` if it cannot find a remote or if the fetch fails.

### `stashed`

Stash uncommitted changes for the length of a `with` block. On entry, `stashed` stashes the changes if the working tree is dirty. On exit, it pops the stash. It yields `True` if it created a stash, and `False` if the tree was clean.

```python
from nclutils.git import run_git, stashed

with stashed() as did_stash:
    run_git("checkout", "main")
    run_git("merge", "feature-branch")
# If did_stash is True, the stash is popped here, also when the block raised.
```

| Parameter           | Type          | Default | Description                                                         |
| ------------------- | ------------- | ------- | ------------------------------------------------------------------- |
| `message`           | `str \| None` | `None`  | Stash message that `git stash list` shows.                          |
| `include_untracked` | `bool`        | `True`  | Pass `-u` to `git stash push`, so untracked files are stashed too.  |

If the tree is clean on entry, `stashed` creates no stash and does nothing on exit. If the pop conflicts, the stash stays on the stack and `stashed` raises `ShellCommandFailedError`. This error replaces any exception from inside the block, because the stash is the easier state to recover.

`stashed` raises `NotARepoError` outside a repo, and `ShellCommandFailedError` if the push or the pop fails.

### `sync_branch`

Update the checked-out branch from its upstream. `sync_branch` fetches the upstream, stashes a dirty tree if necessary, then fast-forwards or rebases the branch. It returns a `SyncResult`.

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

`sync_branch` works only on a checked-out branch that has an upstream. It never merges: it fast-forwards or rebases. It runs these steps:

1. Get the current branch. On detached HEAD, raise `ValueError`.
2. If `branch` is set and is not the current branch, raise `ValueError`. `branch` is a safety check, not a way to sync a different branch.
3. Get the upstream of the current branch. If there is no upstream, raise `ValueError`.
4. Fetch the upstream's remote.
5. Count the commits ahead and behind the upstream. If behind is `0`, return `action="up_to_date"`.
6. If the tree is dirty and `stash=True`, stash the changes with `stashed()`. If the tree is dirty and `stash=False`, raise `ShellCommandFailedError` before any change.
7. If ahead is `0`, run `git pull --ff-only`. If it succeeds, return `action="fast_forwarded"`.
8. If `allow_rebase=True`, run `git pull --rebase`. If it succeeds, return `action="rebased"`. If `allow_rebase=False`, raise `ShellCommandFailedError`.
9. If the rebase has conflicts and `on_conflict="abort"`, run `git rebase --abort`, restore the stash, and return `action="aborted"` with `conflicts` set. If `git rebase --abort` fails, raise `ShellCommandFailedError`.
10. If the rebase has conflicts and `on_conflict="leave"`, leave the rebase paused and the stash on the stack, and raise `ShellCommandFailedError`.

| Parameter      | Type                        | Default   | Description                                                                                      |
| -------------- | --------------------------- | --------- | ------------------------------------------------------------------------------------------------ |
| `cwd`          | `Path \| str \| None`       | `None`    | Repo to operate on. `None` uses the process working directory.                                   |
| `branch`       | `str \| None`               | `None`    | Safety check. If set, it must be the checked-out branch, or `ValueError` is raised.              |
| `stash`        | `bool`                      | `True`    | Stash a dirty tree before the pull. If `False`, a dirty tree raises `ShellCommandFailedError`.   |
| `allow_rebase` | `bool`                      | `True`    | Run `git pull --rebase` when a fast-forward is not possible. If `False`, raise instead.          |
| `on_conflict`  | `Literal["abort", "leave"]` | `"abort"` | Action on a rebase conflict. `"abort"` rolls back. `"leave"` keeps the rebase paused and raises. |
| `stream`       | `bool`                      | `False`   | Show git output in the terminal.                                                                 |
| `env`          | `Mapping[str, str] \| None` | `None`    | Environment for every git process.                                                               |

`sync_branch` raises `NotARepoError` outside a repo.

`SyncResult` is a frozen dataclass:

| Field           | Type                                                            | Description                                                                              |
| --------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `action`        | `Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]` | What the sync did.                                                                       |
| `ahead_before`  | `int`                                                           | Commits ahead of the upstream before the pull.                                           |
| `behind_before` | `int`                                                           | Commits behind the upstream before the pull.                                             |
| `conflicts`     | `tuple[Path, ...]`                                              | Paths with conflicts, relative to the repo root. Empty unless `action` is `"aborted"`.   |
| `stashed`       | `bool`                                                          | `True` if `sync_branch` stashed the changes. The stash is popped before it returns.      |

> [!NOTE]
> After `action="fast_forwarded"` or `action="rebased"`, the local branch contains the remote commits. After `action="aborted"`, the local branch is where it started. The fetched remote commits are in `origin/<branch>` but are not on the local branch.

### `prunable_branches` and `delete_branches`

Find local branches that are safe to delete, then delete them. The two helpers are separate, so you can review the list before you delete.

```python
from nclutils.git import delete_branches, prunable_branches

candidates = prunable_branches()
for candidate in candidates:
    print(f"{candidate.name}: {candidate.reason}")  # for example "feat/old-thing: gone"

outcome = delete_branches([candidate.name for candidate in candidates])
print(
    f"deleted {len(outcome.deleted)}, skipped {len(outcome.skipped)}, failed {len(outcome.failed)}"
)
```

> [!WARNING]
> `prunable_branches` returns `list[PrunableBranch]`, and `delete_branches` returns a `DeleteOutcome`. Neither is a `list[str]`. Pass `[candidate.name for candidate in candidates]` to `delete_branches`, and read the results from `outcome.deleted`, `outcome.skipped`, and `outcome.failed`.

`prunable_branches` returns a list of `PrunableBranch`, sorted by name. `PrunableBranch` is a frozen dataclass:

| Field    | Type          | Description                                                   |
| -------- | ------------- | ------------------------------------------------------------- |
| `name`   | `str`         | Short local branch name.                                      |
| `reason` | `PruneReason` | Why the branch qualifies: `"gone"`, `"merged"`, or `"empty"`. |

`PruneReason` is the type alias `Literal["merged", "gone", "empty"]`. If a branch qualifies for more than one reason, `"gone"` wins over `"merged"`, and `"merged"` wins over `"empty"`.

| Parameter       | Type              | Default                          | Description                                                                                         |
| --------------- | ----------------- | -------------------------------- | --------------------------------------------------------------------------------------------------- |
| `merged`        | `bool`            | `True`                           | Include branches merged into `target` (from `git branch --merged`).                                 |
| `gone`          | `bool`            | `True`                           | Include branches whose upstream was deleted on the remote (the `gone` marker in `git branch -vv`). |
| `include_empty` | `bool`            | `False`                          | Include branches with zero commits ahead of `target`: branches that nobody committed to.            |
| `target`        | `str \| None`     | `None`                           | Base branch for `merged` and `include_empty`. If `None`, use `default_branch()`.                    |
| `exclude`       | `tuple[str, ...]` | `("main", "master", "develop")`  | Names never returned.                                                                               |

The result never contains the current branch, `target`, or a name in `exclude`. If `merged` or `include_empty` is `True`, `target` is `None`, and `default_branch()` returns `None`, `prunable_branches` raises `ValueError`.

`delete_branches` takes a sequence of short branch names and runs `git branch -d` for each. With `force=True`, it runs `git branch -D`, which deletes a branch that is not merged. It returns a `DeleteOutcome` frozen dataclass:

| Field     | Type              | Description                                                                                   |
| --------- | ----------------- | --------------------------------------------------------------------------------------------- |
| `deleted` | `tuple[str, ...]` | Deleted branches, in input order.                                                             |
| `skipped` | `tuple[str, ...]` | Branches not attempted, because they are the current branch or do not exist locally.          |
| `failed`  | `dict[str, str]`  | Branches that git did not delete, mapped to the stderr of `git branch`.                       |

A per-branch failure, for example an unmerged branch without `force=True`, goes into `failed` and does not raise. You get the result for every branch instead of an exception at the first failure.

```python
from nclutils.git import delete_branches, prunable_branches

# Delete a branch you reviewed, merged or not
outcome = delete_branches(["feat/abandoned"], force=True)

# Delete only merged branches
candidates = prunable_branches(gone=False)
outcome = delete_branches([candidate.name for candidate in candidates])
for branch, message in outcome.failed.items():
    print(f"could not delete {branch}: {message}")
```

### `add_worktree`

Create a worktree and return its `Worktree` record. `add_worktree` runs `create_worktree`, then reads the new worktree from `list_worktrees`, so the record includes the HEAD SHA.

```python
from pathlib import Path

from nclutils.git import add_worktree

# Check out an existing branch in a new worktree
worktree = add_worktree(Path("../feature-x"), branch="feature-x")

# Create a new branch in the same operation
worktree = add_worktree(
    Path("../experiment"),
    branch="experiment",
    new_branch=True,
    start_point="origin/main",
)

print(worktree.path, worktree.branch, worktree.head)
```

| Parameter     | Type          | Default  | Description                                                                                                                                |
| ------------- | ------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `path`        | `Path \| str` | required | Where to create the worktree.                                                                                                              |
| `branch`      | `str`         | required | Short name of the branch to check out, or to create if `new_branch=True`.                                                                  |
| `new_branch`  | `bool`        | `False`  | Pass `-b` to create `branch`.                                                                                                              |
| `start_point` | `str \| None` | `None`   | Commit or ref for the new branch to start from. Requires `new_branch=True`.                                                                |
| `track`       | `bool \| None`| `None`   | Upstream tracking for the new branch. `None` keeps git's default. `True` passes `--track`. `False` passes `--no-track`, for a local branch that you do not push. |

`add_worktree` raises `ValueError` if `start_point` is set without `new_branch=True`. It raises `RuntimeError` if git creates the worktree but the worktree is not in the listing that follows.

`Worktree` is a frozen dataclass:

| Field         | Type          | Description                                                                            |
| ------------- | ------------- | -------------------------------------------------------------------------------------- |
| `path`        | `Path`        | Path of the worktree as `git worktree list` reports it. The path is not resolved.      |
| `branch`      | `str \| None` | Short name of the checked-out branch. `None` on detached HEAD.                         |
| `head`        | `str`         | Full commit SHA at HEAD.                                                               |
| `is_bare`     | `bool`        | `True` for the bare worktree of a bare repo.                                           |
| `is_detached` | `bool`        | `True` if HEAD is detached.                                                            |
| `is_locked`   | `bool`        | `True` if the worktree is locked.                                                      |

## Primitives

Use the primitives when no composite fits. Every primitive except `is_git_installed` accepts `cwd`, `stream`, and `env`. The examples below leave them out and operate on the process working directory.

### Repo

`is_git_installed() -> bool`. `True` if the `git` binary is on `PATH`. Use it when `git` is optional for your script. It runs no subprocess.

`is_git_repo(cwd=None) -> bool`. `True` if `cwd` is inside a git working tree. Outside a repo, or if `git` is not installed, it returns `False`.

`repo_root(cwd=None) -> Path`. Absolute path to the working tree root, from `git rev-parse --show-toplevel`. Raises `NotARepoError` outside a repo.

`primary_remote(cwd=None) -> Remote | None`. The first remote that `git remote` lists, as a `Remote`. `git remote` sorts names alphabetically, so a repo with one remote usually gets `origin`. Returns `None` if no remote is configured. See the `Remote` table under [`get_repo_state`](#get_repo_state).

`is_dirty(cwd=None) -> bool`. `True` if the working tree has staged changes, unstaged changes, or untracked files. Raises `NotARepoError` outside a repo.

`is_rebase_in_progress(cwd=None) -> bool`. `True` if an interactive or non-interactive rebase is paused. Raises `NotARepoError` outside a repo.

`stash_counts(cwd=None) -> dict[str, int]`. Stash counts for every branch in the repo, from `git stash list`. Use it when you need stashes for all branches. `RepoState.stash_count` gives only the current branch. Stashes made on detached HEAD are not counted.

```python
from nclutils.git import stash_counts

for branch, count in stash_counts().items():
    print(f"{branch}: {count} stash(es)")
```

### Branch

`current_branch(cwd=None) -> str | None`. Short name of the checked-out branch. Returns `None` on detached HEAD and outside a repo.

`default_branch(cwd=None, *, remote="origin") -> str | None`. Short name of the branch that `<remote>/HEAD` points to. Returns `None` if that ref is not set. `git clone` sets it. To set it in another repo, run `git remote set-head <remote> -a`.

`branch_exists(branch, cwd=None) -> bool`. `True` if `branch` is a local branch. It does not look at remote-tracking branches.

`all_local_branches(cwd=None) -> frozenset[str]`. Short names of all local branches. Returns an empty `frozenset` outside a repo.

`tracking_branch(branch=None, cwd=None) -> tuple[str, str] | None`. `(remote, branch_on_remote)` for the upstream of `branch`, for example `("origin", "main")`. `branch=None` means the checked-out branch. Returns `None` if no upstream is configured, or if `branch=None` and HEAD is detached.

`ahead_behind(left, right, cwd=None) -> tuple[int, int]`. `(ahead, behind)` commit counts of `left` compared to `right`, from `git rev-list --left-right --count left...right`. Both arguments accept any revision. For example, `ahead_behind("main", "origin/main")` compares your `main` to `origin/main`. Raises `ShellCommandFailedError` if a revision does not exist.

`merged_branches(target=None, cwd=None) -> frozenset[str]`. Short names of local branches merged into `target`, from `git branch --merged`. The result includes `target`, because every branch is merged into itself. `target=None` uses `default_branch()`. Raises `ValueError` if `default_branch()` also returns `None`, and `ShellCommandFailedError` if `target` does not exist.

`gone_branches(cwd=None) -> frozenset[str]`. Short names of local branches whose upstream was deleted on the remote. These branches carry the `[<upstream>: gone]` marker in `git branch -vv` after `git fetch --prune`.

`is_empty_branch(branch, target=None, *, cwd=None) -> bool`. `True` if `branch` has zero commits ahead of `target`. An empty branch is a cleanup candidate even if it is not merged or gone. `target=None` uses `default_branch()`. Raises `ValueError` if `default_branch()` also returns `None`.

```python
from nclutils.git import is_empty_branch

if is_empty_branch("feat/placeholder"):
    print("this branch has no commits of its own")
```

### Worktree

`list_worktrees(cwd=None) -> list[Worktree]`. All registered worktrees, from `git worktree list --porcelain`. In a bare repo, the bare worktree has `is_bare=True`.

`create_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None, track=None) -> None`. Run `git worktree add` to create a worktree at `path` with `branch` checked out. The parameters are the same as for [`add_worktree`](#add_worktree), and so is the `ValueError`. Use `add_worktree` to get the `Worktree` record.

`remove_worktree(path, *, cwd=None, force=False) -> None`. Run `git worktree remove`. With `force=True`, pass `--force` to delete a worktree that is dirty or contains submodules.

```python
from nclutils.git import list_worktrees, remove_worktree

for worktree in list_worktrees():
    if worktree.branch == "experiment":
        remove_worktree(worktree.path)
```

### Runner

`run_git(*args, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,)) -> CompletedCommand`. Every other helper in the module uses it to run git. It puts `git` before `args` and passes every option to `nclutils.sh.run_command`. It returns a `CompletedCommand` with `stdout`, `stderr`, `returncode`, `argv`, `duration`, and `cwd`. See [shell_commands.md](shell_commands.md) for the options.

```python
from nclutils.git import run_git

# Run a git subcommand that no helper covers
result = run_git("log", "--oneline", "-5")
for line in result.stdout.splitlines():
    print(line)

# Read the exit code without an exception
result = run_git("diff", "--quiet", check=False)
print("dirty" if result.returncode != 0 else "clean")
```

Use `run_git` for a subcommand that no helper covers (`git log`, `git show`, `git tag`), for options the helpers do not expose, or to get the full `CompletedCommand`.

`run_git` raises `ShellCommandNotFoundError` if `git` is not on `PATH`, `ShellCommandFailedError` if the exit code is not in `okay_codes` and `check=True`, and `ShellCommandTimeoutError` if `timeout` expires.

## Error handling

A git helper returns a value or raises one of these exceptions:

| Exception                                      | When raised                                                                                                                                                                          |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `NotARepoError`                                | The helper needs a repo and `cwd` is not inside one. Raised by `repo_root`, `is_dirty`, `is_rebase_in_progress`, `get_repo_state`, `fetch`, `stashed`, and `sync_branch`.             |
| `ValueError`                                   | The request has no clear meaning: detached HEAD where a branch is necessary, a `branch` that is not checked out, no upstream, no default branch, or `start_point` without `new_branch=True`. |
| `RuntimeError`                                 | Raised only by `add_worktree`, if git creates the worktree but it is not in the listing that follows.                                                                                |
| `nclutils.sh.ShellCommandError` and subclasses | A git process failure: `git` not on `PATH`, an exit code that is not allowed, or a timeout.                                                                                           |

`ShellCommandError` is the base class for all shell failures, so one `except` clause catches every git process error:

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

See [shell_commands.md](shell_commands.md#error-handling) for the `ShellCommandError` subclasses (`ShellCommandNotFoundError`, `ShellCommandFailedError`, `ShellCommandTimeoutError`).

## Diagnostic logging

`nclutils.sh.run_command` logs every git command at `DEBUG`. The records go to the `nclutils.sh` logger, not `nclutils.git`:

```python
import logging

logging.getLogger("nclutils.sh").setLevel(logging.DEBUG)
logging.basicConfig()
```

See [shell_commands.md](shell_commands.md#diagnostic-logging) for the content of the records. The git module never writes to the console. To show progress for a slow command, pass `stream=True` to the helper.

## API reference

### Foundation

- `run_git(*args, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,)) -> CompletedCommand`. Run a `git` subcommand and return the captured result.
- `NotARepoError`. Raised when a helper needs a repo and `cwd` is not inside one.

### Repo

- `is_git_installed() -> bool`. `True` if `git` is on `PATH`.
- `is_git_repo(cwd=None, *, stream=False, env=None) -> bool`. `True` if `cwd` is inside a working tree. Never raises.
- `repo_root(cwd=None, *, stream=False, env=None) -> Path`. Absolute path to the working tree root.
- `primary_remote(cwd=None, *, stream=False, env=None) -> Remote | None`. The first configured remote, or `None`.
- `Remote`. Frozen dataclass with `name`, `url`, and `web_url`.
- `is_dirty(cwd=None, *, stream=False, env=None) -> bool`. `True` if the working tree has changes or untracked files.
- `is_rebase_in_progress(cwd=None, *, stream=False, env=None) -> bool`. `True` if a rebase is paused.
- `stash_counts(cwd=None, *, stream=False, env=None) -> dict[str, int]`. Stash counts for every branch.
- `get_repo_state(cwd=None, *, stream=False, env=None) -> RepoState`. The state of a repo in one call.
- `RepoState`. Frozen dataclass. See the field table under [`get_repo_state`](#get_repo_state).

### Branch

- `current_branch(cwd=None, *, stream=False, env=None) -> str | None`. Short name of the current branch, or `None` on detached HEAD.
- `default_branch(cwd=None, *, remote="origin", stream=False, env=None) -> str | None`. Short name of the branch `<remote>/HEAD` points to, or `None`.
- `branch_exists(branch, cwd=None, *, stream=False, env=None) -> bool`. `True` if `branch` exists locally.
- `all_local_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]`. Short names of all local branches.
- `tracking_branch(branch=None, cwd=None, *, stream=False, env=None) -> tuple[str, str] | None`. `(remote, branch_on_remote)`, or `None`.
- `ahead_behind(left, right, cwd=None, *, stream=False, env=None) -> tuple[int, int]`. `(ahead, behind)` for two revisions.
- `merged_branches(target=None, cwd=None, *, stream=False, env=None) -> frozenset[str]`. Local branches merged into `target`, including `target`.
- `gone_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]`. Local branches whose upstream was deleted.
- `is_empty_branch(branch, target=None, *, cwd=None, stream=False, env=None) -> bool`. `True` if `branch` has zero commits ahead of `target`.
- `prunable_branches(cwd=None, *, merged=True, gone=True, include_empty=False, target=None, exclude=("main", "master", "develop"), stream=False, env=None) -> list[PrunableBranch]`. Branches that are safe to delete, with the reason for each, sorted by name.
- `PrunableBranch`. Frozen dataclass with `name: str` and `reason: PruneReason`.
- `PruneReason`. `Literal["merged", "gone", "empty"]`.
- `delete_branches(branches, cwd=None, *, force=False, stream=False, env=None) -> DeleteOutcome`. Delete local branches and return the result for each.
- `DeleteOutcome`. Frozen dataclass with `deleted: tuple[str, ...]`, `skipped: tuple[str, ...]`, and `failed: dict[str, str]`.

### Sync

- `fetch(cwd=None, *, remote=None, prune=True, all_remotes=False, tags=True, stream=False, env=None) -> None`. Fetch from a remote.
- `stashed(cwd=None, *, message=None, include_untracked=True, stream=False, env=None)`. Context manager that yields `True` if it created a stash.
- `sync_branch(cwd=None, *, branch=None, stash=True, allow_rebase=True, on_conflict="abort", stream=False, env=None) -> SyncResult`. Fast-forward or rebase the current branch onto its upstream.
- `SyncResult`. Frozen dataclass. See the field table under [`sync_branch`](#sync_branch).

### Worktree

- `list_worktrees(cwd=None, *, stream=False, env=None) -> list[Worktree]`. All registered worktrees.
- `create_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None, track=None, stream=False, env=None) -> None`. Create a worktree.
- `remove_worktree(path, *, cwd=None, force=False, stream=False, env=None) -> None`. Delete the worktree at `path`.
- `add_worktree(path, branch, *, cwd=None, new_branch=False, start_point=None, track=None, stream=False, env=None) -> Worktree`. Create a worktree and return its record.
- `Worktree`. Frozen dataclass. See the field table under [`add_worktree`](#add_worktree).
