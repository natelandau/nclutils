# `nclutils.git` reference

Git operations through the `git` binary via `nclutils.sh.run_command`. Hooks, config, and `GIT_*` env vars behave as on the command line. No global state.

## Conventions

- Branch names in and out are short (`"main"`, not `"refs/heads/main"`). Remotes are short (`"origin"`). Exception: `ahead_behind` takes any `git rev-parse` expression (SHA, tag, `HEAD~3`, `origin/main`).
- Every helper except `is_git_installed` and `run_git` takes these, with the same meaning everywhere. `stream`, `env`, and every option parameter are keyword-only.

| Parameter | Type and default | Meaning |
| --- | --- | --- |
| `cwd` | `Path \| str \| None = None` | Repo to operate on. `None` -> process cwd. `~` expanded. |
| `stream` | `bool = False` | Tee git's stdout/stderr to the parent streams in real time. |
| `env` | `Mapping[str, str] \| None = None` | Replaces the child env. Extend with `{**os.environ, "GIT_SSH_COMMAND": "..."}`. |

- Signatures below omit these types: `cwd=None, *, stream=False, env=None` always means the table above.
- `cwd` that is not an existing directory -> `ShellCommandFailedError` from every helper except `is_git_repo` (returns `False`), including the helpers that otherwise raise `NotARepoError`.

### Outside a repository

| Behavior | Helpers |
| --- | --- |
| Returns empty or falsy | `is_git_repo` (`False`), `current_branch` (`None`), `default_branch` (`None`), `branch_exists` (`False`), `tracking_branch` (`None`), `primary_remote` (`None`), `all_local_branches` (empty `frozenset`) |
| Every name in `skipped` | `delete_branches` |
| Raises `NotARepoError` | `repo_root`, `is_dirty`, `is_rebase_in_progress`, `get_repo_state`, `fetch`, `stashed`, `sync_branch` |
| Raises `ShellCommandFailedError` | `ahead_behind`, `gone_branches`, `stash_counts`, `run_git`, `list_worktrees`, `create_worktree`, `add_worktree`, `remove_worktree`, `merged_branches` with an explicit `target` |
| Raises `ValueError` | `merged_branches`, `is_empty_branch`, `prunable_branches` with `target=None` (no default branch resolves) |

To guard a script that can start outside a repo: `if not is_git_repo(): ...`.

## Errors

| Exception | Raised when |
| --- | --- |
| `NotARepoError(Exception)` | Helper needs a repo and `cwd` is not inside one. Helpers listed above. |
| `ValueError` | Detached HEAD where a branch is required, `branch=` mismatch or no upstream in `sync_branch`, no default branch for `target=None`, `start_point` without `new_branch=True`. |
| `RuntimeError` | `add_worktree` only: created worktree missing from the following `git worktree list`. |
| `nclutils.sh.ShellCommandError` and subclasses | `git` not on PATH -> `ShellCommandNotFoundError`; non-zero exit or bad `cwd` -> `ShellCommandFailedError`; timeout -> `ShellCommandTimeoutError`. Catch the base class for all. |

```python
from nclutils.git import NotARepoError, sync_branch
from nclutils.sh import ShellCommandError

try:
    result = sync_branch()
except NotARepoError:
    ...
except ValueError:  # detached HEAD, no upstream, branch= mismatch
    ...
except ShellCommandError:  # git failure
    ...
```

## Composites

### `get_repo_state`

```python
get_repo_state(cwd=None, *, stream=False, env=None) -> RepoState
```

One-call snapshot (`git status --branch --porcelain=v2` plus `repo_root`, `git stash list`, `is_rebase_in_progress`, `primary_remote`). Raises `NotARepoError` outside a repo.

`RepoState` (frozen dataclass, `slots=True`):

| Field | Type | Meaning |
| --- | --- | --- |
| `root` | `Path` | Absolute working tree root. |
| `branch` | `str \| None` | Short branch name; `None` on detached HEAD. |
| `upstream` | `str \| None` | `"<remote>/<branch>"`, for example `"origin/main"`; `None` without upstream. |
| `primary_remote` | `Remote \| None` | Same value as `primary_remote()`. |
| `ahead` | `int` | Commits on local not on upstream. `0` without upstream. |
| `behind` | `int` | Commits on upstream not on local. `0` without upstream. |
| `is_dirty` | `bool` | `True` if any of the four counts below is nonzero. |
| `staged` | `int` | Entries with index changes. |
| `modified` | `int` | Entries with worktree changes and no index change. |
| `untracked` | `int` | Untracked entries. |
| `unmerged` | `int` | Files with merge conflicts. |
| `stash_count` | `int` | Stashes created on the current branch. `0` on detached HEAD. |
| `rebase_in_progress` | `bool` | `True` if `rebase-merge/` or `rebase-apply/` exists in the git dir. |

