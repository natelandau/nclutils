"""Tests for nclutils.git.branch primitives."""

import subprocess
from pathlib import Path

import pytest

from nclutils.git import (
    ahead_behind,
    all_local_branches,
    branch_exists,
    current_branch,
    default_branch,
    gone_branches,
    is_empty_branch,
    merged_branches,
    tracking_branch,
)


class TestCurrentBranch:
    """Tests for current_branch."""

    def test_returns_branch_name(self, repo: Path) -> None:
        """Verify current_branch returns 'main' on a fresh repo."""
        # Given/When/Then
        assert current_branch(repo) == "main"

    def test_returns_none_on_detached_head(self, repo_detached_head: Path) -> None:
        """Verify current_branch returns None when HEAD is detached."""
        # Given/When/Then
        assert current_branch(repo_detached_head) is None


class TestDefaultBranch:
    """Tests for default_branch."""

    def test_returns_main_when_origin_head_set(self, repo_with_remote: Path) -> None:
        """Verify default_branch follows origin/HEAD's symref."""
        # Given/When
        result = default_branch(repo_with_remote)
        # Then
        assert result == "main"

    def test_returns_none_without_remote(self, repo: Path) -> None:
        """Verify default_branch returns None when no remote symref exists."""
        # Given/When/Then
        assert default_branch(repo) is None


class TestBranchExists:
    """Tests for branch_exists."""

    def test_true_for_existing_branch(self, repo: Path) -> None:
        """Verify branch_exists returns True for the current branch."""
        assert branch_exists("main", cwd=repo) is True

    def test_false_for_missing_branch(self, repo: Path) -> None:
        """Verify branch_exists returns False for an unknown name."""
        assert branch_exists("nope", cwd=repo) is False


class TestAllLocalBranches:
    """Tests for all_local_branches."""

    def test_returns_all_branches(self, repo_with_branches: Path) -> None:
        """Verify all_local_branches returns every local branch as a frozenset."""
        # Given/When
        result = all_local_branches(repo_with_branches)
        # Then
        assert isinstance(result, frozenset)
        assert {"main", "feat", "local-only"} <= result

    def test_returns_empty_frozenset_outside_repo(self, tmp_path: Path) -> None:
        """Verify all_local_branches returns an empty frozenset outside any repo."""
        # Given/When/Then
        assert all_local_branches(tmp_path) == frozenset()


class TestTrackingBranch:
    """Tests for tracking_branch."""

    def test_returns_remote_and_branch(self, repo_with_remote: Path) -> None:
        """Verify tracking_branch returns (remote, branch) for a tracking branch."""
        # Given/When
        result = tracking_branch(cwd=repo_with_remote)
        # Then
        assert result == ("origin", "main")

    def test_returns_none_without_upstream(self, repo_with_branches: Path) -> None:
        """Verify tracking_branch returns None for a branch with no upstream."""
        assert tracking_branch("local-only", cwd=repo_with_branches) is None

    def test_named_branch(self, repo_with_branches: Path) -> None:
        """Verify tracking_branch resolves a named branch's upstream."""
        # Given/When
        result = tracking_branch("feat", cwd=repo_with_branches)
        # Then
        assert result == ("origin", "feat")

    def test_returns_none_for_missing_branch(self, repo: Path) -> None:
        """Verify tracking_branch returns None for a branch that does not exist."""
        # Given/When/Then: a branch name that doesn't exist
        assert tracking_branch("does-not-exist", cwd=repo) is None


class TestAheadBehind:
    """Tests for ahead_behind."""

    def test_zero_when_equal(self, repo_with_remote: Path) -> None:
        """Verify ahead_behind returns (0, 0) for equal refs."""
        assert ahead_behind("main", "main", cwd=repo_with_remote) == (0, 0)

    def test_diverged_counts(self, repo_diverged: Path) -> None:
        """Verify ahead_behind reports correct counts for diverged refs."""
        # Given: main is 2 ahead, origin/main is 1 ahead
        # When
        result = ahead_behind("main", "origin/main", cwd=repo_diverged)
        # Then: 2 ahead, 1 behind
        assert result == (2, 1)


