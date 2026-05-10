"""Git utilities built on top of nclutils.sh."""

from .branch import (
    ahead_behind,
    all_local_branches,
    branch_exists,
    current_branch,
    default_branch,
    gone_branches,
    merged_branches,
    tracking_branch,
)
from .repo import (
    RepoState,
    get_repo_state,
    is_dirty,
    is_git_installed,
    is_git_repo,
    is_rebase_in_progress,
    primary_remote,
    repo_root,
)
from .runner import NotARepoError, run_git
from .sync import fetch, stashed

__all__ = [
    "NotARepoError",
    "RepoState",
    "ahead_behind",
    "all_local_branches",
    "branch_exists",
    "current_branch",
    "default_branch",
    "fetch",
    "get_repo_state",
    "gone_branches",
    "is_dirty",
    "is_git_installed",
    "is_git_repo",
    "is_rebase_in_progress",
    "merged_branches",
    "primary_remote",
    "repo_root",
    "run_git",
    "stashed",
    "tracking_branch",
]
