"""Test the copy_file function."""

from collections.abc import Callable
from pathlib import Path

import pytest

from nclutils import check_python_version, copy_directory, copy_file, logger


def test_copy_file_file_not_found(tmp_path: Path):
    """Verify copy_file raises FileNotFoundError when source file doesn't exist."""
    # Given: Source and destination paths
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"

    # When/Then: Copying non-existent file raises error
    with pytest.raises(FileNotFoundError):
        copy_file(src, dst)


def test_copy_file_not_transient(
    tmp_path: Path, clean_stdout: pytest.CaptureFixture, debug: Callable
):
    """Verify copy_file shows progress bar when transient=False."""
    # Given: Source file with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file with visible progress bar
    copy_file(src, dst, transient=False, with_progress=True)
    output = clean_stdout()

    # Then: Progress bar was displayed and file was copied
    assert "Copy test.txt" in output
    assert "100%" in output
    assert dst.read_text() == "Hello, world!"


def test_copy_file_transient(tmp_path: Path, clean_stdout: pytest.CaptureFixture, debug: Callable):
    """Verify copy_file hides progress bar when transient=True."""
    # Given: Source file with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file with hidden progress bar
    copy_file(src, dst, transient=True, with_progress=True)
    output = clean_stdout()

    # Then: Progress bar was hidden and file was copied
    assert output == "\n"
    assert dst.read_text() == "Hello, world!"


def test_copy_file_overwrite(tmp_path: Path, clean_stdout: pytest.CaptureFixture, debug: Callable):
    """Verify copy_file overwrites existing destination file."""
    # Given: Source and destination files with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")
    dst.write_text("Old content")

    # When: Copying file and overwriting destination
    copy_file(src, dst, keep_backup=False)

    assert dst.read_text() == "Hello, world!"


def test_copy_file_keep_backup(
    tmp_path: Path, clean_stdout: pytest.CaptureFixture, debug: Callable
):
    """Verify copy_file overwrites existing destination file."""
    # Given: Source and destination files with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")
    dst.write_text("Old content")

    # When: Copying file and overwriting destination
    copy_file(src, dst, keep_backup=True)

    for file in tmp_path.iterdir():
        if file in {src, dst}:
            assert file.read_text() == "Hello, world!"
        else:
            assert file.name.startswith("test_copy.txt.")
            assert file.name.endswith(".bak")
            assert file.read_text() == "Old content"


def test_copy_file_same_file(tmp_path: Path, clean_stderr: pytest.CaptureFixture, debug: Callable):
    """Verify copy_file handles same file as destination."""
    # Given: Source and destination files with same content
    logger.configure(log_level="WARNING")
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file to itself

    copy_file(src, src)
    output = clean_stderr().replace(str(tmp_path), "")
    # debug(output)

    # Then: No progress bar was displayed
    assert "Did not copy" in output.replace("\n", " ").replace("  ", " ")
    assert not dst.exists()
    assert src.exists()


def test_copy_directory(tmp_path: Path, clean_stderr):
    """Verify copy_file raises error when copying directory."""
    logger.configure(log_level="WARNING")
    # Given: Source directory with files
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "file1.txt").write_text("Hello, world!")
    (src / "file2.txt").write_text("Hello, world!")

    # When: Attempting to copy directory
    with pytest.raises(FileNotFoundError):
        copy_file(src, dst)

    output = clean_stderr()

    assert "is not a file. Did not copy" in output


def test_copy_file_with_no_progress(
    tmp_path: Path, clean_stdout: pytest.CaptureFixture, debug: Callable
):
    """Verify copy_file works without progress bar."""
    # Given: Source file with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file without progress bar
    copy_file(src, dst, with_progress=False, transient=False)
    output = clean_stdout()

    # Then: File is copied without progress output
    assert not output
    assert src.read_text() == "Hello, world!"
    assert dst.read_text() == "Hello, world!"


