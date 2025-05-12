"""Test logging module."""

import pytest

from nclutils import logger
from nclutils.logging.logging import Logger


def test_no_output_when_log_level_is_notset(clean_stderr, debug):
    """Verify that no output is produced when the logger is not configured."""
    # Given a logger instance without configuration
    logger = Logger()

    # When logging messages at various levels
    logger.trace("Hello, world!")
    logger.debug("Hello, world!")
    logger.info("Hello, world!")
    logger.success("Hello, world!")
    logger.warning("Hello, world!")
    logger.error("Hello, world!")
    logger.critical("Hello, world!")

    # Then no output should be produced
    output = clean_stderr()
    assert not output


def test_exception_if_level_not_known():
    """Verify that an exception is raised if an unknown log level is used."""
    # When configuring logger with unknown level
    # Then KeyError should be raised
    with pytest.raises(KeyError):
        logger.configure(log_level="unknown")


def test_logger_respects_log_level(clean_stderr):
    """Verify that the logger respects the log level."""
    # Given logger configured at INFO level
    logger.configure(log_level="info")

    # When logging messages at various levels
    logger.trace("Hello, world!")
    logger.debug("Hello, world!")
    logger.info("Hello, world!")
    logger.success("Hello, world!")
    logger.warning("Hello, world!")
    logger.error("Hello, world!")
    logger.critical("Hello, world!")

    # Then only messages at INFO and above should appear
    output = clean_stderr()
    assert "DEBUG" not in output
    assert "TRACE" not in output
    assert "INFO" in output
    assert "SUCCESS" in output
    assert "WARNING" in output
    assert "ERROR" in output
    assert "CRITICAL" in output


def test_logger_respects_stderr_false(clean_stderr):
    """Verify that the logger respects the log level."""
    # Given logger configured with stderr disabled
    logger.configure(log_level="info", stderr=False)

    # When logging messages at various levels
    logger.trace("Hello, world!")
    logger.debug("Hello, world!")
    logger.info("Hello, world!")
    logger.success("Hello, world!")
    logger.warning("Hello, world!")
    logger.error("Hello, world!")
    logger.critical("Hello, world!")

    # Then no output should be produced
    output = clean_stderr()
    assert not output


def test_logger_extra_attributes(clean_stderr, debug):
    """Verify that the logger respects the log level."""
    # Given logger configured at INFO level
    logger.configure(log_level="info")

    # When logging messages with extra attributes
    logger.info("Hello world1")
    logger.info("Hello world2", somevar="somevalue")

    # Then output should contain the messages and attributes
    output = clean_stderr()
    # debug(output)
    assert "INFO     | Hello world1 | tests.test_logger" in output
    assert "INFO     | Hello world2 | {'somevar': 'somevalue'} | tests.test_logger" in output


def test_log_to_file(clean_stderr, tmp_path, debug):
    """Verify that the logger respects the log level."""
    # Given logger configured to write to file
    log_path = tmp_path / "somedir" / "test.log"
    logger.configure(log_level="info", log_file=str(log_path))

    # When logging messages
    logger.info("Hello world1")
    logger.info("Hello world2", somevar="somevalue")

    # Then messages should appear in stderr and log file
    output = clean_stderr()
    assert "INFO     | Hello world1 | tests.test_logger" in output
    assert "INFO     | Hello world2 | {'somevar': 'somevalue'} | tests.test_logger" in output

    assert log_path.exists()
    logfile_text = log_path.read_text()

    assert "| INFO     | Hello world1 | tests.test_logger" in logfile_text
    assert (
        "| INFO     | Hello world2 | {'somevar': 'somevalue'} | tests.test_logger" in logfile_text
    )


def test_catch_decorator(clean_stderr, tmp_path, debug):
    """Verify that the catch decorator works."""
    # Given logger configured to write to file
    log_path = tmp_path / "test.log"
    logger.configure(log_level="info", log_file=str(log_path))

    # When a decorated function raises an exception
    @logger.catch
    def divide(a: int, b: int) -> float:  # noqa: FURB118
        return a / b

    divide(1, 0)

    # Then error details should be logged to stderr and file
    output = clean_stderr()

    assert "ERROR    | An error has been caught in function 'test_catch_decorator'" in output
    assert (
        """
    return a / b
           │   └ 0
           └ 1
"""
        in output
    )

    assert log_path.exists()
    logfile_text = log_path.read_text()

    assert (
        "| ERROR    | An error has been caught in function 'test_catch_decorator'" in logfile_text
    )
    assert (
        """
    return a / b
           │   └ 0
           └ 1
"""
        in logfile_text
    )
