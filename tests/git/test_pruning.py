"""Tests for nclutils.git.prunable_branches and delete_branches."""

import subprocess
from pathlib import Path

import pytest

from nclutils.git import (
    DeleteOutcome,
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

    def test_include_empty_surfaces_empty_branch(self, repo_with_remote: Path) -> None:
        """Verify include_empty=True reports an empty branch with reason='empty'."""
        # Given: feat branched off main with no new commits
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

        # When
        result = prunable_branches(repo_with_remote, merged=False, gone=False, include_empty=True)

        # Then
        assert PrunableBranch(name="feat/empty", reason="empty") in result

    def test_excludes_empty_by_default(self, repo_with_remote: Path) -> None:
        """Verify empty branches are absent when include_empty is False (default)."""
        # Given: feat branched off main with no new commits
        subprocess.run(
            ["git", "checkout", "-b", "feat/empty-default"],
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

        # When: exclude merged so only include_empty=False is being tested
        result = prunable_branches(repo_with_remote, merged=False, gone=False)

        # Then
        assert all(pb.name != "feat/empty-default" for pb in result)

    def test_empty_loses_to_merged(self, repo_with_merged_branch: Path) -> None:
        """Verify a branch that is empty AND merged reports reason='merged'."""
        # Given: merged-feat is merged into main. After merge, merged-feat
        # is also "zero commits ahead" of main, so both classifiers fire.
        # When
        result = prunable_branches(
            repo_with_merged_branch, merged=True, gone=False, include_empty=True
        )
        # Then
        match = next(pb for pb in result if pb.name == "merged-feat")
        assert match.reason == "merged"

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

    def test_gone_wins_over_empty(self, repo_with_remote: Path) -> None:
        """Verify a branch that is both empty and gone reports reason='gone'."""
        # Given: feat branched off main with no commits, pushed, then remote deleted
        subprocess.run(
            ["git", "checkout", "-b", "feat/empty-gone"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        # Push the empty branch (still at main's commit) so it has an upstream
        subprocess.run(
            ["git", "push", "-u", "origin", "feat/empty-gone"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )
        # Delete the remote tracking ref and prune so [gone] is reported
        subprocess.run(
            ["git", "push", "origin", "--delete", "feat/empty-gone"],
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
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo_with_remote,
            check=True,
            capture_output=True,
        )

        # When
        result = prunable_branches(repo_with_remote, merged=False, gone=True, include_empty=True)

        # Then: feat/empty-gone appears exactly once with reason='gone'
        match = next(pb for pb in result if pb.name == "feat/empty-gone")
        assert match.reason == "gone"


class TestDeleteBranches:
    """Tests for delete_branches."""

    def test_deleted_appears_in_outcome(self, repo_with_merged_branch: Path) -> None:
        """Verify a successfully deleted branch lands in outcome.deleted."""
        # Given: merged-feat exists
        # When
        outcome = delete_branches(["merged-feat"], cwd=repo_with_merged_branch)
        # Then
        assert isinstance(outcome, DeleteOutcome)
        assert outcome.deleted == ("merged-feat",)
        assert outcome.skipped == ()
        assert outcome.failed == {}
        assert branch_exists("merged-feat", cwd=repo_with_merged_branch) is False

    def test_current_branch_skipped(self, repo: Path) -> None:
        """Verify the current branch lands in outcome.skipped."""
        # Given/When
        outcome = delete_branches(["main"], cwd=repo)
        # Then
        assert outcome.deleted == ()
        assert outcome.skipped == ("main",)
        assert outcome.failed == {}
        assert branch_exists("main", cwd=repo) is True

    def test_missing_branch_skipped(self, repo: Path) -> None:
        """Verify a non-existent branch lands in outcome.skipped."""
        # Given/When
        outcome = delete_branches(["nope"], cwd=repo)
        # Then
        assert outcome.deleted == ()
        assert outcome.skipped == ("nope",)
        assert outcome.failed == {}

    def test_force_deletes_unmerged(self, repo_with_branches: Path) -> None:
        """Verify force=True deletes an unmerged branch."""
        # Given: feat is unmerged
        # When
        outcome = delete_branches(["feat"], cwd=repo_with_branches, force=True)
        # Then
        assert outcome.deleted == ("feat",)
        assert outcome.failed == {}
        assert branch_exists("feat", cwd=repo_with_branches) is False

    def test_unmerged_branch_without_force_fails(self, repo_with_branches: Path) -> None:
        """Verify an unmerged branch with force=False lands in outcome.failed."""
        # Given: unpushed has local commits with no remote; git -d refuses it
        # When
        outcome = delete_branches(["unpushed"], cwd=repo_with_branches, force=False)
        # Then
        assert outcome.deleted == ()
        assert outcome.skipped == ()
        assert "unpushed" in outcome.failed
        assert outcome.failed["unpushed"] != ""
        assert branch_exists("unpushed", cwd=repo_with_branches) is True

    def test_partial_failures_do_not_block_other_deletions(self, repo_with_branches: Path) -> None:
        """Verify a per-branch failure does not stop subsequent branches."""
        # Given: unpushed has local-only commits with no remote so -d fails;
        # local-only is a no-op branch at main's commit, safely deletable with -d
        # When: ask to delete a missing name, the unpushed branch, and
        # local-only; only local-only should succeed
        outcome = delete_branches(
            ["nope", "unpushed", "local-only"],
            cwd=repo_with_branches,
            force=False,
        )
        # Then
        assert outcome.deleted == ("local-only",)
        assert outcome.skipped == ("nope",)
        assert "unpushed" in outcome.failed
