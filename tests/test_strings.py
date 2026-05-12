"""Test the strings module."""

import re

import pytest

from nclutils.strings import human_size, random_string


def test_random_string() -> None:
    """Test random_string()."""
    returned = random_string(10)

    assert isinstance(returned, str)
    assert len(returned) == 10
    assert re.match(r"[a-zA-Z]{10}", returned)


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (0, "0 B"),
        (1, "1 B"),
        (512, "512 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024 * 1024, "1.0 MB"),
        (1024**3, "1.0 GB"),
        (1024**4, "1.0 TB"),
        (1024**5, "1.0 PB"),
        (1024**6, "1.0 EB"),
        (1024**7, "1.0 ZB"),
        (1024**8, "1.0 YB"),
        (1024**9, "1024.0 YB"),
    ],
)
def test_human_size_default_decimals(size_bytes: int, expected: str) -> None:
    """Verify human_size renders each unit with the default 1-decimal precision."""
    # Given a byte count covering each unit boundary

    # When formatting with defaults
    result = human_size(size_bytes)

    # Then the value uses the largest unit below 1024 of the next
    assert result == expected


@pytest.mark.parametrize(
    ("size_bytes", "decimals", "expected"),
    [
        (1536, 0, "2 KB"),
        (1536, 2, "1.50 KB"),
        (1536, 4, "1.5000 KB"),
        (999, 3, "999 B"),
    ],
)
def test_human_size_custom_decimals(size_bytes: int, decimals: int, expected: str) -> None:
    """Verify decimals kwarg controls precision for non-byte units only."""
    # Given a byte count and a target precision

    # When formatting with the precision override
    result = human_size(size_bytes, decimals=decimals)

    # Then bytes stay integer and larger units honor the precision
    assert result == expected


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (-1, "-1 B"),
        (-1536, "-1.5 KB"),
        (-(1024**3), "-1.0 GB"),
    ],
)
def test_human_size_negative_values(size_bytes: int, expected: str) -> None:
    """Verify negative inputs are formatted with a leading minus sign."""
    # Given a negative byte count

    # When formatting it
    result = human_size(size_bytes)

    # Then the sign is preserved and the unit selection mirrors the positive case
    assert result == expected


def test_human_size_accepts_float() -> None:
    """Verify human_size accepts float inputs without truncation in unit selection."""
    # Given a fractional byte count

    # When formatting it
    result = human_size(2048.5)

    # Then it is divided into the appropriate unit
    assert result == "2.0 KB"
