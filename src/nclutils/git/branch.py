"""Branch primitives: queries about branches, upstreams, and divergence."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .runner import run_git

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

_GONE_RE = re.compile(r"^[*+ ]?\s*(\S+)\s+\S+\s+\[[^\]]+:\s*gone\b")


def current_branch(cwd: Path | str | None = None) -> str | None:
    """Return the current branch name, or None on detached HEAD."""
    result = run_git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=cwd, check=False)
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name or None


def default_branch(
    cwd: Path | str | None = None,
    *,
    remote: str = "origin",
) -> str | None:
    """Return the default branch name as advertised by ``<remote>/HEAD``.

    Returns None if the remote symbolic ref is not configured (e.g., no
    remote, or the symref was never resolved with ``git remote set-head``).
    """
    ref = f"refs/remotes/{remote}/HEAD"
    result = run_git("symbolic-ref", "--quiet", ref, cwd=cwd, check=False)
    if result.returncode != 0:
        return None
    target = result.stdout.strip()
    prefix = f"refs/remotes/{remote}/"
    if not target.startswith(prefix):
        return None
    return target[len(prefix) :] or None


def branch_exists(branch: str, cwd: Path | str | None = None) -> bool:
    """Return True if ``branch`` is a local branch."""
    result = run_git(
        "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", cwd=cwd, check=False
    )
    return result.returncode == 0


def all_local_branches(cwd: Path | str | None = None) -> frozenset[str]:
    """Return the set of local branch names.

    Returns an empty frozenset if cwd is not inside a repo (matching the
    "absent → empty" pattern used by other branch primitives).
    """
    result = run_git("branch", "--list", "--format=%(refname:short)", cwd=cwd, check=False)
    if result.returncode != 0:
        return frozenset()
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def tracking_branch(
    branch: str | None = None,
    cwd: Path | str | None = None,
) -> tuple[str, str] | None:
    """Return ``(remote, branch_on_remote)`` for the upstream of ``branch``.

    ``branch=None`` means the current branch. Returns None if there is no
    upstream configured (or if HEAD is detached and ``branch=None``).
    """
    target = branch if branch is not None else current_branch(cwd)
    if target is None:
        return None

    remote_result = run_git("config", "--get", f"branch.{target}.remote", cwd=cwd, check=False)
    merge_result = run_git("config", "--get", f"branch.{target}.merge", cwd=cwd, check=False)
    if remote_result.returncode != 0 or merge_result.returncode != 0:
        return None
    remote = remote_result.stdout.strip()
    merge = merge_result.stdout.strip()
    prefix = "refs/heads/"
    branch_on_remote = merge.removeprefix(prefix)
    if not remote or not branch_on_remote:
        return None
    return (remote, branch_on_remote)


def ahead_behind(
    left: str,
    right: str,
    cwd: Path | str | None = None,
) -> tuple[int, int]:
    """Return ``(ahead, behind)`` commit counts comparing ``left`` to ``right``.

    ``left`` is the side ``(ahead)`` measures from. For a typical
    "is my branch ahead of upstream?" check, pass ``left=branch`` and
    ``right=upstream_ref``.
    """
    result = run_git("rev-list", "--left-right", "--count", f"{left}...{right}", cwd=cwd)
    parts = result.stdout.strip().split()
    if len(parts) != 2:  # noqa: PLR2004
        return (0, 0)
    return (int(parts[0]), int(parts[1]))


def merged_branches(
    target: str | None = None,
    cwd: Path | str | None = None,
) -> frozenset[str]:
    """Return local branches merged into ``target``.

    The result includes ``target`` itself (every branch is "merged" with
    itself). Callers performing cleanup operations should exclude the
    target before iterating. See :func:`prunable_branches` for a wrapper
    that does this automatically.

    ``target=None`` defers to :func:`default_branch` (with the implicit
    default ``remote="origin"``). Raises ``ValueError`` if ``target`` is
    None and no default branch can be resolved.

    Raises:
        ValueError: target=None and default_branch() returns None.
        nclutils.sh.ShellCommandFailedError: target is a non-existent ref
            (e.g., a typo).
    """
    if target is None:
        target = default_branch(cwd)
    if target is None:
        msg = "merged_branches: target=None and default branch could not be resolved"
        raise ValueError(msg)

    result = run_git("branch", "--list", "--merged", target, "--format=%(refname:short)", cwd=cwd)
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def gone_branches(cwd: Path | str | None = None) -> frozenset[str]:
    """Return branches whose upstream tracking ref has been deleted.

    Parses ``git branch -vv`` for the ``[<upstream>: gone]`` marker.
    """
    result = run_git("branch", "-vv", "--no-color", cwd=cwd)
    out: set[str] = set()
    for line in result.stdout.splitlines():
        match = _GONE_RE.match(line)
        if match:
            out.add(match.group(1))
    return frozenset(out)


def prunable_branches(
    cwd: Path | str | None = None,
    *,
    merged: bool = True,
    gone: bool = True,
    empty: bool = True,
    target: str | None = None,
    exclude: tuple[str, ...] = ("main", "master", "develop"),
) -> list[str]:
    """Return local branches safe to delete.

    Combines:
      - branches merged into ``target`` (or, equivalently, with zero
        commits ahead of ``target``) when ``merged`` or ``empty`` is True.
        ``target`` defaults to ``default_branch()``.
      - branches whose upstream is gone, when ``gone`` is True.

    Always excludes the current branch and any name in ``exclude``.

    Raises:
        ValueError: target=None and default_branch() returns None.
    """
    if (merged or empty) and target is None:
        target = default_branch(cwd)
    if (merged or empty) and target is None:
        msg = "prunable_branches: no target and default branch could not be resolved"
        raise ValueError(msg)

    candidates: set[str] = set()
    if (merged or empty) and target is not None:
        # merged_branches(target) returns the same set as branches with
        # ahead_behind(branch, target)[0] == 0. The two flags are
        # semantically equivalent and resolved with one subprocess call.
        candidates |= set(merged_branches(target, cwd=cwd))
    if gone:
        candidates |= set(gone_branches(cwd=cwd))

    current = current_branch(cwd)
    excluded = set(exclude)
    if current is not None:
        excluded.add(current)
    if target is not None:
        excluded.add(target)

    return sorted(candidates - excluded)


def delete_branches(
    branches: Sequence[str],
    cwd: Path | str | None = None,
    *,
    force: bool = False,
) -> list[str]:
    """Delete local branches; return the names actually deleted.

    Silently skips:
      - the current branch (``git branch -d`` would fail anyway)
      - branches that don't exist locally

    With ``force=True``, runs ``git branch -D`` (deletes regardless of merge state).
    """
    current = current_branch(cwd)
    existing = all_local_branches(cwd)
    flag = "-D" if force else "-d"
    deleted: list[str] = []
    for name in branches:
        if name == current:
            continue
        if name not in existing:
            continue
        run_git("branch", flag, name, cwd=cwd)
        deleted.append(name)
    return deleted
