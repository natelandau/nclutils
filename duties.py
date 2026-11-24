"""Duty tasks for the project."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from duty import duty
from rich import print as rprint

if TYPE_CHECKING:
    from duty.context import Context

PY_SRC_PATHS = (Path(_) for _ in ("src/", "tests/", "duties.py", "scripts/") if Path(_).exists())
PY_SRC_LIST = tuple(str(_) for _ in PY_SRC_PATHS)
CI = os.environ.get("CI", "0") in {"1", "true", "yes", ""}

# Everything git tracks that the test suite reads. A change outside these paths skips the test gate.
TEST_GATE_PATHS = ("src/", "tests/", "pyproject.toml", "uv.lock", "duties.py")
TEST_JUNIT_REPORT = ".cache/junit.xml"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string.

    Args:
        text (str): String to remove ANSI escape sequences from.

    Returns:
        str: String without ANSI escape sequences.
    """
    ansi_chars = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")

    # Replace [ with \[ so rich doesn't interpret output as style tags
    return ansi_chars.sub("", text).replace("[", r"\[")


def pyprefix(title: str) -> str:
    """Add a prefix to the title if CI is true.

    Returns:
        str: Title with prefix if CI is true.
    """
    if CI:
        prefix = f"(python{sys.version_info.major}.{sys.version_info.minor})"
        return f"{prefix:14}{title}"
    return title


def gated(name: str, *cmd: str, paths: tuple[str, ...] = (), junit: str | None = None) -> list[str]:
    """Wrap a command in gate-cache so it skips when it already passed on the same files.

    The Python version is the gate's key because the git tree that keys the cache does not cover the interpreter.

    Args:
        name (str): Short, stable gate name shown by `gate-cache status` and the stats dashboard.
        *cmd (str): The command to run.
        paths (tuple[str, ...]): Git pathspecs the command reads. Empty means the whole repository.
        junit (str | None): Path of the JUnit XML report the command writes, so stats record each test.

    Returns:
        list[str]: The command prefixed with a gate-cache invocation.
    """
    key = f"py{sys.version_info.major}.{sys.version_info.minor}"
    options = [f"--name={name}@{key}"]
    options.extend(f"--path={path}" for path in paths)
    if junit:
        options.append(f"--junit={junit}")
    return ["gate-cache", *options, "--", *cmd]


@duty(silent=True)
def clean(ctx: Context) -> None:
    """Clean the project."""
    ctx.run("rm -rf .cache")
    ctx.run("rm -rf build")
    ctx.run("rm -rf dist")
    ctx.run("rm -rf pip-wheel-metadata")
    ctx.run("find . -type d -name __pycache__ | xargs rm -rf")
    ctx.run("find . -name '.DS_Store' -delete")


@duty
def ruff(ctx: Context) -> None:
    """Check the code quality with ruff."""
    ctx.run(
        ["ruff", "check", "--config", "pyproject.toml", "--no-fix", *PY_SRC_LIST],
        title=pyprefix("code quality check"),
    )


@duty
def format(ctx: Context) -> None:  # noqa: A001
    """Format the code with ruff."""
    ctx.run(
        ["ruff", "format", "--check", "--config", "pyproject.toml", *PY_SRC_LIST],
        title=pyprefix("code formatting"),
    )


@duty
def ty(ctx: Context) -> None:
    """Check the code with ty."""
    os.environ["FORCE_COLOR"] = "1"
    ctx.run(["ty", "check", "src/"], title="ty check")


@duty
def typos(ctx: Context) -> None:
    """Check the code with typos."""
    ctx.run(
        gated("typos", "typos", "--config", ".typos.toml"),
        title=pyprefix("typos check"),
    )


@duty
def actionlint(ctx: Context) -> None:
    """Check the GitHub Actions workflows with actionlint."""
    ctx.run(["actionlint"], title=pyprefix("actionlint"))


@duty
def prek(ctx: Context) -> None:
    """Run prek hooks."""
    # These hooks call the duties above, which lint already runs
    os.environ["SKIP"] = "ruff,format,ty,typos,actionlint,pytest"
    ctx.run(gated("prek", "prek", "run", "--all-files"), title=pyprefix("prek hooks"))


@duty(pre=[ruff, format, ty, typos, actionlint, prek], capture=CI)
def lint(ctx: Context) -> None:
    """Run all linting duties."""


@duty(capture=CI)
def update(ctx: Context) -> None:
    """Update the project."""
    ctx.run(["uv", "lock", "--upgrade"], title="update uv lock")
    ctx.run(["uv", "sync"], title="sync uv")
    ctx.run(["prek", "autoupdate"], title="prek autoupdate")


@duty()
def test(ctx: Context, *cli_args: str) -> None:
    """Test package and generate coverage reports."""
    pytest_cmd = [
        "pytest",
        "tests/",
        "src/",
        "--config-file=pyproject.toml",
        "--color=yes",
        "--numprocesses=auto",
        "--cov",
        "--cov-config=pyproject.toml",
        "--cov-report=xml",
        "--cov-report=term",
    ]

    # Extra arguments usually filter the suite, and a pass on a subset must not mark the full suite as passed
    if cli_args:
        cmd = [*pytest_cmd, *cli_args]
    else:
        cmd = gated(
            "test",
            *pytest_cmd,
            f"--junitxml={TEST_JUNIT_REPORT}",
            paths=TEST_GATE_PATHS,
            junit=TEST_JUNIT_REPORT,
        )

    out = ctx.run(cmd, title=pyprefix("Running tests"))

    if not CI:
        rprint(strip_ansi(out))
