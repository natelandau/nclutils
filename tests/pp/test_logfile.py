"""Tests for file-logging behavior on `Emitter` (logfile, loglevel, logfmt)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from rich.json import JSON
from rich.text import Text

from nclutils.pp._logsink import _LogSink
from nclutils.pp.emitter import Emitter, LogLevel, Verbosity

if TYPE_CHECKING:
    from collections.abc import Callable

    from .conftest import RecordingEmitterFactory


class TestLogSinkModule:
    """`nclutils.pp._logsink` registers TRACE at import and exposes _LogSink."""

    def test_trace_level_name_registered(self) -> None:
        """Verify importing _logsink registers level 5 as 'TRACE' with stdlib logging."""
        # When asking stdlib logging for the name of level 5
        # Then it returns "TRACE"
        assert logging.getLevelName(5) == "TRACE"

    def test_logsink_class_is_importable(self) -> None:
        """Verify _LogSink is exposed from the private module."""
        assert isinstance(_LogSink, type)


class TestLogSinkLazyFileCreation:
    """The logfile is opened lazily on first emit, not at sink construction."""

    def test_constructing_logsink_does_not_create_file(self, tmp_path: Path) -> None:
        """Verify _LogSink(logfile=path) does not touch the filesystem."""
        path = tmp_path / "run.log"
        _LogSink(logfile=path)
        assert not path.exists()

    def test_first_emit_creates_file_and_writes_record(self, tmp_path: Path) -> None:
        """Verify the first emit() call creates the file and writes one record."""
        # Given a sink configured with a path
        path = tmp_path / "run.log"
        sink = _LogSink(logfile=path)

        # When emit is called once
        sink.emit(level=logging.INFO, message="hello world", details=None)

        # Then the file exists and contains one matching record
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "INFO" in content
        assert "hello world" in content

    def test_emit_with_logfile_none_is_a_noop(self, tmp_path: Path) -> None:
        """Verify _LogSink(logfile=None).emit() does nothing and creates no files."""
        # Given a sink with no logfile
        sink = _LogSink(logfile=None)

        # When emit is called
        sink.emit(level=logging.INFO, message="hello", details=None)

        # Then no files were created in the test directory (sanity)
        assert list(tmp_path.iterdir()) == []


class TestLogSinkDefaultFormat:
    """Records produced by `_LogSink` match the documented default format."""

    def test_record_format_has_timestamp_level_message(self, tmp_path: Path) -> None:
        """Verify the default format is 'YYYY-MM-DD HH:MM:SS.fff | LEVEL    | message'."""
        # Given a sink with a logfile and the default format
        path = tmp_path / "run.log"
        sink = _LogSink(logfile=path)

        # When a record is written
        sink.emit(level=logging.INFO, message="formatted", details=None)

        # Then the line matches the documented shape
        line = path.read_text(encoding="utf-8").splitlines()[0]
        pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \| INFO\s{4} \| formatted$"
        assert re.match(pattern, line), f"line did not match expected format: {line!r}"


class TestLogSinkOpenErrorsSurface:
    """File open failures raise on the first emit, not silently."""

    def test_emit_raises_when_parent_dir_missing(self, tmp_path: Path) -> None:
        """Verify emit raises FileNotFoundError when the parent directory does not exist."""
        # Given a sink whose logfile path has a missing parent directory
        bad_path = tmp_path / "does-not-exist" / "run.log"
        sink = _LogSink(logfile=bad_path)

        # When emit is called
        # Then FileNotFoundError surfaces (no silent swallow)
        with pytest.raises(FileNotFoundError):
            sink.emit(level=logging.INFO, message="should fail", details=None)


class TestEmitterLogfileBasics:
    """Each level method writes one record to the logfile at the expected severity."""

    @pytest.mark.parametrize(
        ("method", "expected_level_token"),
        [
            ("info", "INFO"),
            ("success", "INFO"),  # success logs at INFO; not a real severity
            ("warning", "WARNING"),
            ("error", "ERROR"),
            ("critical", "CRITICAL"),
        ],
    )
    def test_level_method_writes_at_expected_severity(
        self, tmp_path: Path, method: str, expected_level_token: str
    ) -> None:
        """Verify each non-verbose level method writes one record with the expected severity name."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        getattr(e, method)("hello")
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert expected_level_token in lines[0]
        assert "hello" in lines[0]

    def test_dryrun_logs_at_info_with_inline_tag(self, tmp_path: Path) -> None:
        """Verify dryrun() logs at INFO and the [dry-run] tag survives in the message text."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.dryrun("would delete /tmp")
        line = path.read_text(encoding="utf-8").splitlines()[0]
        assert "INFO" in line
        assert "[dry-run]" in line
        assert "would delete /tmp" in line

    def test_header_is_console_only(self, tmp_path: Path) -> None:
        """Verify header() does not produce any log records."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.header("Section")
        if path.exists():
            assert path.read_text(encoding="utf-8") == ""

    def test_verbose_levels_write_when_verbosity_low_for_console_but_logfile_open(
        self, tmp_path: Path
    ) -> None:
        """Verify file output ignores verbosity (console-only gate); only loglevel filters the file."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)  # verbosity stays default (INFO)
        e.debug("diagnostic")
        # No record: even though verbosity gates console, loglevel default INFO filters DEBUG (10) out.
        # Verifies we route through stdlib filtering, not bypass it.
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        assert "diagnostic" not in text


class TestLogLevelFilter:
    """`loglevel` filters file output by stdlib-aligned numeric severity."""

    def test_loglevel_warning_drops_info_and_below(self, tmp_path: Path) -> None:
        """Verify loglevel=WARNING filters out info/success/dryrun/debug/trace."""
        path = tmp_path / "run.log"
        e = Emitter(
            logfile=path,
            loglevel=LogLevel.WARNING,
            verbosity=Verbosity.TRACE,
        )

        # When all levels emit
        e.trace("trace-line")
        e.debug("debug-line")
        e.info("info-line")
        e.success("success-line")
        e.dryrun("dryrun-line")
        e.warning("warning-line")
        e.error("error-line")
        e.critical("critical-line")

        # Then only warning, error, and critical lines made it to the file
        text = path.read_text(encoding="utf-8")
        assert "warning-line" in text
        assert "error-line" in text
        assert "critical-line" in text
        assert "trace-line" not in text
        assert "debug-line" not in text
        assert "info-line" not in text
        assert "success-line" not in text
        assert "dryrun-line" not in text

    def test_loglevel_trace_captures_everything(self, tmp_path: Path) -> None:
        """Verify loglevel=TRACE captures all eight emit levels."""
        # Given an Emitter at TRACE verbosity and TRACE loglevel
        path = tmp_path / "run.log"
        e = Emitter(
            logfile=path,
            loglevel=LogLevel.TRACE,
            verbosity=Verbosity.TRACE,
        )

        # When all levels emit
        e.trace("t")
        e.debug("d")
        e.info("i")
        e.success("s")
        e.dryrun("dr")
        e.warning("w")
        e.error("e")
        e.critical("c")

        # Then all eight messages appear in the file
        text = path.read_text(encoding="utf-8")
        for token in ("| t", "| d", "| i", "| s", "[dry-run] dr", "| w", "| e", "| c"):
            assert token in text, f"missing {token!r} in:\n{text}"


class TestLogFmtOverride:
    """`logfmt` is a custom stdlib-style format string applied verbatim."""

    def test_custom_format_string_is_applied(self, tmp_path: Path) -> None:
        """Verify a custom logfmt rewrites the file output shape."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path, logfmt="<%(levelname)s>%(message)s</%(levelname)s>")

        # When info is emitted
        e.info("hi")

        # Then the file uses the custom shape
        line = path.read_text(encoding="utf-8").splitlines()[0]
        assert line == "<INFO>hi</INFO>"


