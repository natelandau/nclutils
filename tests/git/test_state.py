"""Tests for nclutils.git.get_repo_state."""

import subprocess
from pathlib import Path

import pytest

from nclutils.git import NotARepoError, RepoState, get_repo_state


class TestGetRepoState:
    """Tests for get_repo_state."""

    def test_returns_repo_state_clean(self, repo: Path) -> None:
        """Verify get_repo_state returns a clean RepoState on a fresh repo."""
        # Given/When
        state = get_repo_state(repo)
        # Then
        assert isinstance(state, RepoState)
        assert state.root == repo
        assert state.branch == "main"
        assert state.upstream is None
        assert state.ahead == 0
        assert state.behind == 0
        assert state.is_dirty is False
        assert state.staged == 0
        assert state.modified == 0
        assert state.untracked == 0
        assert state.unmerged == 0
        assert state.stash_count == 0
        assert state.rebase_in_progress is False

    def test_dirty_repo(self, dirty_repo: Path) -> None:
        """Verify get_repo_state reports an untracked file."""
        # Given/When
        state = get_repo_state(dirty_repo)
        # Then
        assert state.is_dirty is True
        assert state.untracked == 1
        assert state.modified == 0

    def test_modified_file(self, repo: Path) -> None:
        """Verify get_repo_state distinguishes modified from untracked."""
        # Given: modify the existing README
        (repo / "README.md").write_text("changed\n")
        # When
        state = get_repo_state(repo)
        # Then
        assert state.is_dirty is True
        assert state.modified == 1
        assert state.untracked == 0

    def test_staged_file(self, repo: Path) -> None:
        """Verify get_repo_state reports staged changes."""
        # Given: stage a new file
        (repo / "new.txt").write_text("new\n")
        subprocess.run(["git", "add", "new.txt"], cwd=repo, check=True)  # noqa: S607 -- relying on PATH for git is intentional in tests
        # When
        state = get_repo_state(repo)
        # Then
        assert state.staged == 1
        assert state.untracked == 0

    def test_upstream_and_divergence(self, repo_diverged: Path) -> None:
        """Verify get_repo_state reports upstream and ahead/behind counts."""
        # Given/When
        state = get_repo_state(repo_diverged)
        # Then
        assert state.upstream == "origin/main"
        assert state.ahead == 2
        assert state.behind == 1

    def test_stash_count(self, repo_with_stash: Path) -> None:
        """Verify get_repo_state counts stashes for the current branch."""
        # Given/When
        state = get_repo_state(repo_with_stash)
        # Then
        assert state.stash_count == 1

    def test_raises_not_a_repo(self, tmp_path: Path) -> None:
        """Verify get_repo_state raises NotARepoError outside a repo."""
        # Given/When/Then
        with pytest.raises(NotARepoError):
            get_repo_state(tmp_path)

    def test_stash_count_filters_by_branch(self, repo: Path) -> None:
        """Verify stash_count only counts stashes created on the current branch."""
        # Given: a stash created on a different branch
        (repo / "x.txt").write_text("x\n")
        subprocess.run(
            ["git", "checkout", "-b", "other"],  # noqa: S607
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "stash", "push", "-u", "-m", "on other"],  # noqa: S607
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],  # noqa: S607
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # When
        state = get_repo_state(repo)

        # Then: stash exists, but not on this branch, so count is 0
        assert state.stash_count == 0

    def test_detached_head(self, repo_detached_head: Path) -> None:
        """Verify get_repo_state reports branch=None on detached HEAD."""
        # Given/When
        state = get_repo_state(repo_detached_head)
        # Then
        assert state.branch is None
        assert state.stash_count == 0

    def test_rebase_in_progress(self, repo_in_rebase: Path) -> None:
        """Verify get_repo_state reports rebase_in_progress=True during a paused rebase."""
        # Given/When
        state = get_repo_state(repo_in_rebase)
        # Then
        assert state.rebase_in_progress is True
