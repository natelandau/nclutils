"""Tests for nclutils.git.repo primitives."""

import subprocess
from pathlib import Path

import pytest

from nclutils.git import (
    NotARepoError,
    is_dirty,
    is_git_installed,
    is_git_repo,
    is_rebase_in_progress,
    primary_remote,
    repo_root,
    stash_counts,
)
from nclutils.git.repo import _infer_web_url


class TestIsGitInstalled:
    """Tests for is_git_installed."""

    def test_returns_true_when_git_on_path(self) -> None:
        """Verify is_git_installed returns True when git is on PATH (CI assumption)."""
        # Given/When/Then: git is on PATH in any CI/dev env
        assert is_git_installed() is True


class TestIsGitRepo:
    """Tests for is_git_repo."""

    def test_true_inside_repo(self, repo: Path) -> None:
        """Verify is_git_repo returns True inside a fresh repo."""
        # Given/When/Then
        assert is_git_repo(repo) is True

    def test_false_outside_repo(self, tmp_path: Path) -> None:
        """Verify is_git_repo returns False outside any repo."""
        # Given/When/Then
        assert is_git_repo(tmp_path) is False


class TestRepoRoot:
    """Tests for repo_root."""

    def test_returns_root_path(self, repo: Path) -> None:
        """Verify repo_root returns an absolute Path equal to the repo dir."""
        # Given/When
        result = repo_root(repo)

        # Then
        assert result == repo

    def test_returns_root_from_subdirectory(self, repo: Path) -> None:
        """Verify repo_root walks up from a subdirectory to the root."""
        # Given: a nested directory inside the repo
        sub = repo / "a" / "b"
        sub.mkdir(parents=True)

        # When
        result = repo_root(sub)

        # Then
        assert result == repo

    def test_raises_outside_repo(self, tmp_path: Path) -> None:
        """Verify repo_root raises NotARepoError outside any repo."""
        # Given/When/Then
        with pytest.raises(NotARepoError):
            repo_root(tmp_path)


class TestPrimaryRemote:
    """Tests for primary_remote."""

    def test_returns_name_and_url(self, repo_with_remote: Path) -> None:
        """Verify primary_remote returns a Remote with name and url when origin is configured."""
        # Given/When
        result = primary_remote(repo_with_remote)

        # Then
        assert result is not None
        assert result.name == "origin"
        assert "remote.git" in result.url

    def test_returns_none_with_no_remote(self, repo: Path) -> None:
        """Verify primary_remote returns None when no remote is configured."""
        # Given/When/Then
        assert primary_remote(repo) is None

    def test_web_url_none_for_local_path_remote(self, repo_with_remote: Path) -> None:
        """Verify web_url is None when the remote is a local filesystem path."""
        # Given: the test fixture configures origin as a local bare repo path
        # When
        result = primary_remote(repo_with_remote)
        # Then
        assert result is not None
        assert result.web_url is None


class TestInferWebUrl:
    """Tests for _infer_web_url."""

    @pytest.mark.parametrize(
        ("git_url", "expected"),
        [
            # SCP-like syntax (the most common case)
            (
                "git@github.com:acme/widget.git",
                "https://github.com/acme/widget",
            ),
            (
                "git@gitlab.com:group/subgroup/project.git",
                "https://gitlab.com/group/subgroup/project",
            ),
            # ssh:// with port
            (
                "ssh://git@gitea.example.com:2222/acme/widget.git",
                "https://gitea.example.com/acme/widget",
            ),
            # ssh:// without port
            (
                "ssh://git@codeberg.org/foo/bar.git",
                "https://codeberg.org/foo/bar",
            ),
            # https:// already; just strip .git
            (
                "https://github.com/foo/bar.git",
                "https://github.com/foo/bar",
            ),
            # http:// gets upgraded to https
            (
                "http://git.example.com/foo/bar.git",
                "https://git.example.com/foo/bar",
            ),
            # git:// protocol
            (
                "git://github.com/foo/bar.git",
                "https://github.com/foo/bar",
            ),
            # Trailing slash and no .git suffix
            (
                "https://github.com/foo/bar/",
                "https://github.com/foo/bar",
            ),
        ],
    )
    def test_infers_web_url(self, git_url: str, expected: str) -> None:
        """Verify _infer_web_url rewrites common git URLs to https browser URLs."""
        # Given/When/Then
        assert _infer_web_url(git_url) == expected

    @pytest.mark.parametrize(
        "git_url",
        [
            "/srv/git/foo.git",
            "file:///srv/git/foo.git",
            "C:/repos/foo.git",
            "",
            "not-a-url",
        ],
    )
    def test_returns_none_for_uninferable(self, git_url: str) -> None:
        """Verify _infer_web_url returns None for local paths and unrecognized inputs."""
        # Given/When/Then
        assert _infer_web_url(git_url) is None


class TestIsDirty:
    """Tests for is_dirty."""

    def test_clean_repo(self, repo: Path) -> None:
        """Verify is_dirty returns False on a clean repo."""
        # Given/When/Then
        assert is_dirty(repo) is False

    def test_dirty_repo(self, dirty_repo: Path) -> None:
        """Verify is_dirty returns True when an untracked file is present."""
        # Given/When/Then
        assert is_dirty(dirty_repo) is True


class TestIsRebaseInProgress:
    """Tests for is_rebase_in_progress."""

    def test_false_normally(self, repo: Path) -> None:
        """Verify is_rebase_in_progress is False on a clean repo."""
        # Given/When/Then
        assert is_rebase_in_progress(repo) is False

    def test_true_during_rebase(self, repo_in_rebase: Path) -> None:
        """Verify is_rebase_in_progress detects a paused rebase."""
        # Given/When/Then
        assert is_rebase_in_progress(repo_in_rebase) is True


class TestStashCounts:
    """Tests for stash_counts."""

    def test_returns_empty_mapping_with_no_stashes(self, repo: Path) -> None:
        """Verify stash_counts returns {} when no stashes exist."""
        # Given/When/Then
        assert stash_counts(repo) == {}

    def test_aggregates_across_branches(self, repo: Path) -> None:
        """Verify stash_counts returns per-branch counts across the whole repo."""
        # Given: two stashes on feat/a, one on main
        subprocess.run(
            ["git", "checkout", "-b", "feat/a"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "a1.txt").write_text("a1\n")
        subprocess.run(
            ["git", "stash", "push", "-u", "-m", "a1"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "a2.txt").write_text("a2\n")
        subprocess.run(
            ["git", "stash", "push", "-u", "-m", "a2"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "m1.txt").write_text("m1\n")
        subprocess.run(
            ["git", "stash", "push", "-u", "-m", "m1"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # When
        result = stash_counts(repo)

        # Then
        assert result == {"feat/a": 2, "main": 1}

    def test_excludes_detached_head_stashes(self, repo: Path) -> None:
        """Verify stash_counts omits stashes created in detached-HEAD state."""
        # Given: detach HEAD and stash an untracked file
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "checkout", head],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "detached.txt").write_text("d\n")
        subprocess.run(
            ["git", "stash", "push", "-u", "-m", "detached"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # When
        result = stash_counts(repo)

        # Then: no branch key from the detached-HEAD stash
        assert all(name not in result for name in ("(no", "(no branch)"))
        assert result == {}
