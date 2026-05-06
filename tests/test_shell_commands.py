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
    run_command,
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


class TestRunCommandCapture:
    """Tests for run_command without stream=True (capture only)."""

    def test_returns_completed_command_on_success(self) -> None:
        """Verify run_command returns a CompletedCommand with stdout, returncode, and argv."""
        # Given/When: a successful echo
        result = run_command(["echo", "hello"])

        # Then: a CompletedCommand with hello on stdout and exit 0
        assert isinstance(result, CompletedCommand)
        assert result.returncode == 0
        assert result.argv == ("echo", "hello")
        assert "hello" in result.stdout
        assert result.stderr == ""
        assert result.duration >= 0
        assert result.ok is True

    def test_check_true_raises_failed_on_nonzero(self) -> None:
        """Verify check=True raises ShellCommandFailedError carrying the result."""
        # Given/When: a command that exits 1
        # Then: ShellCommandFailedError is raised and exposes the result
        with pytest.raises(ShellCommandFailedError) as exc:
            run_command(["false"])
        assert exc.value.result is not None
        assert exc.value.result.returncode == 1
        assert exc.value.result.argv == ("false",)

    def test_check_false_returns_nonzero_result(self) -> None:
        """Verify check=False suppresses raising and returns the failed result."""
        # Given/When: a failing command with check=False
        result = run_command(["false"], check=False)

        # Then: result is returned, returncode is non-zero
        assert result.returncode != 0
        assert result.ok is False

    def test_okay_codes_treats_listed_codes_as_success(self) -> None:
        """Verify a returncode in okay_codes does not raise."""
        # Given/When: false (rc=1) with 0 and 1 both okay
        result = run_command(["false"], okay_codes=(0, 1))

        # Then: returns normally
        assert result.returncode == 1

    def test_command_not_found_raises(self) -> None:
        """Verify a missing executable raises ShellCommandNotFoundError."""
        # Given/When/Then: a non-existent binary raises NotFound
        with pytest.raises(ShellCommandNotFoundError):
            run_command(["definitely-not-a-real-binary-xyz-12345"])

    def test_cwd_changes_directory(self, tmp_path: Path) -> None:
        """Verify cwd= runs the command from the given directory."""
        # Given: a subdir containing one file
        (tmp_path / "marker.txt").write_text("hi")

        # When: running ls under cwd=tmp_path
        result = run_command(["ls"], cwd=tmp_path)

        # Then: marker.txt appears in stdout
        assert "marker.txt" in result.stdout
        assert result.cwd == tmp_path.resolve()

    def test_cwd_unreachable_raises_failed(self) -> None:
        """Verify a missing cwd raises ShellCommandFailedError with result=None."""
        # Given/When/Then: a non-existent dir raises Failed with no result
        with pytest.raises(ShellCommandFailedError) as exc:
            run_command(["echo", "hi"], cwd="/no/such/dir/xyz")
        assert exc.value.result is None
        assert "/no/such/dir/xyz" in str(exc.value)

    def test_env_replaces_environment(self) -> None:
        """Verify env= replaces (does not extend) the child environment."""
        # Given/When: a fully replaced env containing only FOO=bar
        result = run_command(
            ["sh", "-c", "echo $FOO"],
            env={"FOO": "bar", "PATH": "/usr/bin:/bin"},
        )

        # Then: FOO is bar
        assert result.stdout.strip() == "bar"

    def test_input_str_is_written_to_stdin(self) -> None:
        """Verify input= writes a string to the child's stdin and is read back via cat."""
        # Given/When: cat reads stdin
        result = run_command(["cat"], input="ping pong")

        # Then: the same text comes back on stdout
        assert result.stdout == "ping pong"

    def test_input_bytes_is_passed_through(self) -> None:
        """Verify input= accepts bytes and forwards them verbatim."""
        # Given/When: bytes input
        result = run_command(["cat"], input=b"raw bytes\n")

        # Then: stdout matches the bytes decoded as utf-8
        assert result.stdout == "raw bytes\n"

    def test_timeout_raises_timeout_error_with_partial_result(self) -> None:
        """Verify timeout= terminates the child and raises ShellCommandTimeoutError."""
        # Given/When/Then: a long sleep with a 0.2s timeout
        with pytest.raises(ShellCommandTimeoutError) as exc:
            run_command(["sleep", "5"], timeout=0.2)
        assert exc.value.timeout == 0.2
        assert exc.value.result.argv == ("sleep", "5")

    def test_sudo_prepends_sudo(self, mocker) -> None:
        """Verify sudo=True prepends 'sudo' to argv before invocation."""
        # Given: a Popen mock that records argv
        from nclutils.sh import shell_command as sc  # noqa: PLC0415

        recorded: dict = {}

        class FakeProc:
            def __init__(self, argv: list[str], **kwargs: object) -> None:
                recorded["argv"] = argv
                self.stdout = mocker.MagicMock()
                self.stdout.readline.side_effect = [b""]
                self.stderr = mocker.MagicMock()
                self.stderr.readline.side_effect = [b""]
                self.stdin = None
                self.returncode = 0

            def wait(self, timeout: float | None = None) -> int:
                return 0

            def kill(self) -> None:
                pass

        mocker.patch.object(sc.subprocess, "Popen", autospec=True, side_effect=FakeProc)

        # When: running with sudo=True
        run_command(["whoami"], sudo=True)

        # Then: argv was prefixed
        assert recorded["argv"][:2] == ["sudo", "whoami"]

    def test_quiet_by_default_does_not_print(self, capsys: pytest.CaptureFixture) -> None:
        """Verify the default (stream=False) writes nothing to sys.stdout/sys.stderr."""
        # Given/When: a successful echo with default stream=False
        run_command(["echo", "hello"])

        # Then: nothing leaked to capsys
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_invalid_utf8_in_child_output_raises(self) -> None:
        """Verify non-utf8 child output surfaces UnicodeDecodeError to the caller."""
        # Given/When/Then: a printf that emits invalid utf-8 bytes
        with pytest.raises(UnicodeDecodeError):
            run_command(["printf", r"\xff\xfe"])

    def test_concurrent_stdout_and_stderr_both_captured(self) -> None:
        """Verify both stdout and stderr are captured when child writes to both."""
        # Given/When: a shell command writing to both streams
        result = run_command(["sh", "-c", "echo out; echo err >&2"])

        # Then: both streams captured into the result's separate fields
        assert "out" in result.stdout
        assert "err" in result.stderr

    def test_cwd_accepts_str_and_path(self, tmp_path: Path) -> None:
        """Verify cwd accepts both str and Path."""
        # Given: a tmp directory
        # When: invoked once with str cwd, once with Path cwd
        for cwd in (tmp_path, str(tmp_path)):
            result = run_command(["pwd"], cwd=cwd)

            # Then: both produce the same resolved cwd
            assert result.cwd == tmp_path.resolve()


