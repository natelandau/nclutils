"""Tests for nclutils.git.worktree primitives."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from nclutils.git import (
    Worktree,
    add_worktree,
    branch_exists,
    create_worktree,
    list_worktrees,
    remove_worktree,
    run_git,
)
from nclutils.git import worktree as wt_mod


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


class TestAddWorktree:
    """Tests for add_worktree."""

    def test_returns_worktree_record(self, repo: Path, tmp_path: Path) -> None:
        """Verify add_worktree returns a Worktree matching what list_worktrees reports."""
        # Given/When
        wt_path = tmp_path / "wt-add"
        result = add_worktree(wt_path, "feature-add", cwd=repo, new_branch=True)

        # Then
        assert isinstance(result, Worktree)
        assert result.path.resolve() == wt_path.resolve()
        assert result.branch == "feature-add"

        # And the record matches the listing
        listed = next(wt for wt in list_worktrees(repo) if wt.path.resolve() == wt_path.resolve())
        assert listed == result

    def test_raises_when_worktree_not_found_after_create(
        self, repo: Path, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Verify add_worktree raises if the listing does not contain the new path."""
        # Given: simulate a create that leaves no listing
        mocker.patch.object(wt_mod, "list_worktrees", autospec=True, return_value=[])

        # When/Then
        with pytest.raises(RuntimeError, match="not found"):
            add_worktree(tmp_path / "nope", "x", cwd=repo, new_branch=True)


class TestCreateWorktreeTrack:
    """Tests for the track parameter on create_worktree and add_worktree."""

    def test_track_false_disables_upstream(self, repo_with_remote: Path, tmp_path: Path) -> None:
        """Verify track=False produces a local branch with no upstream configured."""
        # Given: origin/main exists (via repo_with_remote)
        # When
        wt_path = tmp_path / "wt-no-track"
        create_worktree(
            wt_path,
            "feat/no-track",
            cwd=repo_with_remote,
            new_branch=True,
            start_point="origin/main",
            track=False,
        )
        # Then: branch exists but has no remote configured
        assert branch_exists("feat/no-track", cwd=repo_with_remote)
        remote_result = run_git(
            "config",
            "--get",
            "branch.feat/no-track.remote",
            cwd=repo_with_remote,
            check=False,
        )
        assert remote_result.returncode != 0
        assert remote_result.stdout.strip() == ""

    def test_track_none_preserves_default_tracking(
        self, repo_with_remote: Path, tmp_path: Path
    ) -> None:
        """Verify track=None leaves git's default tracking behavior intact."""
        # Given: origin/main exists; default git behavior sets up tracking
        # When
        wt_path = tmp_path / "wt-default"
        create_worktree(
            wt_path,
            "feat/default",
            cwd=repo_with_remote,
            new_branch=True,
            start_point="origin/main",
        )
        # Then: branch.feat/default.remote is "origin"
        remote_result = run_git(
            "config",
            "--get",
            "branch.feat/default.remote",
            cwd=repo_with_remote,
        )
        assert remote_result.stdout.strip() == "origin"

    def test_track_true_forces_tracking_against_local_ref(
        self, repo_with_remote: Path, tmp_path: Path
    ) -> None:
        """Verify track=True forces tracking even against a non-remote start point."""
        # Given: HEAD is a local-only ref (no remote tracking by default)
        # When
        wt_path = tmp_path / "wt-force-track"
        create_worktree(
            wt_path,
            "feat/force-track",
            cwd=repo_with_remote,
            new_branch=True,
            start_point="HEAD",
            track=True,
        )
        # Then: branch.feat/force-track.remote is configured (value is "."
        # for local-ref tracking; what matters is that it is set)
        remote_result = run_git(
            "config",
            "--get",
            "branch.feat/force-track.remote",
            cwd=repo_with_remote,
        )
        assert remote_result.returncode == 0
        assert remote_result.stdout.strip() != ""

    def test_add_worktree_forwards_track_false(
        self, repo_with_remote: Path, tmp_path: Path
    ) -> None:
        """Verify add_worktree forwards track=False to create_worktree."""
        # Given/When
        wt_path = tmp_path / "wt-add-no-track"
        result = add_worktree(
            wt_path,
            "feat/add-no-track",
            cwd=repo_with_remote,
            new_branch=True,
            start_point="origin/main",
            track=False,
        )
        # Then: returned Worktree is correct and upstream is not set
        assert result.branch == "feat/add-no-track"
        remote_result = run_git(
            "config",
            "--get",
            "branch.feat/add-no-track.remote",
            cwd=repo_with_remote,
            check=False,
        )
        assert remote_result.returncode != 0
