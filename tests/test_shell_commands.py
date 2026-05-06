"""Test shell command execution functionality."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from nclutils.sh import (
    ShellCommandFailedError,
    ShellCommandNotFoundError,
    run_command,
    which,
)


def test_run_command_successful_execution(capsys: pytest.CaptureFixture) -> None:
    """Execute a command successfully and verify output."""
    # Given: A simple echo command
    cmd = "echo"
    args = ["Hello World"]

    # When: Running the command
    output = run_command(cmd, args)

    # Then: Command executes successfully
    assert "Hello World" in str(output)

    # Verify console output when not quiet
    captured = capsys.readouterr()
    assert "Hello World" in str(captured.out)


def test_run_command_quiet_mode(capsys: pytest.CaptureFixture) -> None:
    """Execute a command in quiet mode and verify no console output."""
    # Given: A simple echo command
    cmd = "echo"
    args = ["Hello World"]

    # When: Running the command in quiet mode
    output = run_command(cmd, args, quiet=True)

    # Then: Command executes successfully but produces no console output
    assert "Hello World" in str(output)
    captured = capsys.readouterr()
    assert not captured.out


def test_run_command_fg_is_true(capsys: pytest.CaptureFixture) -> None:
    """Execute a command in foreground mode."""
    # Given: A simple echo command
    cmd = "echo"
    args = ["Hello World"]

    # When: Running the command in foreground mode
    output = run_command(cmd, args, quiet=True, fg=True)
    captured = capsys.readouterr().err

    # Then: Command executes successfully but produces no console output
    assert not output  # No output expected in foreground mode
    assert not captured  # A new tty is spawned for the command, so no output is captured


def test_run_command_not_found(capsys: pytest.CaptureFixture) -> None:
    """Handle non-existent command gracefully."""
    # Given: A non-existent command
    cmd = "nonexistentcommand"
    args = []

    # When: Attempting to run the command in quiet mode
    with pytest.raises(ShellCommandNotFoundError, match="Shell command not found"):
        run_command(cmd, args)

    # Then: Command fails with appropriate error
    captured = capsys.readouterr()
    assert not captured.out


def test_run_command_not_found_quiet_mode(capsys: pytest.CaptureFixture) -> None:
    """Handle non-existent command gracefully in quiet mode."""
    # Given: A non-existent command
    cmd = "nonexistentcommand"
    args = []

    # When: Attempting to run the command in quiet mode
    with pytest.raises(ShellCommandNotFoundError, match="Shell command not found"):
        run_command(cmd, args, quiet=True)

    # Then: Command fails with appropriate error
    captured = capsys.readouterr()
    assert not captured.out


def test_run_command_with_error(capsys: pytest.CaptureFixture) -> None:
    """Handle command execution errors appropriately."""
    # Given: A command that will fail (ls with invalid path)
    cmd = "ls"
    args = ["/some/nonexistent/path"]

    # When: Running the command
    with pytest.raises(ShellCommandFailedError) as excinfo:
        run_command(cmd, args, err_to_out=False)

    # debug(excinfo.value.__dict__)

    # Then: Command fails with non-zero return code and error message
    assert excinfo.value.exit_code == 2
    assert "ls /some/nonexistent/path" in excinfo.value.full_cmd
    assert "No such file or directory" in excinfo.value.stderr
    assert not excinfo.value.stdout
    stderrout = capsys.readouterr().err
    # debug(stderrout)
    assert not stderrout


def test_run_command_with_error_print_stderr(capsys: pytest.CaptureFixture) -> None:
    """Handle command execution errors appropriately."""
    # Given: A command that will fail (ls with invalid path)
    cmd = "ls"
    args = ["/some/nonexistent/path"]

    # When: Running the command
    with pytest.raises(ShellCommandFailedError) as excinfo:
        run_command(cmd, args, err_to_out=True)

    # debug(excinfo.value.__dict__)

    # Then: Command fails with non-zero return code and error message
    assert excinfo.value.exit_code == 2
    assert "ls /some/nonexistent/path" in excinfo.value.full_cmd
    assert "No such file or directory" in excinfo.value.stderr
    assert not excinfo.value.stdout
    stdout = capsys.readouterr().out

    assert "ls: cannot access '/some/nonexistent/path': No such file or directory" in stdout


def test_run_command_with_error_quiet_mode(capsys: pytest.CaptureFixture) -> None:
    """Handle command execution errors appropriately in quiet mode."""
    # Given: A command that will fail (ls with invalid path)
    cmd = "ls"
    args = ["/some/nonexistent/path"]

    # When: Running the command
    with pytest.raises(ShellCommandFailedError) as excinfo:
        run_command(cmd, args, quiet=True)

    # Then: Command fails with non-zero return code and error message
    assert excinfo.value.exit_code == 2
    assert "ls /some/nonexistent/path" in excinfo.value.full_cmd
    assert "No such file or directory" in excinfo.value.stderr
    assert not excinfo.value.stdout
    captured = capsys.readouterr()
    assert not captured.out


def test_which_success() -> None:
    """Test the which function with a successful command."""
    # Given: A command that exists in the PATH
    cmd = "ls"
    # When: Running the command
    result = which(cmd)
    # Then: The command exists in the PATH
    assert result is not None
    assert isinstance(result, str)
    assert result.strip()
    assert Path(result).exists()


def test_which_failure() -> None:
    """Test the which function with a command that does not exist in the PATH."""
    # Given: A command that does not exist in the PATH
    cmd = "nonexistentcommand"

    # When: Running the command
    result = which(cmd)

    # Then: The command does not exist in the PATH
    assert result is None


def test_run_command_with_pushd(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Execute a command in a different directory using pushd."""
    # Given: A temporary directory and pwd command
    cmd = "pwd"
    original_dir = Path.cwd()

    # When: Running the command with pushd
    output = run_command(cmd, [], pushd=str(tmp_path))

    # Then: Command executes in the specified directory
    assert str(tmp_path) in str(output).replace("\r", "").replace("\n", "")
    assert Path.cwd() == original_dir
    captured = capsys.readouterr()
    assert str(tmp_path) in captured.out.replace("\r", "").replace("\n", "")


