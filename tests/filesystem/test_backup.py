"""Test the backup function."""

import shutil
import stat
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
    """Verify backup_path raises FileNotFoundError under strict=True when src is missing."""
    # Given: A path that does not exist
    test_file = tmp_path / "test.txt"

    # When/Then: strict=True surfaces the missing source
    with pytest.raises(FileNotFoundError):
        backup_path(test_file, strict=True)


def test_backup_missing_file_no_raise(tmp_path: Path) -> None:
    """Verify backup_path returns None when src is missing and strict is False."""
    # Given: A path that does not exist
    test_file = tmp_path / "test.txt"

    # When: Creating backup without strict
    output = backup_path(test_file, strict=False)

    # Then: Output is None
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


def test_backup_directory_preserves_empty_subdirs(tmp_path: Path) -> None:
    """Verify directory backup preserves empty subdirectories."""
    # Given: A directory tree with an empty subdirectory
    src = tmp_path / "src"
    src.mkdir()
    (src / "empty").mkdir()
    (src / "file.txt").write_text("hi")

    # When: Backing up
    target = backup_path(src, backup_suffix=".bak")

    # Then: Empty subdirectory exists in the backup
    assert target is not None
    assert (target / "empty").is_dir()
    assert (target / "file.txt").read_text() == "hi"


def test_backup_directory_preserves_file_mode(tmp_path: Path) -> None:
    """Verify directory backup preserves file permission bits."""
    # Given: A file with unusual permissions inside a directory
    src = tmp_path / "src"
    src.mkdir()
    f = src / "secret.txt"
    f.write_text("x")
    f.chmod(0o600)

    # When: Backing up
    target = backup_path(src, backup_suffix=".bak")

    # Then: The file in the backup has the same permission bits
    assert target is not None
    assert stat.S_IMODE((target / "secret.txt").stat().st_mode) == 0o600


def test_backup_directory_preserves_directory_mode(tmp_path: Path) -> None:
    """Verify directory backup preserves directory permission bits."""
    # Given: A subdirectory with unusual permissions
    src = tmp_path / "src"
    src.mkdir()
    sub = src / "private"
    sub.mkdir()
    sub.chmod(0o700)

    # When: Backing up
    target = backup_path(src, backup_suffix=".bak")

    # Then: The mirrored subdirectory has the same permission bits
    assert target is not None
    assert stat.S_IMODE((target / "private").stat().st_mode) == 0o700


def test_backup_directory_follows_symlink_to_file(tmp_path: Path) -> None:
    """Verify directory backup follows symlinks (resolves to target contents)."""
    # Given: A directory containing a symlink to a file outside the tree
    real = tmp_path / "real.txt"
    real.write_text("content")
    src = tmp_path / "src"
    src.mkdir()
    (src / "link.txt").symlink_to(real)

    # When: Backing up
    target = backup_path(src, backup_suffix=".bak")

    # Then: The backup contains the resolved file contents (matches shutil.copytree default)
    assert target is not None
    assert (target / "link.txt").is_file()
    assert not (target / "link.txt").is_symlink()
    assert (target / "link.txt").read_text() == "content"


def test_backup_directory_follows_symlink_to_directory(tmp_path: Path) -> None:
    """Verify directory backup descends into symlinks pointing to directories."""
    # Given: A directory with a symlink to another directory containing a file
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    (real_dir / "deep.txt").write_text("deep content")

    src = tmp_path / "src"
    src.mkdir()
    (src / "link_to_dir").symlink_to(real_dir)

    # When: Backing up
    target = backup_path(src, backup_suffix=".bak")

    # Then: The link is materialized as a real directory containing the symlink target's contents
    assert target is not None
    backed_up = target / "link_to_dir"
    assert backed_up.exists()
    assert backed_up.is_dir()
    assert not backed_up.is_symlink()
    assert (backed_up / "deep.txt").read_text() == "deep content"


def test_backup_directory_matches_shutil_copytree_output(tmp_path: Path) -> None:
    """Verify the chunked walk produces a tree functionally identical to shutil.copytree."""
    # Given: A non-trivial directory tree
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("alpha")
    (src / "sub").mkdir()
    (src / "sub" / "b.txt").write_text("beta")
    (src / "sub" / "empty").mkdir()
    (src / "sub" / "c.bin").write_bytes(b"\x00\x01\x02\x03")

    # When: Backing up via our chunked walk and via shutil.copytree separately
    via_backup = backup_path(src, backup_suffix=".ours")
    via_shutil = src.with_name(src.name + ".shutil")
    shutil.copytree(src, via_shutil)

    # Then: The two trees contain identical relative paths and file contents
    assert via_backup is not None
    ours = sorted(p.relative_to(via_backup) for p in via_backup.rglob("*"))
    theirs = sorted(p.relative_to(via_shutil) for p in via_shutil.rglob("*"))
    assert ours == theirs
    for rel in ours:
        a = via_backup / rel
        b = via_shutil / rel
        if a.is_file():
            assert a.read_bytes() == b.read_bytes()
