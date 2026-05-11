"""Tests for nclutils.git.prunable_branches and delete_branches."""

import subprocess
from pathlib import Path

import pytest

from nclutils.git import (
    PrunableBranch,
    branch_exists,
    delete_branches,
    prunable_branches,
)


class TestPrunableBranches:
    """Tests for prunable_branches."""

    def test_includes_merged_with_reason(self, repo_with_merged_branch: Path) -> None:
        """Verify prunable_branches reports a merged branch with reason='merged'."""
        # Given/When
        result = prunable_branches(repo_with_merged_branch, merged=True, gone=False)
        # Then
        assert PrunableBranch(name="merged-feat", reason="merged") in result

    def test_includes_gone_with_reason(self, repo_with_gone_branch: Path) -> None:
        """Verify prunable_branches reports a gone branch with reason='gone'."""
        # Given/When
        result = prunable_branches(repo_with_gone_branch, merged=False, gone=True)
        # Then
        assert PrunableBranch(name="gone-feat", reason="gone") in result

    def test_excludes_current_branch(self, repo_with_merged_branch: Path) -> None:
        """Verify prunable_branches never lists the current branch."""
        # Given: main is current and was merged into itself trivially
        # When
        result = prunable_branches(repo_with_merged_branch)
        # Then
        assert all(pb.name != "main" for pb in result)

    def test_excludes_named(self, repo_with_merged_branch: Path) -> None:
        """Verify prunable_branches honors the exclude list."""
        # Given/When: merged-feat would be prunable, but exclude it
        result = prunable_branches(
            repo_with_merged_branch,
            merged=True,
            gone=False,
            exclude=("main", "master", "develop", "merged-feat"),
        )
        # Then
        assert all(pb.name != "merged-feat" for pb in result)

    def test_no_default_branch_raises(self, repo: Path) -> None:
        """Verify prunable_branches raises ValueError without a default branch."""
        # Given/When/Then
        with pytest.raises(ValueError, match="default branch"):
            prunable_branches(repo)

    def test_gone_wins_over_merged(self, repo_with_remote: Path) -> None:
        """Verify a branch that is both merged and gone reports reason='gone'."""
        # Given: create branch, push, merge into main, then delete remote
        subprocess.run(
            ["git", "checkout", "-b", "both"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        (repo_with_remote / "both.txt").write_text("b\n")
        subprocess.run(
            ["git", "add", "both.txt"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "both"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", "both"],
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
        subprocess.run(
            ["git", "merge", "--no-ff", "both", "-m", "merge both"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "--delete", "both"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "fetch", "--prune", "origin"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )

        # When
        result = prunable_branches(repo_with_remote, merged=True, gone=True)

        # Then: 'both' appears exactly once, with reason='gone'
        names = [pb.name for pb in result]
        assert names.count("both") == 1
        match = next(pb for pb in result if pb.name == "both")
        assert match.reason == "gone"


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
