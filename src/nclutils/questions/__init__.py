"""Deprecated alias for nclutils.ask. Removed in v4.0.0."""

import warnings

warnings.warn(
    "nclutils.questions is deprecated and will be removed in v4.0.0. Use nclutils.ask instead.",
    DeprecationWarning,
    stacklevel=2,
)

from nclutils.ask import choose_multiple_from_list, choose_one_from_list  # noqa: E402

__all__ = ["choose_multiple_from_list", "choose_one_from_list"]
