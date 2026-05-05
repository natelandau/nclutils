"""Shared fixtures for filesystem tests."""

import logging

import pytest


@pytest.fixture
def fs_caplog(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture WARNING-and-above records from `nclutils.fs.filesystem`."""
    caplog.set_level(logging.WARNING, logger="nclutils.fs.filesystem")
    return caplog