class TestMergedBranches:
    """Tests for merged_branches."""

    def test_includes_merged_branch(self, repo_with_merged_branch: Path) -> None:
        """Verify merged_branches lists a branch merged into main."""
        # Given/When
        result = merged_branches("main", cwd=repo_with_merged_branch)
        # Then
        assert "merged-feat" in result

    def test_excludes_unmerged_branch(self, repo_with_branches: Path) -> None:
        """Verify merged_branches omits an unmerged feature branch."""
        # Given/When
        result = merged_branches("main", cwd=repo_with_branches)
        # Then
        assert "feat" not in result

    def test_target_none_uses_default_branch(self, repo_with_merged_branch: Path) -> None:
        """Verify target=None defers to default_branch when origin/HEAD is set."""
        # Given/When
        result = merged_branches(cwd=repo_with_merged_branch)
        # Then
        assert "merged-feat" in result

    def test_target_none_raises_without_default(self, repo: Path) -> None:
        """Verify target=None raises ValueError when default_branch returns None."""
        # Given/When/Then
        with pytest.raises(ValueError, match="default branch"):
            merged_branches(cwd=repo)


class TestGoneBranches:
    """Tests for gone_branches."""

    def test_detects_gone_branch(self, repo_with_gone_branch: Path) -> None:
        """Verify gone_branches lists a branch whose upstream was deleted."""
        # Given/When
        result = gone_branches(cwd=repo_with_gone_branch)
        # Then
        assert "gone-feat" in result

    def test_excludes_normal_branches(self, repo_with_remote: Path) -> None:
        """Verify gone_branches returns an empty frozenset when no upstreams are gone."""
        # Given/When
        result = gone_branches(cwd=repo_with_remote)
        # Then: an intact upstream produces no entries at all
        assert result == frozenset()

    def test_detects_gone_branch_in_worktree(self, repo_with_gone_branch_in_worktree: Path) -> None:
        """Verify gone_branches lists a gone branch checked out in a worktree."""
        # Given a gone branch whose "git branch -vv" line carries a (worktree-path) token
        # When gone_branches parses that output
        result = gone_branches(cwd=repo_with_gone_branch_in_worktree)
        # Then the worktree-checked-out gone branch is still detected
        assert "gone-feat" in result


class TestIsEmptyBranch:
    """Tests for is_empty_branch."""

    def test_zero_ahead_returns_true(self, repo_with_remote: Path) -> None:
        """Verify a branch created from target with no new commits is empty."""
        # Given
        subprocess.run(
            ["git", "checkout", "-b", "feat/empty"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        # When/Then
        assert is_empty_branch("feat/empty", cwd=repo_with_remote) is True

    def test_one_ahead_returns_false(self, repo_with_remote: Path) -> None:
        """Verify a branch with one commit ahead of target is not empty."""
        # Given
        subprocess.run(
            ["git", "checkout", "-b", "feat/with-commit"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        (repo_with_remote / "wc.txt").write_text("wc\n")
        subprocess.run(
            ["git", "add", "wc.txt"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "wc"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        # When/Then
        assert is_empty_branch("feat/with-commit", cwd=repo_with_remote) is False

    def test_explicit_target_overrides_default(self, repo_with_remote: Path) -> None:
        """Verify an explicit target argument is used instead of default_branch."""
        # Given: feat branches off main with no new commits, so it is empty
        # relative to main
        subprocess.run(
            ["git", "checkout", "-b", "feat/explicit"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        # When/Then
        assert is_empty_branch("feat/explicit", target="main", cwd=repo_with_remote) is True

    def test_no_default_branch_raises(self, repo: Path) -> None:
        """Verify is_empty_branch raises ValueError without a default branch."""
        # Given: repo has no origin, default_branch returns None
        # When/Then
        with pytest.raises(ValueError, match="default branch"):
            is_empty_branch("main", cwd=repo)
