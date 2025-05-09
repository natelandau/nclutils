"""Test the backup function."""

import pytest

from nclutils import backup_path


@pytest.fixture
def backup_test_path(tmp_path):
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


def test_backup_path(backup_test_path, clean_stdout):
    """Verify creating backup files preserves original content."""
    # Given: A test file
    _, test_file, _ = backup_test_path

    # When: Creating a backup
    backup = backup_path(test_file, transient=False, with_progress=True)
    output = clean_stdout()
    assert "Backup test.txt" in output
    assert "100%" in output

    # Then: Original and backup exist with same content
    assert test_file.exists()
    assert backup.exists()
    assert backup.read_text() == "Hello, world!"


def test_backup_multiple_backups(backup_test_path, debug):
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


def test_backup_multiple_backups_same_backup_suffix(backup_test_path, debug):
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


def test_backup_directory(backup_test_path, debug):
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


def test_backup_missing_file(tmp_path, debug):
    """Verify backup raises error for missing files when configured."""
    # Given: A non-existent file path
    test_file = tmp_path / "test.txt"

    # When/Then: Backup attempt raises error
    with pytest.raises(FileNotFoundError):
        backup_path(test_file, raise_on_missing=True)

    assert not test_file.exists()


def test_backup_missing_file_no_raise(tmp_path, clean_stdout):
    """Verify backup handles missing files gracefully when configured."""
    # Given: A non-existent file path
    test_file = tmp_path / "test.txt"

    # When: Creating backup with raise_on_missing=False
    output = backup_path(test_file, raise_on_missing=False)

    # Then: No backup created
    assert not test_file.exists()
    assert output is None
