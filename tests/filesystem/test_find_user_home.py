"""Tests for the find_user_home_dir function."""

import os
from pathlib import Path

import pytest

from nclutils import ShellCommandFailedError, find_user_home_dir


@pytest.fixture
def mock_platform_linux(mocker):
    """Mock platform.system() to return 'Linux'."""
    mocker.patch("platform.system", return_value="Linux")


@pytest.fixture
def mock_platform_darwin(mocker):
    """Mock platform.system() to return 'Darwin'."""
    mocker.patch("platform.system", return_value="Darwin")


def test_find_user_home_dir_no_username(mocker):
    """Verify finding home directory when no username is provided."""
    # Given: No SUDO_USER environment variable
    mocker.patch.dict(os.environ, {}, clear=True)

    # When: Finding home directory without username
    result = find_user_home_dir()

    # Then: Return current user's home directory
    assert result == Path.home()


def test_find_user_home_dir_with_sudo_user(mocker):
    """Verify finding home directory when SUDO_USER is set."""
    # Given: SUDO_USER environment variable is set and Linux platform
    mocker.patch.dict(os.environ, {"SUDO_USER": "testuser"})
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch(
        "nclutils.fs.filesystem.run_command",
        return_value="/home/testuser:x:1000:1000::/home/testuser:/bin/bash",
    )

    # When: Finding home directory without username
    result = find_user_home_dir()

    # Then: Return sudo user's home directory
    assert result == Path("/home/testuser")


def test_find_user_home_dir_linux_success(mock_platform_linux, mocker):
    """Verify finding home directory on Linux with valid username."""
    # Given: Mock successful command execution
    mocker.patch(
        "nclutils.fs.filesystem.run_command",
        return_value="/home/testuser:x:1000:1000::/home/testuser:/bin/bash",
    )

    # When: Finding home directory for specific user
    result = find_user_home_dir("testuser")

    # Then: Return correct home directory path
    assert result == Path("/home/testuser")


def test_find_user_home_dir_linux_failure(mock_platform_linux, mocker):
    """Verify handling non-existent user on Linux."""
    # Given: Mock failed command execution
    mocker.patch(
        "nclutils.fs.filesystem.run_command",
        side_effect=ShellCommandFailedError("Command failed"),
    )

    # When: Finding home directory for non-existent user
    result = find_user_home_dir("nonexistentuser")

    # Then: Return None for non-existent user
    assert result is None


def test_find_user_home_dir_darwin_success(mock_platform_darwin, mocker):
    """Verify finding home directory on macOS with valid username."""
    # Given: Mock successful command execution
    mocker.patch(
        "nclutils.fs.filesystem.run_command",
        return_value="NFSHomeDirectory: /Users/testuser",
    )

    # When: Finding home directory for specific user
    result = find_user_home_dir("testuser")

    # Then: Return correct home directory path
    assert result == Path("/Users/testuser")


def test_find_user_home_dir_darwin_failure(mock_platform_darwin, mocker):
    """Verify handling non-existent user on macOS."""
    # Given: Mock failed command execution
    mocker.patch(
        "nclutils.fs.filesystem.run_command",
        side_effect=ShellCommandFailedError("Command failed"),
    )

    # When: Finding home directory for non-existent user
    result = find_user_home_dir("nonexistentuser")

    # Then: Return None for non-existent user
    assert result is None
