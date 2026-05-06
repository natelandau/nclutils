"""Tests for nclutils.pp's module-level API surface.

Covers the module-level wrapper functions (`info`, `success`, `step`, etc.),
default-emitter management (`get_default` / `set_default`), and package-level
re-exports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from nclutils.pp import Emitter, Level, Theme, Verbosity, get_default, set_default
from nclutils.pp import emitter as emitter_module

if TYPE_CHECKING:
    from .conftest import RecordingEmitterFactory


class TestModuleLevelWrappers:
    """The module-level functions delegate to the shared default emitter."""

    @pytest.mark.parametrize(
        ("method", "to_stderr"),
        [
            ("info", False),
            ("success", False),
            ("debug", False),
            ("trace", False),
            ("dryrun", False),
            ("warning", True),
            ("error", True),
        ],
    )
    def test_level_function_routes_to_default_emitter(
        self,
        isolated_default: None,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
        *,
        to_stderr: bool,
    ) -> None:
        """Verify each module-level level function emits via the shared default emitter."""
        # Given a default emitter wired to recording consoles at TRACE verbosity
        e, out, err = make_recording_emitter(verbosity=Verbosity.TRACE)
        set_default(e)

        # When the module-level wrapper is called
        getattr(emitter_module, method)("hello")

        # Then the message appears on the appropriate stream
        target_text = err.export_text() if to_stderr else out.export_text()
        assert "hello" in target_text

    def test_header_routes_to_default_emitter(
        self,
        isolated_default: None,
        make_recording_emitter: RecordingEmitterFactory,
    ) -> None:
        """Verify module-level header() routes through the default emitter's stdout."""
        # Given a default emitter wired to a recording stdout console
        e, out, _ = make_recording_emitter()
        set_default(e)

        # When the module-level header() is called
        emitter_module.header("Section A")

        # Then the title appears on the captured stdout
        assert "Section A" in out.export_text()

    def test_step_routes_to_default_emitter(
        self,
        isolated_default: None,
        make_recording_emitter: RecordingEmitterFactory,
    ) -> None:
        """Verify module-level step() opens a Live block on the default emitter."""
        # Given a default emitter wired to a recording stdout console
        e, out, _ = make_recording_emitter()
        set_default(e)

        # When the module-level step() runs to completion
        with emitter_module.step("compiling"):
            pass

        # Then the success marker and message appear on the captured stdout
        text = out.export_text()
        assert "compiling" in text
        assert "✓" in text

    def test_configure_applies_theme_to_default_emitter(self, isolated_default: None) -> None:
        """Verify the module-level configure() routes theme updates to the default emitter."""
        # Given the isolated_default fixture installs a fresh default emitter

        # When the module-level configure(theme=...) is called
        emitter_module.configure(theme=Theme(success=Level(marker="🎉 ")))

        # Then the default emitter's resolved success marker reflects the override
        assert get_default()._resolve("success") == ("bold green", "green", "🎉 ")


class TestModuleWrapperPerCallOverrides:
    """Module-level level functions accept the same per-call style/detail_style/marker kwargs."""

    def test_module_info_accepts_style_kwarg_without_collision(
        self, isolated_default: None, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify nclutils.pp.info(message, style=...) works through the module-level wrapper."""
        # Given a default emitter wired to a recording stdout
        e, out, _ = make_recording_emitter()
        set_default(e)

        # When the module-level wrapper is called with a per-call style override
        emitter_module.info("hello", style="blue")

        # Then the message renders without raising and the color appears in HTML
        # (`clear=False` keeps the recorded segments so both exports see the same content)
        assert "hello" in out.export_text(clear=False)
        assert "#000080" in out.export_html(inline_styles=True)


class TestDefaultEmitter:
    """get_default() and set_default() govern the shared default emitter."""

    def test_set_default_to_fresh_emitter_clears_overrides(self, isolated_default: None) -> None:
        """Verify replacing the default emitter resets resolved styles to defaults."""
        # Given a default emitter with a marker override
        set_default(Emitter(theme=Theme(success=Level(marker="🎉 "))))
        assert get_default()._resolve("success") == ("bold green", "green", "🎉 ")

        # When the default is replaced with a brand-new Emitter
        set_default(Emitter())

        # Then the override is gone and built-in defaults are restored
        assert get_default()._resolve("success") == ("bold green", "green", "✓ ")


class TestCriticalWrapper:
    """The module-level `critical()` delegates to the default emitter."""

    def test_module_critical_writes_to_default_emitter_stderr(self, isolated_default: None) -> None:
        """Verify the module-level critical() routes through the default emitter to stderr."""
        # Given a default emitter wired to a recording stderr console

        err = Console(record=True, force_terminal=True, width=80, color_system="truecolor")
        emitter_module.set_default(emitter_module.Emitter(err_console=err))

        # When the module-level critical is called
        emitter_module.critical("module-level kaboom")

        # Then the message is on stderr via the default emitter
        assert "module-level kaboom" in err.export_text()


class TestConsoleAccessors:
    """Module-level `console()` / `err_console()` return the default emitter's consoles."""

    @pytest.mark.parametrize("accessor", ["console", "err_console"])
    def test_accessor_returns_default_emitter_console(
        self,
        isolated_default: None,
        make_recording_emitter: RecordingEmitterFactory,
        accessor: str,
    ) -> None:
        """Verify console()/err_console() return the same Console the default emitter holds."""
        # Given a default emitter wired to recording consoles
        e, _, _ = make_recording_emitter()
        set_default(e)

        # When the accessor is called
        result = getattr(emitter_module, accessor)()

        # Then it returns the matching attribute on the default emitter
        assert result is getattr(e, accessor)

    def test_accessor_re_resolves_after_set_default_swap(
        self,
        isolated_default: None,
        make_recording_emitter: RecordingEmitterFactory,
    ) -> None:
        """Verify accessors reflect set_default() swaps without caching the prior emitter."""
        # Given an initial default emitter
        first, _, _ = make_recording_emitter()
        set_default(first)
        assert emitter_module.console() is first.console

        # When the default is swapped to a different emitter
        second, _, _ = make_recording_emitter()
        set_default(second)

        # Then both accessors return the new emitter's consoles, not the prior ones
        assert emitter_module.console() is second.console
        assert emitter_module.err_console() is second.err_console
