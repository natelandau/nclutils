"""Sync workflows: fetch, stashed (ctx mgr), sync_branch."""

from __future__ import annotations

from pathlib import Path

from nclutils.sh import CompletedCommand, ShellCommandFailedError

from .branch import current_branch, tracking_branch
from .repo import primary_remote, repo_root
from .runner import run_git


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
            target = primary[0]
    if target is None:
        # Match nclutils.sh.run_command's cwd invariant (always None or absolute resolved Path).
        resolved_cwd = Path(cwd).expanduser().resolve() if cwd is not None else None
        result = CompletedCommand(
            argv=("git", *args),
            returncode=1,
            stdout="",
            stderr="fetch: no remote configured and no remote argument given",
            duration=0.0,
            cwd=resolved_cwd,
        )
        raise ShellCommandFailedError(result=result)

    args.append(target)
    run_git(*args, cwd=cwd)
