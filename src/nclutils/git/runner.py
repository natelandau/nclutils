"""Foundation: NotARepoError, run_git.

This module is the single git-subprocess entry point. Every other module in
nclutils.git calls run_git rather than running subprocess directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nclutils.sh import CompletedCommand, run_command

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

logger = logging.getLogger("nclutils.git")


class NotARepoError(Exception):
    """Raised when an operation requires a git repo but cwd isn't inside one."""


def run_git(  # noqa: PLR0913
    *args: str,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    input: str | bytes | None = None,  # noqa: A002 -- mirrors run_command
    timeout: float | None = None,
    exclude_regex: str | None = None,
    stream: bool = False,
    check: bool = True,
    okay_codes: tuple[int, ...] = (0,),
) -> CompletedCommand:
    """Run a git subcommand and return the structured result.

    Thin prefix-and-log wrapper over :func:`nclutils.sh.run_command`.
    Prepends ``git`` to ``args``, logs the invocation at DEBUG level under
    the ``nclutils.git`` logger, and passes every other parameter through
    verbatim. ``run_command`` handles cwd normalization (``Path.expanduser().resolve()``
    plus ``is_dir()`` validation), so this layer does not re-resolve.

    Args:
        *args: Git subcommand and arguments. ``run_git("status", "-s")``
            invokes ``git status -s``.
        cwd: Working directory; ``None`` inherits the process cwd.
        env: Replaces the child env (extend via ``{**os.environ, ...}``).
            Useful for ``GIT_TERMINAL_PROMPT=0``, ``LC_ALL=C``,
            ``GIT_AUTHOR_*``, ``GIT_SSH_COMMAND``.
        input: Bytes/text written to the child's stdin.
        timeout: Seconds before the child is killed; ``None`` (default)
            means no timeout. Long operations like ``clone`` and ``fetch``
            legitimately take minutes.
        exclude_regex: Drops matching lines from both capture and stream.
        stream: When ``True``, tees stdout/stderr to the parent streams
            in real time. Useful for ``fetch``, ``clone``, ``push``.
        check: When ``True`` (default), a returncode not in ``okay_codes``
            raises ``ShellCommandFailedError``.
        okay_codes: Exit codes treated as success when ``check=True``.

    Returns:
        :class:`nclutils.sh.CompletedCommand` with stdout, stderr,
        returncode, argv, duration, cwd.

    Raises:
        nclutils.sh.ShellCommandNotFoundError: ``git`` is not on PATH.
        nclutils.sh.ShellCommandFailedError: command failed under ``check=True``.
        nclutils.sh.ShellCommandTimeoutError: ``timeout`` exceeded.
    """
    argv = ["git", *args]
    logger.debug(" ".join(argv))
    return run_command(
        argv,
        cwd=cwd,
        env=env,
        input=input,
        timeout=timeout,
        exclude_regex=exclude_regex,
        stream=stream,
        check=check,
        okay_codes=okay_codes,
    )
