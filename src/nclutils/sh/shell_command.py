"""Run shell commands using stdlib subprocess."""

from __future__ import annotations

import logging
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ._streaming import pump_pipe
from .errors import (
    ShellCommandFailedError,
    ShellCommandNotFoundError,
    ShellCommandTimeoutError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

logger = logging.getLogger("nclutils.sh")


@dataclass(frozen=True, slots=True)
class CompletedCommand:
    """The full record of a finished subprocess invocation.

    Returned from :func:`run_command` on success and exposed as ``.result`` on
    :class:`ShellCommandFailedError` / :class:`ShellCommandTimeoutError`.
    Trailing newlines on ``stdout`` and ``stderr`` are stripped; embedded
    newlines between lines are preserved.
    """

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float
    cwd: Path | None

    @property
    def ok(self) -> bool:
        """Return True when the command exited with status 0."""
        return self.returncode == 0

    @property
    def command_line(self) -> str:
        """Return ``argv`` rendered with :func:`shlex.join` so it can be pasted into a shell."""
        return shlex.join(self.argv)

    @property
    def stdout_lines(self) -> list[str]:
        """Return ``stdout`` split into lines. Recomputed on each access; bind locally to iterate twice."""
        return self.stdout.splitlines()

    @property
    def stderr_lines(self) -> list[str]:
        """Return ``stderr`` split into lines. Recomputed on each access; bind locally to iterate twice."""
        return self.stderr.splitlines()


def which(cmd: str) -> Path | None:
    """Return the absolute Path to ``cmd`` on PATH, or None if it is missing.

    Use this to gate optional features without raising. Wraps
    :func:`shutil.which`; returns the same answer the shell would pick.

    Args:
        cmd: The executable name to look up.

    Returns:
        The resolved absolute Path, or None if ``cmd`` is not on PATH.
    """
    found = shutil.which(cmd)
    return Path(found) if found is not None else None


def _resolve_cwd(cwd: Path | str | None) -> Path | None:
    """Resolve ``cwd`` to an absolute Path or return None for the inherited cwd.

    Raises ShellCommandFailedError(result=None) if the directory cannot be entered.
    """
    if cwd is None:
        return None
    resolved = Path(cwd).expanduser().resolve()
    if not resolved.is_dir():
        raise ShellCommandFailedError(
            msg=f"Cannot enter directory {resolved}: not a directory",
            result=None,
        )
    return resolved


def run_command(  # noqa: C901, PLR0912, PLR0913, PLR0915
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    input: str | bytes | None = None,  # noqa: A002 -- mirrors subprocess.run
    timeout: float | None = None,
    exclude_regex: str | None = None,
    stream: bool = False,
    check: bool = True,
    okay_codes: tuple[int, ...] = (0,),
    sudo: bool = False,
) -> CompletedCommand:
    """Run a shell command and return a structured CompletedCommand.

    Use this for non-interactive commands. For commands that need a real terminal
    (vim, less, ssh), use :func:`run_interactive` instead (added in a later task).

    Args:
        argv: Full command including executable. Passed verbatim to subprocess.
        cwd: Working directory; None inherits the parent's cwd.
        env: If provided, replaces the child env. Caller extends via ``{**os.environ, ...}``.
        input: Text or bytes written to the child's stdin and then closed.
            For large inputs (>64KB) where the child also produces output,
            deadlock is possible because stdout drainage starts after stdin
            is fully written; pipe via shell redirection in that case.
        timeout: Seconds before the child is terminated and TimeoutError raised.
        exclude_regex: Lines matching this regex are dropped from both the streamed
            output and the captured strings.
        stream: When True, also tees stdout/stderr to sys.stdout/sys.stderr live.
        check: When True (default), a returncode not in ``okay_codes`` raises FailedError.
        okay_codes: Returncodes treated as success when ``check=True``.
        sudo: When True, prepends ``["sudo"]`` to argv.

    Returns:
        See :class:`CompletedCommand` for the returned shape.
    """
    final_argv: list[str] = list(argv)
    if sudo:
        final_argv = ["sudo", *final_argv]
    final_argv_tuple = tuple(final_argv)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("%s", shlex.join(final_argv))

    resolved_cwd = _resolve_cwd(cwd)
    exclude_pattern = re.compile(exclude_regex) if exclude_regex else None

    # input: bytes go through unchanged; str is encoded utf-8.
    input_bytes: bytes | None
    if input is None:
        input_bytes = None
    elif isinstance(input, bytes):
        input_bytes = input
    else:
        input_bytes = input.encode("utf-8")

    stdin = subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL

    started = time.monotonic()
    try:
        proc = subprocess.Popen(  # noqa: S603 -- argv is a list, never shelled
            final_argv,
            cwd=resolved_cwd,
            env=dict(env) if env is not None else None,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ShellCommandNotFoundError(argv=final_argv_tuple, e=e) from e
    except OSError as e:
        raise ShellCommandFailedError(
            msg=f"Failed to spawn {final_argv[0]}: {e}",
            result=None,
        ) from e

    if input_bytes is not None and proc.stdin is not None:
        try:
            proc.stdin.write(input_bytes)
        except BrokenPipeError:
            # Child exited before consuming stdin. Let the normal returncode path
            # surface the failure via ShellCommandFailedError (or check=False).
            pass
        finally:
            proc.stdin.close()

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    sout_sink = sys.stdout if stream else None
    serr_sink = sys.stderr if stream else None

    # proc.stdout and proc.stderr are always set when PIPE is passed to Popen.
    # Capture into locals so type checkers can narrow them inside the drain closures.
    out_pipe = proc.stdout
    err_pipe = proc.stderr
    if out_pipe is None or err_pipe is None:  # pragma: no cover
        _msg = "Popen did not open stdout/stderr pipes as expected"
        raise RuntimeError(_msg)

    out_exc: list[BaseException | None] = [None]
    err_exc: list[BaseException | None] = [None]

    def _drain_stdout() -> None:
        try:
            pump_pipe(
                pipe=out_pipe,
                buffer=stdout_lines,
                sink=sout_sink,
                exclude_pattern=exclude_pattern,
            )
        except BaseException as e:  # noqa: BLE001 -- capture and re-raise from caller
            out_exc[0] = e

    def _drain_stderr() -> None:
        try:
            pump_pipe(
                pipe=err_pipe,
                buffer=stderr_lines,
                sink=serr_sink,
                exclude_pattern=exclude_pattern,
            )
        except BaseException as e:  # noqa: BLE001 -- capture and re-raise from caller
            err_exc[0] = e

    t_out = threading.Thread(target=_drain_stdout)
    t_err = threading.Thread(target=_drain_stderr)
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    finally:
        t_out.join()
        t_err.join()

    # Surface any pump-thread exception (e.g., UnicodeDecodeError) before evaluating
    # the timeout/check branches so a decode error isn't masked by a normal exit.
    if out_exc[0] is not None:
        raise out_exc[0]
    if err_exc[0] is not None:
        raise err_exc[0]

    duration = time.monotonic() - started
    result = CompletedCommand(
        argv=final_argv_tuple,
        returncode=proc.returncode,
        stdout="".join(stdout_lines).rstrip("\n"),
        stderr="".join(stderr_lines).rstrip("\n"),
        duration=duration,
        cwd=resolved_cwd,
    )

    if timed_out:
        # timeout is non-None when timed_out is True (TimeoutExpired only fires with timeout)
        raise ShellCommandTimeoutError(result=result, timeout=timeout)  # ty:ignore[invalid-argument-type]
    if check and proc.returncode not in okay_codes:
        raise ShellCommandFailedError(result=result)

    return result


def run_interactive(
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    sudo: bool = False,
    check: bool = True,
) -> int:
    """Run a command that needs a real terminal (vim, less, ssh).

    Inherits the parent's stdin/stdout/stderr - no capture, no pipes, no
    streaming layer. Use :func:`run_command` for non-interactive commands
    where you want the captured output.

    Args:
        argv: Full command including executable.
        cwd: Working directory; None inherits parent.
        env: If provided, replaces the child env.
        sudo: When True, prepends ``["sudo"]`` to argv.
        check: When True (default), a non-zero exit raises FailedError.

    Returns:
        The child's exit code.
    """
    final_argv: list[str] = list(argv)
    if sudo:
        final_argv = ["sudo", *final_argv]
    final_argv_tuple = tuple(final_argv)

    resolved_cwd = _resolve_cwd(cwd)

    started = time.monotonic()
    try:
        proc = subprocess.Popen(  # noqa: S603 -- argv is a list, never shelled
            final_argv,
            cwd=resolved_cwd,
            env=dict(env) if env is not None else None,
        )
    except FileNotFoundError as e:
        raise ShellCommandNotFoundError(argv=final_argv_tuple, e=e) from e
    except OSError as e:
        raise ShellCommandFailedError(
            msg=f"Failed to spawn {final_argv[0]}: {e}",
            result=None,
        ) from e

    rc = proc.wait()
    duration = time.monotonic() - started

    if check and rc != 0:
        result = CompletedCommand(
            argv=final_argv_tuple,
            returncode=rc,
            stdout="",
            stderr="",
            duration=duration,
            cwd=resolved_cwd,
        )
        raise ShellCommandFailedError(result=result)

    return rc
