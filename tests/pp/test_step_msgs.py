"""Tests for step() success_msg and failure_msg kwargs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

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
