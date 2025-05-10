"""Test Utilities."""

import re
from datetime import datetime, timezone

from freezegun import freeze_time

from nclutils import (
    check_python_version,
    format_iso_timestamp,
    iso_timestamp,
    new_timestamp_uid,
    new_uid,
    unique_id,
)


def test_new_uid_default_bits() -> None:
    """Verify new_uid() generates a string with default 64 bits of entropy."""
    # When: Generating a UID with default bits
    uid = new_uid()

    # Then: String has correct length and characters
    expected_length = int(64 / 5.16) + 1  # log2(36) ≈ 5.17
    assert len(uid) == expected_length
    assert re.match(r"^[0-9a-z]+$", uid)


def test_new_uid_custom_bits() -> None:
    """Verify new_uid() generates a string with specified bits of entropy."""
    # Given: Different bit values to test
    test_bits = [32, 64, 128, 256]

    for bits in test_bits:
        # When: Generating a UID with specified bits
        uid = new_uid(bits)

        # Then: String has correct length and characters
        expected_length = int(bits / 5.16) + 1
        assert len(uid) == expected_length
        assert re.match(r"^[0-9a-z]+$", uid)


def test_new_uid_uniqueness() -> None:
    """Verify new_uid() generates unique strings."""
    # When: Generating multiple UIDs
    uids = {new_uid() for _ in range(100)}

    # Then: All UIDs are unique
    assert len(uids) == 100


def test_new_uid_character_distribution() -> None:
    """Verify new_uid() uses all base-36 characters."""
    # When: Generating a large number of UIDs
    uids = "".join(new_uid() for _ in range(1000))

    # Then: All base-36 characters are used
    used_chars = set(uids)
    expected_chars = set("0123456789abcdefghijklmnopqrstuvwxyz")
    assert used_chars == expected_chars


def test_unique_id() -> None:
    """Verify unique_id generates incrementing IDs with optional prefix."""
    # Given: No initial IDs generated

    # When: Calling unique_id multiple times
    # Then: IDs increment correctly with and without prefix
    assert unique_id() == "1"
    assert unique_id("id_") == "id_2"
    assert unique_id() == "3"


def test_check_python_version_pass() -> None:
    """Verify check_python_version passes for current Python version."""
    # Given: Python 3.9 minimum version requirement
    # When: Checking against current Python version
    # Then: Version check passes
    assert check_python_version(3, 9)


def test_check_python_version_fail() -> None:
    """Verify check_python_version fails for future Python version."""
    # Given: Python 5.18 minimum version requirement
    # When: Checking against current Python version
    # Then: Version check fails
    assert not check_python_version(5, 18)


@freeze_time("2024-03-15 12:34:56.789012")
def test_new_timestamp_uid_format(debug) -> None:
    """Verify new_timestamp_uid() generates correctly formatted string."""
    # When: Generating a timestamped UID
    uid = new_timestamp_uid()

    # Then: String matches expected format
    assert re.match(r"^20240315T123456Z-789012-[0-9a-z]+$", uid)


@freeze_time("2024-03-15 12:34:56.789012")
def test_new_timestamp_uid_custom_bits() -> None:
    """Verify new_timestamp_uid() generates correct length with custom bits."""
    # Given: Different bit values to test
    test_bits = [32, 64, 128, 256]

    for bits in test_bits:
        # When: Generating a timestamped UID with specified bits
        uid = new_timestamp_uid(bits)

        # Then: Random part has correct length
        random_part = uid.split("-")[-1]
        expected_length = int(bits / 5.16) + 1
        assert len(random_part) == expected_length


@freeze_time("2024-03-15 12:34:56.789012")
def test_new_timestamp_uid_uniqueness() -> None:
    """Verify new_timestamp_uid() generates unique strings."""
    # When: Generating multiple timestamped UIDs
    uids = {new_timestamp_uid() for _ in range(100)}

    # Then: All UIDs are unique
    assert len(uids) == 100


@freeze_time("2024-03-15 12:34:56.789012")
def test_new_timestamp_uid_components() -> None:
    """Verify new_timestamp_uid() contains all required components."""
    # When: Generating a timestamped UID
    uid = new_timestamp_uid()

    # Then: UID contains timestamp, microseconds, and random parts
    parts = uid.split("-")
    assert len(parts) == 3
    assert parts[0] == "20240315T123456Z"  # timestamp
    assert parts[1] == "789012"  # microseconds
    assert re.match(r"^[0-9a-z]+$", parts[2])  # random part


@freeze_time("2024-03-15 12:34:56.000000")
def test_new_timestamp_uid_zero_microseconds(debug) -> None:
    """Verify new_timestamp_uid() handles zero microseconds correctly."""
    # When: Generating a timestamped UID with zero microseconds
    uid = new_timestamp_uid()

    # Then: UID contains zero microseconds
    assert uid.startswith("20240315T1234560000-")


@freeze_time("2024-03-15 12:34:56.789012")
def test_iso_timestamp_with_microseconds() -> None:
    """Verify iso_timestamp() generates correct UTC timestamp with microseconds."""
    # When: Generating timestamp with microseconds
    timestamp = iso_timestamp(microseconds=True)

    # Then: Timestamp matches expected format and value
    assert timestamp == "2024-03-15T12:34:56.789012Z"


@freeze_time("2024-03-15 12:34:56.789012")
def test_iso_timestamp_without_microseconds() -> None:
    """Verify iso_timestamp() generates correct UTC timestamp without microseconds."""
    # When: Generating timestamp without microseconds
    timestamp = iso_timestamp(microseconds=False)

    # Then: Timestamp matches expected format and value
    assert timestamp == "2024-03-15T12:34:56Z"


def test_format_iso_timestamp_with_microseconds() -> None:
    """Verify format_iso_timestamp() formats datetime object with microseconds."""
    # Given: A datetime object
    dt = datetime(2024, 3, 15, 12, 34, 56, 789012, tzinfo=timezone.utc)

    # When: Formatting timestamp with microseconds
    timestamp = format_iso_timestamp(dt, microseconds=True)

    # Then: Timestamp matches expected format and value
    assert timestamp == "2024-03-15T12:34:56.789012Z"


def test_format_iso_timestamp_without_microseconds() -> None:
    """Verify format_iso_timestamp() formats datetime object without microseconds."""
    # Given: A datetime object
    dt = datetime(2024, 3, 15, 12, 34, 56, 789012, tzinfo=timezone.utc)

    # When: Formatting timestamp without microseconds
    timestamp = format_iso_timestamp(dt, microseconds=False)

    # Then: Timestamp matches expected format and value
    assert timestamp == "2024-03-15T12:34:56Z"
