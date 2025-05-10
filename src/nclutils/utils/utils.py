"""Utility functions."""

import re
import sys
from datetime import datetime, timezone

from nclutils.constants import RANDOM

ID_COUNTER = 0


def new_uid(bits: int = 64) -> str:
    """Generate a random alphanumeric identifier with guaranteed minimum entropy.

    Create a random string using base-36 characters (0-9, a-z) with enough length to provide at least the requested bits of entropy. The case-insensitive output is suitable for filenames on any filesystem. Uses cryptographically secure random number generation via random.SystemRandom().

    Inspired by https://github.com/jlevy/strif/

    Args:
        bits (int, optional): Minimum bits of entropy required in the output. Defaults to 64.

    Returns:
        str: A random alphanumeric string with at least the specified bits of entropy.
    """
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    length = int(bits / 5.16) + 1  # log2(36) ≈ 5.17
    return "".join(RANDOM.choices(chars, k=length))


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


def iso_timestamp(*, microseconds: bool = False) -> str:
    """Generate an ISO 8601 formatted UTC timestamp.

    Creates a timestamp string in ISO 8601 format, using UTC timezone. The timestamp includes a 'Z' suffix to explicitly indicate UTC timezone. The microseconds precision can be controlled via the microseconds parameter.

    Inspired by https://github.com/jlevy/strif/

    Args:
        microseconds: If True, includes microseconds in the timestamp. If False, truncates to seconds precision. Defaults to False.

    Returns:
        str: An ISO 8601 formatted UTC timestamp string.
    """
    timespec = "microseconds" if microseconds else "seconds"
    return datetime.now(timezone.utc).isoformat(timespec=timespec).replace("+00:00", "Z")


def format_iso_timestamp(datetime_obj: datetime, *, microseconds: bool = False) -> str:
    """Format a datetime object into an ISO 8601 UTC timestamp string.

    Convert the given datetime to UTC timezone and format it as an ISO 8601 string with 'Z' suffix to explicitly indicate UTC. Control microseconds precision via the microseconds parameter.

    Args:
        datetime_obj (datetime): The datetime object to format
        microseconds (bool, optional): Include microseconds in the timestamp if True, truncate to seconds if False. Defaults to False.

    Returns:
        str: An ISO 8601 formatted UTC timestamp string

    """
    timespec = "microseconds" if microseconds else "seconds"
    return datetime_obj.astimezone(timezone.utc).isoformat(timespec=timespec).replace("+00:00", "Z")


def new_timestamp_uid(bits: int = 32) -> str:
    """Generate a unique ID prefixed with an ISO timestamp.

    Create a unique identifier that combines an ISO 8601 UTC timestamp with random bits for uniqueness. The timestamp prefix enables chronological sorting while the random suffix ensures uniqueness.

    Inspired by https://github.com/jlevy/strif/

    Args:
        bits (int, optional): Number of random bits to append after timestamp. Defaults to 32.

    Returns:
        str: A unique ID in format "YYYYMMDDTHHmmssZ-microseconds-randomstring"
    """
    timestamp = re.sub(r"[^\w.]", "", datetime.now(timezone.utc).isoformat()).replace(".", "Z-")[
        :23
    ]
    return f"{timestamp}-{new_uid(bits)}"


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
