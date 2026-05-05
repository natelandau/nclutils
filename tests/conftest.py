"""Shared fixtures for tests."""

import pytest
from loguru import logger as _logger

from nclutils.logging.logging import Logger


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset the Logger singleton before each test."""
    # Remove all existing handlers
    _logger.remove()

    # Reset the singleton instance
    Logger._instance = None
    Logger._initialized = False

    yield

    # Clean up Loguru handlers after the test
    _logger.remove()
    Logger._instance = None
    Logger._initialized = False
