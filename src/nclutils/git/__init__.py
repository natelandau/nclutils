"""Git utilities built on top of nclutils.sh."""

from .repo import (
    is_dirty,
    is_git_installed,
    is_git_repo,
    is_rebase_in_progress,
    primary_remote,
    repo_root,
)
from .runner import NotARepoError, run_git

__all__ = [
    "NotARepoError",
    "is_dirty",
    "is_git_installed",
    "is_git_repo",
    "is_rebase_in_progress",
    "primary_remote",
    "repo_root",
    "run_git",
]
