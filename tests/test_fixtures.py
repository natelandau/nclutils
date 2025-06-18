"""Test the pytest fixtures."""

import sys


def test_debug_string(debug, clean_stdout) -> None:
    """Verify that the debug fixture works with a simple string."""
    # Given a simple string
    test_string = "Hello, world!"
    test_label = "Test"

    # When debugging the string
    debug(test_string, test_label)
    output = clean_stdout()

    # Then the output contains the string and label
    assert "Hello, world!" in output
    assert "─ Test ─" in output


def test_debug_string_strip_tmp_path(debug, clean_stdout, tmp_path) -> None:
    """Verify that the debug fixture works with a simple string."""
    # Given a simple string
    test_string = f"Hello, {tmp_path}world!"

    # When debugging the string
    debug(test_string, strip_tmp_path=True)
    output = clean_stdout()

    # Then the output contains the string and label
    assert "Hello, …world!" in output


def test_debug_path(debug, clean_stdout, tmp_path) -> None:
    """Verify that the debug fixture works with a Path."""
    # Given a test file
    testfile = tmp_path / "test.txt"
    testfile.touch()

    # When debugging the file path
    debug(tmp_path, "Test", width=200, strip_tmp_path=False)
    output = clean_stdout(strip_tmp_path=False)

    # Then the output contains the file path and label
    assert str(testfile) in output
    assert "─ Test ─" in output


def test_debug_path_strip_tmp_path(debug, clean_stdout, tmp_path) -> None:
    """Verify that the debug fixture works with a Path."""
    # Given a test directory with a file
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir(parents=True, exist_ok=True)
    testfile = test_dir / "test.txt"
    testfile.touch()

    # When debugging with strip_tmp_path enabled
    debug(tmp_path, width=200, strip_tmp_path=True)
    output = clean_stdout()

    # Then the output excludes tmp_path but includes relative path
    assert str(tmp_path) not in output
    assert f"…/{testfile.relative_to(tmp_path)!s}" in output


def test_clean_stderr(debug, clean_stderr) -> None:
    """Verify that the clean_stderr fixture works."""
    # Given a test string
    test_string = "Hello, world!"
    sys.stderr.write(test_string)

    # When cleaning the stderr
    output = clean_stderr()

    # Then the output contains the string
    assert test_string in output


def test_clean_stderr_with_tmp_path(debug, clean_stderr, tmp_path) -> None:
    """Verify that the clean_stderr fixture works."""
    # Given a test string
    test_string = f"Hello, {tmp_path}world!"
    sys.stderr.write(test_string)

    # When cleaning the stderr
    output = clean_stderr(strip_tmp_path=False)

    # Then the output contains the string
    assert test_string in output


def test_clean_stderr_without_tmp_path(debug, clean_stderr, tmp_path) -> None:
    """Verify that the clean_stderr fixture works."""
    # Given a test string
    test_string = f"Hello, {tmp_path}world!"
    sys.stderr.write(test_string)

    # When cleaning the stderr
    output = clean_stderr(strip_tmp_path=True)

    # Then the output contains the string
    assert "Hello, …world!" in output


def test_clean_stderrout(debug, clean_stderrout) -> None:
    """Verify that the clean_stderr fixture works."""
    sys.stdout.write("this is stdout\n")
    sys.stderr.write("this is stderr\n")

    # When cleaning the stderr
    output = clean_stderrout(strip_tmp_path=False)

    # Then the output contains the string
    assert "this is stderr" in output
    assert "this is stdout" in output


def test_clean_stderrout_without_tmp_path(debug, clean_stderrout, tmp_path) -> None:
    """Verify that the clean_stderr fixture works."""
    # Given a test string
    test_string = f"Hello, {tmp_path}world!"
    sys.stderr.write(test_string)

    # When cleaning the stderr
    output = clean_stderrout(strip_tmp_path=True)

    # Then the output contains the string
    assert "Hello, …world!" in output
