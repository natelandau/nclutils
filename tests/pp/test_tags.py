"""Tests for per-call `tag` and `right_tag` kwargs on level methods."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nclutils import pp
from nclutils.pp.emitter import LogLevel, Verbosity, set_default

if TYPE_CHECKING:
    from pathlib import Path

    from .conftest import RecordingEmitterFactory


class TestTagRendering:
    """The `tag` kwarg renders dim between marker and message."""

    @pytest.mark.parametrize("method", ["info", "success", "dryrun"])
    def test_tag_appears_in_stdout_output(
        self, make_recording_emitter: RecordingEmitterFactory, method: str
    ) -> None:
        """Verify tag kwarg renders between marker and message on stdout levels."""
        # Given an emitter wired to a recording stdout console
        e, out, _ = make_recording_emitter()

        # When the level method is called with a tag
        getattr(e, method)("hello", tag="api")

        # Then the tag appears in the rendered text alongside the message
        text = out.export_text()
        assert "api" in text
        assert "hello" in text

    @pytest.mark.parametrize("method", ["warning", "error", "critical"])
    def test_tag_appears_in_stderr_output(
        self, make_recording_emitter: RecordingEmitterFactory, method: str
    ) -> None:
        """Verify tag kwarg renders alongside message on stderr levels."""
        # Given an emitter wired to a recording stderr console
        e, _, err = make_recording_emitter()

        # When the level method is called with a tag
        getattr(e, method)("hello", tag="api")

        # Then the tag appears in stderr alongside the message
        text = err.export_text()
        assert "api" in text
        assert "hello" in text

    @pytest.mark.parametrize("method", ["debug", "trace"])
    def test_tag_appears_for_debug_and_trace(
        self, make_recording_emitter: RecordingEmitterFactory, method: str
    ) -> None:
        """Verify tag kwarg renders alongside debug/trace output when verbosity allows."""
        # Given a TRACE-verbosity emitter so debug and trace render
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When the verbose level method is called with a tag
        getattr(e, method)("hello", tag="api")

        # Then the tag appears in the recorded stdout
        text = out.export_text()
        assert "api" in text
        assert "hello" in text


class TestRightTagRendering:
    """The `right_tag` kwarg renders dim, right-aligned on the first line."""

    def test_right_tag_appears_in_output(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify right_tag kwarg renders alongside info-level output."""
        # Given an emitter wired to a recording stdout console
        e, out, _ = make_recording_emitter()

        # When info is called with a right_tag
        e.info("saved", right_tag="200ms")

        # Then the right_tag appears in the rendered text
        text = out.export_text()
        assert "saved" in text
        assert "200ms" in text


