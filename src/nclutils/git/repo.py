"""Repo-level primitives: installation/repo checks, dirty state, rebase state."""

from __future__ import annotations

from pathlib import Path

from nclutils.sh import ShellCommandError, which

from .runner import NotARepoError, run_git


def _cwd_for_message(cwd: Path | str | None) -> Path:
    """Return the cwd as a Path for use in error messages (unresolved is fine)."""
    return Path(cwd) if cwd is not None else Path.cwd()


def is_git_installed() -> bool:
    """Return True if the git binary is on PATH."""
    return which("git") is not None


def is_git_repo(cwd: Path | str | None = None) -> bool:
    """Return True if cwd is inside a git working tree."""
    try:
        result = run_git("rev-parse", "--is-inside-work-tree", cwd=cwd, check=False)
    except ShellCommandError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def repo_root(cwd: Path | str | None = None) -> Path:
    """Return the absolute path to the repo's working tree root.

    Raises:
        NotARepoError: cwd is not inside a git repo.
    """
    result = run_git("rev-parse", "--show-toplevel", cwd=cwd, check=False)
    if result.returncode != 0:
        msg = f"not a git repository: {_cwd_for_message(cwd)}"
        raise NotARepoError(msg)
    return Path(result.stdout.strip())


def primary_remote(cwd: Path | str | None = None) -> tuple[str, str] | None:
    """Return the (name, url) of the first configured remote, or None.

    "First" means the first line returned by ``git remote`` (alphabetical
    by default). Most repos have only one remote, so this is usually
    ``origin``.
    """
    listing = run_git("remote", cwd=cwd, check=False)
    if listing.returncode != 0 or not listing.stdout.strip():
        return None
    name = listing.stdout.splitlines()[0].strip()
    url_result = run_git("remote", "get-url", name, cwd=cwd, check=False)
    if url_result.returncode != 0:
        return None
    return (name, url_result.stdout.strip())


def is_dirty(cwd: Path | str | None = None) -> bool:
    """Return True if the working tree has uncommitted changes or untracked files.

    Raises:
        NotARepoError: cwd is not inside a git repo.
    """
    repo_root(cwd)  # validate; raises NotARepoError if not a repo
    result = run_git("status", "--porcelain", cwd=cwd)
    return bool(result.stdout.strip())


def is_rebase_in_progress(cwd: Path | str | None = None) -> bool:
    """Return True if either rebase-merge/ or rebase-apply/ exists in .git/.

    Interactive rebases use rebase-merge/; non-interactive use rebase-apply/.
    Either presence indicates a paused rebase.

    Raises:
        NotARepoError: cwd is not inside a git repo.
    """
    # --absolute-git-dir gives us a usable Path without manual cwd resolution.
    git_dir_result = run_git("rev-parse", "--absolute-git-dir", cwd=cwd, check=False)
    if git_dir_result.returncode != 0:
        msg = f"not a git repository: {_cwd_for_message(cwd)}"
        raise NotARepoError(msg)
    git_dir = Path(git_dir_result.stdout.strip())
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()
