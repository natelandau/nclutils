"""Tests for nclutils.git.runner."""

import logging
import os
from pathlib import Path

import pytest

from nclutils.git import NotARepoError, run_git
from nclutils.sh import (
    CompletedCommand,
    ShellCommandFailedError,
)


class TestNotARepoError:
    """Tests for the NotARepoError exception."""

    def test_inherits_from_exception(self) -> None:
        """Verify NotARepoError is a normal Exception subclass."""
        # Given/Then: the class is a subclass of Exception
        assert issubclass(NotARepoError, Exception)

    def test_carries_message(self) -> None:
        """Verify NotARepoError stores its message via str()."""
        # Given/When: an instance is built with a message
        err = NotARepoError("not in a repo: /tmp")

        # Then: the message round-trips
        assert "not in a repo" in str(err)


class TestRunGit:
    """Tests for run_git."""

    def test_returns_completed_command_on_success(self, repo: Path) -> None:
        """Verify run_git returns a CompletedCommand on success."""
        # Given/When: a basic status call inside a repo
        result = run_git("status", "--porcelain", cwd=repo)

        # Then: a CompletedCommand with exit 0
        assert isinstance(result, CompletedCommand)
        assert result.returncode == 0
        assert result.argv[:2] == ("git", "status")

    def test_prepends_git_to_argv(self, repo: Path) -> None:
        """Verify run_git prepends 'git' to the supplied args."""
        # Given/When: a single-arg invocation
        result = run_git("status", cwd=repo)

        # Then: argv starts with git
        assert result.argv[0] == "git"
        assert result.argv[1] == "status"

    def test_check_true_raises_on_failure(self, tmp_path: Path) -> None:
        """Verify run_git raises ShellCommandFailedError outside a repo with check=True."""
        # Given/When/Then: rev-parse outside any repo fails
        with pytest.raises(ShellCommandFailedError):
            run_git("rev-parse", "--show-toplevel", cwd=tmp_path)

    def test_check_false_returns_failure_result(self, tmp_path: Path) -> None:
        """Verify run_git returns the failure result when check=False."""
        # Given/When: a failing call with check=False
        result = run_git("rev-parse", "--show-toplevel", cwd=tmp_path, check=False)

        # Then: result is returned with non-zero exit
        assert result.returncode != 0

    def test_okay_codes_treats_listed_codes_as_success(self, repo: Path) -> None:
        """Verify run_git honors okay_codes for non-zero exits."""
        # Given/When: diff --quiet returns 1 when there are differences
        (repo / "README.md").write_text("changed\n")
        result = run_git("diff", "--quiet", cwd=repo, okay_codes=(0, 1))

        # Then: returns normally with rc=1
        assert result.returncode == 1

    def test_passes_env_through(self, repo: Path) -> None:
        """Verify run_git passes env to the underlying run_command."""
        # Given/When: GIT_AUTHOR_NAME via env is observed in commit metadata
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "EnvAuthor",
            "GIT_AUTHOR_EMAIL": "env@example.com",
            "GIT_COMMITTER_NAME": "EnvAuthor",
            "GIT_COMMITTER_EMAIL": "env@example.com",
        }
        (repo / "x.txt").write_text("x")
        run_git("add", "x.txt", cwd=repo)
        run_git("commit", "-m", "via env", cwd=repo, env=env)

        # Then: the most recent commit author is EnvAuthor
        result = run_git("log", "-1", "--pretty=%an", cwd=repo)
        assert result.stdout.strip() == "EnvAuthor"

    def test_logs_at_debug_level(self, repo: Path, sh_caplog: pytest.LogCaptureFixture) -> None:
        """Verify run_git invocations surface through nclutils.sh and add no nclutils.git records."""
        # Given: also capture the retired nclutils.git logger so a regression would show up
        sh_caplog.set_level(logging.DEBUG, logger="nclutils.git")

        # When
        run_git("status", cwd=repo)

        # Then: the invocation surfaces under nclutils.sh, and the retired
        # nclutils.git logger emits nothing.
        sh_messages = [r.getMessage() for r in sh_caplog.records if r.name == "nclutils.sh"]
        assert any("git status" in m for m in sh_messages)
        assert not any(r.name == "nclutils.git" for r in sh_caplog.records)