class TestDryrunTagComposition:
    """`dryrun` combines caller-supplied `tag` with the existing `[dry-run]` tag."""

    def test_caller_tag_combines_with_dryrun_marker_on_console(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify caller tag renders before [dry-run] on the dryrun console output."""
        # Given an emitter wired to a recording stdout console
        e, out, _ = make_recording_emitter()

        # When dryrun is called with a caller tag
        e.dryrun("would deploy", tag="deploy")

        # Then both tags render and the caller's tag precedes [dry-run]
        text = out.export_text()
        assert "deploy" in text
        assert "[dry-run]" in text
        assert text.index("deploy") < text.index("[dry-run]")

    def test_caller_tag_combines_with_dryrun_marker_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify caller tag and [dry-run] both record inline in the dryrun logfile message."""
        # Given an emitter with a logfile attached
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When dryrun is called with a caller tag
        e.dryrun("would deploy", tag="deploy")

        # Then the logfile contains both tags inline with the caller's tag first
        contents = logfile.read_text()
        assert "[deploy] [dry-run] would deploy" in contents

    def test_dryrun_without_tag_keeps_existing_behavior(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify dryrun without a caller tag still records [dry-run] inline as before."""
        # Given an emitter with a logfile attached
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When dryrun is called without a tag
        e.dryrun("would deploy")

        # Then the logfile contains the [dry-run] marker but no extra caller tag
        contents = logfile.read_text()
        assert "[dry-run] would deploy" in contents


class TestDebugTraceRightTagConflict:
    """Caller's right_tag replaces the auto-elapsed timestamp on console."""

    def test_caller_right_tag_replaces_elapsed_on_console(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify caller-supplied right_tag replaces auto-elapsed [+s] tag on console."""
        # Given a TRACE-verbosity emitter
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When debug is called with an explicit right_tag
        e.debug("query", right_tag="db: 1.2s")

        # Then the caller's tag appears and the auto-elapsed marker is absent on console
        text = out.export_text()
        assert "db: 1.2s" in text
        # the auto-elapsed marker uses [+s.fffs] format
        assert "[+" not in text

    def test_caller_right_tag_replaces_elapsed_on_trace_console(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify caller-supplied right_tag replaces auto-elapsed [+s] tag for trace too."""
        # Given a TRACE-verbosity emitter
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When trace is called with an explicit right_tag
        e.trace("event", right_tag="rpc: 0.4s")

        # Then the caller's tag appears and the auto-elapsed marker is absent on console
        text = out.export_text()
        assert "rpc: 0.4s" in text
        assert "[+" not in text


class TestTagInLogfile:
    """`tag` is recorded inline in the logfile message; `right_tag` is presentation-only."""

    def test_tag_appears_inline_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify tag appears as `[tag] msg` in the logfile."""
        # Given an emitter with a logfile attached
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When info is called with a tag
        e.info("saved", tag="api")

        # Then the logfile contains `[api] saved`
        contents = logfile.read_text()
        assert "[api] saved" in contents

    def test_right_tag_absent_from_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify right_tag does NOT appear in the logfile."""
        # Given an emitter with a logfile attached
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When info is called with a right_tag
        e.info("saved", right_tag="200ms")

        # Then the logfile does NOT contain the right_tag value
        contents = logfile.read_text()
        assert "saved" in contents
        assert "200ms" not in contents

    def test_debug_logfile_keeps_elapsed_when_right_tag_set(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify debug logfile keeps auto-elapsed [+s] even when caller passes right_tag."""
        # Given a TRACE-verbosity emitter with a TRACE-loglevel logfile so debug is captured
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(
            verbosity=Verbosity.TRACE,
            logfile=logfile,
            loglevel=LogLevel.TRACE,
        )

        # When debug is called with an explicit right_tag
        e.debug("query", right_tag="db: 1.2s")

        # Then the logfile contains the [+s] elapsed marker (preserves audit trail)
        contents = logfile.read_text()
        assert "[+" in contents

    def test_trace_logfile_keeps_elapsed_when_right_tag_set(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify trace logfile keeps auto-elapsed [+s] even when caller passes right_tag."""
        # Given a TRACE-verbosity emitter with a TRACE-loglevel logfile so trace is captured
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(
            verbosity=Verbosity.TRACE,
            logfile=logfile,
            loglevel=LogLevel.TRACE,
        )

        # When trace is called with an explicit right_tag
        e.trace("event", right_tag="rpc: 0.4s")

        # Then the logfile retains the elapsed marker
        contents = logfile.read_text()
        assert "[+" in contents

    @pytest.mark.parametrize(
        "method",
        ["info", "success", "warning", "error", "critical"],
    )
    def test_tag_inline_for_non_dryrun_levels(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
        method: str,
    ) -> None:
        """Verify tag renders as `[tag] msg` in the logfile across non-dryrun levels."""
        # Given an emitter with a logfile attached
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When the level method is called with a tag
        getattr(e, method)("hello", tag="api")

        # Then the logfile records the tag inline
        contents = logfile.read_text()
        assert "[api] hello" in contents


class TestModuleLevelDelegation:
    """Module-level functions forward tag/right_tag to the default emitter."""

    @pytest.mark.usefixtures("isolated_default")
    def test_module_level_info_forwards_tag(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify module-level pp.info() forwards tag through to the default emitter."""
        # Given an isolated default emitter wired to a recording console
        e, out, _ = make_recording_emitter()
        set_default(e)

        # When the module-level function is called with a tag
        pp.info("hello", tag="api")

        # Then the tag appears in the recorded output
        text = out.export_text()
        assert "api" in text
        assert "hello" in text

    @pytest.mark.usefixtures("isolated_default")
    @pytest.mark.parametrize(
        "method",
        ["info", "success", "warning", "error", "critical", "dryrun"],
    )
    def test_module_level_levels_forward_right_tag(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
    ) -> None:
        """Verify module-level level functions forward right_tag through to the default emitter."""
        # Given an isolated default emitter wired to a recording console
        e, out, err = make_recording_emitter()
        set_default(e)

        # When the module-level function is called with a right_tag
        getattr(pp, method)("hello", right_tag="200ms")

        # Then the right_tag appears in the recorded output (stdout or stderr)
        combined = out.export_text() + err.export_text()
        assert "200ms" in combined
        assert "hello" in combined

    @pytest.mark.usefixtures("isolated_default")
    @pytest.mark.parametrize("method", ["debug", "trace"])
    def test_module_level_debug_trace_forward_right_tag(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
    ) -> None:
        """Verify module-level debug/trace forward right_tag and replace the elapsed marker."""
        # Given an isolated TRACE-verbosity default emitter
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)
        set_default(e)

        # When the module-level function is called with a right_tag
        getattr(pp, method)("hello", right_tag="custom")

        # Then the caller's right_tag replaces the auto-elapsed marker on the console
        text = out.export_text()
        assert "custom" in text
        assert "[+" not in text
