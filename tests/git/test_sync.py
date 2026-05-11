"""Tests for nclutils.git.sync (fetch, stashed, sync_branch)."""

import subprocess
from pathlib import Path

import pytest

from nclutils.git import (
    NotARepoError,
    SyncResult,
    fetch,
    stashed,
    sync_branch,
)
from nclutils.git.sync import _conflict_paths
from nclutils.sh import ShellCommandFailedError

from .conftest import advance_origin


class TestFetch:
    """Tests for fetch."""

    def test_fetches_default_remote(self, repo_with_remote: Path) -> None:
        """Verify fetch runs without raising on a normal remote."""
        # Given: a repo with origin
        # When/Then: fetch returns without error
        fetch(repo_with_remote)

    def test_fetch_specific_remote(self, repo_with_remote: Path) -> None:
        """Verify fetch accepts an explicit remote name."""
        # Given/When/Then
        fetch(repo_with_remote, remote="origin")

    def test_fetch_prunes_by_default(self, repo_with_gone_branch: Path) -> None:
        """Verify fetch with default prune=True keeps stale tracking refs absent."""
        # Given: gone-feat was already pruned by the fixture; verify a fresh
        # fetch under prune=True does not resurrect it
        # When
        fetch(repo_with_gone_branch)

        # Then: the local tracking ref for gone-feat should not exist
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/gone-feat"],
            cwd=repo_with_gone_branch,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0  # ref does not exist

    def test_raises_not_a_repo(self, tmp_path: Path) -> None:
        """Verify fetch raises NotARepoError outside a repo."""
        # Given/When/Then
        with pytest.raises(NotARepoError):
            fetch(tmp_path)

    def test_raises_when_no_remote(self, repo: Path) -> None:
        """Verify fetch raises ShellCommandFailedError when no remote exists."""
        # Given: a repo with no remote
        # When/Then
        with pytest.raises(ShellCommandFailedError):
            fetch(repo)

    def test_fetch_all_remotes(self, repo_with_remote: Path) -> None:
        """Verify fetch(all_remotes=True) calls git fetch --all without raising."""
        # Given/When/Then
        fetch(repo_with_remote, all_remotes=True)


class TestStashed:
    """Tests for the stashed context manager."""

    def test_clean_tree_no_op(self, repo: Path) -> None:
        """Verify stashed yields False on a clean tree and does nothing."""
        # Given/When
        with stashed(repo) as did_stash:
            # Then: yielded False; tree still clean inside the block
            assert did_stash is False
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout == ""

    def test_dirty_tree_stash_and_pop(self, dirty_repo: Path) -> None:
        """Verify stashed stashes on enter and pops on normal exit."""
        # Given: a dirty tree
        # When: inside the block
        with stashed(dirty_repo) as did_stash:
            assert did_stash is True
            # Inside: tree is clean
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=dirty_repo,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout == ""

        # Then (after exit): the untracked file is back
        assert (dirty_repo / "untracked.txt").exists()

    def test_pops_even_when_block_raises(self, dirty_repo: Path) -> None:
        """Verify stashed pops the stash even when the with-block raises."""

        class BoomError(RuntimeError):
            pass

        # Given: a dirty tree
        # When/Then: in-block exception propagates, but pop still happens
        msg = "inside"
        with pytest.raises(BoomError), stashed(dirty_repo):
            raise BoomError(msg)

        # The stash was popped regardless: untracked file is back
        assert (dirty_repo / "untracked.txt").exists()


