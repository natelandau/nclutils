"""Shared fixtures for nclutils tests."""

import logging

import pytest


@pytest.fixture
def sh_caplog(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture DEBUG-and-above records from `nclutils.sh`."""
    caplog.set_level(logging.DEBUG, logger="nclutils.sh")
    return caplog
