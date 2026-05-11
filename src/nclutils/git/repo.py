"""Repo-level primitives: installation/repo checks, dirty state, rebase state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

from nclutils.sh import ShellCommandError, which

from .runner import NotARepoError, run_git

if TYPE_CHECKING:
    from collections.abc import Mapping

_BRANCH_HEAD_RE = re.compile(r"^# branch\.head (\S.*)$")
_BRANCH_UPSTREAM_RE = re.compile(r"^# branch\.upstream (\S+)$")
_BRANCH_AB_RE = re.compile(r"^# branch\.ab \+(\d+) -(\d+)$")
_STASH_BRANCH_RE = re.compile(r"^stash@\{\d+\}: (?:WIP )?[oO]n (\S+):")
_PORCELAIN_V2_XY_LEN = 2
_SCP_REMOTE_RE = re.compile(r"^[\w.-]+@([\w.-]+):(.+)$")
_REMOTE_URL_SCHEMES = frozenset({"http", "https", "ssh", "git"})


def _cwd_for_message(cwd: Path | str | None) -> Path:
    """Return the cwd as a Path for use in error messages (unresolved is fine)."""
    return Path(cwd) if cwd is not None else Path.cwd()


def _not_a_repo_error(cwd: Path | str | None) -> NotARepoError:
    """Build a NotARepoError with the standard "not a git repository: <cwd>" message."""
    return NotARepoError(f"not a git repository: {_cwd_for_message(cwd)}")


def is_git_installed() -> bool:
    """Return True if the git binary is on PATH."""
    return which("git") is not None


def is_git_repo(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True if cwd is inside a git working tree."""
    try:
        result = run_git(
            "rev-parse",
            "--is-inside-work-tree",
            cwd=cwd,
            check=False,
            stream=stream,
            env=env,
        )
    except ShellCommandError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def repo_root(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Return the absolute path to the repo's working tree root.

    Raises:
        NotARepoError: cwd is not inside a git repo.
    """
    result = run_git(
        "rev-parse",
        "--show-toplevel",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    if result.returncode != 0:
        raise _not_a_repo_error(cwd)
    return Path(result.stdout.strip())


@dataclass(frozen=True, slots=True)
class Remote:
    """A configured git remote.

    ``name`` is the short remote name (e.g., ``"origin"``).
    ``url`` is the configured fetch URL (the same value ``git remote get-url``
    prints).
    ``web_url`` is a best-effort browser URL inferred from ``url``: an
    ``https://<host>/<owner>/<repo>`` rewrite that works for hosts that
    follow the common forge layout (GitHub, GitLab, Bitbucket, Gitea,
    Forgejo, Codeberg, sourcehut, and similar). It is ``None`` when no
    sensible inference is possible (e.g., local paths, ``file://`` URLs).
    """

    name: str
    url: str
    web_url: str | None


def _infer_web_url(url: str) -> str | None:
    """Infer a ``https://<host>/<path>`` browser URL from a git remote URL.

    Handles SCP-like (``git@host:owner/repo``), ``ssh://``, ``git://``,
    ``http://``, and ``https://`` forms. Strips a trailing ``.git``,
    drops any user and port, and rewrites the scheme to ``https``.
    Returns ``None`` for local paths, ``file://`` URLs, or anything
    without a recognizable host.
    """
    cleaned = url.rstrip("/")
    cleaned = cleaned.removesuffix(".git")

    scp_match = _SCP_REMOTE_RE.match(cleaned)
    if scp_match:
        host, path = scp_match.groups()
        path = path.lstrip("/")
        return f"https://{host}/{path}" if path else None

    parsed = urlparse(cleaned)
    if parsed.scheme not in _REMOTE_URL_SCHEMES or not parsed.hostname:
        return None
    path = parsed.path.lstrip("/")
    return f"https://{parsed.hostname}/{path}" if path else None


def primary_remote(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> Remote | None:
    """Return the first configured remote, or None.

    "First" means the first line returned by ``git remote`` (alphabetical
    by default). Most repos have only one remote, so this is usually
    ``origin``.
    """
    listing = run_git("remote", cwd=cwd, check=False, stream=stream, env=env)
    if listing.returncode != 0 or not listing.stdout.strip():
        return None
    name = listing.stdout.splitlines()[0].strip()
    url_result = run_git(
        "remote",
        "get-url",
        name,
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    if url_result.returncode != 0:
        return None
    url = url_result.stdout.strip()
    return Remote(name=name, url=url, web_url=_infer_web_url(url))


def is_dirty(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True if the working tree has uncommitted changes or untracked files.

    Raises:
        NotARepoError: cwd is not inside a git repo.
    """
    result = run_git(
        "status",
        "--porcelain",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    if result.returncode != 0:
        raise _not_a_repo_error(cwd)
    return bool(result.stdout.strip())


def is_rebase_in_progress(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True if either rebase-merge/ or rebase-apply/ exists in .git/.

    Interactive rebases use rebase-merge/; non-interactive use rebase-apply/.
    Either presence indicates a paused rebase.

    Raises:
        NotARepoError: cwd is not inside a git repo.
    """
    # --absolute-git-dir gives us a usable Path without manual cwd resolution.
    git_dir_result = run_git(
        "rev-parse",
        "--absolute-git-dir",
        cwd=cwd,
        check=False,
        stream=stream,
        env=env,
    )
    if git_dir_result.returncode != 0:
        raise _not_a_repo_error(cwd)
    git_dir = Path(git_dir_result.stdout.strip())
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


@dataclass(frozen=True, slots=True)
class RepoState:
    """Snapshot of a repo's state.

    Includes branch, divergence, file counts, and stash count.
    """

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


def _classify_porcelain_v2_entry(  # noqa: PLR0911
    line: str,
) -> Literal["staged", "modified", "unmerged", "untracked"] | None:
    """Return one of 'staged', 'modified', 'unmerged', 'untracked', or None.

    Porcelain v2 lines:
      '1 XY ...'   ordinary changed entry; X is staged, Y is worktree
      '2 XY ...'   renamed/copied; same XY semantics
      'u XY ...'   unmerged
      '? path'     untracked
      '! path'     ignored (skip)
    """
    if line.startswith("? "):
        return "untracked"
    if line.startswith("u "):
        return "unmerged"
    if not line.startswith(("1 ", "2 ")):
        return None
    parts = line.split(" ", 2)
    if len(parts) < 2:  # noqa: PLR2004 -- minimum field count for malformed-line guard
        return None
    xy = parts[1]
    if len(xy) < _PORCELAIN_V2_XY_LEN:
        return None
    x, y = xy[0], xy[1]
    # An entry can be both staged and modified; we classify staged first
    # so the staged-count matches what callers expect.
    if x != ".":
        return "staged"
    if y != ".":
        return "modified"
    return None


def stash_counts(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, int]:
    r"""Return per-branch stash counts parsed from ``git stash list``.

    Useful for status dashboards that need stash counts across the whole
    repo rather than just the current branch (which is what
    :attr:`RepoState.stash_count` reports).

    Detached-HEAD stashes (where ``git stash list`` shows ``(no branch)``
    instead of a branch name) are excluded. The regex's ``\S+`` group
    cannot match across the whitespace inside ``(no branch)``.

    Args:
        cwd: Working directory; ``None`` inherits the process cwd.
        stream: Forwarded to :func:`run_git`.
        env: Forwarded to :func:`run_git`.

    Returns:
        Mapping of branch name to stash count. Empty dict when no
        branch-attached stashes exist.
    """
    result = run_git("stash", "list", cwd=cwd, stream=stream, env=env)
    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        match = _STASH_BRANCH_RE.match(line)
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def _stash_count_for_branch(
    branch: str | None,
    cwd: Path | str | None,
    *,
    stream: bool,
    env: Mapping[str, str] | None,
) -> int:
    """Return the count of stash entries created on ``branch``."""
    if branch is None:
        return 0
    return stash_counts(cwd, stream=stream, env=env).get(branch, 0)


def get_repo_state(
    cwd: Path | str | None = None,
    *,
    stream: bool = False,
    env: Mapping[str, str] | None = None,
) -> RepoState:
    """Snapshot a repo's state in one git status pass.

    Replaces 6+ separate primitive calls (current_branch, is_dirty,
    ahead_behind, stash list, status --porcelain, rebase-in-progress,
    primary remote).

    Issues these subprocess calls under the hood:
      1. ``git rev-parse --show-toplevel`` (via ``repo_root``) for the
         root path and to surface ``NotARepoError`` cleanly.
      2. ``git status --branch --porcelain=v2`` for branch, upstream,
         ahead/behind, and file counts.
      3. ``git stash list`` filtered to the current branch.
      4. ``git rev-parse --absolute-git-dir`` (via ``is_rebase_in_progress``).
      5. ``git remote`` and ``git remote get-url`` (via ``primary_remote``)
         for the first configured remote, if any.

    The composite still wins because callers no longer assemble the
    primitive calls and parse status output themselves.

    Raises:
        NotARepoError: cwd is not inside a repo.
    """
    # Call repo_root first so non-repo cwd surfaces as NotARepoError
    # rather than a ShellCommandFailedError from the status call below.
    root = repo_root(cwd, stream=stream, env=env)

    status = run_git(
        "status",
        "--branch",
        "--porcelain=v2",
        cwd=cwd,
        stream=stream,
        env=env,
    )

    branch: str | None = None
    upstream: str | None = None
    ahead = 0
    behind = 0
    staged = modified = untracked = unmerged = 0

    for line in status.stdout.splitlines():
        head_match = _BRANCH_HEAD_RE.match(line)
        if head_match:
            value = head_match.group(1)
            if value != "(detached)":
                branch = value
            continue
        ups_match = _BRANCH_UPSTREAM_RE.match(line)
        if ups_match:
            upstream = ups_match.group(1)
            continue
        ab_match = _BRANCH_AB_RE.match(line)
        if ab_match:
            ahead = int(ab_match.group(1))
            behind = int(ab_match.group(2))
            continue
        kind = _classify_porcelain_v2_entry(line)
        if kind == "staged":
            staged += 1
        elif kind == "modified":
            modified += 1
        elif kind == "unmerged":
            unmerged += 1
        elif kind == "untracked":
            untracked += 1

    is_dirty_now = bool(staged or modified or untracked or unmerged)
    stash_count = _stash_count_for_branch(branch, cwd, stream=stream, env=env)
    rebase = is_rebase_in_progress(cwd, stream=stream, env=env)
    primary = primary_remote(cwd, stream=stream, env=env)

    return RepoState(
        root=root,
        branch=branch,
        upstream=upstream,
        primary_remote=primary,
        ahead=ahead,
        behind=behind,
        is_dirty=is_dirty_now,
        staged=staged,
        modified=modified,
        untracked=untracked,
        unmerged=unmerged,
        stash_count=stash_count,
        rebase_in_progress=rebase,
    )
