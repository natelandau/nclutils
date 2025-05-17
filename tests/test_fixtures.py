"""Test the pytest fixtures."""


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
    assert "Hello, world!" in output


def test_debug_path(debug, clean_stdout, tmp_path) -> None:
    """Verify that the debug fixture works with a Path."""
    # Given a test file
    testfile = tmp_path / "test.txt"
    testfile.touch()

    # When debugging the file path
    debug(tmp_path, "Test", width=200)
    output = clean_stdout()

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
    assert str(testfile.relative_to(tmp_path)) in output
