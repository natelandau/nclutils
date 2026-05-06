"""Test the copy_file function."""

from collections.abc import Callable
from io import StringIO
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from rich.console import Console

from nclutils.fs import copy_directory, copy_file
from nclutils.utils import check_python_version


def test_copy_file_file_not_found(tmp_path: Path) -> None:
    """Verify copy_file raises FileNotFoundError when source file doesn't exist."""
    # Given: Source and destination paths
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"

    # When/Then: Copying non-existent file raises error
    with pytest.raises(FileNotFoundError):
        copy_file(src, dst)


def test_copy_file_not_transient(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify copy_file shows progress bar when transient=False."""
    # Given: Source file with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file with visible progress bar
    copy_file(src, dst, transient=False, with_progress=True)
    output = capsys.readouterr().out

    # Then: Progress bar was displayed and file was copied
    assert "Copy test.txt" in output
    assert "100%" in output
    assert dst.read_text() == "Hello, world!"


def test_copy_file_transient(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify copy_file hides progress bar when transient=True."""
    # Given: Source file with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file with hidden progress bar
    copy_file(src, dst, transient=True, with_progress=True)
    output = capsys.readouterr().out

    # Then: Progress bar was hidden and file was copied
    assert output == "\n"
    assert dst.read_text() == "Hello, world!"


def test_copy_file_overwrite(tmp_path: Path) -> None:
    """Verify copy_file overwrites existing destination file."""
    # Given: Source and destination files with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")
    dst.write_text("Old content")

    # When: Copying file and overwriting destination
    copy_file(src, dst, keep_backup=False)

    assert dst.read_text() == "Hello, world!"


def test_copy_file_keep_backup(tmp_path: Path) -> None:
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


def test_copy_file_same_file(tmp_path: Path, fs_caplog: pytest.LogCaptureFixture) -> None:
    """Verify copy_file handles same file as destination."""
    # Given: Source and destination files with same content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file to itself
    copy_file(src, src)

    # Then: No progress bar was displayed
    assert "Did not copy" in fs_caplog.text.replace("\n", " ").replace("  ", " ")
    assert not dst.exists()
    assert src.exists()


def test_copy_file_source_is_directory(tmp_path: Path, fs_caplog: pytest.LogCaptureFixture) -> None:
    """Verify copy_file raises IsADirectoryError when the source is a directory."""
    # Given: A source directory with files
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "file1.txt").write_text("Hello, world!")

    # When/Then: Calling copy_file on a directory raises the correct exception type
    with pytest.raises(IsADirectoryError):
        copy_file(src, dst)

    # And: An error is logged describing the directory rejection
    assert "is a directory" in fs_caplog.text


