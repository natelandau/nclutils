"""Tests for deprecated namespace aliases."""

import importlib
import warnings

import pytest


@pytest.mark.parametrize(
    ("old_module", "new_module", "symbol"),
    [
        ("nclutils.questions", "nclutils.ask", "choose_one_from_list"),
        ("nclutils.text_processing", "nclutils.text", "replace_in_file"),
        ("nclutils.network", "nclutils.net", "network_available"),
    ],
)
def test_deprecated_alias_warns_and_reexports(
    old_module: str, new_module: str, symbol: str
) -> None:
    """Verify old namespace emits DeprecationWarning and re-exports the same symbol as the new one."""
    # Given: catch_warnings with simplefilter("always") so the warning fires even after the first import
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        # When: import the old module fresh, and import the new module
        old = importlib.reload(importlib.import_module(old_module))
        new = importlib.import_module(new_module)

    # Then: a DeprecationWarning naming the old module path was emitted
    assert any(
        issubclass(w.category, DeprecationWarning) and old_module in str(w.message) for w in caught
    ), f"expected DeprecationWarning naming {old_module}, got {[str(w.message) for w in caught]}"

    # And: the symbol re-exported from the old path is identical to the one in the new path
    assert getattr(old, symbol) is getattr(new, symbol)
