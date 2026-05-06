"""Shared fixtures for nclutils.pp tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from nclutils.pp.emitter import (
    Emitter,
    LogLevel,
    Theme,
    Verbosity,
    get_default,
    set_default,
)

if TYPE_CHECKING:
    from pathlib import Path

RecordingEmitterFactory = Callable[..., tuple[Emitter, Console, Console]]


@pytest.fixture
def isolated_default() -> Generator[None, None, None]:
    """Save and restore the module-level default emitter so tests don't leak state."""
    original = get_default()
    set_default(Emitter())
    yield
    set_default(original)


@pytest.fixture
def make_recording_emitter() -> RecordingEmitterFactory:
    """Return a factory that builds an Emitter wired to recording stdout/stderr consoles.

    The factory accepts the same kwargs as `Emitter` (theme, verbosity, quiet,
    logfile, loglevel, logfmt) and returns the trio
    `(emitter, stdout_console, stderr_console)`. Both consoles use `record=True`
    with a fixed width and `truecolor` color system so `export_text()` /
    `export_html()` output is deterministic across hosts.
    """

    def _factory(
        *,
        theme: Theme | None = None,
        verbosity: int | Verbosity = Verbosity.INFO,
        quiet: bool = False,
        logfile: Path | None = None,
        loglevel: LogLevel | None = None,
        logfmt: str | None = None,
    ) -> tuple[Emitter, Console, Console]:
        out = Console(record=True, force_terminal=True, width=80, color_system="truecolor")
        err = Console(record=True, force_terminal=True, width=80, color_system="truecolor")
        kwargs: dict[str, object] = {
            "console": out,
            "err_console": err,
            "theme": theme,
            "verbosity": verbosity,
            "quiet": quiet,
            "logfile": logfile,
        }
        if loglevel is not None:
            kwargs["loglevel"] = loglevel
        if logfmt is not None:
            kwargs["logfmt"] = logfmt
        e = Emitter(**kwargs)
        return e, out, err

    return _factory
