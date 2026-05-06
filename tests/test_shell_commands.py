"""Tests for the rewritten nclutils.sh module."""

from __future__ import annotations

import io
import os
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from nclutils.sh import (
    CompletedCommand,
    ShellCommandError,
    ShellCommandFailedError,
    ShellCommandNotFoundError,
    ShellCommandTimeoutError,
    which,
)
from nclutils.sh._streaming import pump_pipe


class TestCompletedCommand:
    """Tests for the CompletedCommand dataclass."""

    def test_fields_and_ok_property(self) -> None:
        """Verify CompletedCommand exposes argv/returncode/stdout/stderr/duration/cwd and ok."""
        # Given: a CompletedCommand built with returncode 0
        result = CompletedCommand(
            argv=("echo", "hi"),
            returncode=0,
            stdout="hi\n",
            stderr="",
            duration=0.01,
            cwd=Path("/some/cwd"),
        )

        # Then: every field is reachable and ok is True
        assert result.argv == ("echo", "hi")
        assert result.returncode == 0
        assert result.stdout == "hi\n"
        assert result.stderr == ""
        assert result.duration == 0.01
        assert result.cwd == Path("/some/cwd")
        assert result.ok is True

    def test_ok_false_on_nonzero(self) -> None:
        """Verify ok is False when returncode is non-zero."""
        # Given: a CompletedCommand with returncode 2
        result = CompletedCommand(
            argv=("false",),
            returncode=2,
            stdout="",
            stderr="",
            duration=0.0,
            cwd=None,
        )

        # Then: ok is False
        assert result.ok is False

    def test_frozen_and_hashable(self) -> None:
        """Verify CompletedCommand is frozen and hashable."""
        # Given: a CompletedCommand
        result = CompletedCommand(
            argv=("ls",), returncode=0, stdout="", stderr="", duration=0.0, cwd=None
        )

        # When: attempting to mutate, it raises; hashing succeeds
        with pytest.raises(FrozenInstanceError):
            result.returncode = 1  # type: ignore[misc]
        assert isinstance(hash(result), int)


class TestErrorHierarchy:
    """Tests for the unified ShellCommandError hierarchy."""

    def test_all_subclasses_inherit_from_base(self) -> None:
        """Verify every concrete error inherits from ShellCommandError."""
        # Given: the three concrete error classes
        # Then: each is a subclass of the base
        assert issubclass(ShellCommandNotFoundError, ShellCommandError)
        assert issubclass(ShellCommandFailedError, ShellCommandError)
        assert issubclass(ShellCommandTimeoutError, ShellCommandError)

    def test_failed_carries_result(self) -> None:
        """Verify ShellCommandFailedError exposes the CompletedCommand it would have returned."""
        # Given: a CompletedCommand and an error built from it
        result = CompletedCommand(
            argv=("git", "push"),
            returncode=1,
            stdout="",
            stderr="rejected",
            duration=0.5,
            cwd=Path("/some/cwd"),
        )
        err = ShellCommandFailedError(result=result)

        # Then: the result is reachable via attribute and the message includes context
        assert err.result is result
        assert "git push" in str(err)
        assert "exit code 1" in str(err)
        assert "rejected" in str(err)

    def test_failed_with_no_result_for_cwd_error(self) -> None:
        """Verify ShellCommandFailedError accepts result=None when cwd was unreachable."""
        # Given: an error raised before the command ran
        err = ShellCommandFailedError(
            msg="Cannot enter directory /no/such/dir: not a directory", result=None
        )

        # Then: result is None and the message is preserved
        assert err.result is None
        assert "Cannot enter directory /no/such/dir" in str(err)

    def test_timeout_carries_partial_result(self) -> None:
        """Verify ShellCommandTimeoutError exposes partial output and the exceeded timeout."""
        # Given: partial output captured before kill and a 1.5s timeout
        partial = CompletedCommand(
            argv=("sleep", "10"),
            returncode=-9,
            stdout="started\n",
            stderr="",
            duration=1.5,
            cwd=None,
        )
        err = ShellCommandTimeoutError(result=partial, timeout=1.5)

        # Then: the partial result and the timeout value are both reachable
        assert err.result is partial
        assert err.timeout == 1.5
        assert "1.5" in str(err)

    def test_not_found_message_uses_argv(self) -> None:
        """Verify ShellCommandNotFoundError reports the missing executable name."""
        # Given: an error built for a missing binary
        err = ShellCommandNotFoundError(argv=("not-a-real-command", "--help"))

        # Then: the executable name is in the message
        assert "not-a-real-command" in str(err)


