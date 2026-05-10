"""Fixtures for nclutils.git tests.

All fixtures create real git repositories under tmp_path. We do NOT mock
subprocess output. The parsers under test must handle real git output.
"""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _scrub_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip inherited GIT_* env vars for every test in tests/git/.

    Pre-commit hooks set GIT_INDEX_FILE, GIT_DIR, GIT_WORK_TREE, etc. pointing
    at the host repo. Those leak into subprocess calls that operate on temp
    repos and break operations like `git worktree add` (which tries to write
    a new index at the inherited path).
    """
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key, raising=False)


def _git_env() -> dict[str, str]:
    """Return os.environ extended with deterministic GIT_AUTHOR/COMMITTER identity."""
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }


def _init_repo(cwd: Path, *extra: str) -> None:
    """Initialize a non-bare repo and set per-repo user.name/email.

    Per-repo identity makes the test repo self-contained: the code under test
    can run rebase/merge/commit operations on it without depending on the
    runner's global git config or on inherited GIT_AUTHOR_* env vars (the
    autouse _scrub_git_env fixture strips those).
    """
    _git("init", "-b", "main", *extra, cwd=cwd)
    _git("config", "user.name", "Test", cwd=cwd)
    _git("config", "user.email", "test@example.com", cwd=cwd)


def _git(*args: str, cwd: Path) -> None:
    """Run a git command with deterministic identity and signing off."""
    cfg = [
        "-c",
        "commit.gpgsign=false",
        "-c",
        "tag.gpgsign=false",
        "-c",
        "init.defaultBranch=main",
    ]
    subprocess.run(
        ["git", *cfg, *args],
        cwd=cwd,
        env=_git_env(),
        check=True,
        capture_output=True,
        text=True,
    )


def advance_origin(*, remote_dir: Path, sibling_dir: Path, filename: str) -> None:
    """Push one new commit to ``origin/main`` from a fresh sibling clone.

    Used by sync tests to manufacture a behind-only state on the test repo
    without disturbing its working tree.
    """
    env = _git_env()
    subprocess.run(
        ["git", "clone", str(remote_dir), str(sibling_dir)],
        check=True,
        capture_output=True,
    )
    (sibling_dir / filename).write_text(f"{filename}\n")
    subprocess.run(
        ["git", "add", filename],
        cwd=sibling_dir,
        env=env,
        check=True,
    )
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", filename],
        cwd=sibling_dir,
        env=env,
        check=True,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=sibling_dir,
        env=env,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Empty repo with one commit on main."""
    _init_repo(tmp_path)
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
    _init_repo(work)
    (work / "README.md").write_text("# test\n")
    _git("add", "README.md", cwd=work)
    _git("commit", "-m", "initial", cwd=work)
    _git("remote", "add", "origin", str(remote), cwd=work)
    _git("push", "-u", "origin", "main", cwd=work)
    _git("remote", "set-head", "origin", "main", cwd=work)
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
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "rebase", "main"],
        cwd=repo,
        env=_git_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0  # paused at the conflict
    return repo


@pytest.fixture
def repo_with_branches(repo_with_remote: Path) -> Path:
    """Repo with: feat (tracks origin/feat), local-only (no upstream)."""
    _git("checkout", "-b", "feat", cwd=repo_with_remote)
    (repo_with_remote / "f.txt").write_text("f\n")
    _git("add", "f.txt", cwd=repo_with_remote)
    _git("commit", "-m", "feat", cwd=repo_with_remote)
    _git("push", "-u", "origin", "feat", cwd=repo_with_remote)

    _git("checkout", "-b", "local-only", "main", cwd=repo_with_remote)
    _git("checkout", "main", cwd=repo_with_remote)
    return repo_with_remote


@pytest.fixture
def repo_detached_head(repo: Path) -> Path:
    """Repo checked out at a commit (detached HEAD)."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    _git("checkout", head, cwd=repo)
    return repo


@pytest.fixture
def repo_diverged(repo_with_remote: Path) -> Path:
    """Repo whose main is 2 ahead of origin/main, after origin gained 1 new commit."""
    # Local commits
    (repo_with_remote / "a.txt").write_text("a\n")
    _git("add", "a.txt", cwd=repo_with_remote)
    _git("commit", "-m", "a", cwd=repo_with_remote)
    (repo_with_remote / "b.txt").write_text("b\n")
    _git("add", "b.txt", cwd=repo_with_remote)
    _git("commit", "-m", "b", cwd=repo_with_remote)

    # Add a commit on the bare remote via a sibling clone, then re-fetch.
    sibling = repo_with_remote.parent / "sibling"
    _git(
        "clone",
        str(repo_with_remote.parent / "remote.git"),
        str(sibling),
        cwd=repo_with_remote.parent,
    )
    (sibling / "c.txt").write_text("c\n")
    _git("add", "c.txt", cwd=sibling)
    _git("commit", "-m", "c", cwd=sibling)
    _git("push", "origin", "main", cwd=sibling)

    _git("fetch", "origin", cwd=repo_with_remote)
    return repo_with_remote


@pytest.fixture
def repo_with_merged_branch(repo_with_remote: Path) -> Path:
    """Repo with a feature branch merged into main."""
    _git("checkout", "-b", "merged-feat", cwd=repo_with_remote)
    (repo_with_remote / "m.txt").write_text("m\n")
    _git("add", "m.txt", cwd=repo_with_remote)
    _git("commit", "-m", "merged change", cwd=repo_with_remote)
    _git("checkout", "main", cwd=repo_with_remote)
    _git("merge", "--no-ff", "merged-feat", "-m", "merge feat", cwd=repo_with_remote)
    return repo_with_remote


@pytest.fixture
def repo_with_gone_branch(repo_with_remote: Path) -> Path:
    """Repo with a branch whose upstream tracking ref was deleted."""
    # Create gone-feat tracking origin/gone-feat
    _git("checkout", "-b", "gone-feat", cwd=repo_with_remote)
    (repo_with_remote / "g.txt").write_text("g\n")
    _git("add", "g.txt", cwd=repo_with_remote)
    _git("commit", "-m", "g", cwd=repo_with_remote)
    _git("push", "-u", "origin", "gone-feat", cwd=repo_with_remote)

    # Delete it from the remote
    _git("push", "origin", "--delete", "gone-feat", cwd=repo_with_remote)
    # Prune the local tracking ref so [gone] is reported
    _git("fetch", "--prune", "origin", cwd=repo_with_remote)
    _git("checkout", "main", cwd=repo_with_remote)
    return repo_with_remote


@pytest.fixture
def repo_with_stash(dirty_repo: Path) -> Path:
    """Repo with one stash entry on the current branch."""
    _git("stash", "push", "-u", "-m", "test stash", cwd=dirty_repo)
    return dirty_repo


@pytest.fixture
def repo_with_worktree(repo: Path, tmp_path: Path) -> Path:
    """Repo plus a worktree at tmp_path/wt-feat tracking branch 'feat'."""
    wt_path = tmp_path / "wt-feat"
    _git("worktree", "add", "-b", "feat", str(wt_path), cwd=repo)
    return repo