class TestSyncBranch:
    """Tests for sync_branch."""

    def test_up_to_date(self, repo_with_remote: Path) -> None:
        """Verify sync_branch returns 'up_to_date' when behind == 0."""
        # Given: a repo at parity with origin
        # When
        result = sync_branch(repo_with_remote)
        # Then
        assert isinstance(result, SyncResult)
        assert result.action == "up_to_date"
        assert result.ahead_before == 0
        assert result.behind_before == 0
        assert result.stashed is False

    def test_fast_forward(self, repo_with_remote: Path, tmp_path: Path) -> None:
        """Verify sync_branch fast-forwards when only behind."""
        # Given: a sibling clone advances origin/main
        advance_origin(
            remote_dir=tmp_path / "remote.git",
            sibling_dir=tmp_path / "ff_sibling",
            filename="ff.txt",
        )

        # When
        result = sync_branch(repo_with_remote)

        # Then
        assert result.action == "fast_forwarded"
        assert result.behind_before == 1
        assert result.ahead_before == 0

    def test_dirty_with_stash_round_trip(self, repo_with_remote: Path, tmp_path: Path) -> None:
        """Verify dirty tree is stashed, sync runs, then dirty state restored."""
        # Given: dirty tree + behind state via sibling push
        advance_origin(
            remote_dir=tmp_path / "remote.git",
            sibling_dir=tmp_path / "stash_round_sibling",
            filename="z.txt",
        )

        # Make local tree dirty
        (repo_with_remote / "dirty.txt").write_text("dirty\n")

        # When
        result = sync_branch(repo_with_remote, stash=True)

        # Then: ff applied, stashed flag set, dirty file restored
        assert result.action == "fast_forwarded"
        assert result.stashed is True
        assert result.behind_before == 1
        assert (repo_with_remote / "dirty.txt").exists()

    def test_dirty_with_stash_false_raises(self, repo_with_remote: Path) -> None:
        """Verify sync_branch with stash=False raises if there are changes to lose."""
        # Given: dirty tree + a behind-only state, forced via a sibling push.
        advance_origin(
            remote_dir=repo_with_remote.parent / "remote.git",
            sibling_dir=repo_with_remote.parent / "stash_false_sibling",
            filename="y.txt",
        )

        # Make local tree dirty
        (repo_with_remote / "dirty.txt").write_text("dirty\n")

        # When/Then
        with pytest.raises(ShellCommandFailedError):
            sync_branch(repo_with_remote, stash=False)

    def test_detached_head_raises_value_error(self, repo_detached_head: Path) -> None:
        """Verify sync_branch raises ValueError on detached HEAD with branch=None."""
        # Given/When/Then
        with pytest.raises(ValueError, match="detached"):
            sync_branch(repo_detached_head)

    def test_raises_not_a_repo_outside_repo(self, tmp_path: Path) -> None:
        """Verify sync_branch raises NotARepoError (not ValueError) outside any repo."""
        # Given/When/Then: a non-repo dir must surface as NotARepoError, not as a
        # misread "detached HEAD" ValueError from current_branch returning None.
        with pytest.raises(NotARepoError):
            sync_branch(tmp_path)

    def test_no_upstream_raises_value_error(self, repo: Path) -> None:
        """Verify sync_branch raises ValueError when the branch has no upstream."""
        # Given/When/Then
        with pytest.raises(ValueError, match="upstream"):
            sync_branch(repo)

    def test_rebase_diverged(self, repo_diverged: Path) -> None:
        """Verify sync_branch rebases when ahead and behind are both nonzero."""
        # Given: repo_diverged is 2 ahead, 1 behind
        # When
        result = sync_branch(repo_diverged)

        # Then
        assert result.action == "rebased"
        assert result.ahead_before == 2
        assert result.behind_before == 1
        assert result.stashed is False

    def test_allow_rebase_false_raises_when_ff_unavailable(self, repo_diverged: Path) -> None:
        """Verify sync_branch with allow_rebase=False raises when ff-only fails."""
        # Given: repo_diverged is 2 ahead, 1 behind, so --ff-only cannot succeed
        # When/Then
        with pytest.raises(ShellCommandFailedError, match="allow_rebase=False"):
            sync_branch(repo_diverged, allow_rebase=False)

    def test_rebase_conflict_aborts_by_default(self, repo_will_conflict_rebase: Path) -> None:
        """Verify sync_branch rolls back and returns action='aborted' on conflict."""
        # Given: local and origin both modified README.md (1 ahead, 1 behind)
        # When
        result = sync_branch(repo_will_conflict_rebase)

        # Then: action=aborted, conflicts populated, rebase rolled back
        assert result.action == "aborted"
        assert result.ahead_before == 1
        assert result.behind_before == 1
        assert Path("README.md") in result.conflicts
        assert not (repo_will_conflict_rebase / ".git" / "rebase-merge").exists()
        assert not (repo_will_conflict_rebase / ".git" / "rebase-apply").exists()
        # Local branch is exactly where it started
        head_msg = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=repo_will_conflict_rebase,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert head_msg == "local change"

    def test_rebase_conflict_leave_raises(self, repo_will_conflict_rebase: Path) -> None:
        """Verify sync_branch on_conflict='leave' raises and keeps the rebase paused."""
        # Given: local and origin both modified README.md
        # When/Then
        with pytest.raises(ShellCommandFailedError):
            sync_branch(repo_will_conflict_rebase, on_conflict="leave")

        # Rebase is still paused on disk
        rebase_paused = (repo_will_conflict_rebase / ".git" / "rebase-merge").exists() or (
            repo_will_conflict_rebase / ".git" / "rebase-apply"
        ).exists()
        assert rebase_paused


class TestConflictPaths:
    """Tests for the _conflict_paths internal helper."""

    def test_returns_empty_outside_repo(self, tmp_path: Path) -> None:
        """Verify _conflict_paths returns an empty tuple when git diff fails."""
        # Given: a directory that is not a git repo
        # When
        result = _conflict_paths(tmp_path, stream=False, env=None)
        # Then
        assert result == ()

    def test_returns_empty_on_clean_repo(self, repo: Path) -> None:
        """Verify _conflict_paths returns an empty tuple when no files are unmerged."""
        # Given: a clean repo with no merge in progress
        # When
        result = _conflict_paths(repo, stream=False, env=None)
        # Then
        assert result == ()

    def test_returns_unmerged_paths(self, repo_in_rebase: Path) -> None:
        """Verify _conflict_paths returns the paths of files with merge conflicts."""
        # Given: a repo paused mid-rebase with README.md unmerged
        # When
        result = _conflict_paths(repo_in_rebase, stream=False, env=None)
        # Then
        assert Path("README.md") in result
