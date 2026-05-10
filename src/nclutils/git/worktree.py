"""Worktree primitives + Worktree dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .runner import run_git

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class Worktree:
    """A registered git worktree."""

    path: Path
    branch: str | None
    head: str
    is_bare: bool
    is_detached: bool
    is_locked: bool


def list_worktrees(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> list[Worktree]:
    """Return the registered worktrees.

    Parses ``git worktree list --porcelain``. Each worktree block looks like:

        worktree /path
        HEAD <sha>
        branch refs/heads/<name>      (or "detached")
        bare                          (only for the bare worktree)
        locked [reason]               (only when locked)
        <blank line>

    Args:
        cwd: Working directory; ``None`` inherits the process cwd.
        stream: Forwarded to :func:`run_git` (rarely useful here, but kept
            for consistency with other helpers).
        env: Forwarded to :func:`run_git`.

    Returns:
        List of :class:`Worktree` records, one per registered worktree.
    """
    result = run_git("worktree", "list", "--porcelain", cwd=cwd, stream=stream, env=env)
    return _parse_worktree_porcelain(result.stdout)


def _parse_worktree_porcelain(text: str) -> list[Worktree]:
    """Parse ``git worktree list --porcelain`` output into Worktree records."""
    out: list[Worktree] = []
    block: dict[str, str | bool] = {}

    def flush() -> None:
        if not block:
            return
        path = Path(str(block.get("worktree", "")))
        head = str(block.get("HEAD", ""))
        is_bare = bool(block.get("bare", False))
        is_detached = bool(block.get("detached", False))
        is_locked = bool(block.get("locked", False))
        branch_ref = block.get("branch")
        branch: str | None
        if isinstance(branch_ref, str) and branch_ref.startswith("refs/heads/"):
            branch = branch_ref[len("refs/heads/") :]
        else:
            branch = None
        out.append(
            Worktree(
                path=path,
                branch=branch,
                head=head,
                is_bare=is_bare,
                is_detached=is_detached,
                is_locked=is_locked,
            )
        )

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            flush()
            block = {}
            continue
        if " " in line:
            key, value = line.split(" ", 1)
        else:
            key, value = line, ""
        if key in {"bare", "detached"}:
            block[key] = True
        elif key == "locked":
            block["locked"] = True
        else:
            block[key] = value
    flush()
    return out


def create_worktree(  # noqa: PLR0913
    path: Path | str,
    branch: str,
    *,
    cwd: Path | str | None = None,
    new_branch: bool = False,
    start_point: str | None = None,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> None:
    """Create a worktree at ``path`` checked out to ``branch``.

    With ``new_branch=True``, also creates the branch (passes ``-b``).
    ``start_point`` is the commit/ref to start the new branch from and
    requires ``new_branch=True``.

    Args:
        path: Filesystem path where the new worktree will be created.
        branch: Branch name to check out (or create when ``new_branch=True``).
        cwd: Working directory of the source repo; ``None`` inherits the
            process cwd.
        new_branch: When ``True``, create ``branch`` as part of adding the
            worktree (passes ``-b`` to ``git worktree add``).
        start_point: Optional commit/ref to base ``branch`` on. Requires
            ``new_branch=True``.
        stream: Forwarded to :func:`run_git`.
        env: Forwarded to :func:`run_git`.

    Raises:
        ValueError: ``start_point`` is set without ``new_branch=True``.
    """
    if start_point is not None and not new_branch:
        msg = "create_worktree: start_point requires new_branch=True"
        raise ValueError(msg)
    args: list[str] = ["worktree", "add"]
    if new_branch:
        args.extend(["-b", branch, str(path)])
        if start_point is not None:
            args.append(start_point)
    else:
        args.extend([str(path), branch])
    run_git(*args, cwd=cwd, stream=stream, env=env)


def remove_worktree(
    path: Path | str,
    *,
    cwd: Path | str | None = None,
    force: bool = False,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> None:
    """Remove the worktree at ``path``.

    With ``force=True``, removes even when the worktree is dirty or contains
    submodules.

    Args:
        path: Filesystem path of the worktree to remove.
        cwd: Working directory of the source repo; ``None`` inherits the
            process cwd.
        force: When ``True``, pass ``--force`` to ``git worktree remove``.
        stream: Forwarded to :func:`run_git`.
        env: Forwarded to :func:`run_git`.
    """
    args: list[str] = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
    run_git(*args, cwd=cwd, stream=stream, env=env)


def add_worktree(  # noqa: PLR0913
    path: Path | str,
    branch: str,
    *,
    cwd: Path | str | None = None,
    new_branch: bool = False,
    start_point: str | None = None,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> Worktree:
    """Create a worktree and return its :class:`Worktree` record.

    Composite over :func:`create_worktree` + :func:`list_worktrees`. Creates
    the worktree, then reads back the resolved record from
    ``git worktree list``.

    Args:
        path: Filesystem path where the new worktree will be created.
        branch: Branch name to check out (or create when ``new_branch=True``).
        cwd: Working directory of the source repo; ``None`` inherits the
            process cwd.
        new_branch: When ``True``, create ``branch`` as part of adding the
            worktree (passes ``-b`` to ``git worktree add``).
        start_point: Optional commit/ref to base ``branch`` on. Requires
            ``new_branch=True``.
        stream: Forwarded to every internal :func:`run_git` call.
        env: Forwarded to every internal :func:`run_git` call.

    Returns:
        The :class:`Worktree` record for the newly created worktree.

    Raises:
        ValueError: ``start_point`` is set without ``new_branch=True``.
        RuntimeError: the worktree was created but does not appear in the
            subsequent listing. Should not happen in practice; guards
            against silent bugs.
    """
    create_worktree(
        path,
        branch,
        cwd=cwd,
        new_branch=new_branch,
        start_point=start_point,
        stream=stream,
        env=env,
    )
    resolved_path = Path(path).expanduser().resolve()
    for wt in list_worktrees(cwd, stream=stream, env=env):
        if wt.path.resolve() == resolved_path:
            return wt
    msg = f"add_worktree: created worktree at {resolved_path} not found in listing"
    raise RuntimeError(msg)
