"""Tests for nclutils.git.prunable_branches and delete_branches."""

from pathlib import Path

import pytest

from nclutils.git import (
    branch_exists,
    delete_branches,
    prunable_branches,
)


class TestPrunableBranches:
    """Tests for prunable_branches."""

    def test_includes_merged(self, repo_with_merged_branch: Path) -> None:
        """Verify prunable_branches lists a merged branch when merged=True."""
        # Given/When
        result = prunable_branches(repo_with_merged_branch, merged=True, gone=False, empty=False)
        # Then
        assert "merged-feat" in result

    def test_includes_gone(self, repo_with_gone_branch: Path) -> None:
        """Verify prunable_branches lists a gone branch when gone=True."""
        # Given/When
        result = prunable_branches(repo_with_gone_branch, merged=False, gone=True, empty=False)
        # Then
        assert "gone-feat" in result

    def test_excludes_current_branch(self, repo_with_merged_branch: Path) -> None:
        """Verify prunable_branches never lists the current branch."""
        # Given: main is current and was merged into itself trivially
        # When
        result = prunable_branches(repo_with_merged_branch)
        # Then
        assert "main" not in result

    def test_excludes_named(self, repo_with_merged_branch: Path) -> None:
        """Verify prunable_branches honors the exclude list."""
        # Given/When: merged-feat would be prunable, but exclude it
        result = prunable_branches(
            repo_with_merged_branch,
            merged=True,
            gone=False,
            empty=False,
            exclude=("main", "master", "develop", "merged-feat"),
        )
        # Then
        assert "merged-feat" not in result

    def test_no_default_branch_raises(self, repo: Path) -> None:
        """Verify prunable_branches raises ValueError without a default branch."""
        # Given/When/Then
        with pytest.raises(ValueError, match="default branch"):
            prunable_branches(repo)


class TestDeleteBranches:
    """Tests for delete_branches."""

    def test_deletes_merged(self, repo_with_merged_branch: Path) -> None:
        """Verify delete_branches removes a merged branch."""
        # Given: merged-feat exists
        # When
        deleted = delete_branches(["merged-feat"], cwd=repo_with_merged_branch)
        # Then
        assert deleted == ["merged-feat"]
        assert branch_exists("merged-feat", cwd=repo_with_merged_branch) is False

    def test_skips_current_branch(self, repo: Path) -> None:
        """Verify delete_branches silently skips the current branch."""
        # Given/When
        deleted = delete_branches(["main"], cwd=repo)
        # Then
        assert deleted == []
        assert branch_exists("main", cwd=repo) is True

    def test_skips_missing_branch(self, repo: Path) -> None:
        """Verify delete_branches silently skips a branch that doesn't exist."""
        # Given/When
        deleted = delete_branches(["nope"], cwd=repo)
        # Then
        assert deleted == []

    def test_force_deletes_unmerged(self, repo_with_branches: Path) -> None:
        """Verify force=True deletes an unmerged branch."""
        # Given: feat is unmerged
        # When
        deleted = delete_branches(["feat"], cwd=repo_with_branches, force=True)
        # Then
        assert deleted == ["feat"]
        assert branch_exists("feat", cwd=repo_with_branches) is False
