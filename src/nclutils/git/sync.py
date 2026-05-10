"""Sync workflows: fetch, stashed (ctx mgr), sync_branch."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from nclutils.sh import ShellCommandFailedError

from .branch import ahead_behind, current_branch, tracking_branch
from .repo import is_dirty, primary_remote, repo_root
from .runner import run_git

if TYPE_CHECKING:
    from collections.abc import Iterator


def fetch(
    cwd: Path | str | None = None,
    *,
    remote: str | None = None,
    prune: bool = True,
    all_remotes: bool = False,
    tags: bool = True,
) -> None:
    """Fetch from a remote with sensible defaults.

    ``prune=True`` removes stale remote tracking refs (almost always wanted).
    ``all_remotes=True`` calls ``git fetch --all``. When ``remote`` is None
    and ``all_remotes`` is False, defaults to the upstream's remote of the
    current branch, falling back to ``primary_remote()``.

    Raises:
        NotARepoError: cwd is not inside a repo.
        ShellCommandFailedError: no remote could be resolved, or fetch
            itself failed.
    """
    repo_root(cwd)  # validate; raises NotARepoError if not a repo

    args: list[str] = ["fetch"]
    if prune:
        args.append("--prune")
    if not tags:
        args.append("--no-tags")

    if all_remotes:
        args.append("--all")
        run_git(*args, cwd=cwd)
        return

    target = remote
    if target is None:
        upstream = tracking_branch(current_branch(cwd), cwd)
        if upstream is not None:
            target = upstream[0]
    if target is None:
        primary = primary_remote(cwd)
        if primary is not None:
            target = primary.name
    if target is None:
        msg = "fetch: no remote configured and no remote argument given"
        raise ShellCommandFailedError(msg=msg)

    args.append(target)
    run_git(*args, cwd=cwd)


@contextmanager
def stashed(
    cwd: Path | str | None = None,
    *,
    message: str | None = None,
    include_untracked: bool = True,
) -> Iterator[bool]:
    """Context manager: stash on enter (if dirty), pop on exit.

    Yields True if a stash was created, False if the tree was clean (no-op).

    On exit (whether the block returned normally or raised), if a stash was
    created, pops it unconditionally. If the pop conflicts, leaves the
    stash on the stack and raises ShellCommandFailedError. If the with-block
    also raised, that exception is suppressed in favor of the pop failure
    (the stash is the more recoverable artifact).

    Raises:
        NotARepoError: cwd is not a git repo.
        ShellCommandFailedError: stash push or pop failed.
    """
    if not is_dirty(cwd):
        yield False
        return

    stash_args: list[str] = ["stash", "push"]
    if include_untracked:
        stash_args.append("-u")
    if message is not None:
        stash_args.extend(["-m", message])
    run_git(*stash_args, cwd=cwd)

    try:
        yield True
    finally:
        # Pop unconditionally. If pop raises, it supersedes any in-block
        # exception (the stash is the more recoverable artifact).
        run_git("stash", "pop", cwd=cwd)


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Outcome of a sync_branch call."""

    action: Literal["up_to_date", "fast_forwarded", "rebased", "aborted"]
    ahead_before: int
    behind_before: int
    conflicts: tuple[Path, ...] = ()
    stashed: bool = False


def _conflict_paths(cwd: Path | str | None) -> tuple[Path, ...]:
    """Return paths of files with merge conflicts."""
    result = run_git("diff", "--name-only", "--diff-filter=U", cwd=cwd, check=False)
    if result.returncode != 0:
        return ()
    return tuple(Path(line.strip()) for line in result.stdout.splitlines() if line.strip())


