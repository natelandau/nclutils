"""Tests for step() success_msg kwarg and outcome-control APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rich.padding import Padding

from nclutils.pp import emitter as pp_emitter

if TYPE_CHECKING:
    from pathlib import Path

    from .conftest import RecordingEmitterFactory


class TestStepSuccessMsg:
    """`success_msg` swaps the success header text on completion."""

    def test_success_msg_replaces_header_on_success(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify success_msg appears in place of the original message on success."""
        # Given an emitter wired to a recording console
        e, out, _ = make_recording_emitter()

        # When step() runs to success with a success_msg override
        with e.step("compiling", success_msg="compiled 42 files"):
            pass

        # Then the override message appears in the rendered output
        text = out.export_text()
        assert "compiled 42 files" in text

    def test_success_msg_default_keeps_original(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify omitting success_msg preserves current behavior (original message kept)."""
        # Given an emitter wired to a recording console
        e, out, _ = make_recording_emitter()

        # When step() runs without override kwargs
        with e.step("compiling"):
            pass

        # Then the original message appears in the success line
        text = out.export_text()
        assert "compiling" in text

    def test_success_msg_renderable_replaces_header(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify success_msg accepts an arbitrary Rich renderable and the override is applied."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When step() runs to success with a renderable success_msg
        with e.step("compiling", success_msg=Padding("compiled 42 files", (0, 1))):
            pass

        # Then the override text appears in the rendered output
        text = out.export_text()
        assert "compiled 42 files" in text


class TestStepLogfile:
    """Override messages are recorded in the logfile lifecycle records."""

    def test_success_msg_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify the succeeded: line in the logfile uses success_msg when provided."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When step() succeeds with an override
        with e.step("compiling", success_msg="compiled 42 files"):
            pass

        # Then the logfile records the override message in the succeeded: line
        contents = logfile.read_text()
        assert "succeeded: compiled 42 files" in contents

    def test_success_default_logs_original_message(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify omitting success_msg keeps original message in the logfile succeeded: line."""
        # Given an emitter with a logfile and no override
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When step() succeeds without overrides
        with e.step("compiling"):
            pass

        # Then the logfile records the original message
        contents = logfile.read_text()
        assert "succeeded: compiling" in contents


class TestEphemeralStepInteraction:
    """`ephemeral=True` interacts correctly with override messages."""

    def test_ephemeral_success_records_msg_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify ephemeral success records success_msg in the logfile even though console is wiped."""
        # Given an emitter with logfile and ephemeral step
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When step() runs ephemerally with a success_msg
        with e.step("warming caches", ephemeral=True, success_msg="caches warm"):
            pass

        # Then logfile records the override message
        contents = logfile.read_text()
        assert "succeeded: caches warm" in contents


class TestModuleLevelStep:
    """Module-level `step()` forwards override kwargs to the default emitter."""

    def test_module_step_accepts_success_msg(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        isolated_default: None,
    ) -> None:
        """Verify the module-level step() forwards success_msg to the default emitter."""
        # Given the default emitter is replaced with a recording one
        e, out, _ = make_recording_emitter()
        pp_emitter.set_default(e)

        # When the module-level step() runs with a success_msg override
        with pp_emitter.step("compiling", success_msg="compiled 42 files"):
            pass

        # Then the override message appears in the rendered output
        text = out.export_text()
        assert "compiled 42 files" in text


class TestMarkupAppliesToOverrides:
    """`markup=True` parses Rich markup in success_msg."""

    def test_markup_true_parses_success_msg(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify markup=True parses Rich markup tags in success_msg."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When step() runs to success with a markup-containing override and markup=True
        with e.step("compiling", success_msg="[bold]compiled all[/]", markup=True):
            pass

        # Then the rendered output contains the message text but not the literal markup tags
        text = out.export_text()
        assert "compiled all" in text
        assert "[bold]" not in text


class TestSetSuccessMsgFromBlock:
    """`Step.set_success_msg()` updates the success header from inside the block."""

    def test_set_success_msg_replaces_header(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success_msg() applied inside the block replaces the success header."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When the block computes a result and applies it via set_success_msg
        with e.step("compiling") as s:
            count = 42
            s.set_success_msg(f"compiled {count} files")

        # Then the dynamic message appears in the rendered output
        text = out.export_text()
        assert "compiled 42 files" in text

    def test_set_success_msg_overrides_kwarg(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success_msg() takes precedence over the success_msg kwarg."""
        # Given an emitter with a kwarg-provided success_msg
        e, out, _ = make_recording_emitter()

        # When set_success_msg() overrides it from inside the block
        with e.step("compiling", success_msg="kwarg wins?") as s:
            s.set_success_msg("setter wins")

        # Then the setter's message appears and the kwarg's does not
        text = out.export_text()
        assert "setter wins" in text
        assert "kwarg wins" not in text

    def test_set_success_msg_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify set_success_msg() value is recorded in the succeeded: log line."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When set_success_msg() is used inside the block
        with e.step("compiling") as s:
            s.set_success_msg("compiled 42 files")

        # Then the logfile records the setter message
        contents = logfile.read_text()
        assert "succeeded: compiled 42 files" in contents

    def test_set_success_msg_markup_parses_tags(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success_msg(markup=True) parses Rich markup in the message."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When the setter is invoked with markup=True
        with e.step("compiling") as s:
            s.set_success_msg("[bold]all done[/]", markup=True)

        # Then the rendered output contains the message text without literal tags
        text = out.export_text()
        assert "all done" in text
        assert "[bold]" not in text

    def test_set_success_msg_accepts_renderable(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success_msg() accepts an arbitrary Rich renderable."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When a Padding renderable is supplied
        with e.step("compiling") as s:
            s.set_success_msg(Padding("compiled 42 files", (0, 1)))

        # Then the renderable's text appears in the rendered output
        text = out.export_text()
        assert "compiled 42 files" in text


class TestStepFail:
    """`Step.fail()` exits the block with failure outcome."""

    def test_fail_exits_the_block(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify fail() ends the with-block immediately; code after the call does not run."""
        # Given an emitter
        e, _, _ = make_recording_emitter()
        after_fail_ran = False

        # When fail() is called inside the block
        with e.step("compiling") as s:
            s.fail("aborted")
            after_fail_ran = True  # should be unreachable

        # Then code after fail() did not execute and the block ended normally
        assert after_fail_ran is False

    def test_fail_renders_error_header(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify fail() replaces the spinner with an error-marker completion header."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When fail() is called inside the block
        with e.step("compiling") as s:
            s.fail("aborted after 17 files")

        # Then the failure message appears with the error marker on the recorded output
        text = out.export_text()
        assert "aborted after 17 files" in text
        assert "✗" in text  # default unicode error marker

    def test_fail_writes_failed_log_line(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify fail() records a `failed:` line in the logfile."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When fail() is called
        with e.step("compiling") as s:
            s.fail("aborted")

        # Then the logfile contains the failed: line
        contents = logfile.read_text()
        assert "failed: aborted" in contents

    def test_fail_with_exception_attaches_traceback_to_log(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify fail(exception=e) attaches the exception type/message as a logfile continuation line."""
        # Given an emitter with a logfile and a real exception to attach
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When the block catches an exception and calls fail(exception=...)
        err_msg = "bad input"
        with e.step("compiling") as s:
            try:
                raise ValueError(err_msg)
            except ValueError as caught:
                s.fail("compilation failed", exception=caught)

        # Then the logfile contains the exception type and message as a continuation
        contents = logfile.read_text()
        assert "failed: compilation failed" in contents
        assert "ValueError" in contents
        assert "bad input" in contents

    def test_fail_in_ephemeral_prints_visible_error_line(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify fail() in ephemeral mode surfaces a fresh error line on stderr after wiping."""
        # Given an emitter with recording stderr in ephemeral mode
        e, _, err = make_recording_emitter()

        # When fail() is called inside an ephemeral step
        with e.step("warming caches", ephemeral=True) as s:
            s.fail("cache priming failed")

        # Then a visible error line lands on stderr
        err_text = err.export_text()
        assert "cache priming failed" in err_text
        assert "✗" in err_text  # default unicode error marker

    def test_fail_markup_parses_tags(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify fail(markup=True) parses Rich markup in the message."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When fail() is called with markup-containing message and markup=True
        with e.step("compiling") as s:
            s.fail("[bold]aborted[/]", markup=True)

        # Then the rendered output contains the message text but not the literal markup tags
        text = out.export_text()
        assert "aborted" in text
        assert "[bold]" not in text

    def test_fail_requires_message(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify fail() without a message argument is a TypeError."""
        # Given an emitter
        e, _, _ = make_recording_emitter()

        # When fail() is called without a message
        # Then a TypeError is raised
        with pytest.raises(TypeError), e.step("compiling") as s:
            s.fail()  # type: ignore[call-arg]


class TestStepSkip:
    """`Step.skip()` exits the block with skip outcome."""

    def test_skip_exits_the_block(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify skip() ends the with-block immediately; code after the call does not run."""
        # Given an emitter
        e, _, _ = make_recording_emitter()
        after_skip_ran = False

        # When skip() is called inside the block
        with e.step("warming caches") as s:
            s.skip("already warm")
            after_skip_ran = True  # should be unreachable

        # Then code after skip() did not execute
        assert after_skip_ran is False

    def test_skip_renders_info_header_no_checkmark(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify skip() replaces the spinner with an info-styled completion (no checkmark)."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When skip() is called inside the block
        with e.step("warming caches") as s:
            s.skip("already warm")

        # Then the skip message appears without the success checkmark
        text = out.export_text()
        assert "already warm" in text
        assert "✓" not in text  # default unicode success marker

    def test_skip_writes_skipped_log_line(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify skip() records a `skipped:` line in the logfile."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When skip() is called
        with e.step("warming caches") as s:
            s.skip("already warm")

        # Then the logfile contains the skipped: line
        contents = logfile.read_text()
        assert "skipped: already warm" in contents

    def test_skip_in_ephemeral_wipes_no_extra_output(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify skip() in ephemeral mode wipes everything and prints no extra line."""
        # Given an emitter with recording streams
        e, _, err = make_recording_emitter()

        # When skip() is called inside an ephemeral step
        with e.step("warming caches", ephemeral=True) as s:
            s.skip("already warm")

        # Then no extra stderr error line is produced (skip is not an error)
        err_text = err.export_text()
        assert "already warm" not in err_text

    def test_skip_markup_parses_tags(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify skip(markup=True) parses Rich markup in the message."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When skip() is called with markup-containing message
        with e.step("warming caches") as s:
            s.skip("[bold]already warm[/]", markup=True)

        # Then the rendered output contains the message text but not the literal tags
        text = out.export_text()
        assert "already warm" in text
        assert "[bold]" not in text

    def test_skip_requires_message(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify skip() without a message argument is a TypeError."""
        # Given an emitter
        e, _, _ = make_recording_emitter()

        # When skip() is called without a message
        # Then a TypeError is raised
        with pytest.raises(TypeError), e.step("warming caches") as s:
            s.skip()  # type: ignore[call-arg]


class TestStepUncaughtException:
    """An uncaught exception inside step() propagates cleanly with no marker and no log line."""

    def test_uncaught_exception_propagates(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify an unhandled exception inside the block still propagates to the caller."""
        # Given an emitter
        e, _, _ = make_recording_emitter()
        err_msg = "boom"

        # When the block raises and nothing catches it
        # Then the exception is re-raised by the context manager
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling"):
            raise RuntimeError(err_msg)

    def test_uncaught_exception_writes_no_log_line(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify step() writes no failed:/succeeded:/skipped: line on an uncaught exception."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)
        err_msg = "boom"

        # When the block raises
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling"):
            raise RuntimeError(err_msg)

        # Then the logfile has the `starting:` line but no completion line
        contents = logfile.read_text()
        assert "starting: compiling" in contents
        assert "failed:" not in contents
        assert "succeeded:" not in contents
        assert "skipped:" not in contents

    def test_uncaught_exception_renders_no_error_marker(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify the rendered output contains no error marker glyph on uncaught exception."""
        # Given an emitter
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When the block raises
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling"):
            raise RuntimeError(err_msg)

        # Then no failure marker appears in the rendered output
        text = out.export_text()
        assert "✗" not in text  # unicode error marker
        assert "compiling" in text  # original message still visible (neutralized header)

    def test_uncaught_exception_ephemeral_emits_nothing_extra(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify ephemeral=True wipes everything and emits no fresh stderr line on uncaught exception."""
        # Given an emitter
        e, _, err = make_recording_emitter()
        err_msg = "boom"

        # When an ephemeral step's body raises
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("warming caches", ephemeral=True),
        ):
            raise RuntimeError(err_msg)

        # Then no fresh error line is produced on stderr (caller owns error reporting)
        err_text = err.export_text()
        assert "warming caches" not in err_text

    def test_subitems_remain_visible_after_uncaught_exception(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify sub-items added before the exception remain in the non-ephemeral output."""
        # Given an emitter
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When sub-items are added then the block raises
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling") as s:
            s.sub("src/a.py")
            s.sub("src/b.py")
            raise RuntimeError(err_msg)

        # Then the sub-items appear in the rendered output
        text = out.export_text()
        assert "src/a.py" in text
        assert "src/b.py" in text
