"""Deprecated alias for nclutils.text. To be removed in a future major release."""

import warnings

warnings.warn(
    "nclutils.text_processing is deprecated and will be removed in a future major release. "
    "Use nclutils.text instead.",
    DeprecationWarning,
    stacklevel=2,
)

from nclutils.text import ensure_lines_in_file, replace_in_file  # noqa: E402

__all__ = ["ensure_lines_in_file", "replace_in_file"]
