"""Tests for nclutils.git.branch primitives."""

from pathlib import Path

from nclutils.git import (
    ahead_behind,
    all_local_branches,
    branch_exists,
    current_branch,
    default_branch,
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
