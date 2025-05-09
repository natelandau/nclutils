"""Test Utilities."""

from nclutils import check_python_version, unique_id


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
