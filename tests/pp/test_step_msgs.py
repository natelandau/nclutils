"""Tests for step() success_msg and failure_msg kwargs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rich.padding import Padding
from rich.text import Text

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


class TestStepFailureMsg:
    """`failure_msg` swaps the error header text on exception."""

    def test_failure_msg_replaces_header_on_exception(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify failure_msg appears in place of the original message on exception."""
        # Given an emitter wired to a recording console
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When step() raises with a failure_msg override
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("compiling", failure_msg="compilation aborted"),
        ):
            raise RuntimeError(err_msg)

        # Then the failure_msg appears in the rendered output
        text = out.export_text()
        assert "compilation aborted" in text

    def test_failure_msg_default_keeps_original(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify omitting failure_msg preserves current behavior (original message kept)."""
        # Given an emitter wired to a recording console
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When step() raises without override kwargs
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling"):
            raise RuntimeError(err_msg)

        # Then the original message appears in the failure line
        text = out.export_text()
        assert "compiling" in text


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

    def test_failure_msg_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify the failed: line in the logfile uses failure_msg when provided."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)
        err_msg = "boom"

        # When step() raises with an override
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("compiling", failure_msg="compilation aborted"),
        ):
            raise RuntimeError(err_msg)

        # Then the logfile records the override message in the failed: line
        contents = logfile.read_text()
        assert "failed: compilation aborted" in contents

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

    def test_ephemeral_failure_displays_failure_msg(
        self,
        make_recording_emitter: RecordingEmitterFactory,
    ) -> None:
        """Verify ephemeral failure surfaces failure_msg on stderr."""
        # Given an emitter wired to recording stderr
        e, _, err = make_recording_emitter()
        err_msg = "boom"

        # When step() raises in ephemeral mode with a failure_msg
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step(
                "warming caches",
                ephemeral=True,
                failure_msg="cache priming failed",
            ),
        ):
            raise RuntimeError(err_msg)

        # Then the failure_msg appears in the surfaced error output
        text = err.export_text()
        assert "cache priming failed" in text

    def test_ephemeral_failure_default_surfaces_original(
        self,
        make_recording_emitter: RecordingEmitterFactory,
    ) -> None:
        """Verify ephemeral failure falls back to the original message on stderr without override."""
        # Given an emitter wired to recording stderr
        e, _, err = make_recording_emitter()
        err_msg = "boom"

        # When step() raises in ephemeral mode without a failure_msg
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("warming caches", ephemeral=True),
        ):
            raise RuntimeError(err_msg)

        # Then the original message appears in the surfaced error output
        text = err.export_text()
        assert "warming caches" in text

    def test_ephemeral_failure_preserves_failure_msg_styling(
        self,
        make_recording_emitter: RecordingEmitterFactory,
    ) -> None:
        """Verify ephemeral failure preserves Rich markup styling in failure_msg."""
        # Given an emitter wired to recording stderr
        e, _, err = make_recording_emitter()
        err_msg = "boom"

        # When step() raises ephemerally with a styled failure_msg
        styled = Text("cache priming failed", style="bold red")
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("warming", ephemeral=True, failure_msg=styled),
        ):
            raise RuntimeError(err_msg)

        # Then the styled fragment appears in the recorded HTML output with styling preserved
        html = err.export_html()
        assert "cache priming failed" in html
        # The styling marker should be present (red color or bold weight)
        assert "color: " in html or "font-weight" in html


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

    def test_module_step_accepts_failure_msg(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        isolated_default: None,
    ) -> None:
        """Verify the module-level step() forwards failure_msg to the default emitter."""
        # Given the default emitter is replaced with a recording one
        e, out, _ = make_recording_emitter()
        pp_emitter.set_default(e)
        err_msg = "boom"

        # When the module-level step() raises with a failure_msg override
        with (
            pytest.raises(RuntimeError, match=err_msg),
            pp_emitter.step("compiling", failure_msg="compilation aborted"),
        ):
            raise RuntimeError(err_msg)

        # Then the override message appears in the rendered output
        text = out.export_text()
        assert "compilation aborted" in text


class TestMarkupAppliesToOverrides:
    """`markup=True` parses Rich markup in success_msg and failure_msg."""

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

    def test_markup_true_parses_failure_msg(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify markup=True parses Rich markup tags in failure_msg."""
        # Given an emitter
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When step() raises with a markup-containing override and markup=True
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("compiling", failure_msg="[bold]aborted[/]", markup=True),
        ):
            raise RuntimeError(err_msg)

        # Then the rendered output contains the message text but not the literal markup tags
        text = out.export_text()
        assert "aborted" in text
        assert "[bold]" not in text