class TestVerboseElapsedTagInLogfile:
    """The `[+s.fffs]` elapsed tag from debug/trace appears inline in the file."""

    def test_debug_logfile_record_includes_elapsed_tag(self, tmp_path: Path) -> None:
        """Verify debug() inlines the elapsed tag into the file's message text."""
        # Given an Emitter at DEBUG loglevel and DEBUG verbosity
        path = tmp_path / "run.log"
        e = Emitter(
            logfile=path,
            loglevel=LogLevel.DEBUG,
            verbosity=Verbosity.DEBUG,
        )

        # When debug emits
        e.debug("step done")

        # Then the file line contains the inlined `[+s.fffs]` tag
        line = path.read_text(encoding="utf-8").splitlines()[0]
        assert "step done" in line
        # Tag shape: `[+0.000s]` -- digit/dot/digits/`s]`

        assert re.search(r"\[\+\d+\.\d{3}s\]", line), f"missing elapsed tag in: {line!r}"


class TestReconfiguration:
    """`configure()` swaps logfiles, updates loglevel, and updates logfmt cleanly."""

    def test_configure_swaps_logfile(self, tmp_path: Path) -> None:
        """Verify configure(logfile=other) closes the old handler and writes to the new file."""
        path_a = tmp_path / "a.log"
        path_b = tmp_path / "b.log"
        e = Emitter(logfile=path_a)
        e.info("first")

        e.configure(logfile=path_b)
        e.info("second")

        text_a = path_a.read_text(encoding="utf-8")
        text_b = path_b.read_text(encoding="utf-8")
        assert "first" in text_a
        assert "second" not in text_a
        assert "second" in text_b
        assert "first" not in text_b

    def test_configure_with_same_logfile_path_is_a_noop(self, tmp_path: Path) -> None:
        """Verify configure(logfile=same_path) does not reopen the file."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("first")
        first_handler_id = id(e._logsink._handler)

        e.configure(logfile=path)
        e.info("second")

        text = path.read_text(encoding="utf-8")
        assert "first" in text
        assert "second" in text
        assert id(e._logsink._handler) == first_handler_id

    def test_configure_updates_loglevel_in_place(self, tmp_path: Path) -> None:
        """Verify configure(loglevel=...) updates the existing handler's level."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path, verbosity=Verbosity.DEBUG)
        e.debug("muted")

        e.configure(loglevel=LogLevel.DEBUG)
        e.debug("captured")

        text = path.read_text(encoding="utf-8")
        assert "captured" in text
        assert "muted" not in text

    def test_configure_updates_logfmt_in_place(self, tmp_path: Path) -> None:
        """Verify configure(logfmt=...) updates the existing handler's formatter."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("default-format")

        e.configure(logfmt="X|%(message)s")
        e.info("custom-format")

        lines = path.read_text(encoding="utf-8").splitlines()
        assert "default-format" in lines[0]
        assert lines[0] != "X|default-format"
        assert lines[1] == "X|custom-format"

    def test_configure_logfile_none_is_a_noop_does_not_disable(self, tmp_path: Path) -> None:
        """Verify configure(logfile=None) does not disable an already-configured logfile."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("before")

        e.configure(logfile=None)
        e.info("after")

        text = path.read_text(encoding="utf-8")
        assert "before" in text
        assert "after" in text


