"""Tests for the exception= kwarg on level methods."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nclutils import pp
from nclutils.pp.constants import Verbosity
from nclutils.pp.emitter import set_default

if TYPE_CHECKING:
    from pathlib import Path

    from .conftest import RecordingEmitterFactory


def _capture(exc_cls: type[BaseException], message: str) -> BaseException:
    """Raise `exc_cls(message)`, catch it, and return the captured instance with a traceback."""
    try:
        raise exc_cls(message)  # noqa: TRY301 -- inner raise IS the test setup; cannot abstract further
    except BaseException as exc:  # noqa: BLE001 -- intentional broad catch to relay any subtype
        return exc


def _raises_with_local() -> None:
    """Raise RuntimeError after binding a distinctive local for show_locals dump tests."""
    local_marker = "sentinel_value_42"  # noqa: F841 -- inspected via show_locals dump
    msg = "boom"
    raise RuntimeError(msg)


class TestExceptionInstance:
    """exception=<BaseException instance> appends a Traceback to the rendered output."""

    def test_exception_instance_renders_traceback(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify passing an exception instance renders a Rich Traceback below the message."""
        # Given an emitter wired to recording stderr and a captured exception
        e, _, err = make_recording_emitter()
        captured = _capture(RuntimeError, "403 Forbidden")

        # When error is called with the exception instance
        e.error("upload failed", exception=captured)

        # Then both the message and the traceback identifying info appear
        text = err.export_text()
        assert "upload failed" in text
        assert "RuntimeError" in text
        assert "403 Forbidden" in text

    def test_exception_instance_appended_after_existing_details(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify the traceback is appended as the final detail item, after any caller details."""
        # Given an emitter and a captured exception with caller-supplied details
        e, _, err = make_recording_emitter()
        captured = _capture(RuntimeError, "boom")

        # When error is called with both details and an exception
        e.error("failed", details=["target: prod"], exception=captured)

        # Then the original detail and the traceback both render
        text = err.export_text()
        assert "target: prod" in text
        assert "RuntimeError" in text
        # Traceback should appear after the caller-supplied detail in the stream
        assert text.index("target: prod") < text.index("RuntimeError")


class TestExceptionTrue:
    """exception=True grabs sys.exc_info() inside an except block."""

    def test_exception_true_inside_except_block(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify exception=True inside an except block uses sys.exc_info()."""
        # Given an emitter wired to recording stderr
        e, _, err = make_recording_emitter()

        # When error is called with exception=True inside an except block
        try:
            msg = "boom"
            raise ValueError(msg)  # noqa: TRY301 -- direct raise required to populate sys.exc_info
        except ValueError:
            e.error("operation failed", exception=True)

        # Then the traceback for the active exception appears
        text = err.export_text()
        assert "ValueError" in text
        assert "boom" in text

    def test_exception_true_outside_except_is_noop(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify exception=True outside an except block is a silent no-op."""
        # Given an emitter wired to recording stderr (no active exception)
        e, _, err = make_recording_emitter()

        # When error is called with exception=True outside any except block
        e.error("operation failed", exception=True)

        # Then the message renders but no Traceback frame appears
        text = err.export_text()
        assert "operation failed" in text
        assert "Traceback" not in text

    def test_exception_true_outside_except_has_no_logfile_traceback(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify exception=True outside an except block leaves the logfile traceback-free."""
        # Given an emitter with a logfile and no active exception
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When error is called with exception=True outside any except block
        e.error("operation failed", exception=True)

        # Then the logfile records the message but no traceback markers
        contents = logfile.read_text()
        assert "operation failed" in contents
        assert "Traceback" not in contents


class TestShowLocals:
    """show_locals flows through to Rich's Traceback for verbose dumps."""

    def test_show_locals_true_includes_local_variable(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify show_locals=True surfaces a frame's local variables in the rendered traceback."""
        # Given an emitter and a function that raises with a distinctive local variable
        e, _, err = make_recording_emitter()
        try:
            _raises_with_local()
        except RuntimeError as exc:
            captured = exc

        # When error is called with show_locals=True
        e.error("boom", exception=captured, show_locals=True)

        # Then the local variable marker appears in the dumped traceback
        text = err.export_text()
        assert "local_marker" in text
        assert "sentinel_value_42" in text


class TestExceptionLogfile:
    """Tracebacks are written to the logfile as continuation lines."""

    def test_traceback_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify the formatted traceback string is written to the logfile."""
        # Given an emitter with a logfile and a captured exception
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)
        captured = _capture(RuntimeError, "403 Forbidden")

        # When error is called with the exception instance
        e.error("upload failed", exception=captured)

        # Then the logfile records both the message and the formatted traceback
        contents = logfile.read_text()
        assert "upload failed" in contents
        assert "RuntimeError" in contents
        assert "403 Forbidden" in contents
        assert "Traceback (most recent call last)" in contents

    def test_logfile_traceback_uses_parent_severity(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify each traceback continuation line is logged at the parent record's severity."""
        # Given an emitter with a logfile and a captured exception
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)
        captured = _capture(RuntimeError, "soft fail")

        # When warning is called with the exception
        e.warning("retrying", exception=captured)

        # Then every traceback continuation line is tagged WARNING (not INFO)
        contents = logfile.read_text()
        traceback_lines = [line for line in contents.splitlines() if "RuntimeError" in line]
        assert traceback_lines
        for line in traceback_lines:
            assert "WARNING" in line


class TestExceptionAcrossLevels:
    """exception= works on every level method."""

    @pytest.mark.parametrize(
        ("method", "to_stderr", "verbosity_needed"),
        [
            ("info", False, False),
            ("success", False, False),
            ("warning", True, False),
            ("error", True, False),
            ("critical", True, False),
            ("debug", False, True),
            ("trace", False, True),
            ("dryrun", False, False),
        ],
    )
    def test_exception_appears_on_each_level(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
        *,
        to_stderr: bool,
        verbosity_needed: bool,
    ) -> None:
        """Verify exception= renders a traceback on every level method."""
        # Given an emitter with verbosity high enough to surface debug/trace
        verbosity = Verbosity.TRACE if verbosity_needed else Verbosity.INFO
        e, out, err = make_recording_emitter(verbosity=verbosity)
        captured = _capture(ValueError, "boom")

        # When the level method is called with the exception
        getattr(e, method)("something happened", exception=captured)

        # Then the traceback appears in the appropriate stream
        target_text = err.export_text() if to_stderr else out.export_text()
        assert "ValueError" in target_text
        assert "boom" in target_text


class TestModuleLevelDelegation:
    """Module-level functions forward exception/show_locals to the default emitter."""

    @pytest.mark.usefixtures("isolated_default")
    def test_module_level_error_forwards_exception(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify module-level pp.error() forwards exception= through."""
        # Given an isolated default emitter swapped in
        e, _, err = make_recording_emitter()
        set_default(e)
        captured = _capture(ValueError, "boom")

        # When pp.error is called with an exception
        pp.error("operation failed", exception=captured)

        # Then the traceback appears in the recorded stderr
        text = err.export_text()
        assert "ValueError" in text
        assert "boom" in text

    @pytest.mark.usefixtures("isolated_default")
    @pytest.mark.parametrize(
        "method",
        ["info", "success", "warning", "critical", "dryrun"],
    )
    def test_module_level_levels_forward_exception(
        self, make_recording_emitter: RecordingEmitterFactory, method: str
    ) -> None:
        """Verify each module-level function forwards exception= to the default emitter."""
        # Given an isolated default emitter swapped in
        e, out, err = make_recording_emitter()
        set_default(e)
        captured = _capture(ValueError, "boom")

        # When the matching module-level function is called with the exception
        getattr(pp, method)("something happened", exception=captured)

        # Then the traceback surfaces somewhere in the recorded output streams
        combined = out.export_text() + err.export_text()
        assert "ValueError" in combined
        assert "boom" in combined
