# type: ignore
"""Test filesystem utilities."""

from pathlib import Path

import pytest

from nclutils import console
from nclutils.fs import (
    clean_directory,
    directory_tree,
    find_files,
    find_subdirectories,
)


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


def test_directory_tree(temp_directory: Path, capsys: pytest.CaptureFixture) -> None:
    """Build a rich.tree representation of a directory's contents."""
    # When: Building a directory tree
    result = directory_tree(temp_directory)
    console().print(result)
    output = capsys.readouterr().out

    assert "├── 📂 " in output
    assert "│   ├── 📄" in output
    assert "│   └── 📄" in output
    assert "(0 bytes)" in output


def test_clean_directory(temp_directory: Path) -> None:
    """Verify that a directory is cleaned up."""
    # Given: A directory with files and subdirectories
    # When: Cleaning up a directory
    clean_directory(temp_directory)

    # Then: The directory should be empty
    assert temp_directory.exists()
    assert temp_directory.is_dir()
    assert not list(temp_directory.iterdir())


def test_clean_directory_not_a_directory(
    tmp_path: Path, fs_caplog: pytest.LogCaptureFixture
) -> None:
    """Verify clean_directory warns and skips when the target is a file."""
    test_file = tmp_path / "test.txt"
    test_file.touch()

    # When: Cleaning up a directory
    clean_directory(test_file)

    # Then: The directory should be empty
    assert test_file.exists()
    assert test_file.is_file()
    assert "test.txt is not a directory. Did not clean" in fs_caplog.text


def test_clean_directory_removes_symlink_to_directory(tmp_path: Path) -> None:
    """Verify clean_directory unlinks directory symlinks instead of recursing into them."""
    # Given: A directory containing a symlink that points at another directory
    target = tmp_path / "real_dir"
    target.mkdir()
    (target / "keep.txt").write_text("keep me")
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / "link").symlink_to(target)

    # When: Cleaning the workdir
    clean_directory(workdir)

    # Then: Symlink is removed but its target survives untouched
    assert not (workdir / "link").exists()
    assert not list(workdir.iterdir())
    assert (target / "keep.txt").read_text() == "keep me"


def test_clean_directory_removes_broken_symlink(tmp_path: Path) -> None:
    """Verify clean_directory removes dangling symlinks without raising."""
    # Given: A directory with a broken symlink
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / "broken").symlink_to(tmp_path / "missing_target")

    # When: Cleaning the workdir
    clean_directory(workdir)

    # Then: Broken symlink is gone
    assert not list(workdir.iterdir())


def test_clean_directory_removes_symlink_to_file(tmp_path: Path) -> None:
    """Verify clean_directory unlinks file symlinks without touching the target."""
    # Given: A directory containing a symlink that points at a regular file
    target = tmp_path / "real.txt"
    target.write_text("content")
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / "link").symlink_to(target)

    # When: Cleaning the workdir
    clean_directory(workdir)

    # Then: Symlink is removed but the target file survives untouched
    assert not list(workdir.iterdir())
    assert target.read_text() == "content"


def test_find_files_dedupes_overlapping_globs(temp_directory: Path) -> None:
    """Verify find_files returns each match once when globs overlap."""
    # Given: Globs that both match the same files
    globs = ["*.txt", "*"]

    # When: Searching with overlapping globs
    result = find_files(temp_directory, globs=globs)

    # Then: Each file appears once
    assert len(result) == len(set(result))


def test_find_files_ignore_dotfiles_excludes_hidden_parents(tmp_path: Path) -> None:
    """Verify ignore_dotfiles also excludes files reached through hidden directories."""
    # Given: A visible root containing a hidden subdir with files
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "deep.py").write_text("nested")
    (tmp_path / "visible.py").write_text("top")

    # When: Searching recursively with dotfiles ignored
    result = find_files(tmp_path, globs=["**/*.py"], ignore_dotfiles=True)

    # Then: Only the file outside the hidden dir is returned
    assert result == [tmp_path / "visible.py"]


def test_find_files_root_dotfile_is_not_filtered(tmp_path: Path) -> None:
    """Verify a hidden search root is supported when ignore_dotfiles is True."""
    # Given: A user-supplied hidden root containing a non-hidden file
    root = tmp_path / ".config"
    root.mkdir()
    (root / "settings.toml").write_text("k=v")

    # When: Searching with dotfiles ignored
    result = find_files(root, ignore_dotfiles=True)

    # Then: The non-hidden file inside the hidden root is returned
    assert result == [root / "settings.toml"]


def test_fetch_subdirectories_invalid_depth_zero() -> None:
    """Verify depth < 1 raises ValueError."""
    # Given: A real directory and an invalid depth
    # When/Then: depth=0 is rejected
    with pytest.raises(ValueError, match=r"depth must be >= 1"):
        find_subdirectories(Path(), depth=0)


def test_fetch_subdirectories_invalid_depth_negative() -> None:
    """Verify negative depth raises ValueError."""
    # Given: An invalid depth value
    # When/Then: A negative depth is rejected
    with pytest.raises(ValueError, match=r"depth must be >= 1"):
        find_subdirectories(Path(), depth=-1)


def test_fetch_subdirectories_leaf_dirs_only_with_prefix_siblings(tmp_path: Path) -> None:
    """Verify leaf detection treats sibling directories with shared name prefixes as independent leaves."""
    # Given: Two sibling dirs whose names share a string prefix but are not parent/child
    (tmp_path / "ab").mkdir()
    (tmp_path / "abc").mkdir()

    # When: Listing leaves
    result = find_subdirectories(tmp_path, depth=1, leaf_dirs_only=True)

    # Then: Both siblings are leaves
    assert sorted(result) == sorted([tmp_path / "ab", tmp_path / "abc"])


def test_fetch_subdirectories_root_dotfile_is_supported(tmp_path: Path) -> None:
    """Verify ignore_dotfiles treats the search root as ordinary even when its own name starts with a dot."""
    # Given: A hidden root with non-hidden children
    root = tmp_path / ".config"
    root.mkdir()
    (root / "kit").mkdir()
    (root / "tools").mkdir()

    # When: Searching the hidden root with dotfiles ignored
    result = find_subdirectories(root, depth=1, ignore_dotfiles=True)

    # Then: Non-hidden children are returned
    assert sorted(result) == sorted([root / "kit", root / "tools"])
