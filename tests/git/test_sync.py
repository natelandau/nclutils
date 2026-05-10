"""Tests for nclutils.git.sync (fetch, stashed, sync_branch)."""

import subprocess
from pathlib import Path

import pytest

from nclutils.git import (
    NotARepoError,
    fetch,
)
from nclutils.sh import ShellCommandFailedError


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
            ["git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/gone-feat"],  # noqa: S607
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
