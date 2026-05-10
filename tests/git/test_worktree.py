"""Tests for nclutils.git.worktree primitives."""

from pathlib import Path

from nclutils.git import (
    Worktree,
    branch_exists,
    create_worktree,
    list_worktrees,
    remove_worktree,
    run_git,
)


class TestListWorktrees:
    """Tests for list_worktrees."""

    def test_lists_main_worktree_only(self, repo: Path) -> None:
        """Verify list_worktrees returns one entry for a fresh repo."""
        # Given/When
        result = list_worktrees(repo)
        # Then
        assert len(result) == 1
        assert isinstance(result[0], Worktree)
        assert result[0].path.resolve() == repo.resolve()
        assert result[0].branch == "main"
        assert result[0].is_detached is False

    def test_lists_added_worktree(self, repo_with_worktree: Path, tmp_path: Path) -> None:
        """Verify list_worktrees includes a separately added worktree."""
        # Given/When
        result = list_worktrees(repo_with_worktree)
        resolved_paths = {wt.path.resolve() for wt in result}
        branches = {wt.branch for wt in result}
        # Then
        assert (tmp_path / "wt-feat").resolve() in resolved_paths
        assert "feat" in branches


class TestCreateWorktree:
    """Tests for create_worktree."""

    def test_creates_with_existing_branch(self, repo: Path, tmp_path: Path) -> None:
        """Verify create_worktree adds a worktree for an existing branch."""
        # Given: a branch
        run_git("branch", "feature", cwd=repo)
        # When
        wt_path = tmp_path / "wt"
        create_worktree(wt_path, "feature", cwd=repo)
        # Then
        assert wt_path.exists()
        resolved_paths = {wt.path.resolve() for wt in list_worktrees(repo)}
        assert wt_path.resolve() in resolved_paths

    def test_creates_with_new_branch(self, repo: Path, tmp_path: Path) -> None:
        """Verify new_branch=True creates the branch as part of the worktree."""
        # Given/When
        wt_path = tmp_path / "wt-new"
        create_worktree(wt_path, "newbranch", cwd=repo, new_branch=True)
        # Then: the branch now exists
        assert branch_exists("newbranch", cwd=repo)


class TestRemoveWorktree:
    """Tests for remove_worktree."""

    def test_removes_existing_worktree(self, repo_with_worktree: Path, tmp_path: Path) -> None:
        """Verify remove_worktree removes the worktree from the repo's listing."""
        # Given: the worktree exists
        wt_path = tmp_path / "wt-feat"
        assert wt_path.exists()
        # When
        remove_worktree(wt_path, cwd=repo_with_worktree)
        # Then
        resolved_paths = {wt.path.resolve() for wt in list_worktrees(repo_with_worktree)}
        assert wt_path.resolve() not in resolved_paths
