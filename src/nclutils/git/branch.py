"""Branch primitives: queries about branches, upstreams, and divergence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .runner import run_git

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

_GONE_RE = re.compile(r"^[*+ ]?\s*(\S+)\s+\S+\s+\[[^\]]+:\s*gone\b")

PruneReason = Literal["merged", "gone", "empty"]


@dataclass(frozen=True, slots=True)
class PrunableBranch:
    """A local branch that is safe to delete, with the reason it qualifies.

    Returned from :func:`prunable_branches`. The ``reason`` field carries
    the precedence-resolved classification:

    - ``"gone"``: upstream tracking ref has been deleted.
    - ``"merged"``: branch is fully merged into the target.
    - ``"empty"``: branch has zero commits ahead of the target (only
      surfaced when ``prunable_branches(include_empty=True)``).
    """

    name: str
    reason: PruneReason


@dataclass(frozen=True, slots=True)
class DeleteOutcome:
    """Per-branch result from :func:`delete_branches`.

    Returned by :func:`delete_branches`. Callers can report fine-grained
    progress (e.g., "deleted 3, skipped 1, failed 2") instead of seeing
    a list truncated by the first failure.

    Attributes:
        deleted: Branches that were actually deleted, in input order.
        skipped: Branches skipped because they are the current branch or
            do not exist locally.
        failed: Branches whose ``git branch -d/-D`` invocation returned
            non-zero. The value is the captured stderr (or a fallback
            "git branch failed (exit N)" when stderr is empty).
    """

    deleted: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: dict[str, str]


def current_branch(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return the current branch name, or None on detached HEAD."""
    result = run_git(
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name or None


def default_branch(
    cwd: Path | str | None = None,
    *,
    remote: str = "origin",
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return the default branch name as advertised by ``<remote>/HEAD``.

    Returns None if the remote symbolic ref is not configured (e.g., no
    remote, or the symref was never resolved with ``git remote set-head``).
    """
    ref = f"refs/remotes/{remote}/HEAD"
    result = run_git(
        "symbolic-ref",
        "--quiet",
        ref,
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    if result.returncode != 0:
        return None
    target = result.stdout.strip()
    prefix = f"refs/remotes/{remote}/"
    name = target.removeprefix(prefix)
    if name == target or not name:
        return None
    return name


def branch_exists(
    branch: str,
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True if ``branch`` is a local branch."""
    result = run_git(
        "rev-parse",
        "--verify",
        "--quiet",
        f"refs/heads/{branch}",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    return result.returncode == 0


def all_local_branches(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Return the set of local branch names.

    Returns an empty frozenset if cwd is not inside a repo (matching the
    "absent → empty" pattern used by other branch primitives).
    """
    result = run_git(
        "branch",
        "--list",
        "--format=%(refname:short)",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    if result.returncode != 0:
        return frozenset()
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def tracking_branch(
    branch: str | None = None,
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str] | None:
    """Return ``(remote, branch_on_remote)`` for the upstream of ``branch``.

    ``branch=None`` means the current branch. Returns None if there is no
    upstream configured (or if HEAD is detached and ``branch=None``).
    """
    target = branch if branch is not None else current_branch(cwd, stream=stream, env=env)
    if target is None:
        return None

    remote_result = run_git(
        "config",
        "--get",
        f"branch.{target}.remote",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    merge_result = run_git(
        "config",
        "--get",
        f"branch.{target}.merge",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
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
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> tuple[int, int]:
    """Return ``(ahead, behind)`` commit counts comparing ``left`` to ``right``.

    ``left`` is the side ``(ahead)`` measures from. For a typical
    "is my branch ahead of upstream?" check, pass ``left=branch`` and
    ``right=upstream_ref``.
    """
    result = run_git(
        "rev-list",
        "--left-right",
        "--count",
        f"{left}...{right}",
        cwd=cwd,
        stream=stream,
        env=env,
    )
    parts = result.stdout.strip().split()
    if len(parts) != 2:  # noqa: PLR2004
        return (0, 0)
    return (int(parts[0]), int(parts[1]))


def is_empty_branch(
    branch: str,
    target: str | None = None,
    *,
    cwd: Path | str | None = None,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True when ``branch`` has zero commits ahead of ``target``.

    Useful as a primitive for "is this feature branch worth keeping?"
    checks: an empty branch was never written to and is a legitimate
    cleanup candidate even when it is not merged or gone.

    ``target=None`` defers to :func:`default_branch` (with the implicit
    default ``remote="origin"``).

    Args:
        branch: Branch to inspect.
        target: Comparison base. Defaults to the repo's default branch.
        cwd: Working directory; ``None`` inherits the process cwd.
        stream: Forwarded to :func:`run_git`.
        env: Forwarded to :func:`run_git`.

    Returns:
        True when ``branch`` has zero commits that are not also on ``target``.

    Raises:
        ValueError: ``target=None`` and ``default_branch()`` returns None.
    """
    if target is None:
        target = default_branch(cwd, stream=stream, env=env)
    if target is None:
        msg = "is_empty_branch: target=None and default branch could not be resolved"
        raise ValueError(msg)
    ahead, _ = ahead_behind(branch, target, cwd=cwd, stream=stream, env=env)
    return ahead == 0


def merged_branches(
    target: str | None = None,
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
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
        target = default_branch(cwd, stream=stream, env=env)
    if target is None:
        msg = "merged_branches: target=None and default branch could not be resolved"
        raise ValueError(msg)

    result = run_git(
        "branch",
        "--list",
        "--merged",
        target,
        "--format=%(refname:short)",
        cwd=cwd,
        stream=stream,
        env=env,
    )
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def gone_branches(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Return branches whose upstream tracking ref has been deleted.

    Parses ``git branch -vv`` for the ``[<upstream>: gone]`` marker.
    """
    result = run_git("branch", "-vv", "--no-color", cwd=cwd, stream=stream, env=env)
    out: set[str] = set()
    for line in result.stdout.splitlines():
        match = _GONE_RE.match(line)
        if match:
            out.add(match.group(1))
    return frozenset(out)


def prunable_branches(  # noqa: C901, PLR0912, PLR0913
    cwd: Path | str | None = None,
    *,
    merged: bool = True,
    gone: bool = True,
    include_empty: bool = False,
    target: str | None = None,
    exclude: tuple[str, ...] = ("main", "master", "develop"),
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> list[PrunableBranch]:
    """Return local branches safe to delete, with the reason each qualifies.

    Combines:
      - branches merged into ``target`` when ``merged`` is True. ``target``
        defaults to ``default_branch()``.
      - branches whose upstream is gone, when ``gone`` is True.
      - branches with zero commits ahead of ``target`` when
        ``include_empty`` is True (excluding those already classified as
        merged or gone).

    Always excludes the current branch and any name in ``exclude``.

    Reason precedence when a branch qualifies under multiple criteria:
    ``"gone"`` > ``"merged"`` > ``"empty"``. Order is alphabetical by
    name.

    Raises:
        ValueError: ``merged`` or ``include_empty`` is True, ``target``
            is None, and ``default_branch()`` returns None.
    """
    if (merged or include_empty) and target is None:
        target = default_branch(cwd, stream=stream, env=env)
    if (merged or include_empty) and target is None:
        msg = "prunable_branches: no target and default branch could not be resolved"
        raise ValueError(msg)

    reasons: dict[str, PruneReason] = {}
    if merged and target is not None:
        for name in merged_branches(target, cwd=cwd, stream=stream, env=env):
            reasons[name] = "merged"
    if gone:
        for name in gone_branches(cwd=cwd, stream=stream, env=env):
            reasons[name] = "gone"  # overwrites "merged"; gone wins
    if include_empty and target is not None:
        for name in all_local_branches(cwd=cwd, stream=stream, env=env):
            if name in reasons:
                continue
            if name == target:
                continue
            ahead, _ = ahead_behind(name, target, cwd=cwd, stream=stream, env=env)
            if ahead == 0:
                reasons[name] = "empty"

    current = current_branch(cwd, stream=stream, env=env)
    excluded: set[str] = set(exclude)
    if current is not None:
        excluded.add(current)
    if target is not None:
        excluded.add(target)

    return [
        PrunableBranch(name=n, reason=r) for n, r in sorted(reasons.items()) if n not in excluded
    ]


def delete_branches(
    branches: Sequence[str],
    cwd: Path | str | None = None,
    *,
    force: bool = False,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> DeleteOutcome:
    """Delete local branches, returning a structured per-branch outcome.

    Skips (does not attempt) the current branch and branches that do not
    exist locally. Per-branch deletion failures (e.g., unmerged with
    ``force=False``) are captured in ``DeleteOutcome.failed`` rather than
    raised. Infrastructural errors (git missing, not a repo) still
    propagate.

    With ``force=True``, runs ``git branch -D`` (deletes regardless of
    merge state).

    Args:
        branches: Branch names to delete.
        cwd: Working directory; ``None`` inherits the process cwd.
        force: When ``True``, pass ``-D`` instead of ``-d``.
        stream: Forwarded to :func:`run_git`.
        env: Forwarded to :func:`run_git`.

    Returns:
        :class:`DeleteOutcome` with deleted, skipped, and failed groups.
    """
    current = current_branch(cwd, stream=stream, env=env)
    existing = all_local_branches(cwd, stream=stream, env=env)
    flag = "-D" if force else "-d"
    deleted: list[str] = []
    skipped: list[str] = []
    failed: dict[str, str] = {}
    for name in branches:
        if name == current or name not in existing:
            skipped.append(name)
            continue
        result = run_git(
            "branch",
            flag,
            name,
            cwd=cwd,
            check=False,
            stream=stream,
            env=env,
        )
        if result.returncode == 0:
            deleted.append(name)
        else:
            msg = result.stderr.strip() or f"git branch failed (exit {result.returncode})"
            failed[name] = msg
    return DeleteOutcome(
        deleted=tuple(deleted),
        skipped=tuple(skipped),
        failed=failed,
    )
