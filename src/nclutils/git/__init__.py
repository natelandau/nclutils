"""Git utilities built on top of nclutils.sh."""

from .branch import (
    ahead_behind,
    all_local_branches,
    branch_exists,
    current_branch,
    default_branch,
    delete_branches,
    gone_branches,
    merged_branches,
    prunable_branches,
    tracking_branch,
)
from .repo import (
    Remote,
    RepoState,
    get_repo_state,
    is_dirty,
    is_git_installed,
    is_git_repo,
    is_rebase_in_progress,
    primary_remote,
    repo_root,
    stash_counts,
)
from .runner import NotARepoError, run_git
from .sync import SyncResult, fetch, stashed, sync_branch
from .worktree import (
    Worktree,
    add_worktree,
    create_worktree,
    list_worktrees,
    remove_worktree,
)

__all__ = [
    "NotARepoError",
    "Remote",
    "RepoState",
    "SyncResult",
    "Worktree",
    "add_worktree",
    "ahead_behind",
    "all_local_branches",
    "branch_exists",
    "create_worktree",
    "current_branch",
    "default_branch",
    "delete_branches",
    "fetch",
    "get_repo_state",
    "gone_branches",
    "is_dirty",
    "is_git_installed",
    "is_git_repo",
    "is_rebase_in_progress",
    "list_worktrees",
    "merged_branches",
    "primary_remote",
    "prunable_branches",
    "remove_worktree",
    "repo_root",
    "run_git",
    "stash_counts",
    "stashed",
    "sync_branch",
    "tracking_branch",
]