- An entry both staged and modified counts once, as `staged`.
- Counts only, no paths. For paths: `run_git("status", "--porcelain=v2")` or `run_git("diff", "--name-only")`.

`Remote` (frozen dataclass, `slots=True`):

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | `str` | Short remote name. |
| `url` | `str` | Fetch URL as `git remote get-url` prints it. |
| `web_url` | `str \| None` | Best-effort `https://<host>/<path>` from `url` (SCP-style, `ssh://`, `git://`, `http(s)://`): trailing `.git`, user, and port dropped. `None` for local paths, `file://`, or no host. |

### `fetch`

```python
fetch(cwd=None, *, remote: str | None = None, prune: bool = True, all_remotes: bool = False, tags: bool = True, stream=False, env=None) -> None
```

- `remote=None` and `all_remotes=False`: fetches the current branch's upstream remote, else `primary_remote()`, else raises `ShellCommandFailedError`.
- `prune=True` -> `--prune`. `tags=False` -> `--no-tags`.
- `all_remotes=True` -> `git fetch --all`; `remote` is ignored.
- Raises `NotARepoError` outside a repo; `ShellCommandFailedError` on fetch failure.

### `stashed` (context manager)

```python
@contextmanager
def stashed(cwd=None, *, message: str | None = None, include_untracked: bool = True, stream=False, env=None) -> Generator[bool]
```

```python
with stashed() as did_stash:
    run_git("checkout", "main")
# stash popped here, even if the block raised
```

- Yields `True` if a stash was pushed; `False` if the tree was clean (no stash, no pop).
- `include_untracked=True` -> `git stash push -u`. `message` -> `-m <message>`.
- On exit, always runs `git stash pop`. Pop fails (conflict) -> stash stays on the stack and `ShellCommandFailedError` is raised, replacing any exception from the block.
- Raises `NotARepoError` outside a repo.

### `sync_branch`

```python
sync_branch(cwd=None, *, branch: str | None = None, stash: bool = True, allow_rebase: bool = True, on_conflict: Literal["abort", "leave"] = "abort", stream=False, env=None) -> SyncResult
```

Fetches and updates the checked-out branch from its upstream by fast-forward or rebase. Never merges. `branch=` is an assertion: it must equal the checked-out branch, else `ValueError`. It does not sync another branch.

Steps:

1. Not a repo -> `NotARepoError`. Detached HEAD -> `ValueError`. `branch=` mismatch -> `ValueError`. No upstream -> `ValueError`.
2. `fetch` the upstream's remote; compute ahead/behind against `<remote>/<branch>`.
3. Behind is `0` -> return `"up_to_date"` (dirty tree not checked).
4. Dirty and `stash=False` -> `ShellCommandFailedError`. Dirty and `stash=True` -> rest runs inside `stashed`.
5. Ahead is `0` -> `git pull --ff-only`; success -> `"fast_forwarded"`.
6. Fast-forward failed or ahead > 0: `allow_rebase=False` -> `ShellCommandFailedError`; else `git pull --rebase`; success -> `"rebased"`.
7. Rebase fails:
    - `on_conflict="abort"`: `git rebase --abort`, stash popped, return `"aborted"` with `conflicts`. Abort itself fails -> `ShellCommandFailedError`.
    - `on_conflict="leave"`: rebase stays paused, `ShellCommandFailedError` raised. With a stash, the pop fails against the conflicted index, so the raised error is the pop failure and the stash stays on the stack.

`SyncResult` (frozen dataclass, `slots=True`):

| Field | Type | Meaning |
| --- | --- | --- |
| `action` | `Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]` | Outcome. |
| `ahead_before` | `int` | Commits ahead of upstream before the pull. |
| `behind_before` | `int` | Commits behind upstream before the pull. |
| `conflicts` | `tuple[Path, ...] = ()` | Conflicted paths relative to repo root. Empty unless `"aborted"`. |
| `stashed` | `bool = False` | `True` if a stash was pushed. |