class TestMultipleEmittersSameFile:
    """Two `Emitter` instances pointed at the same logfile each open their own handler and write independently."""

    def test_two_emitters_share_the_same_file_with_isolated_handlers(self, tmp_path: Path) -> None:
        """Verify each Emitter holds its own handler/logger; both writes land in the same file."""
        path = tmp_path / "shared.log"
        e1 = Emitter(logfile=path)
        e2 = Emitter(logfile=path)

        e1.info("from emitter one")
        e2.info("from emitter two")

        text = path.read_text(encoding="utf-8")
        assert "from emitter one" in text
        assert "from emitter two" in text

        assert e1._logsink._handler is not None
        assert e2._logsink._handler is not None
        assert e1._logsink._handler is not e2._logsink._handler
        assert e1._logsink._logger is not e2._logsink._logger


class TestDetailsInLogfile:
    """`details` items render to text and emit as separate log records at the parent's level."""

    def test_string_detail_emits_indented_continuation_at_parent_level(
        self, tmp_path: Path
    ) -> None:
        """Verify a string detail produces one indented continuation record."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("processing", details=["foo.toml"])

        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert "INFO" in lines[0]
        assert "processing" in lines[0]
        assert "INFO" in lines[1]
        assert "  foo.toml" in lines[1]

    def test_string_detail_strips_rich_markup(self, tmp_path: Path) -> None:
        """Verify Rich markup like [red]...[/] is stripped from string details in the file."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("processing", details=["[red]colored[/]"])

        text = path.read_text(encoding="utf-8")
        assert "  colored" in text
        assert "[red]" not in text
        assert "[/]" not in text

    def test_markup_true_message_strips_brackets_in_logfile(self, tmp_path: Path) -> None:
        """Verify markup=True messages have Rich markup stripped before being written to the logfile."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("[bold]processing[/]", markup=True)

        text = path.read_text(encoding="utf-8")
        assert "processing" in text
        assert "[bold]" not in text
        assert "[/]" not in text

    def test_text_instance_message_writes_plain_to_logfile(self, tmp_path: Path) -> None:
        """Verify a Text instance message is written to the logfile as its plain text."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info(Text.from_markup("[bold]processing[/]"))

        text = path.read_text(encoding="utf-8")
        assert "processing" in text
        assert "[bold]" not in text
        assert "[/]" not in text

    def test_dict_detail_renders_as_pretty_continuation_lines(self, tmp_path: Path) -> None:
        """Verify a dict detail renders via Pretty into one or more indented continuation records."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("response", details=[{"status": 200, "kind": "ok"}])

        lines = path.read_text(encoding="utf-8").splitlines()
        assert any("response" in line for line in lines)
        joined_continuations = "\n".join(line for line in lines if "  " in line)
        assert "status" in joined_continuations
        assert "200" in joined_continuations
        assert "kind" in joined_continuations
        for line in lines:
            assert "INFO" in line, f"unexpected severity in: {line!r}"

    def test_renderable_detail_strips_color_in_file(self, tmp_path: Path) -> None:
        """Verify a Rich JSON renderable produces uncolored continuation records."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("payload", details=[JSON('{"a": 1}')])

        text = path.read_text(encoding="utf-8")
        assert "\x1b[" not in text
        assert '"a"' in text
        assert "1" in text

    def test_multiline_string_detail_emits_multiple_records(self, tmp_path: Path) -> None:
        r"""Verify '\n' inside a string detail produces one record per line, all indented."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)
        e.info("issues", details=["error A\nerror B"])

        lines = path.read_text(encoding="utf-8").splitlines()
        assert any("  error A" in line for line in lines)
        assert any("  error B" in line for line in lines)

    def test_continuation_records_inherit_parent_severity(self, tmp_path: Path) -> None:
        """Verify a debug() call with details emits all records at DEBUG, droppable by an INFO filter."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path, loglevel=LogLevel.DEBUG, verbosity=Verbosity.DEBUG)
        e.debug("verbose op", details=["context line"])

        lines = path.read_text(encoding="utf-8").splitlines()
        assert all("DEBUG" in line for line in lines), lines

        path2 = tmp_path / "run2.log"
        e.configure(logfile=path2, loglevel=LogLevel.INFO)
        e.debug("filtered op", details=["filtered context"])
        text = path2.read_text(encoding="utf-8") if path2.exists() else ""
        assert "filtered op" not in text
        assert "filtered context" not in text


