"""Fixtures for nclutils.git tests.

All fixtures create real git repositories under tmp_path. We do NOT mock
subprocess output. The parsers under test must handle real git output.
"""

import os
import subprocess
from pathlib import Path

import pytest


def _git(*args: str, cwd: Path) -> None:
    """Run a git command with deterministic identity and signing off."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    cfg = [
        "-c",
        "commit.gpgsign=false",
        "-c",
        "tag.gpgsign=false",
        "-c",
        "init.defaultBranch=main",
    ]
    subprocess.run(  # noqa: S603 -- argv is a list; git lookup via PATH is intentional in tests
        ["git", *cfg, *args],  # noqa: S607 -- relying on PATH for git is intentional in tests
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Empty repo with one commit on main."""
    _git("init", "-b", "main", cwd=tmp_path)
    (tmp_path / "README.md").write_text("# test\n")
    _git("add", "README.md", cwd=tmp_path)
    _git("commit", "-m", "initial", cwd=tmp_path)
    return tmp_path


@pytest.fixture
def dirty_repo(repo: Path) -> Path:
    """Repo with one untracked file."""
    (repo / "untracked.txt").write_text("dirty\n")
    return repo


@pytest.fixture
def repo_with_remote(tmp_path: Path) -> Path:
    """Repo with origin pointing to a bare repo at tmp_path/remote.git."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git("init", "--bare", "-b", "main", cwd=remote)

    work = tmp_path / "work"
    work.mkdir()
    _git("init", "-b", "main", cwd=work)
    (work / "README.md").write_text("# test\n")
    _git("add", "README.md", cwd=work)
    _git("commit", "-m", "initial", cwd=work)
    _git("remote", "add", "origin", str(remote), cwd=work)
    _git("push", "-u", "origin", "main", cwd=work)
    return work


@pytest.fixture
def repo_in_rebase(repo: Path) -> Path:
    """Repo paused mid-rebase due to a conflict."""
    # Create divergent histories on two branches that touch the same line.
    _git("checkout", "-b", "feat", cwd=repo)
    (repo / "README.md").write_text("feat\n")
    _git("commit", "-am", "feat change", cwd=repo)

    _git("checkout", "main", cwd=repo)
    (repo / "README.md").write_text("main\n")
    _git("commit", "-am", "main change", cwd=repo)

    _git("checkout", "feat", cwd=repo)

    # Trigger a rebase that will conflict; do not abort. Run via subprocess
    # directly because _git() uses check=True and rebase will exit non-zero.
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "rebase", "main"],  # noqa: S607 -- relying on PATH for git is intentional in tests
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0  # paused at the conflict
    return repo
