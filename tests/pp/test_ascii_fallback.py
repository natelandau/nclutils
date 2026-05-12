"""Tests for auto ASCII fallback when console encoding can't handle box-drawing chars."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from nclutils.pp.emitter import Emitter, Level, Theme, Verbosity

if TYPE_CHECKING:
    from .conftest import RecordingEmitterFactory


class _AsciiConsole(Console):
    """A recording Console subclass that reports `ascii` as its encoding.

    Rich's `Console.encoding` is a property reading `self.file.encoding`, so we
    override it directly. We need a subclass (not `object.__setattr__`) because
    properties live on the class, not the instance.
    """

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return "ascii"


def _make_ascii_emitter() -> tuple[Emitter, _AsciiConsole, _AsciiConsole]:
    """Build an emitter whose stdout AND stderr consoles report ascii encoding."""
    out = _AsciiConsole(record=True, force_terminal=True, width=80, color_system="truecolor")
    err = _AsciiConsole(record=True, force_terminal=True, width=80, color_system="truecolor")
    return Emitter(console=out, err_console=err, verbosity=Verbosity.TRACE), out, err


class TestAsciiConnectors:
    """Detail tree connectors fall back to '- ' on ASCII consoles."""

    def test_ascii_console_uses_hyphen_prefix(self) -> None:
        """Verify details render with '- ' prefix when console encoding is ASCII."""
        # Given an emitter wired to an ASCII-encoding console
        e, out, _ = _make_ascii_emitter()

        # When info is called with details
        e.info("status", details=["one", "two", "three"])

        # Then the connector glyphs are absent and '- ' prefix appears
        text = out.export_text()
        assert "├" not in text
        assert "└" not in text
        assert "│" not in text
        assert "- one" in text
        assert "- two" in text
        assert "- three" in text

    def test_ascii_step_sub_uses_hyphen_prefix(self) -> None:
        """Verify step sub-items render with '- ' prefix when console encoding is ASCII."""
        # Given an emitter wired to an ASCII-encoding console
        e, out, _ = _make_ascii_emitter()

        # When a step with sub-items completes
        with e.step("compiling") as s:
            s.sub("api.py")
            s.sub("cli.py")

        # Then the connector glyphs are absent and '- ' prefix appears
        text = out.export_text()
        assert "├" not in text
        assert "└" not in text
        assert "- api.py" in text
        assert "- cli.py" in text


class TestAsciiMarkers:
    """Default markers fall back to ASCII equivalents on ASCII consoles."""

    @pytest.mark.parametrize(
        ("method", "ascii_marker", "to_stderr"),
        [
            ("success", "+", False),
            ("error", "x", True),
            ("critical", "!!", True),
            ("debug", ">", False),
            ("trace", ".", False),
        ],
    )
    def test_default_markers_substitute_in_ascii(
        self, method: str, ascii_marker: str, *, to_stderr: bool
    ) -> None:
        """Verify each level's default unicode marker becomes its ASCII fallback."""
        # Given an ASCII-encoding emitter (both stdout and stderr report ascii)
        e, out, err = _make_ascii_emitter()

        # When the level method is called
        getattr(e, method)("hello")

        # Then the unicode default is absent and the ASCII fallback appears
        target = err if to_stderr else out
        text = target.export_text()
        unicode_marker = {
            "success": "✓",
            "error": "✗",
            "critical": "‼",
            "debug": "›",  # noqa: RUF001
            "trace": "·",
        }[method]
        assert unicode_marker not in text
        assert ascii_marker in text


class TestUserOverridesWinInAscii:
    """User-supplied Theme markers always win, even on ASCII consoles."""

    def test_user_marker_override_kept_on_ascii_console(self) -> None:
        """Verify a user-set Theme marker is preserved verbatim on ASCII consoles."""
        # Given an ASCII-encoding emitter with a user-set marker
        e, out, _ = _make_ascii_emitter()
        e.configure(theme=Theme(success=Level(marker=">> ")))

        # When success is called
        e.success("done")

        # Then the user marker appears (no substitution)
        text = out.export_text()
        assert ">> done" in text


class TestAsciiStepHeader:
    """Step success/failure header markers fall back to ASCII on ASCII consoles."""

    def test_ascii_step_success_header_uses_ascii_marker(self) -> None:
        """Verify the success header marker substitutes to ASCII on an ascii-encoding console."""
        # Given an ASCII-encoding emitter
        e, out, _ = _make_ascii_emitter()

        # When step() runs to success
        with e.step("compiling"):
            pass

        # Then the success line uses the ASCII success marker, not the unicode one
        text = out.export_text()
        assert "✓" not in text
        assert "+ compiling" in text

    def test_ascii_step_failure_header_uses_ascii_marker(self) -> None:
        """Verify the failure header marker substitutes to ASCII on an ascii-encoding console."""
        # Given an ASCII-encoding emitter
        e, out, _ = _make_ascii_emitter()

        # When step() exits via fail() (non-ephemeral)
        with e.step("compiling") as s:
            s.fail("compiling")

        # Then the failure line uses the ASCII error marker, not the unicode one
        text = out.export_text()
        assert "✗" not in text
        assert "x compiling" in text

    def test_user_step_marker_override_kept_on_ascii_console(self) -> None:
        """Verify a Theme-set success marker is preserved verbatim on ASCII consoles."""
        # Given an ASCII-encoding emitter with a user-set success marker
        e, out, _ = _make_ascii_emitter()
        e.configure(theme=Theme(success=Level(marker=">> ")))

        # When step() runs to success
        with e.step("done"):
            pass

        # Then the user marker appears (no substitution)
        text = out.export_text()
        assert ">> done" in text


class TestUtfConsoleUnchanged:
    """UTF-8 consoles continue to render unicode connectors and markers."""

    def test_utf_console_keeps_unicode_glyphs(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify the existing recording fixture (utf-8) still renders unicode connectors."""
        # Given a default (utf-8) emitter
        e, out, _ = make_recording_emitter()

        # When details are emitted
        e.info("status", details=["one", "two"])

        # Then the unicode connectors appear
        text = out.export_text()
        assert "├" in text or "└" in text

    def test_utf_console_keeps_unicode_markers(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify default unicode markers render unchanged on utf-8 consoles."""
        # Given a default (utf-8) emitter
        e, out, err = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When success and error are emitted
        e.success("ok")
        e.error("bad")

        # Then the unicode markers appear (and ASCII fallbacks are absent)
        out_text = out.export_text()
        err_text = err.export_text()
        assert "✓" in out_text
        assert "✗" in err_text
