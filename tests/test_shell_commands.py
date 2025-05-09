"""Test shell command execution functionality."""

from pathlib import Path

import pytest

from nclutils import (
    ShellCommandFailedError,
    ShellCommandNotFoundError,
    run_command,
    which,
)


def test_run_command_successful_execution(capsys) -> None:
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


def test_run_command_quiet_mode(capsys) -> None:
    """Execute a command in quiet mode and verify no console output."""
    # Given: A simple echo command with quiet mode
    cmd = "echo"
    args = ["Hello World"]

    # When: Running the command in quiet mode
    output = run_command(cmd, args, quiet=True)

    # Then: Command executes successfully but produces no console output
    assert "Hello World" in str(output)
    captured = capsys.readouterr()
    assert not captured.out


def test_run_command_not_found(capsys) -> None:
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


def test_run_command_not_found_quiet_mode(debug, capsys) -> None:
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


def test_run_command_with_error(capsys, debug) -> None:
    """Handle command execution errors appropriately."""
    # Given: A command that will fail (ls with invalid path)
    cmd = "ls"
    args = ["/some/nonexistent/path"]

    # When: Running the command
    with pytest.raises(ShellCommandFailedError) as excinfo:
        run_command(cmd, args)

    # debug(excinfo.value.__dict__)

    # Then: Command fails with non-zero return code and error message
    assert excinfo.value.exit_code == 2
    assert "ls /some/nonexistent/path" in excinfo.value.full_cmd
    assert "No such file or directory" in excinfo.value.stderr
    assert not excinfo.value.stdout
    captured = capsys.readouterr()
    assert not captured.out


def test_run_command_with_error_quiet_mode(capsys) -> None:
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


def test_which_success(debug) -> None:
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


def test_which_failure(debug) -> None:
    """Test the which function with a command that does not exist in the PATH."""
    # Given: A command that does not exist in the PATH
    cmd = "nonexistentcommand"

    # When: Running the command
    result = which(cmd)

    # Then: The command does not exist in the PATH
    assert result is None


def test_run_command_with_pushd(tmp_path: Path, capsys) -> None:
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


def test_run_command_with_pushd_quiet_mode(tmp_path: Path, capsys) -> None:
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


def test_run_command_with_pushd_nonexistent_dir(capsys) -> None:
    """Handle pushd to nonexistent directory gracefully."""
    # Given: A nonexistent directory
    nonexistent_dir = Path("/some/nonexistent/directory")
    cmd = "pwd"

    # When/Then: Running command with invalid pushd raises error
    with pytest.raises(ShellCommandFailedError, match=r"Directory.*does not exist"):
        run_command(cmd, [], pushd=nonexistent_dir)

    captured = capsys.readouterr()
    assert not captured.out


def test_exclude_lines(tmp_path: Path, capsys) -> None:
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