def sync_branch(
    cwd: Path | str | None = None,
    *,
    branch: str | None = None,
    stash: bool = True,
    allow_rebase: bool = True,
    on_conflict: Literal["abort", "leave"] = "abort",
) -> SyncResult:
    """Fetch and pull (rebase) the current branch from its upstream.

    The optional ``branch=`` parameter is a safety check: if provided, it
    must equal the currently checked-out branch, otherwise ``ValueError``
    is raised. ``sync_branch`` always operates on the checked-out branch
    because ``git pull`` does, the parameter exists so callers can assert
    they are syncing the branch they think they are.

    Sequence:
      1. Resolve the current branch via ``current_branch(cwd)``. If None
         (detached HEAD), raise ValueError. If ``branch=`` was passed and
         doesn't match, also raise ValueError.
      2. Resolve upstream via ``tracking_branch(branch)``. If None, raise
         ``ValueError``.
      3. ``fetch()`` the upstream's remote.
      4. Compute ahead/behind counts via ``ahead_behind()``.
      5. If behind == 0: return ``action='up_to_date'``.
      6. If dirty and ``stash=True``: stash via the ``stashed`` context manager.
         If dirty and ``stash=False``: raise ``ShellCommandFailedError`` before
         any rebase attempt.
      7. If ``allow_rebase=True`` and ahead == 0: ``git pull --ff-only``.
         Otherwise (or if ``--ff-only`` fails): ``git pull --rebase``.
      8. On rebase conflict:
         - ``on_conflict='abort'``: ``git rebase --abort``, restore stash,
           return ``action='aborted'`` with conflicts populated.
         - ``on_conflict='leave'``: leave the rebase paused and stash unpopped;
           raise ``ShellCommandFailedError``.

    Raises:
        NotARepoError: cwd is not a git repo.
        ValueError: detached HEAD, ``branch=`` does not match the checked-out
            branch, or the branch has no upstream.
        ShellCommandFailedError: dirty tree with ``stash=False``, unrecoverable
            rebase conflict (``on_conflict='leave'``), failed
            ``git rebase --abort``, or any other git command failure not
            handled above.
    """
    repo_root(cwd)  # validate; raises NotARepoError before we misread HEAD state
    current = current_branch(cwd)
    if current is None:
        msg = "sync_branch: detached HEAD; check out a branch first"
        raise ValueError(msg)
    if branch is not None and branch != current:
        msg = (
            f"sync_branch: branch={branch!r} does not match the checked-out "
            f"branch {current!r}; sync_branch operates on the current branch"
        )
        raise ValueError(msg)

    upstream = tracking_branch(current, cwd)
    if upstream is None:
        msg = f"sync_branch: branch {current!r} has no upstream configured"
        raise ValueError(msg)
    remote, remote_branch = upstream
    upstream_ref = f"{remote}/{remote_branch}"

    fetch(cwd, remote=remote)

    ahead_before, behind_before = ahead_behind(current, upstream_ref, cwd=cwd)
    if behind_before == 0:
        return SyncResult(
            action="up_to_date",
            ahead_before=ahead_before,
            behind_before=behind_before,
        )

    dirty = is_dirty(cwd)
    if dirty and not stash:
        msg = (
            "sync_branch: working tree has uncommitted changes "
            "and stash=False; refusing to overwrite"
        )
        raise ShellCommandFailedError(msg=msg)

    cm = stashed(cwd) if dirty else nullcontext(False)  # noqa: FBT003 -- yielded value, not a flag
    with cm as did_stash:
        return _do_pull(
            cwd=cwd,
            ahead_before=ahead_before,
            behind_before=behind_before,
            allow_rebase=allow_rebase,
            on_conflict=on_conflict,
            stashed_flag=did_stash,
        )


def _do_pull(
    *,
    cwd: Path | str | None,
    ahead_before: int,
    behind_before: int,
    allow_rebase: bool,
    on_conflict: Literal["abort", "leave"],
    stashed_flag: bool,
) -> SyncResult:
    """Perform the actual pull and shape a SyncResult."""
    if ahead_before == 0:
        ff_result = run_git("pull", "--ff-only", cwd=cwd, check=False)
        if ff_result.returncode == 0:
            return SyncResult(
                action="fast_forwarded",
                ahead_before=ahead_before,
                behind_before=behind_before,
                stashed=stashed_flag,
            )

    if not allow_rebase:
        # Caller refused rebase but ff-only failed (or wasn't tried).
        msg = "sync_branch: fast-forward not possible and allow_rebase=False"
        raise ShellCommandFailedError(msg=msg)

    rebase_result = run_git("pull", "--rebase", cwd=cwd, check=False)
    if rebase_result.returncode == 0:
        return SyncResult(
            action="rebased",
            ahead_before=ahead_before,
            behind_before=behind_before,
            stashed=stashed_flag,
        )

    # Rebase failed (almost always a conflict).
    conflicts = _conflict_paths(cwd)
    if on_conflict == "leave":
        raise ShellCommandFailedError(result=rebase_result)

    # on_conflict == 'abort': roll back the rebase.
    abort_result = run_git("rebase", "--abort", cwd=cwd, check=False)
    if abort_result.returncode != 0:
        # Surface the original failure if abort itself broke.
        raise ShellCommandFailedError(result=rebase_result)
    return SyncResult(
        action="aborted",
        ahead_before=ahead_before,
        behind_before=behind_before,
        conflicts=conflicts,
        stashed=stashed_flag,
    )
