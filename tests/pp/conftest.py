"""Shared fixtures for nclutils.pp tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from io import StringIO
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
    soft_wrap, logfile, loglevel, logfmt) and returns the trio
    `(emitter, stdout_console, stderr_console)`. Both consoles use `record=True`
    with a fixed width and `truecolor` color system so `export_text()` /
    `export_html()` output is deterministic across hosts.

    Pass `force_terminal=False` to build consoles that report `is_terminal` as
    False, which is what exercises the auto-detected soft-wrap path.
    """

    def _factory(
        *,
        theme: Theme | None = None,
        verbosity: int | Verbosity = Verbosity.INFO,
        quiet: bool = False,
        soft_wrap: bool | None = None,
        force_terminal: bool = True,
        logfile: Path | None = None,
        loglevel: LogLevel | None = None,
        logfmt: str | None = None,
    ) -> tuple[Emitter, Console, Console]:
        # A StringIO file keeps is_terminal deterministically False when the
        # test wants the non-tty path; force_terminal=True overrides it.
        def _build() -> Console:
            return Console(
                record=True,
                force_terminal=force_terminal or None,
                file=None if force_terminal else StringIO(),
                width=80,
                color_system="truecolor",
            )

        out = _build()
        err = _build()
        kwargs: dict[str, object] = {
            "console": out,
            "err_console": err,
            "theme": theme,
            "verbosity": verbosity,
            "quiet": quiet,
            "soft_wrap": soft_wrap,
            "logfile": logfile,
        }
        if loglevel is not None:
            kwargs["loglevel"] = loglevel
        if logfmt is not None:
            kwargs["logfmt"] = logfmt
        e = Emitter(**kwargs)
        return e, out, err

    return _factory