class TestRunCommandStreaming:
    """Tests for stream=True and exclude_regex."""

    def test_stream_true_writes_stdout_live(self, capsys: pytest.CaptureFixture) -> None:
        """Verify stream=True tees stdout to sys.stdout while still capturing it."""
        # Given/When: a streamed echo
        result = run_command(["echo", "streamed"], stream=True)
        captured = capsys.readouterr()

        # Then: live output and captured output both contain the line
        assert "streamed" in captured.out
        assert "streamed" in result.stdout

    def test_stream_true_writes_stderr_live(self, capsys: pytest.CaptureFixture) -> None:
        """Verify stream=True tees stderr to sys.stderr."""
        # Given/When: a command that writes to stderr
        result = run_command(["sh", "-c", "echo errline 1>&2"], stream=True)
        captured = capsys.readouterr()

        # Then: live stderr saw the line, captured stderr too
        assert "errline" in captured.err
        assert "errline" in result.stderr

    def test_exclude_regex_drops_from_capture_and_stream(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exclude_regex removes matching lines from both stream and capture."""
        # Given/When: noisy output with a regex matching the noise
        result = run_command(
            ["sh", "-c", "echo keep; echo drop me; echo also keep"],
            stream=True,
            exclude_regex=r"^drop",
        )
        captured = capsys.readouterr()

        # Then: noise gone from both
        assert "drop me" not in captured.out
        assert "drop me" not in result.stdout
        assert "keep" in result.stdout
        assert "also keep" in result.stdout

    def test_exclude_regex_applies_when_stream_false(self) -> None:
        """Verify exclude_regex still filters captured output when stream=False."""
        # Given/When: filter without streaming
        result = run_command(
            ["sh", "-c", "echo a; echo b; echo c"],
            exclude_regex=r"^b$",
        )

        # Then: b is gone from capture
        assert "a\n" in result.stdout
        assert "b" not in result.stdout
        assert "c\n" in result.stdout


class TestRunInteractive:
    """Tests for run_interactive."""

    def test_returns_exit_code_on_success(self, mocker) -> None:
        """Verify run_interactive returns the child's exit code without capture."""
        # Given: a Popen mock that exits 0
        from nclutils.sh import run_interactive  # noqa: PLC0415
        from nclutils.sh import shell_command as sc  # noqa: PLC0415

        fake = mocker.MagicMock()
        fake.wait.return_value = 0
        fake.returncode = 0
        mocker.patch.object(sc.subprocess, "Popen", autospec=True, return_value=fake)

        # When: invoking
        rc = run_interactive(["true"])

        # Then: the returncode is returned
        assert rc == 0

    def test_inherits_parent_stdio(self, mocker) -> None:
        """Verify run_interactive does not pass stdin/stdout/stderr=PIPE."""
        # Given: a Popen mock
        from nclutils.sh import run_interactive  # noqa: PLC0415
        from nclutils.sh import shell_command as sc  # noqa: PLC0415

        fake = mocker.MagicMock()
        fake.wait.return_value = 0
        fake.returncode = 0
        popen = mocker.patch.object(sc.subprocess, "Popen", autospec=True, return_value=fake)

        # When: invoking
        run_interactive(["vim"])

        # Then: Popen was called without stdout=PIPE / stderr=PIPE
        kwargs = popen.call_args.kwargs
        assert "stdout" not in kwargs or kwargs["stdout"] is None
        assert "stderr" not in kwargs or kwargs["stderr"] is None

    def test_check_true_raises_failed_on_nonzero(self, mocker) -> None:
        """Verify check=True raises ShellCommandFailedError for non-zero exits."""
        # Given: a Popen mock that exits 1
        from nclutils.sh import run_interactive  # noqa: PLC0415
        from nclutils.sh import shell_command as sc  # noqa: PLC0415

        fake = mocker.MagicMock()
        fake.wait.return_value = 1
        fake.returncode = 1
        mocker.patch.object(sc.subprocess, "Popen", autospec=True, return_value=fake)

        # When/Then: check=True (default) raises
        with pytest.raises(ShellCommandFailedError) as exc:
            run_interactive(["false"])
        assert exc.value.result is not None
        assert exc.value.result.returncode == 1

    def test_check_false_returns_nonzero(self, mocker) -> None:
        """Verify check=False returns the exit code without raising."""
        # Given: a Popen mock that exits 1
        from nclutils.sh import run_interactive  # noqa: PLC0415
        from nclutils.sh import shell_command as sc  # noqa: PLC0415

        fake = mocker.MagicMock()
        fake.wait.return_value = 1
        fake.returncode = 1
        mocker.patch.object(sc.subprocess, "Popen", autospec=True, return_value=fake)

        # When: check=False
        rc = run_interactive(["false"], check=False)

        # Then: returns 1
        assert rc == 1

    def test_sudo_prepends(self, mocker) -> None:
        """Verify sudo=True prepends sudo to argv."""
        # Given: a Popen mock recording argv
        from nclutils.sh import run_interactive  # noqa: PLC0415
        from nclutils.sh import shell_command as sc  # noqa: PLC0415

        fake = mocker.MagicMock()
        fake.wait.return_value = 0
        fake.returncode = 0
        popen = mocker.patch.object(sc.subprocess, "Popen", autospec=True, return_value=fake)

        # When: running with sudo=True
        run_interactive(["whoami"], sudo=True)

        # Then: argv prefixed
        assert popen.call_args.args[0][:2] == ["sudo", "whoami"]
