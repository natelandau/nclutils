"""Errors raised by nclutils.sh."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .shell_command import CompletedCommand


class ShellCommandError(Exception):
    """Base class for every error raised by nclutils.sh."""


class ShellCommandNotFoundError(ShellCommandError):
    """Raised when argv[0] cannot be located on PATH."""

    def __init__(
        self,
        *,
        argv: Sequence[str],
        msg: str | None = None,
        e: Exception | None = None,
    ) -> None:
        self.argv: tuple[str, ...] = tuple(argv)
        executable = self.argv[0] if self.argv else "<empty>"
        parts = [msg or f"Command not found on PATH: {executable}"]
        if e is not None:
            parts.append(f"Raised from: {e.__class__.__name__}: {e}")
        super().__init__("\n".join(parts))


class ShellCommandFailedError(ShellCommandError):
    """Raised when a command ran but exited outside the configured okay codes.

    Also raised when ``cwd`` cannot be entered, in which case ``result`` is None
    because no command actually ran; the underlying OSError is chained as
    ``__cause__``.

    When both ``result`` and ``msg`` are provided, ``msg`` is used verbatim as
    the exception message and ``result`` remains reachable via ``self.result``.
    When only ``result`` is provided, the message is auto-built from the result.
    """

    def __init__(
        self,
        *,
        result: CompletedCommand | None = None,
        msg: str | None = None,
    ) -> None:
        self.result = result
        if msg is not None:
            super().__init__(msg)
            return
        if result is None:
            super().__init__("Shell command failed (no result captured)")
            return

        parts = [f"Shell command failed: {result.command_line} (exit code {result.returncode})"]
        if result.stderr:
            parts.append(f"Stderr: {result.stderr}")
        if result.stdout:
            parts.append(f"Stdout: {result.stdout}")
        super().__init__("\n".join(parts))


class ShellCommandTimeoutError(ShellCommandError):
    """Raised when a command exceeded its ``timeout=`` and was killed."""

    def __init__(
        self,
        *,
        result: CompletedCommand,
        timeout: float,
    ) -> None:
        self.result = result
        self.timeout = timeout
        super().__init__(f"Shell command timed out after {timeout}s: {result.command_line}")
