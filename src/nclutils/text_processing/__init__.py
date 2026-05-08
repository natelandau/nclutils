"""Deprecated alias for nclutils.text. Removed in v4.0.0."""

import warnings

warnings.warn(
    "nclutils.text_processing is deprecated and will be removed in v4.0.0. "
    "Use nclutils.text instead.",
    DeprecationWarning,
    stacklevel=2,
)

from nclutils.text import ensure_lines_in_file, replace_in_file  # noqa: E402

__all__ = ["ensure_lines_in_file", "replace_in_file"]
