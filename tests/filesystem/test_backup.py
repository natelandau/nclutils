"""Test the backup function."""

from pathlib import Path

import pytest

from nclutils.fs import backup_path


@pytest.fixture
def backup_test_path(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Setup and teardown for backup tests.

    Returns:
        Path: The parent directory
    """
    # Create a parent directory
    parent_dir = tmp_path / "parent_dir"
    parent_dir.mkdir()

    # Create a test file
    test_file = parent_dir / "test.txt"
    test_file.write_text("Hello, world!")

    # Create a test directory
    test_dir = parent_dir / "test_dir"
    test_dir.mkdir()
    # Create a test file in the test directory
    test_file_in_dir = test_dir / "test.txt"
    test_file_in_dir.write_text("Hello, world!")

    return parent_dir, test_file, test_dir


def test_backup_path(
    backup_test_path: tuple[Path, Path, Path], capsys: pytest.CaptureFixture
) -> None:
    """Verify creating backup files preserves original content."""
    # Given: A test file
    _, test_file, _ = backup_test_path

    # When: Creating a backup
    backup = backup_path(test_file, transient=False, with_progress=True)
    output = capsys.readouterr().out
    assert "Backup test.txt" in output
    assert "100%" in output

    # Then: Original and backup exist with same content
    assert test_file.exists()
    assert backup.exists()
    assert backup.read_text() == "Hello, world!"


def test_backup_multiple_backups(backup_test_path: tuple[Path, Path, Path]) -> None:
    """Verify backup files increment names when backups already exist."""
    # Given: A test file
    _, test_file, _ = backup_test_path

    # When: Creating multiple backups
    backup1 = backup_path(test_file)
    assert len(list(backup1.parent.glob("*.bak"))) == 1
    backup2 = backup_path(test_file)
    assert len(list(backup2.parent.glob("*.bak"))) == 2
    backup3 = backup_path(test_file)
    assert len(list(backup3.parent.glob("*.bak"))) == 3

    # Then: All backups exist with correct content
    assert test_file.exists()
    assert backup1.exists()
    assert backup1.read_text() == "Hello, world!"
    assert backup2.exists()
    assert backup2.read_text() == "Hello, world!"
    assert backup3.exists()
    assert backup3.read_text() == "Hello, world!"


def test_backup_multiple_backups_same_backup_suffix(
    backup_test_path: tuple[Path, Path, Path],
) -> None:
    """Verify backup files increment names when backups already exist."""
    # Given: A test file
    _, test_file, _ = backup_test_path

    # When: Creating multiple backups
    # Then the backup suffix is used and old backups are overwritten
    backup1 = backup_path(test_file, backup_suffix=".bak")
    assert len(list(backup1.parent.glob("*.bak"))) == 1
    backup2 = backup_path(test_file, backup_suffix=".bak")
    assert len(list(backup2.parent.glob("*.bak"))) == 1
    backup3 = backup_path(test_file, backup_suffix=".bak")
    assert len(list(backup3.parent.glob("*.bak"))) == 1


def test_backup_directory(backup_test_path: tuple[Path, Path, Path]) -> None:
    """Verify backing up directories preserves structure and content."""
    # Given: A test directory
    _, _, test_dir = backup_test_path

    # When: Creating a backup
    backup = backup_path(test_dir)

    # Then: Directory backup exists with correct structure
    assert test_dir.exists()
    assert backup.exists()
    assert backup.is_dir()

    assert len(list(backup.glob("*"))) == 1
    assert (backup / "test.txt").exists()
    assert (backup / "test.txt").read_text() == "Hello, world!"


def test_backup_missing_file(tmp_path: Path) -> None:
    """Verify backup raises error for missing files when configured."""
    # Given: A non-existent file path
    test_file = tmp_path / "test.txt"

    # When/Then: Backup attempt raises error
    with pytest.raises(FileNotFoundError):
        backup_path(test_file, raise_on_missing=True)

    assert not test_file.exists()


def test_backup_missing_file_no_raise(tmp_path: Path) -> None:
    """Verify backup handles missing files gracefully when configured."""
    # Given: A non-existent file path
    test_file = tmp_path / "test.txt"

    # When: Creating backup with raise_on_missing=False
    output = backup_path(test_file, raise_on_missing=False)

    # Then: No backup created
    assert not test_file.exists()
    assert output is None


def test_backup_path_preserves_file_mode(tmp_path: Path) -> None:
    """Verify backup_path preserves the executable bit on file backups."""
    # Given: An executable script
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o755)

    # When: Creating a backup
    backup = backup_path(script)

    # Then: Backup retains executable permissions
    assert backup is not None
    assert (backup.stat().st_mode & 0o777) == 0o755


def test_backup_directory_overwrites_existing_file_at_target(tmp_path: Path) -> None:
    """Verify backup_path replaces an existing regular file at the backup target when source is a directory."""
    # Given: A source directory and a regular file already sitting at the backup target
    src = tmp_path / "data"
    src.mkdir()
    (src / "inner.txt").write_text("payload")
    target = tmp_path / "data.bak"
    target.write_text("stale")

    # When: Backing up the directory using a custom suffix that collides with the file
    backup = backup_path(src, backup_suffix=".bak")

    # Then: The backup directory exists and contains the source's contents
    assert backup == target
    assert backup.is_dir()
    assert (backup / "inner.txt").read_text() == "payload"