def test_run_command_with_pushd_quiet_mode(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Execute a command with pushd in quiet mode."""
    cmd = "pwd"
    original_dir = Path.cwd()

    # When: Running the command with pushd
    output = run_command(cmd, [], pushd=tmp_path, quiet=True)

    # Then: Command executes in the specified directory
    assert str(tmp_path) in str(output).replace("\r", "").replace("\n", "")
    assert Path.cwd() == original_dir
    captured = capsys.readouterr()
    assert not captured.out


def test_run_command_with_pushd_nonexistent_dir(capsys: pytest.CaptureFixture) -> None:
    """Handle pushd to nonexistent directory gracefully."""
    # Given: A nonexistent directory
    nonexistent_dir = Path("/some/nonexistent/directory")
    cmd = "pwd"

    # When/Then: Running command with invalid pushd raises error
    with pytest.raises(ShellCommandFailedError, match=r"Cannot enter directory"):
        run_command(cmd, [], pushd=nonexistent_dir)

    captured = capsys.readouterr()
    assert not captured.out


def test_exclude_lines(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Test the exclude_lines parameter."""
    # Given: A temporary file
    tmpfile = tmp_path / "tmpfile.txt"
    tmpfile.write_text("hello world\nworking... 0%\nworking... 10%\ndone")

    # When: Running the command
    output = run_command("cat", [str(tmpfile)], exclude_regex=r"\d+%$")

    captured = capsys.readouterr().out

    # Then: The command executes successfully
    assert "hello world" in str(captured)
    assert "working... 0%" not in str(captured)
    assert "working... 10%" not in str(captured)
    assert "done" in str(captured)
    assert "hello world" in str(output)
    assert "working... 0%" not in str(output)
    assert "working... 10%" not in str(output)
    assert "done" in str(output)


@pytest.mark.parametrize(
    ("codes", "should_raise"),
    [
        ((0, 1), False),
        ((0,), True),
    ],
)
def test_run_command_okay_codes_whitelist(codes: tuple[int, ...], *, should_raise: bool) -> None:
    """Verify okay_codes whitelists non-zero exit codes."""
    # Given: A grep that exits 1 because no line matches
    cmd = "grep"
    args = ["pattern_that_will_not_match", "/dev/null"]

    # When/Then: The exit code raises only when not in okay_codes
    if should_raise:
        with pytest.raises(ShellCommandFailedError) as excinfo:
            run_command(cmd, args, okay_codes=codes, quiet=True)
        assert excinfo.value.exit_code == 1
    else:
        result = run_command(cmd, args, okay_codes=codes, quiet=True)
        assert result == ""


def test_run_command_fg_passes_fg_kwarg_to_sh(mocker: MockerFixture) -> None:
    """Verify fg=True forwards _fg=True to sh.Command and skips capture kwargs."""
    # Given: sh.Command is mocked so the underlying invocation is intercepted
    mock_cmd_class = mocker.patch("nclutils.sh.shell_command.sh.Command")

    # When: Running with fg=True
    run_command("echo", ["test"], fg=True)

    # Then: The command was called with _fg=True and without capture callbacks
    mock_cmd_class.assert_called_once_with("echo")
    cmd_instance = mock_cmd_class.return_value
    cmd_instance.assert_called_once()
    call_kwargs = cmd_instance.call_args.kwargs
    assert call_kwargs.get("_fg") is True
    assert "_out" not in call_kwargs
    assert "_err" not in call_kwargs
    assert "_tee" not in call_kwargs


@pytest.fixture
def stub_sh(mocker: MockerFixture):
    """Stub sh.contrib (a property — can't patch sh.contrib.sudo directly) and sh.Command."""
    fake_contrib = mocker.MagicMock()
    mocker.patch("nclutils.sh.shell_command.sh.contrib", new=fake_contrib)
    mocker.patch("nclutils.sh.shell_command.sh.Command")
    return fake_contrib


def test_run_command_with_sudo_enters_sudo_context(stub_sh) -> None:
    """Verify sudo=True wraps execution in sh.contrib.sudo(_with=True)."""
    # When: Running with sudo=True
    run_command("echo", ["hello"], sudo=True, quiet=True)

    # Then: sudo was invoked with _with=True and entered as a context manager.
    # The absence of k=True is enforced by assert_called_once_with's exact-match.
    stub_sh.sudo.assert_called_once_with(_with=True)
    stub_sh.sudo.return_value.__enter__.assert_called_once()


def test_run_command_without_sudo_does_not_enter_sudo_context(stub_sh) -> None:
    """Verify sudo=False leaves sh.contrib.sudo untouched."""
    # When: Running without sudo
    run_command("echo", ["hello"], quiet=True)

    # Then: sudo was never invoked
    stub_sh.sudo.assert_not_called()


def test_run_command_err_to_out_false_drops_successful_stderr(
    capsys: pytest.CaptureFixture,
) -> None:
    """Verify err_to_out=False suppresses stderr from a successful command."""
    # Given: A successful command emitting both stdout and stderr
    cmd = "sh"
    args = ["-c", "echo OUTLINE; echo ERRLINE >&2"]

    # When: Running with err_to_out=False
    output = run_command(cmd, args, err_to_out=False)

    # Then: stderr is absent from both the captured return value and the streamed console
    assert "OUTLINE" in output
    assert "ERRLINE" not in output
    captured = capsys.readouterr()
    assert "OUTLINE" in captured.out
    assert "ERRLINE" not in captured.out