`"aborted"`: local branch unchanged; fetched commits sit in the remote-tracking ref, not integrated.

### `prunable_branches`

```python
prunable_branches(cwd=None, *, merged: bool = True, gone: bool = True, include_empty: bool = False, target: str | None = None, exclude: tuple[str, ...] = ("main", "master", "develop"), stream=False, env=None) -> list[PrunableBranch]
```

Local branches safe to delete, sorted by name.

| Flag | Selects |
| --- | --- |
| `merged=True` | Branches merged into `target` (`merged_branches`). |
| `gone=True` | Branches whose upstream is gone (`gone_branches`). Run `fetch()` first so `[gone]` markers exist. |
| `include_empty=True` | Remaining branches with zero commits ahead of `target` (`is_empty_branch`). |

- Reason precedence: `"gone"` > `"merged"` > `"empty"`.
- Never returns the current branch, `target`, or a name in `exclude`.
- `target=None` -> `default_branch(cwd)`. If `merged` or `include_empty` is `True` and no default branch resolves -> `ValueError`.

`PrunableBranch` (frozen dataclass, `slots=True`): `name: str`, `reason: PruneReason`. `PruneReason = Literal["merged", "gone", "empty"]`.

Pass names, not the objects, to `delete_branches`:

```python
outcome = delete_branches([pb.name for pb in prunable_branches()])
```

### `delete_branches`

```python
delete_branches(branches: Sequence[str], cwd=None, *, force: bool = False, stream=False, env=None) -> DeleteOutcome
```

- `force=False` -> `git branch -d`; `force=True` -> `git branch -D` (ignores merge state).
- Current branch and names not present locally go to `skipped` without a git call.
- Per-branch git failures go to `failed`; nothing raised for them.

`DeleteOutcome` (frozen dataclass, `slots=True`):

| Field | Type | Meaning |
| --- | --- | --- |
| `deleted` | `tuple[str, ...]` | Deleted, in input order. |
| `skipped` | `tuple[str, ...]` | Current branch or not present locally. |
| `failed` | `dict[str, str]` | Name -> git stderr, or `"git branch failed (exit N)"` when stderr is empty. |

### `add_worktree`

```python
add_worktree(path: Path | str, branch: str, *, cwd=None, new_branch: bool = False, start_point: str | None = None, track: bool | None = None, stream=False, env=None) -> Worktree
```

Runs `create_worktree`, then returns the matching record from `list_worktrees`.

- `branch`: branch to check out; with `new_branch=True`, branch to create (`-b`).
- `cwd`: the source repo. The worktree goes at `path`.
- `start_point`: base ref for the created branch. Without `new_branch=True` -> `ValueError`.
- `track`: `None` -> no flag; `True` -> `--track`; `False` -> `--no-track`.
- Pass `path` absolute with `~` expanded. Git receives `path` as given (relative to `cwd`, `~` not expanded), but the lookup resolves it against the process cwd. A mismatch -> worktree created, then `RuntimeError`.

`Worktree` (frozen dataclass, `slots=True`):

| Field | Type | Meaning |
| --- | --- | --- |
| `path` | `Path` | Path as `git worktree list` reports it. Can differ from `Path.resolve()` (symlinks). |
| `branch` | `str \| None` | Short branch name; `None` when detached or bare. |
| `head` | `str` | Full HEAD SHA. |
| `is_bare` | `bool` | Bare repo entry. |
| `is_detached` | `bool` | HEAD detached. |
| `is_locked` | `bool` | Worktree locked. |

## Primitives

### Repo

| Signature | Returns |
| --- | --- |
| `is_git_installed() -> bool` | `git` on PATH (`nclutils.sh.which`, no subprocess). |
| `is_git_repo(cwd=None, *, stream=False, env=None) -> bool` | Inside a working tree. Never raises: `False` for no repo, bad `cwd`, or missing `git`. |
| `repo_root(cwd=None, *, stream=False, env=None) -> Path` | Absolute working tree root (`git rev-parse --show-toplevel`). |
| `primary_remote(cwd=None, *, stream=False, env=None) -> Remote \| None` | First line of `git remote` (alphabetical). `None` without remotes. |
| `is_dirty(cwd=None, *, stream=False, env=None) -> bool` | `git status --porcelain` has output: staged, unstaged, or untracked. |
| `is_rebase_in_progress(cwd=None, *, stream=False, env=None) -> bool` | Paused interactive or non-interactive rebase. |
| `stash_counts(cwd=None, *, stream=False, env=None) -> dict[str, int]` | Branch -> stash count across the repo, from `git stash list`. Detached-HEAD stashes excluded. For the current branch only: `RepoState.stash_count`. |

