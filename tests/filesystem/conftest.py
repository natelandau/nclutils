"""Shared fixtures for filesystem tests."""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def fs_caplog(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture WARNING-and-above records from `nclutils.fs.filesystem`."""
    caplog.set_level(logging.WARNING, logger="nclutils.fs.filesystem")
    return caplog


@pytest.fixture
def temp_directory(tmp_path: Path) -> Path:
    """Create a nested directory structure for testing.

    Returns:
        Path: The path to the temporary directory.
    """
    (tmp_path / "a" / "a1" / "a11").mkdir(parents=True)
    (tmp_path / "a" / "a2").mkdir(parents=True)
    (tmp_path / "b" / "b1").mkdir(parents=True)
    (tmp_path / ".c").mkdir(parents=True)

    (tmp_path / "file.txt").touch()
    (tmp_path / "file.md").touch()
    (tmp_path / "file2.py").touch()
    (tmp_path / ".hidden.txt").touch()
    (tmp_path / "a" / "file.txt").touch()
    (tmp_path / "a" / "file2.txt").touch()
    (tmp_path / "a" / "file3.txt").touch()
    (tmp_path / "a" / "a1" / "a11" / "file.txt").touch()
    (tmp_path / "b" / "file.txt").touch()
    (tmp_path / "b" / "b1" / "file4.txt").touch()

    return tmp_path


@pytest.fixture
def fake_pwd(mocker):
    """Inject a fake `pwd` module into `sys.modules`.

    Returns a factory that swaps `pwd` with a `SimpleNamespace` carrying a
    mocked `getpwnam`. Pass `pw_dir=...` for a successful lookup, or
    `side_effect=...` for failure cases (e.g. `KeyError`).
    """

    def _factory(*, pw_dir=None, side_effect=None) -> SimpleNamespace:
        getpwnam = mocker.MagicMock()
        if side_effect is not None:
            getpwnam.side_effect = side_effect
        else:
            getpwnam.return_value = SimpleNamespace(pw_dir=pw_dir)
        module = SimpleNamespace(getpwnam=getpwnam)
        mocker.patch.dict(sys.modules, {"pwd": module})
        return module

    return _factory
