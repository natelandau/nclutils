"""Test the strings module."""

import re

from nclutils import random_string


def test_random_string(debug) -> None:
    """Test random_string()."""
    returned = random_string(10)

    assert isinstance(returned, str)
    assert len(returned) == 10
    assert re.match(r"[a-zA-Z]{10}", returned)