### Branch

| Signature | Returns |
| --- | --- |
| `current_branch(cwd=None, *, stream=False, env=None) -> str \| None` | Checked-out branch; `None` on detached HEAD. |
| `default_branch(cwd=None, *, remote: str = "origin", stream=False, env=None) -> str \| None` | Target of `refs/remotes/<remote>/HEAD`; `None` if unset. Set by `git clone`; repair with `git remote set-head <remote> -a`. |
| `branch_exists(branch: str, cwd=None, *, stream=False, env=None) -> bool` | Local branch exists (`refs/heads/<branch>`). Remote-tracking branches not checked. |
| `all_local_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]` | All local branch names. |
| `tracking_branch(branch: str \| None = None, cwd=None, *, stream=False, env=None) -> tuple[str, str] \| None` | `(remote, branch_on_remote)` from `branch.<name>.remote` and `.merge` config. `branch=None` -> current. `None` without upstream or on detached HEAD. |
| `ahead_behind(left: str, right: str, cwd=None, *, stream=False, env=None) -> tuple[int, int]` | `(ahead, behind)` of `left` vs `right` (`git rev-list --left-right --count left...right`). Unknown ref -> `ShellCommandFailedError`. |
| `is_empty_branch(branch: str, target: str \| None = None, *, cwd=None, stream=False, env=None) -> bool` | `branch` has zero commits ahead of `target`. `target=None` -> `default_branch(cwd)`, else `ValueError`. |
| `merged_branches(target: str \| None = None, cwd=None, *, stream=False, env=None) -> frozenset[str]` | Local branches merged into `target`, including `target` itself. `target=None` -> `default_branch(cwd)`, else `ValueError`. Unknown `target` -> `ShellCommandFailedError`. |
| `gone_branches(cwd=None, *, stream=False, env=None) -> frozenset[str]` | Branches whose upstream shows `[gone]` in `git branch -vv`, including branches checked out in other worktrees. Markers appear only after a pruning fetch. |

`is_empty_branch` and `merged_branches` take `cwd` in different positions: keyword-only in `is_empty_branch`, second positional in `merged_branches`.

### Worktree

| Signature | Effect |
| --- | --- |
| `list_worktrees(cwd=None, *, stream=False, env=None) -> list[Worktree]` | All registered worktrees from `git worktree list --porcelain`, the main one included. |
| `create_worktree(path: Path \| str, branch: str, *, cwd=None, new_branch: bool = False, start_point: str \| None = None, track: bool \| None = None, stream=False, env=None) -> None` | `git worktree add`; same parameters and `ValueError` as `add_worktree`. No record returned. |
| `remove_worktree(path: Path \| str, *, cwd=None, force: bool = False, stream=False, env=None) -> None` | `git worktree remove`. `force=True` -> `--force`, required for dirty worktrees or ones with submodules. |

## `run_git`

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

Prepends `git` to `args` and passes every option to `nclutils.sh.run_command`. Use for subcommands no helper covers (`log`, `show`, `tag`) or to read raw `stdout`, `stderr`, `returncode`.

- Exit code not in `okay_codes` with `check=True` -> `ShellCommandFailedError`. `check=False` -> returns the result.
- Outside a repo -> `ShellCommandFailedError`, not `NotARepoError`.
- `timeout=None` -> no limit; exceeded -> `ShellCommandTimeoutError`.
- `exclude_regex` drops matching output lines from capture and stream.

```python
result = run_git("diff", "--quiet", check=False)
dirty = result.returncode != 0
```

## Logging

Each git call is logged at `DEBUG` under the `nclutils.sh` logger, not `nclutils.git`. The module writes nothing to the console; use `stream=True` for visible progress.

```python
logging.getLogger("nclutils.sh").setLevel(logging.DEBUG)
```