class TestWhich:
    """Tests for which()."""

    def test_returns_path_for_known_binary(self) -> None:
        """Verify which() returns an absolute Path for a binary that exists."""
        # Given: a binary that's reliably on PATH everywhere
        # When: looking up sh
        result = which("sh")

        # Then: an absolute Path is returned
        assert result is not None
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_returns_none_for_unknown_binary(self) -> None:
        """Verify which() returns None when the binary isn't on PATH."""
        # Given: a name that won't exist on any system
        # When: looking it up
        result = which("definitely-not-a-real-binary-xyz-12345")

        # Then: None
        assert result is None


class TestStreamingPump:
    """Tests for pump_pipe."""

    def test_lines_appended_to_buffer(self) -> None:
        """Verify pump_pipe decodes each line and appends it to the buffer."""
        # Given: a pipe with two lines
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"hello\nworld\n")
        os.close(write_fd)
        reader = os.fdopen(read_fd, "rb")
        buffer: list[str] = []

        # When: pumping with no sink and no exclusion
        pump_pipe(pipe=reader, buffer=buffer, sink=None, exclude_pattern=None)

        # Then: both lines are in the buffer and the pipe is closed
        assert buffer == ["hello\n", "world\n"]
        assert reader.closed

    def test_excluded_lines_are_dropped(self) -> None:
        """Verify lines matching exclude_pattern are omitted from buffer and sink."""
        # Given: a pipe with a kept line and a dropped line
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"keep me\ndrop me\n")
        os.close(write_fd)
        reader = os.fdopen(read_fd, "rb")
        pattern = re.compile(r"drop")
        buffer: list[str] = []

        # When: pumping with an exclusion pattern
        pump_pipe(pipe=reader, buffer=buffer, sink=None, exclude_pattern=pattern)

        # Then: only the kept line survives
        assert buffer == ["keep me\n"]

    def test_sink_receives_lines(self) -> None:
        """Verify pump_pipe writes each non-excluded line to the sink."""
        # Given: a pipe with two lines and an in-memory sink
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"alpha\nbeta\n")
        os.close(write_fd)
        reader = os.fdopen(read_fd, "rb")
        sink = io.StringIO()
        buffer: list[str] = []

        # When: pumping with a sink
        pump_pipe(pipe=reader, buffer=buffer, sink=sink, exclude_pattern=None)

        # Then: the sink contains both lines
        assert sink.getvalue() == "alpha\nbeta\n"

    def test_pipe_closed_on_completion(self) -> None:
        """Verify pump_pipe closes the pipe after draining it."""
        # Given: an empty pipe
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        reader = os.fdopen(read_fd, "rb")

        # When: pumping an empty pipe
        pump_pipe(pipe=reader, buffer=[], sink=None, exclude_pattern=None)

        # Then: the pipe is closed
        assert reader.closed

    def test_appends_to_existing_buffer(self) -> None:
        """Verify pump_pipe appends to an existing buffer rather than replacing it."""
        # Given: a pipe with one new line and a buffer with a pre-existing entry
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"new\n")
        os.close(write_fd)
        reader = os.fdopen(read_fd, "rb")
        buffer: list[str] = ["pre-existing\n"]

        # When: pumping
        pump_pipe(pipe=reader, buffer=buffer, sink=None, exclude_pattern=None)

        # Then: the new line is appended after the pre-existing one
        assert buffer == ["pre-existing\n", "new\n"]

    def test_invalid_utf8_raises_and_closes_pipe(self) -> None:
        """Verify pump_pipe surfaces UnicodeDecodeError and still closes the pipe."""
        # Given: a pipe with invalid utf-8 bytes
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"\xff\xfe invalid\n")
        os.close(write_fd)
        reader = os.fdopen(read_fd, "rb")

        # When/Then: pumping raises UnicodeDecodeError and the pipe is closed afterward
        with pytest.raises(UnicodeDecodeError):
            pump_pipe(pipe=reader, buffer=[], sink=None, exclude_pattern=None)
        assert reader.closed

    def test_pump_pipe_partial_final_line_without_newline(self) -> None:
        """Verify pump_pipe captures a final line that lacks a trailing newline."""
        # Given: a pipe whose final line has no newline
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"a\nno-newline-end")
        os.close(write_fd)
        reader = os.fdopen(read_fd, "rb")
        buffer: list[str] = []

        # When: pumping
        pump_pipe(pipe=reader, buffer=buffer, sink=None, exclude_pattern=None)

        # Then: the trailing line is included as-is
        assert buffer == ["a\n", "no-newline-end"]
