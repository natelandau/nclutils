"""Tests for soft-wrap resolution and unpadded rendering in nclutils.pp."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from nclutils import pp
from nclutils.pp.emitter import Emitter

if TYPE_CHECKING:
    from .conftest import RecordingEmitterFactory

# Longer than the 80-column test consoles, and unbroken by spaces so any fold
# lands mid-token the way a real filesystem path does.
LONG_PATH = "/Users/natelandau/repos/project-memory/vault/projects/some-really-long-name/inbox"


def test_details_survive_capture(make_recording_emitter: RecordingEmitterFactory) -> None:
    """Verify a detail item longer than the console width is not truncated when captured."""
    # Given an emitter writing to a non-terminal console
    e, out, _ = make_recording_emitter(force_terminal=False)

    # When emitting a detail item longer than the console width
    e.info("paths", details=[LONG_PATH])

    # Then the full string survives intact on one line
    assert LONG_PATH in out.export_text()


def test_kv_value_survives_capture(make_recording_emitter: RecordingEmitterFactory) -> None:
    """Verify a kv value longer than the console width is not folded when captured."""
    # Given an emitter writing to a non-terminal console
    e, out, _ = make_recording_emitter(force_terminal=False)

    # When rendering a key/value pair whose value exceeds the console width
    e.kv({"inbox": LONG_PATH})

    # Then the full value survives intact on one line
    assert LONG_PATH in out.export_text()


def test_step_sub_survives_capture(make_recording_emitter: RecordingEmitterFactory) -> None:
    """Verify a step sub-item longer than the console width is not folded when captured."""
    # Given an emitter writing to a non-terminal console
    e, out, _ = make_recording_emitter(force_terminal=False)

    # When a step emits a sub-item longer than the console width
    with e.step("scanning") as s:
        s.sub(LONG_PATH)

    # Then the full string survives intact on one line
    assert LONG_PATH in out.export_text()


def test_no_trailing_whitespace_when_captured(
    make_recording_emitter: RecordingEmitterFactory,
) -> None:
    """Verify captured detail and kv lines carry no trailing whitespace padding."""
    # Given an emitter writing to a non-terminal console
    e, out, _ = make_recording_emitter(force_terminal=False)

    # When emitting details and key/value pairs
    e.info("hello", details=["one", "two"])
    e.kv({"key": "value", "longer_key": "other"})

    # Then no rendered line is padded out to the console width
    lines = out.export_text().splitlines()
    assert [line for line in lines if line != line.rstrip()] == []


def test_soft_wrap_auto_folds_on_terminal(make_recording_emitter: RecordingEmitterFactory) -> None:
    """Verify auto-detection keeps folding long messages on an interactive terminal."""
    # Given an emitter on a terminal console with no explicit soft_wrap
    e, out, _ = make_recording_emitter(force_terminal=True)

    # When emitting a message longer than the console width
    e.info(LONG_PATH)

    # Then the message is folded to the console width
    assert LONG_PATH not in out.export_text()


def test_soft_wrap_auto_keeps_capture_intact(
    make_recording_emitter: RecordingEmitterFactory,
) -> None:
    """Verify auto-detection stops folding long messages when the stream is not a terminal."""
    # Given an emitter on a non-terminal console with no explicit soft_wrap
    e, out, _ = make_recording_emitter(force_terminal=False)

    # When emitting a message longer than the console width
    e.info(LONG_PATH)

    # Then the message survives intact
    assert LONG_PATH in out.export_text()


def test_soft_wrap_false_folds_when_captured(
    make_recording_emitter: RecordingEmitterFactory,
) -> None:
    """Verify soft_wrap=False keeps folding even when the stream is not a terminal."""
    # Given an emitter that explicitly opts out of soft wrapping
    e, out, _ = make_recording_emitter(force_terminal=False, soft_wrap=False)

    # When emitting a message longer than the console width
    e.info(LONG_PATH)

    # Then the message is folded
    assert LONG_PATH not in out.export_text()


def test_soft_wrap_true_on_terminal(make_recording_emitter: RecordingEmitterFactory) -> None:
    """Verify soft_wrap=True suppresses folding even on an interactive terminal."""
    # Given an emitter that explicitly opts into soft wrapping
    e, out, _ = make_recording_emitter(force_terminal=True, soft_wrap=True)

    # When emitting a message longer than the console width
    e.info(LONG_PATH)

    # Then the message survives intact
    assert LONG_PATH in out.export_text()


def test_configure_soft_wrap(make_recording_emitter: RecordingEmitterFactory) -> None:
    """Verify configure() updates the soft-wrap setting after construction."""
    # Given a terminal emitter that folds by default
    e, out, _ = make_recording_emitter(force_terminal=True)

    # When soft wrapping is turned on after construction
    e.configure(soft_wrap=True)
    e.info(LONG_PATH)

    # Then the message survives intact
    assert LONG_PATH in out.export_text()


def test_per_call_soft_wrap_overrides_emitter(
    make_recording_emitter: RecordingEmitterFactory,
) -> None:
    """Verify a per-call soft_wrap kwarg takes precedence over the emitter setting."""
    # Given an emitter configured to soft wrap
    e, out, _ = make_recording_emitter(force_terminal=True, soft_wrap=True)

    # When a single call opts out
    e.info(LONG_PATH, soft_wrap=False)

    # Then that message is folded
    assert LONG_PATH not in out.export_text()


@pytest.mark.usefixtures("isolated_default")
def test_module_level_configure_soft_wrap() -> None:
    """Verify the module-level configure() forwards soft_wrap to the default emitter."""
    # Given the default emitter wired to a recording terminal console
    out = Console(record=True, force_terminal=True, width=80, color_system="truecolor")
    pp.configure(console=out)

    # When soft wrapping is turned on through the module-level API
    pp.configure(soft_wrap=True)
    pp.info(LONG_PATH)

    # Then the message survives intact
    assert LONG_PATH in out.export_text()


def test_soft_wrap_resolves_per_console() -> None:
    """Verify auto-detection resolves against each console, not the emitter as a whole."""
    # Given a captured stdout and an interactive stderr
    out = Console(record=True, file=StringIO(), width=80, color_system="truecolor")
    err = Console(record=True, force_terminal=True, width=80, color_system="truecolor")
    e = Emitter(console=out, err_console=err)

    # When the same long message goes to each stream
    e.info(LONG_PATH)
    e.error(LONG_PATH)

    # Then only the captured stream is left unfolded
    assert LONG_PATH in out.export_text()
    assert LONG_PATH not in err.export_text()
