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
