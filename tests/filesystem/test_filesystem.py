# type: ignore
"""Test filesystem utilities."""

from pathlib import Path

import pytest

from nclutils import console, directory_tree, find_files, find_subdirectories


@pytest.fixture
def temp_directory(tmp_path: Path) -> Path:
    """Create a nested directory structure for testing.

    Returns:
        Path: The path to the temporary directory.
    """
    # Create directories
    (tmp_path / "a" / "a1" / "a11").mkdir(parents=True)
    (tmp_path / "a" / "a2").mkdir(parents=True)
    (tmp_path / "b" / "b1").mkdir(parents=True)
    (tmp_path / ".c").mkdir(parents=True)

    # Create a file in each nested directory
    (tmp_path / "file.txt").touch()
    (tmp_path / "file.md").touch()
    (tmp_path / "file2.py").touch()
    (tmp_path / ".hidden.txt").touch()
    (tmp_path / "a" / "file.txt").touch()
    (tmp_path / "a" / "file2.txt").touch()
    (tmp_path / "a" / "file3.txt").touch()
    (tmp_path / "a" / "a1" / "a11" / "file.txt").touch()
    (tmp_path / "b" / "file.txt").touch()
    (tmp_path / "b" / "b1" / "file4.txt").touch()

    return tmp_path


def test_fetch_subdirectories_basic(temp_directory: Path) -> None:
    """Return immediate subdirectories when depth is 1."""
    # When: Fetching immediate subdirectories
    result = find_subdirectories(temp_directory, depth=1)

    # Then: Only top-level directories are returned
    expected = sorted(
        [
            temp_directory / "a",
            temp_directory / "b",
            temp_directory / ".c",
        ]
    )
    assert result == expected


def test_fetch_subdirectories_depth_2(temp_directory: Path, debug) -> None:
    """Return subdirectories up to depth 2."""
    # When: Fetching subdirectories with depth 2
    result = find_subdirectories(temp_directory, depth=2)

    # Then: Directories up to depth 2 are returned
    expected = sorted(
        [
            temp_directory / "a",
            temp_directory / "a" / "a1",
            temp_directory / "a" / "a2",
            temp_directory / "b",
            temp_directory / "b" / "b1",
            temp_directory / ".c",
        ]
    )
    assert result == expected


def test_fetch_subdirectories_depth_3(temp_directory: Path, debug) -> None:
    """Return subdirectories up to depth 3."""
    # When: Fetching subdirectories with depth 3
    result = find_subdirectories(temp_directory, depth=3)

    # Then: Directories up to depth 3 are returned
    expected = sorted(
        [
            temp_directory / "a",
            temp_directory / "a" / "a1",
            temp_directory / "a" / "a1" / "a11",
            temp_directory / "a" / "a2",
            temp_directory / "b",
            temp_directory / "b" / "b1",
            temp_directory / ".c",
        ]
    )
    assert result == expected


def test_fetch_subdirectories_leaf_dirs_only(temp_directory: Path, debug) -> None:
    """Return only subdirectories at maximum depth when leaf_dirs_only is True."""
    # When: Fetching subdirectories with leaf_dirs_only=True
    result = find_subdirectories(temp_directory, depth=3, leaf_dirs_only=True)

    # Then: Only directories at depth 3 are returned
    expected = sorted(
        [
            temp_directory / "a" / "a1" / "a11",
            temp_directory / "a" / "a2",
            temp_directory / "b" / "b1",
            temp_directory / ".c",
        ]
    )
    assert result == expected


def test_fetch_subdirectories_filter_regex(temp_directory: Path) -> None:
    """Return only subdirectories matching the filter regex."""
    # When: Fetching subdirectories with a regex filter
    result = find_subdirectories(temp_directory, depth=2, filter_regex=r"^a", leaf_dirs_only=True)

    # Then: Only directories matching the regex at depth 2 are returned
    expected = sorted(
        [
            temp_directory / "a" / "a1",
            temp_directory / "a" / "a2",
        ]
    )
    assert result == expected


def test_fetch_subdirectories_single_level(temp_directory: Path) -> None:
    """Find subdirectories at a single level depth by default."""
    # When: Fetching subdirectories at the default depth
    result = find_subdirectories(temp_directory)

    # Then: Return only immediate subdirectories in sorted order
    expected = sorted(
        [
            temp_directory / "a",
            temp_directory / "b",
            temp_directory / ".c",
        ]
    )
    assert result == expected


def test_fetch_subdirectories_without_dotfiles(temp_directory: Path, debug) -> None:
    """Return subdirectories up to depth 2."""
    # When: Fetching subdirectories with depth 2
    result = find_subdirectories(temp_directory, depth=2, ignore_dotfiles=True)

    # Then: Directories up to depth 2 are returned
    expected = sorted(
        [
            temp_directory / "a",
            temp_directory / "a" / "a1",
            temp_directory / "a" / "a2",
            temp_directory / "b",
            temp_directory / "b" / "b1",
        ]
    )
    assert result == expected


def test_find_files_no_globs(temp_directory: Path) -> None:
    """Find all non-hidden files in directory when no globs provided."""
    # When: Finding files without glob patterns
    result = find_files(temp_directory)

    # Then: Return all non-hidden files in the root directory
    expected = sorted(
        [
            temp_directory / "file.txt",
            temp_directory / "file2.py",
            temp_directory / "file.md",
            temp_directory / ".hidden.txt",
        ]
    )
    assert result == expected


def test_find_files_with_glob(temp_directory: Path) -> None:
    """Find files matching specific glob patterns."""
    # When: Finding files with specific glob patterns
    result = find_files(temp_directory, globs=["*.txt", "*.py"])

    # Then: Return all matching non-hidden files
    expected = sorted(
        [
            temp_directory / "file.txt",
            temp_directory / "file2.py",
            temp_directory / ".hidden.txt",
        ]
    )
    assert result == expected


def test_find_files_include_dotfiles(temp_directory: Path) -> None:
    """Find all files including dotfiles when ignore_dotfiles is True."""
    # When: Finding files with dotfiles included
    result = find_files(temp_directory, ignore_dotfiles=True)

    # Then: Return all files including hidden ones
    expected = sorted(
        [
            temp_directory / "file.txt",
            temp_directory / "file2.py",
            temp_directory / "file.md",
        ]
    )
    assert result == expected


def test_find_files_single_glob(temp_directory: Path) -> None:
    """Find files matching a single glob pattern."""
    # When: Finding files with a specific extension
    result = find_files(temp_directory, globs=["*.py"])

    # Then: Return only Python files
    expected = sorted(
        [
            temp_directory / "file2.py",
        ]
    )
    assert result == expected


def test_find_files_no_matches(temp_directory: Path) -> None:
    """Return empty list when no files match glob pattern."""
    # When: Finding files with a pattern that matches nothing
    result = find_files(temp_directory, globs=["*.nonexistent"])

    # Then: Return empty list
    assert result == []


def test_directory_tree(temp_directory: Path, clean_stdout) -> None:
    """Build a rich.tree representation of a directory's contents."""
    # When: Building a directory tree
    result = directory_tree(temp_directory)
    console.print(result)
    output = clean_stdout()

    assert "├── 📂 " in output
    assert "│   ├── 📄" in output
    assert "│   └── 📄" in output
    assert "(0 bytes)" in output