class TestSetSuccessFromBlock:
    """`Step.set_success()` updates the success header from inside the block."""

    def test_set_success_replaces_header(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success() applied inside the block replaces the success header."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When the block computes a result and applies it via set_success
        with e.step("compiling") as s:
            count = 42
            s.set_success(f"compiled {count} files")

        # Then the dynamic message appears in the rendered output
        text = out.export_text()
        assert "compiled 42 files" in text

    def test_set_success_overrides_kwarg(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success() takes precedence over the success_msg kwarg."""
        # Given an emitter with a kwarg-provided success_msg
        e, out, _ = make_recording_emitter()

        # When set_success() overrides it from inside the block
        with e.step("compiling", success_msg="kwarg wins?") as s:
            s.set_success("setter wins")

        # Then the setter's message appears and the kwarg's does not
        text = out.export_text()
        assert "setter wins" in text
        assert "kwarg wins" not in text

    def test_set_success_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify set_success() value is recorded in the succeeded: log line."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When set_success() is used inside the block
        with e.step("compiling") as s:
            s.set_success("compiled 42 files")

        # Then the logfile records the setter message
        contents = logfile.read_text()
        assert "succeeded: compiled 42 files" in contents

    def test_set_success_markup_parses_tags(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success(markup=True) parses Rich markup in the message."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When the setter is invoked with markup=True
        with e.step("compiling") as s:
            s.set_success("[bold]all done[/]", markup=True)

        # Then the rendered output contains the message text without literal tags
        text = out.export_text()
        assert "all done" in text
        assert "[bold]" not in text

    def test_set_success_accepts_renderable(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success() accepts an arbitrary Rich renderable."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When a Padding renderable is supplied
        with e.step("compiling") as s:
            s.set_success(Padding("compiled 42 files", (0, 1)))

        # Then the renderable's text appears in the rendered output
        text = out.export_text()
        assert "compiled 42 files" in text

    def test_set_success_ignored_on_failure(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_success() has no effect when the block raises."""
        # Given an emitter
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When set_success() is called and then an exception is raised
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling") as s:
            s.set_success("compiled 42 files")
            raise RuntimeError(err_msg)

        # Then the success setter value does not surface in the failure output
        text = out.export_text()
        assert "compiled 42 files" not in text


class TestSetFailureFromBlock:
    """`Step.set_failure()` updates the failure header from inside the block."""

    def test_set_failure_replaces_header(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_failure() applied inside the block replaces the failure header."""
        # Given an emitter
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When the block sets a contingent failure message before raising
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling") as s:
            s.set_failure("failed after 17 files")
            raise RuntimeError(err_msg)

        # Then the dynamic failure message appears in the rendered output
        text = out.export_text()
        assert "failed after 17 files" in text

    def test_set_failure_overrides_kwarg(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_failure() takes precedence over the failure_msg kwarg."""
        # Given an emitter with a kwarg-provided failure_msg
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When set_failure() overrides it from inside the block
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("compiling", failure_msg="kwarg failure") as s,
        ):
            s.set_failure("setter failure")
            raise RuntimeError(err_msg)

        # Then the setter's message appears and the kwarg's does not
        text = out.export_text()
        assert "setter failure" in text
        assert "kwarg failure" not in text

    def test_set_failure_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify set_failure() value is recorded in the failed: log line."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)
        err_msg = "boom"

        # When set_failure() is used and the block raises
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling") as s:
            s.set_failure("failed after 17 files")
            raise RuntimeError(err_msg)

        # Then the logfile records the setter message
        contents = logfile.read_text()
        assert "failed: failed after 17 files" in contents

    def test_set_failure_ephemeral_surfaces_on_stderr(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_failure() under ephemeral=True surfaces on stderr."""
        # Given an emitter wired to recording stderr
        e, _, err = make_recording_emitter()
        err_msg = "boom"

        # When an ephemeral step sets a failure message and raises
        with (
            pytest.raises(RuntimeError, match=err_msg),
            e.step("warming caches", ephemeral=True) as s,
        ):
            s.set_failure("cache priming failed at item 17")
            raise RuntimeError(err_msg)

        # Then the setter's failure message appears on stderr
        text = err.export_text()
        assert "cache priming failed at item 17" in text

    def test_set_failure_markup_parses_tags(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_failure(markup=True) parses Rich markup in the message."""
        # Given an emitter
        e, out, _ = make_recording_emitter()
        err_msg = "boom"

        # When set_failure() is invoked with markup=True before raising
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling") as s:
            s.set_failure("[bold]aborted hard[/]", markup=True)
            raise RuntimeError(err_msg)

        # Then the rendered output contains the message text without literal tags
        text = out.export_text()
        assert "aborted hard" in text
        assert "[bold]" not in text

    def test_set_failure_ignored_on_success(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify set_failure() has no effect when the block completes normally."""
        # Given an emitter with logfile
        logfile = tmp_path / "run.log"
        e, out, _ = make_recording_emitter(logfile=logfile)

        # When set_failure() is called but the block succeeds
        with e.step("compiling") as s:
            s.set_failure("would-be failure")

        # Then the failure setter value does not surface in success output or log
        text = out.export_text()
        assert "would-be failure" not in text
        assert "would-be failure" not in logfile.read_text()


class TestStepSkipMsg:
    """`skip_msg` kwarg supplies the default text used when `set_skipped()` fires."""

    def test_skip_msg_displays_when_set_skipped_called_no_args(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify skip_msg kwarg supplies the header when set_skipped() is called without args."""
        # Given an emitter wired to a recording console
        e, out, _ = make_recording_emitter()

        # When step() runs and set_skipped() fires with no message
        with e.step("compiling", skip_msg="nothing to compile") as s:
            s.set_skipped()

        # Then the kwarg message appears in the rendered output
        text = out.export_text()
        assert "nothing to compile" in text

    def test_skip_msg_falls_back_to_original_message(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_skipped() with no kwarg/arg uses the original step message."""
        # Given an emitter and a step with no skip_msg
        e, out, _ = make_recording_emitter()

        # When set_skipped() fires without overrides
        with e.step("compiling") as s:
            s.set_skipped()

        # Then the original message appears in the rendered output
        text = out.export_text()
        assert "compiling" in text

    def test_skip_msg_records_skipped_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify the logfile records a `skipped:` line when the step is skipped."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When the block marks itself skipped with a kwarg message
        with e.step("compiling", skip_msg="nothing to compile") as s:
            s.set_skipped()

        # Then the logfile records the skipped: line with the kwarg message
        contents = logfile.read_text()
        assert "skipped: nothing to compile" in contents
        # And it should not record a succeeded: or failed: line
        assert "succeeded:" not in contents
        assert "failed:" not in contents

    def test_skip_msg_kwarg_alone_does_not_trigger_skip(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify skip_msg kwarg without set_skipped() leaves the step on the success path."""
        # Given an emitter with a logfile and a skip_msg kwarg
        logfile = tmp_path / "run.log"
        e, out, _ = make_recording_emitter(logfile=logfile)

        # When the block exits normally without calling set_skipped()
        with e.step("compiling", skip_msg="would skip"):
            pass

        # Then the step records as succeeded and skip_msg does not surface
        contents = logfile.read_text()
        assert "succeeded: compiling" in contents
        assert "skipped:" not in contents
        assert "would skip" not in out.export_text()


class TestSetSkippedFromBlock:
    """`Step.set_skipped()` marks the step as skipped from inside the block."""

    def test_set_skipped_with_message_replaces_header(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_skipped("msg") applied inside the block replaces the completion header."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When the block decides to skip with an inline message
        with e.step("compiling") as s:
            s.set_skipped("no source files found")

        # Then the inline message appears in the rendered output
        text = out.export_text()
        assert "no source files found" in text

    def test_set_skipped_overrides_kwarg(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_skipped(message) takes precedence over the skip_msg kwarg."""
        # Given an emitter with a kwarg-provided skip_msg
        e, out, _ = make_recording_emitter()

        # When set_skipped() overrides it from inside the block
        with e.step("compiling", skip_msg="kwarg skip") as s:
            s.set_skipped("setter skip")

        # Then the setter's message appears and the kwarg's does not
        text = out.export_text()
        assert "setter skip" in text
        assert "kwarg skip" not in text

    def test_set_skipped_in_logfile(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify set_skipped() message is recorded in the `skipped:` log line."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)

        # When set_skipped() is used inside the block
        with e.step("compiling") as s:
            s.set_skipped("no source files found")

        # Then the logfile records the setter message under `skipped:`
        contents = logfile.read_text()
        assert "skipped: no source files found" in contents

    def test_set_skipped_uses_info_styling_not_success(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify the skipped completion does not use the success checkmark marker."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When the block marks itself skipped
        with e.step("compiling") as s:
            s.set_skipped("no source files")

        # Then the rendered output does not contain the success marker glyph
        text = out.export_text()
        assert "no source files" in text
        # Success glyph (unicode or ASCII fallback) must not appear
        assert "✓" not in text
        assert "+ no source files" not in text

    def test_set_skipped_markup_parses_tags(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_skipped(markup=True) parses Rich markup in the message."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When the setter is invoked with markup=True
        with e.step("compiling") as s:
            s.set_skipped("[bold]nothing to do[/]", markup=True)

        # Then the rendered output contains the message text without literal tags
        text = out.export_text()
        assert "nothing to do" in text
        assert "[bold]" not in text

    def test_set_skipped_accepts_renderable(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify set_skipped() accepts an arbitrary Rich renderable."""
        # Given an emitter
        e, out, _ = make_recording_emitter()

        # When a Padding renderable is supplied
        with e.step("compiling") as s:
            s.set_skipped(Padding("no work to do", (0, 1)))

        # Then the renderable's text appears in the rendered output
        text = out.export_text()
        assert "no work to do" in text

    def test_set_skipped_ignored_on_failure(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify set_skipped() has no effect when the block raises (failure path wins)."""
        # Given an emitter with a logfile
        logfile = tmp_path / "run.log"
        e, _, _ = make_recording_emitter(logfile=logfile)
        err_msg = "boom"

        # When set_skipped() is called and then an exception is raised
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling") as s:
            s.set_skipped("would skip")
            raise RuntimeError(err_msg)

        # Then the logfile records `failed:`, not `skipped:`
        contents = logfile.read_text()
        assert "failed: compiling" in contents
        assert "skipped:" not in contents

    def test_set_skipped_ephemeral_clears_console_but_logs(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        tmp_path: Path,
    ) -> None:
        """Verify ephemeral skip wipes the console output but records skipped: in logfile."""
        # Given an emitter with logfile and an ephemeral step
        logfile = tmp_path / "run.log"
        e, out, _ = make_recording_emitter(logfile=logfile)

        # When the block marks itself skipped under ephemeral=True
        with e.step("warming caches", ephemeral=True, skip_msg="caches already warm") as s:
            s.set_skipped()

        # Then the console is clean of skip text (ephemeral wipes the marker)
        # but the logfile records the skip
        assert "caches already warm" not in out.export_text()
        assert "skipped: caches already warm" in logfile.read_text()


class TestModuleLevelStepSkip:
    """Module-level `step()` forwards `skip_msg` to the default emitter."""

    def test_module_step_accepts_skip_msg(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        isolated_default: None,
    ) -> None:
        """Verify the module-level step() forwards skip_msg to the default emitter."""
        # Given the default emitter is replaced with a recording one
        e, out, _ = make_recording_emitter()
        pp_emitter.set_default(e)

        # When the module-level step() runs and the block calls set_skipped()
        with pp_emitter.step("compiling", skip_msg="nothing to compile") as s:
            s.set_skipped()

        # Then the kwarg message appears in the rendered output
        text = out.export_text()
        assert "nothing to compile" in text
