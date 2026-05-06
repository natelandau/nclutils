"""Tests for the find_user_home_dir function."""

import os
import sys
from pathlib import Path

import pytest

from nclutils.fs import find_user_home_dir


def test_find_user_home_dir_no_username_returns_self_home(mocker) -> None:
    """Verify find_user_home_dir returns Path.home() when no SUDO_USER is set."""
    # Given: No SUDO_USER in the environment
    mocker.patch.dict(os.environ, {}, clear=True)

    # When: Looking up without a username
    result = find_user_home_dir()

    # Then: Returns the current process's home
    assert result == Path.home()


def test_find_user_home_dir_uses_sudo_user(mocker, fake_pwd) -> None:
    """Verify find_user_home_dir falls back to SUDO_USER when no username is given."""
    # Given: SUDO_USER points to another user with a known home directory
    mocker.patch.dict(os.environ, {"SUDO_USER": "alice"}, clear=True)
    pwd_module = fake_pwd(pw_dir="/home/alice")

    # When: Resolving home with no explicit username
    result = find_user_home_dir()

    # Then: SUDO_USER's home is returned
    assert result == Path("/home/alice")
    pwd_module.getpwnam.assert_called_once_with("alice")


def test_find_user_home_dir_explicit_user(fake_pwd) -> None:
    """Verify find_user_home_dir resolves an explicitly named user via pwd."""
    # Given: pwd.getpwnam returns a known home for the requested user
    pwd_module = fake_pwd(pw_dir="/Users/bob")

    # When: Resolving home for a specific user
    result = find_user_home_dir("bob")

    # Then: The home from pwd is returned
    assert result == Path("/Users/bob")
    pwd_module.getpwnam.assert_called_once_with("bob")


def test_find_user_home_dir_unknown_user_returns_none(fake_pwd) -> None:
    """Verify a missing user yields None instead of an unhandled KeyError."""
    # Given: pwd.getpwnam raises KeyError for the requested user
    fake_pwd(side_effect=KeyError("ghost"))

    # When: Looking up a non-existent user
    result = find_user_home_dir("ghost")

    # Then: None is returned
    assert result is None


def test_find_user_home_dir_pwd_unavailable_returns_none_and_warns(
    mocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify the lookup returns None and logs a warning when the pwd module cannot be imported."""
    # Given: pwd cannot be imported (Windows-like environment)
    mocker.patch.dict(sys.modules, {"pwd": None})
    caplog.set_level("WARNING", logger="nclutils.fs.filesystem")

    # When: Looking up any user
    result = find_user_home_dir("anyone")

    # Then: None is returned and a warning was logged
    assert result is None
    assert "pwd module" in caplog.text


def test_find_user_home_dir_unknown_user_strict_raises(fake_pwd) -> None:
    """Verify find_user_home_dir raises KeyError when strict=True and user is unknown."""
    # Given: pwd.getpwnam raises KeyError for the requested user
    fake_pwd(side_effect=KeyError("ghost"))

    # When/Then: strict=True turns the silent return into KeyError
    with pytest.raises(KeyError):
        find_user_home_dir("ghost", strict=True)


def test_find_user_home_dir_pwd_unavailable_returns_none_even_under_strict(
    mocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify find_user_home_dir keeps returning None for missing pwd module even under strict."""
    # Given: pwd cannot be imported
    mocker.patch.dict(sys.modules, {"pwd": None})
    caplog.set_level("WARNING", logger="nclutils.fs.filesystem")

    # When: Looking up under strict=True
    result = find_user_home_dir("anyone", strict=True)

    # Then: Still None (platform capability, not a strict-mode violation)
    assert result is None