def test_copy_directory_basic(tmp_path: Path):
    """Verify copy_directory copies files and structure correctly."""
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Source directory with nested files and subdirectories
    # Given: Source directory with nested files and subdirectories
    src = tmp_path / "src"
    src.mkdir()
    (src / "file1.txt").write_text("Hello")
    subdir = src / "subdir"
    subdir.mkdir()
    (subdir / "file2.txt").write_text("World")

    # When: Copying directory
    dst = tmp_path / "dst"
    result = copy_directory(src, dst)

    # Then: Files and structure are copied correctly
    assert result == dst
    assert (dst / "file1.txt").read_text() == "Hello"
    assert (dst / "subdir" / "file2.txt").read_text() == "World"


def test_copy_directory_same_destination(debug, tmp_path, clean_stderr):
    """Verify copy_directory handles copying to same directory."""
    logger.configure(log_level="WARNING")
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Source directory
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.txt").write_text("test")

    # When: Copying directory to itself
    result = copy_directory(src, src)
    output = clean_stderr()
    # debug(output)

    # Then: Warning is shown and original returned
    assert "same directory" in output
    assert result == src


def test_copy_directory_parent_destination(debug, tmp_path: Path, clean_stderr):
    """Verify copy_directory prevents copying to parent directory."""
    logger.configure(log_level="WARNING")
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Nested directory structure
    parent = tmp_path / "parent"
    child = parent / "child"
    parent.mkdir()
    child.mkdir()
    (child / "test.txt").write_text("test")

    # When: Attempting to copy to parent directory
    result = copy_directory(child, parent)
    output = clean_stderr().replace(str(tmp_path), "")
    # debug(output)

    # Then: Warning is shown and original returned
    assert "have parent/child relationship" in output
    assert result == child


def test_copy_directory_dst_in_src(debug, tmp_path: Path, clean_stderr):
    """Verify copy_directory prevents copying when destination is inside source."""
    logger.configure(log_level="WARNING")
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Source directory with destination as subdirectory
    src = tmp_path / "src"
    dst = src / "dst"
    src.mkdir()
    (src / "test.txt").write_text("test")

    # When: Attempting to copy directory into itself
    result = copy_directory(src, dst)
    output = clean_stderr().replace(str(tmp_path), "")

    # Then: Warning is shown and original directory returned
    assert "have parent/child relationship" in output
    assert result == src


def test_copy_directory_missing_source(tmp_path, clean_stderr):
    """Verify copy_directory raises error when source directory does not exist."""
    logger.configure(log_level="WARNING")
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Non-existent source directory path
    src = tmp_path / "missing"
    dst = tmp_path / "dst"

    # When/Then: Copying non-existent directory raises error
    with pytest.raises(FileNotFoundError, match="does not exist"):
        copy_directory(src, dst)

    output = clean_stderr().replace(str(tmp_path), "")
    assert "does not exist" in output


def test_copy_directory_with_progress(tmp_path: Path):
    """Verify copy_directory displays progress bar when enabled."""
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Source directory containing test file
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.txt").write_text("test content")

    # When: Copying directory with progress bar enabled
    dst = tmp_path / "dst"
    result = copy_directory(src, dst, with_progress=True)

    # Then: Directory and contents are copied successfully
    assert result == dst
    assert (dst / "test.txt").read_text() == "test content"


def test_copy_directory_unique_name(tmp_path: Path):
    """Verify copy_directory generates unique name when destination exists."""
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Source and existing destination directories
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "test.txt").write_text("test")
    (dst / "test.txt").write_text("old")

    # When: Copying directory without overwrite flag
    result = copy_directory(src, dst)

    # Then: Files copied to new directory with unique name and a backup is created
    assert result == dst

    for d in tmp_path.iterdir():
        if d in {src, dst}:
            assert (d / "test.txt").read_text() == "test"
        else:
            assert d.name.startswith("dst.")
            assert d.name.endswith(".bak")
            assert (d / "test.txt").read_text() == "old"


def test_copy_directory_python_version(mocker, tmp_path: Path, clean_stderr):
    """Verify copy_directory requires Python 3.12 or higher."""
    # Given: Python version below 3.12
    logger.configure(log_level="WARNING")
    mocker.patch("nclutils.fs.filesystem.check_python_version", return_value=False)

    # When/Then: Copying directory raises version error
    with pytest.raises(ValueError, match=r"requires a minimum of Python version 3\.12"):
        copy_directory("src", "dst")

    output = clean_stderr()
    assert "requires a minimum of Python version 3.12" in output
