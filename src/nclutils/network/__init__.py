"""Deprecated alias for nclutils.net. Removed in v4.0.0."""

import warnings

warnings.warn(
    "nclutils.network is deprecated and will be removed in v4.0.0. Use nclutils.net instead.",
    DeprecationWarning,
    stacklevel=2,
)

from nclutils.net import network_available  # noqa: E402

__all__ = ["network_available"]
