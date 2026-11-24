"""Deprecated alias for nclutils.net. To be removed in a future major release."""

import warnings

warnings.warn(
    "nclutils.network is deprecated and will be removed in a future major release. Use nclutils.net instead.",
    DeprecationWarning,
    stacklevel=2,
)

from nclutils.net import network_available  # noqa: E402

__all__ = ["network_available"]
