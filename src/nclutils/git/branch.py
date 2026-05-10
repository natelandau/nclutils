"""Branch primitives: queries about branches, upstreams, and divergence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .runner import run_git

if TYPE_CHECKING:
    from pathlib import Path


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
