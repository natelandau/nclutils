"""Utility functions."""

import sys

ID_COUNTER = 0


def unique_id(prefix: str = "") -> str:
    """Generate a unique ID with an optional prefix.

    Generate an incrementing numeric ID that can be prefixed with a string. Each call increments a global counter to ensure uniqueness.

    Inspired by https://github.com/dgilland/pydash/

    Args:
        prefix (str): String prefix to prepend to the ID value. Defaults to "".

    Returns:
        str: The unique ID string, consisting of the optional prefix followed by an incrementing number.
    """
    # pylint: disable=global-statement
    global ID_COUNTER  # noqa: PLW0603
    ID_COUNTER += 1

    prefix = str(prefix)
    return f"{prefix}{ID_COUNTER}"


def check_python_version(major: int, minor: int) -> bool:
    """Compare the current Python version against minimum required version.

    Validate that the running Python interpreter meets or exceeds the specified major and minor version requirements. Use this to ensure compatibility with required language features.

    Args:
        major (int): Minimum required major version number
        minor (int): Minimum required minor version number

    Returns:
        bool: True if current Python version meets or exceeds requirements, False otherwise
    """
    return sys.version_info >= (major, minor)
