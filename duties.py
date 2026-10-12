"""Duty tasks for the project."""

from __future__ import annotations

import os
import re
import shlex
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


def gated(*cmd: str) -> list[str]:
    """Wrap a command in gate-cache so it skips when it already passed on the same files.

    The Python version is part of the gate name because the git tree that keys the cache does not cover the interpreter.

    Returns:
        list[str]: The command prefixed with a gate-cache invocation.
    """
    name = f"{shlex.join(cmd)} (python{sys.version_info.major}.{sys.version_info.minor})"
    return ["gate-cache", "--name", name, "--", *cmd]


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
        gated("ruff", "check", "--config", "pyproject.toml", "--no-fix", *PY_SRC_LIST),
        title=pyprefix("code quality check"),
    )


@duty
def format(ctx: Context) -> None:  # noqa: A001
    """Format the code with ruff."""
    ctx.run(
        gated("ruff", "format", "--check", "--config", "pyproject.toml", *PY_SRC_LIST),
        title=pyprefix("code formatting"),
    )


@duty
def ty(ctx: Context) -> None:
    """Check the code with ty."""
    os.environ["FORCE_COLOR"] = "1"
    ctx.run(gated("ty", "check", "src/"), title="ty check")


@duty
def typos(ctx: Context) -> None:
    """Check the code with typos."""
    ctx.run(
        gated("typos", "--config", ".typos.toml"),
        title=pyprefix("typos check"),
    )


@duty(skip_if=CI, skip_reason="skip prek in CI environments")
def prek(ctx: Context) -> None:
    """Run prek hooks."""
    # These hooks call the duties above, which lint already runs
    os.environ["SKIP"] = "ruff,format,ty,typos,pytest"
    ctx.run(gated("prek", "run", "--all-files"), title=pyprefix("prek hooks"))


@duty(pre=[ruff, format, ty, typos, prek], capture=CI)
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
    out = ctx.run(
        gated(
            "pytest",
            "tests/",
            "src/",
            "--config-file=pyproject.toml",
            "--color=yes",
            "--cov",
            "--cov-config=pyproject.toml",
            "--cov-report=xml",
            "--cov-report=term",
            *cli_args,
        ),
        title=pyprefix("Running tests"),
    )

    if not CI:
        rprint(strip_ansi(out))