class TestStepLifecycleInLogfile:
    """`step()` writes start/succeeded/failed records and `Step.sub()` logs immediately."""

    def test_step_clean_exit_writes_starting_and_succeeded(self, tmp_path: Path) -> None:
        """Verify a successful step writes 'starting:' on entry and 'succeeded:' on exit."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)

        with e.step("build assets"):
            pass

        lines = path.read_text(encoding="utf-8").splitlines()
        assert any("starting: build assets" in line and "INFO" in line for line in lines)
        assert any("succeeded: build assets" in line and "INFO" in line for line in lines)
        starting_idx = next(i for i, line in enumerate(lines) if "starting: build assets" in line)
        succeeded_idx = next(i for i, line in enumerate(lines) if "succeeded: build assets" in line)
        assert starting_idx < succeeded_idx

    def test_step_failure_writes_starting_and_failed_with_continuation(
        self, tmp_path: Path
    ) -> None:
        """Verify a step calling fail(exception=) writes 'starting:' then 'failed:' at ERROR with the exception as a continuation."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)

        msg = "boom"
        with e.step("flaky thing") as s:
            try:
                raise RuntimeError(msg)
            except RuntimeError as caught:
                s.fail("flaky thing", exception=caught)

        lines = path.read_text(encoding="utf-8").splitlines()
        assert any("starting: flaky thing" in line and "INFO" in line for line in lines)
        failed_lines = [line for line in lines if "failed: flaky thing" in line]
        assert len(failed_lines) == 1
        assert "ERROR" in failed_lines[0]
        cont_lines = [line for line in lines if "RuntimeError" in line and "boom" in line]
        assert len(cont_lines) == 1
        assert "ERROR" in cont_lines[0]

    def test_step_ephemeral_still_logs_all_three_events(self, tmp_path: Path) -> None:
        """Verify ephemeral=True does NOT suppress lifecycle records in the file."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)

        with e.step("invisible", ephemeral=True):
            pass

        text = path.read_text(encoding="utf-8")
        assert "starting: invisible" in text
        assert "succeeded: invisible" in text

    def test_step_sub_writes_immediately_during_step(self, tmp_path: Path) -> None:
        """Verify `Step.sub("x")` writes its line during the step, not after."""
        path = tmp_path / "run.log"
        e = Emitter(logfile=path)

        with e.step("processing") as s:
            s.sub("file-1")
            s.sub("file-2")
            mid_step_text = path.read_text(encoding="utf-8")

        assert "file-1" in mid_step_text
        assert "file-2" in mid_step_text
        assert "succeeded: processing" not in mid_step_text
        final_text = path.read_text(encoding="utf-8")
        assert "succeeded: processing" in final_text


class TestLogfileAcceptsStringPaths:
    """`logfile=` accepts a `str` or `Path` and normalizes to `Path` internally."""

    def test_string_logfile_at_construction_creates_file_and_writes(
        self, tmp_path: Path, debug: Callable
    ) -> None:
        """Verify Emitter(logfile=str(...)) is accepted and writes to the named file."""
        # Given a string path to the logfile
        path_str = str(tmp_path / "run.log")
        e = Emitter(logfile=path_str)

        # When info is emitted
        e.info("hello")

        # Then the file at the expected location has the record
        assert Path(path_str).exists()
        assert "hello" in Path(path_str).read_text(encoding="utf-8")

    def test_string_logfile_normalized_to_path_object(self, tmp_path: Path) -> None:
        """Verify a str logfile is converted to Path internally so downstream code sees a Path."""
        # Given an emitter constructed with a str logfile
        path_str = str(tmp_path / "run.log")
        e = Emitter(logfile=path_str)

        # Then the internal logfile attribute is a Path, not a str
        assert isinstance(e._logsink._logfile, Path)
        assert e._logsink._logfile == Path(path_str)

    def test_string_logfile_at_configure_swaps_correctly(self, tmp_path: Path) -> None:
        """Verify configure(logfile=str(...)) reconfigures to the named file."""
        # Given an emitter writing to file A (as Path)
        path_a = tmp_path / "a.log"
        path_b_str = str(tmp_path / "b.log")
        e = Emitter(logfile=path_a)
        e.info("first")

        # When configure swaps to file B passed as a string
        e.configure(logfile=path_b_str)
        e.info("second")

        # Then file A has only "first" and file B has only "second"
        assert "first" in path_a.read_text(encoding="utf-8")
        assert "second" not in path_a.read_text(encoding="utf-8")
        assert Path(path_b_str).exists()
        assert "second" in Path(path_b_str).read_text(encoding="utf-8")
        assert "first" not in Path(path_b_str).read_text(encoding="utf-8")

    def test_string_and_path_for_same_file_are_equivalent_no_op(self, tmp_path: Path) -> None:
        """Verify configure(logfile=Path) after Emitter(logfile=str) for the same file is a no-op."""
        # Given an emitter constructed with a str logfile that has already been opened
        path_str = str(tmp_path / "run.log")
        path_obj = tmp_path / "run.log"
        e = Emitter(logfile=path_str)
        e.info("first")
        first_handler_id = id(e._logsink._handler)

        # When configure is called with the same path as a Path object
        e.configure(logfile=path_obj)
        e.info("second")

        # Then both records are in the same file and the handler was not replaced
        text = path_obj.read_text(encoding="utf-8")
        assert "first" in text
        assert "second" in text
        assert id(e._logsink._handler) == first_handler_id


class TestLogfileTreeGlyphs:
    """Tree connectors render to stdout/stderr only and never leak into the logfile."""

    def test_logfile_does_not_contain_tree_glyphs(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify tree connectors live on stdout only and never leak into the logfile."""
        # Given an Emitter wired to a logfile at TRACE level
        logfile = tmp_path / "out.log"
        e, _, _ = make_recording_emitter(
            verbosity=Verbosity.TRACE,
            logfile=logfile,
            loglevel=LogLevel.TRACE,
        )

        # When several level methods emit with multiple details
        e.info("hi", details=["a", "b", "c"])
        e.error("boom", details=["x", "y"])

        # Then the logfile contains the detail text but none of the tree glyphs
        contents = logfile.read_text()
        assert "a" in contents
        assert "x" in contents
        assert "├─" not in contents
        assert "└─" not in contents
        assert "│" not in contents
