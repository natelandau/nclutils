"""Tests for module-private helpers in nclutils.fs.filesystem."""

from pathlib import Path

from nclutils.fs.filesystem import _sum_bytes


def test_sum_bytes_empty_directory(tmp_path: Path) -> None:
    """Verify _sum_bytes returns (0, 0) for an empty directory."""
    # Given: An empty directory
    # When: Summing bytes
    total, count = _sum_bytes(tmp_path)

    # Then: Both are zero
    assert total == 0
    assert count == 0


def test_sum_bytes_flat_directory(tmp_path: Path) -> None:
    """Verify _sum_bytes returns total bytes and file count for a flat directory."""
    # Given: A directory with two files of known sizes
    (tmp_path / "a.txt").write_bytes(b"hello")  # 5 bytes
    (tmp_path / "b.txt").write_bytes(b"world!")  # 6 bytes

    # When: Summing bytes
    total, count = _sum_bytes(tmp_path)

    # Then: Sizes and count match
    assert total == 11
    assert count == 2


def test_sum_bytes_recursive(tmp_path: Path) -> None:
    """Verify _sum_bytes recurses into subdirectories."""
    # Given: A nested directory tree with three files
    (tmp_path / "a.txt").write_bytes(b"a")  # 1 byte
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_bytes(b"bb")  # 2 bytes
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / "sub" / "deep" / "c.txt").write_bytes(b"ccc")  # 3 bytes

    # When: Summing bytes
    total, count = _sum_bytes(tmp_path)

    # Then: Recurses through all levels
    assert total == 6
    assert count == 3