def test_copy_file_expands_tilde_in_src(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verify copy_file expands ~ in src so paths under HOME are usable."""
    # Given: A source file under a fake HOME and a tilde-prefixed path
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    real_src = fake_home / "note.txt"
    real_src.write_text("hello")
    dst = tmp_path / "copy.txt"
    mocker.patch("pathlib.Path.home", return_value=fake_home)
    mocker.patch.dict("os.environ", {"HOME": str(fake_home)})

    # When: Copying with ~/note.txt as the source
    result = copy_file(Path("~/note.txt"), dst)

    # Then: The destination has the source content
    assert dst.read_text() == "hello"
    assert result == dst.expanduser().resolve()


def test_copy_file_with_no_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture, debug: Callable
) -> None:
    """Verify copy_file works without progress bar."""
    # Given: Source file with content
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")

    # When: Copying file without progress bar
    copy_file(src, dst, with_progress=False, transient=False)
    output = capsys.readouterr().out

    # Then: File is copied without progress output
    assert not output
    assert src.read_text() == "Hello, world!"
    assert dst.read_text() == "Hello, world!"


def test_copy_directory_basic(tmp_path: Path) -> None:
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


def test_copy_directory_same_destination(
    tmp_path: Path, fs_caplog: pytest.LogCaptureFixture
) -> None:
    """Verify copy_directory handles copying to same directory."""
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Source directory
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.txt").write_text("test")

    # When: Copying directory to itself
    result = copy_directory(src, src)

    # Then: Warning is shown and original returned
    assert "same directory" in fs_caplog.text
    assert result == src


def test_copy_directory_parent_destination(
    tmp_path: Path, fs_caplog: pytest.LogCaptureFixture
) -> None:
    """Verify copy_directory prevents copying to parent directory."""
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

    # Then: Warning is shown and original returned
    assert "have parent/child relationship" in fs_caplog.text
    assert result == child


def test_copy_directory_dst_in_src(tmp_path: Path, fs_caplog: pytest.LogCaptureFixture) -> None:
    """Verify copy_directory prevents copying when destination is inside source."""
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Source directory with destination as subdirectory
    src = tmp_path / "src"
    dst = src / "dst"
    src.mkdir()
    (src / "test.txt").write_text("test")

    # When: Attempting to copy directory into itself
    result = copy_directory(src, dst)

    # Then: Warning is shown and original directory returned
    assert "have parent/child relationship" in fs_caplog.text
    assert result == src


def test_copy_directory_missing_source(tmp_path: Path, fs_caplog: pytest.LogCaptureFixture) -> None:
    """Verify copy_directory raises error when source directory does not exist."""
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: Non-existent source directory path
    src = tmp_path / "missing"
    dst = tmp_path / "dst"

    # When/Then: Copying non-existent directory raises error
    with pytest.raises(FileNotFoundError, match="does not exist"):
        copy_directory(src, dst)

    # Then: Error is logged
    assert "does not exist" in fs_caplog.text


def test_copy_directory_with_progress(tmp_path: Path) -> None:
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


def test_copy_directory_unique_name(tmp_path: Path) -> None:
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


def test_copy_directory_python_version(mocker: MockerFixture, tmp_path: Path) -> None:
    """Verify copy_directory requires Python 3.12 or higher."""
    # Given: Python version below 3.12
    mocker.patch("nclutils.fs.filesystem.check_python_version", autospec=True, return_value=False)

    # When/Then: Copying directory raises version error
    with pytest.raises(ValueError, match=r"requires a minimum of Python version 3\.12"):
        copy_directory("src", "dst")


def test_copy_directory_preserves_directory_mode(tmp_path: Path) -> None:
    """Verify copy_directory propagates directory permissions from the source tree."""
    if not check_python_version(3, 12):
        pytest.skip("Skipping test for Python version < 3.12")

    # Given: A source tree where a subdirectory has a non-default mode
    src = tmp_path / "src"
    sub = src / "sub"
    sub.mkdir(parents=True)
    (sub / "f.txt").write_text("x")
    sub.chmod(0o750)

    # When: Copying the directory
    dst = tmp_path / "dst"
    copy_directory(src, dst)

    # Then: The mirrored subdirectory carries the same permission bits
    assert ((dst / "sub").stat().st_mode & 0o777) == 0o750


def test_copy_file_uses_provided_console(tmp_path: Path) -> None:
    """Verify copy_file routes its progress bar through the supplied Rich console."""
    # Given: A source file and a Console that captures its output
    src = tmp_path / "test.txt"
    dst = tmp_path / "test_copy.txt"
    src.write_text("Hello, world!")
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=False, width=80)

    # When: Copying with a non-default console and a non-transient progress bar
    copy_file(src, dst, with_progress=True, transient=False, console=console)

    # Then: Progress output landed on the supplied console, not stdout
    assert "Copy test.txt" in buffer.getvalue()


@pytest.mark.skipif(not check_python_version(3, 12), reason="Requires Python 3.12+")
def test_copy_directory_unified_progress_no_backup(tmp_path: Path) -> None:
    """Verify copy_directory shows a single Copy phase when dst does not exist."""
    # Given: A source directory with a couple of files, no pre-existing dst
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    (src / "b.txt").write_text("world")
    dst = tmp_path / "dst"

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)

    # When: Copying with progress and a non-transient bar
    copy_directory(src, dst, with_progress=True, transient=False, console=console)

    output = buf.getvalue()

    # Then: One Copy phase header appears, no Backup phase header
    assert "Copy src" in output
    assert "Backup" not in output
    # And: 100% completion is shown
    assert "100%" in output


@pytest.mark.skipif(not check_python_version(3, 12), reason="Requires Python 3.12+")
def test_copy_directory_unified_progress_with_backup(tmp_path: Path) -> None:
    """Verify copy_directory shows Backup then Copy when dst exists."""
    # Given: An existing dst directory and a fresh src
    src = tmp_path / "src"
    src.mkdir()
    (src / "new.txt").write_text("new content")

    dst = tmp_path / "dst"
    dst.mkdir()
    (dst / "old.txt").write_text("old content")

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)

    # When: Copying with progress, backup enabled, non-transient
    copy_directory(src, dst, with_progress=True, transient=False, keep_backup=True, console=console)

    output = buf.getvalue()

    # Then: Both Backup and Copy phase headers appear, in order
    assert "Backup dst" in output
    assert "Copy src" in output
    assert output.index("Backup dst") < output.index("Copy src")


@pytest.mark.skipif(not check_python_version(3, 12), reason="Requires Python 3.12+")
def test_copy_directory_progress_with_symlinked_subdir(tmp_path: Path) -> None:
    """Verify unified progress reaches 100% for trees containing a symlinked directory."""
    # Given: A tree with a symlink pointing to a directory containing a file
    real = tmp_path / "real_dir"
    real.mkdir()
    (real / "deep.txt").write_text("deep content")

    src = tmp_path / "src"
    src.mkdir()
    (src / "regular.txt").write_text("regular content")
    (src / "link_to_dir").symlink_to(real)

    dst = tmp_path / "dst"

    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)

    # When: Copying with progress
    copy_directory(src, dst, with_progress=True, transient=False, console=console)

    output = buf.getvalue()

    # Then: 100% is shown (would be missed if _sum_bytes didn't follow symlinks)
    assert "100%" in output
    # And: The symlink target's content was copied
    assert (dst / "link_to_dir" / "deep.txt").read_text() == "deep content"
