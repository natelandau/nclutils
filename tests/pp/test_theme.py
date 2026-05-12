"""Tests for nclutils.pp's theme customization API.

Covers the `Level` and `Theme` dataclasses, `_merge_theme` field-merge
semantics, `Emitter._resolve` overlay resolution, and the rendered output of
themed emitters.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import pytest

from nclutils.pp.emitter import Emitter, Level, Theme, _merge_theme

if TYPE_CHECKING:
    from .conftest import RecordingEmitterFactory


class TestLevel:
    """`Level` is a frozen dataclass holding optional per-level overrides."""

    def test_constructs_with_all_none_defaults(self) -> None:
        """Verify a no-arg Level has every override field set to None."""
        # Given/When a Level is constructed with no arguments
        level = Level()

        # Then every field is None (i.e., all defaults inherited)
        assert level.style is None
        assert level.detail_style is None
        assert level.marker is None

    def test_accepts_partial_fields(self) -> None:
        """Verify Level keeps unspecified fields as None when others are set."""
        # Given/When a Level is constructed with only style and marker
        level = Level(style="cyan", marker="🎉 ")

        # Then the supplied fields are stored and unspecified ones stay None
        assert level.style == "cyan"
        assert level.detail_style is None
        assert level.marker == "🎉 "

    def test_rejects_mutation_after_construction(self) -> None:
        """Verify Level is frozen so post-construction assignment raises."""
        # Given a constructed Level
        level = Level(style="cyan")

        # When attempting to mutate a field
        # Then FrozenInstanceError is raised
        with pytest.raises(FrozenInstanceError):
            level.style = "blue"  # type: ignore[misc]  # ty: ignore[invalid-assignment]


class TestTheme:
    """`Theme` is a frozen dataclass holding optional per-level `Level` overrides."""

    def test_constructs_with_all_none_defaults(self) -> None:
        """Verify a no-arg Theme has every level field set to None."""
        # Given/When a Theme is constructed with no arguments
        theme = Theme()

        # Then every level field is None
        assert theme.info is None
        assert theme.success is None
        assert theme.warning is None
        assert theme.error is None
        assert theme.debug is None
        assert theme.trace is None
        assert theme.dryrun is None

    def test_accepts_partial_levels(self) -> None:
        """Verify Theme leaves unspecified levels as None when others are set."""
        # Given/When a Theme is constructed with only success
        theme = Theme(success=Level(style="cyan"))

        # Then success is stored and other levels stay None
        assert theme.success == Level(style="cyan")
        assert theme.warning is None

    def test_rejects_mutation_after_construction(self) -> None:
        """Verify Theme is frozen so post-construction assignment raises."""
        # Given a constructed Theme
        theme = Theme()

        # When attempting to assign a level field
        # Then FrozenInstanceError is raised
        with pytest.raises(FrozenInstanceError):
            theme.success = Level(style="cyan")  # type: ignore[misc]  # ty: ignore[invalid-assignment]


class TestMergeTheme:
    """`_merge_theme` overlays a Theme onto a base, preserving non-None fields."""

    def test_empty_overlay_returns_base(self) -> None:
        """Verify merging an empty overlay leaves the base unchanged."""
        # Given a base Theme with one level overridden
        base = Theme(success=Level(style="cyan", marker="🎉 "))

        # When merged with an empty overlay
        merged = _merge_theme(base, Theme())

        # Then base's overrides survive and unset levels stay None
        assert merged.success == Level(style="cyan", marker="🎉 ")
        assert merged.warning is None

    def test_overlay_field_wins_when_set(self) -> None:
        """Verify overlay's non-None fields replace base's fields on the same level."""
        # Given base and overlay both touching success
        base = Theme(success=Level(style="cyan", marker="🎉 "))
        overlay = Theme(success=Level(detail_style="navy"))

        # When merged
        merged = _merge_theme(base, overlay)

        # Then overlay's detail_style wins; base's other fields survive
        assert merged.success == Level(style="cyan", detail_style="navy", marker="🎉 ")

    def test_overlay_none_field_preserves_base_field(self) -> None:
        """Verify a None field on the overlay does not clobber a set field on base."""
        # Given base with detail_style=None and marker set, overlay with style only
        base = Theme(success=Level(style="cyan", marker="🎉 "))
        overlay = Theme(success=Level(style="blue"))

        # When merged
        merged = _merge_theme(base, overlay)

        # Then overlay's style wins, marker survives, detail_style stays None
        assert merged.success == Level(style="blue", detail_style=None, marker="🎉 ")

    def test_overlay_adds_new_level(self) -> None:
        """Verify an overlay adding a previously-unset level leaves base levels alone."""
        # Given base with success only and overlay with warning only
        base = Theme(success=Level(style="cyan"))
        overlay = Theme(warning=Level(style="orange"))

        # When merged
        merged = _merge_theme(base, overlay)

        # Then both levels appear with their overrides
        assert merged.success == Level(style="cyan")
        assert merged.warning == Level(style="orange")

    def test_overlay_level_replaces_when_base_is_none(self) -> None:
        """Verify an overlay level is adopted wholesale when the base level is None."""
        # Given an empty base and an overlay touching error
        base = Theme()
        overlay = Theme(error=Level(marker="x "))

        # When merged
        merged = _merge_theme(base, overlay)

        # Then the overlay's error level appears as-is
        assert merged.error == Level(marker="x ")

    def test_preserves_empty_string_marker(self) -> None:
        """Verify marker='' on the overlay is treated as explicit suppression, not a fallback."""
        # Given a base with a marker and an overlay that explicitly empties it
        base = Theme(info=Level(marker="• "))
        overlay = Theme(info=Level(marker=""))

        # When merged
        merged = _merge_theme(base, overlay)

        # Then the empty marker is preserved, not replaced by base's marker
        assert merged.info is not None
        assert merged.info.marker == ""


class TestEmitterResolve:
    """`Emitter._resolve` overlays the emitter's stored Theme on built-in defaults."""

    def test_returns_built_in_defaults_with_no_theme(self) -> None:
        """Verify _resolve returns hardcoded defaults when no overrides are set."""
        # Given a default Emitter
        e = Emitter()

        # When resolving each level
        # Then the built-in style/detail/marker triple is returned
        assert e._resolve("success") == ("bold green", "green", "✓ ")
        assert e._resolve("info") == ("bold default", "default", "")

    @pytest.mark.parametrize(
        ("override", "expected"),
        [
            (Level(style="blue"), ("blue", "green", "✓ ")),
            (Level(detail_style="navy"), ("bold green", "navy", "✓ ")),
            (Level(marker="🎉 "), ("bold green", "green", "🎉 ")),
        ],
        ids=["style-only", "detail_style-only", "marker-only"],
    )
    def test_applies_single_field_override(
        self,
        override: Level,
        expected: tuple[str, str, str],
    ) -> None:
        """Verify a single-field Level override leaves the other two as defaults."""
        # Given an Emitter with one field on success overridden
        e = Emitter(theme=Theme(success=override))

        # When resolving success
        # Then only the overridden field changes; the others stay at their defaults
        assert e._resolve("success") == expected

    def test_marker_empty_string_suppresses_marker(self) -> None:
        """Verify marker='' is treated as a real value, not a fallback signal."""
        # Given an Emitter with success.marker explicitly empty
        e = Emitter(theme=Theme(success=Level(marker="")))

        # When resolving success
        _, _, marker = e._resolve("success")

        # Then the empty string survives (not the default "✓ ")
        assert marker == ""

    def test_does_not_share_state_across_instances(self) -> None:
        """Verify two Emitters keep independent theme overrides."""
        # Given one Emitter with overrides and another with defaults
        a = Emitter(theme=Theme(success=Level(style="blue")))
        b = Emitter()

        # When each resolves success
        # Then each gets its own values
        assert a._resolve("success") == ("blue", "green", "✓ ")
        assert b._resolve("success") == ("bold green", "green", "✓ ")


class TestThemeAccumulation:
    """Successive `configure(theme=...)` calls merge field-by-field rather than replacing."""

    def test_theme_accumulates_across_configure_calls(self) -> None:
        """Verify successive configure(theme=...) calls merge field-by-field."""
        # Given a default Emitter
        e = Emitter()

        # When three configure(theme=...) calls land in sequence
        e.configure(theme=Theme(success=Level(style="blue", marker="🎉 ")))
        e.configure(theme=Theme(success=Level(detail_style="navy")))
        e.configure(theme=Theme(warning=Level(style="orange")))

        # Then field-level merge preserves all set fields and untouched levels stay default
        assert e._resolve("success") == ("blue", "navy", "🎉 ")
        assert e._resolve("warning") == ("orange", "yellow", "! ")
        assert e._resolve("error") == ("bold red", "red", "✗ ")

    def test_configure_without_theme_kwarg_leaves_theme_intact(self) -> None:
        """Verify configure() calls that omit theme do not reset overrides."""
        # Given an Emitter with success overridden
        e = Emitter(theme=Theme(success=Level(style="blue")))

        # When configure() is called for an unrelated field
        e.configure(verbosity=2)

        # Then the theme override survives
        assert e._resolve("success") == ("blue", "green", "✓ ")


class TestThemeAppliedToOutput:
    """Theme overrides reach rendered output via the level methods and step()."""

    def test_success_renders_default_marker_when_no_overrides(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify default success output contains the built-in checkmark glyph."""
        # Given a default Emitter with a recording console
        e, out, _ = make_recording_emitter()

        # When success is emitted
        e.success("done")

        # Then the default marker prefixes the message
        assert "✓ done" in out.export_text()

    def test_success_renders_custom_marker_when_overridden(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a marker override appears in rendered output and replaces the default."""
        # Given an Emitter with success.marker overridden
        e, out, _ = make_recording_emitter(theme=Theme(success=Level(marker="🎉 ")))

        # When success is emitted
        e.success("done")

        # Then the custom marker replaces the default
        text = out.export_text()
        assert "🎉 done" in text
        assert "✓" not in text

    def test_success_marker_empty_string_renders_no_glyph(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify marker='' produces output with no marker prefix."""
        # Given an Emitter with success.marker set to an empty string
        e, out, _ = make_recording_emitter(theme=Theme(success=Level(marker="")))

        # When success is emitted
        e.success("done")

        # Then the message renders with neither default nor custom glyph
        text = out.export_text()
        assert "done" in text
        assert "✓" not in text
        assert "🎉" not in text

    def test_success_style_override_appears_in_html_export(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a style override propagates into Rich's inline-styled HTML export."""
        # Given an Emitter with success.style overridden to a recognizable color
        e, out, _ = make_recording_emitter(theme=Theme(success=Level(style="blue")))

        # When success is emitted
        e.success("done")

        # Then the resolved color appears in the inline-styled HTML as its hex value
        # (Rich converts named colors to hex: "blue" → #000080)
        html = out.export_html(inline_styles=True)
        assert "#000080" in html

    def test_success_detail_style_override_applies_to_continuation_lines(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify detail_style propagates to indented detail lines, not the main message."""
        # Given an Emitter with success.detail_style overridden
        e, out, _ = make_recording_emitter(theme=Theme(success=Level(detail_style="magenta")))

        # When success is emitted with details
        e.success("done", details=["one", "two"])

        # Then the detail-style color appears in the HTML export as its hex value
        # (Rich converts named colors to hex: "magenta" → #800080)
        html = out.export_html(inline_styles=True)
        assert "#800080" in html

    def test_step_renders_custom_success_marker_on_completion(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify step()'s success completion uses the success.marker override."""
        # Given an Emitter with success.marker overridden
        e, out, _ = make_recording_emitter(theme=Theme(success=Level(marker="🎉 ")))

        # When a step block completes successfully
        with e.step("compiling"):
            pass

        # Then the custom marker appears and the default checkmark does not
        text = out.export_text()
        assert "🎉" in text
        assert "compiling" in text
        assert "✓" not in text

    def test_step_renders_custom_error_marker_on_fail(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify step()'s failure completion uses the error.marker override."""
        # Given an Emitter with error.marker overridden
        e, out, _ = make_recording_emitter(theme=Theme(error=Level(marker="💥 ")))

        # When a step block exits via s.fail()
        with e.step("compiling") as s:
            s.fail("aborted")

        # Then the custom error marker appears and the default ✗ does not
        text = out.export_text()
        assert "💥" in text
        assert "✗" not in text

    def test_step_spinner_renders_custom_info_style(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify the in-progress spinner header uses the info.style override."""
        # Given an Emitter with info.style overridden to a recognizable color
        e, out, _ = make_recording_emitter(theme=Theme(info=Level(style="magenta")))

        # When a step block runs
        with e.step("compiling"):
            pass

        # Then the resolved info color appears in the recorded HTML
        # (Rich converts named colors to hex: "magenta" → #800080)
        html = out.export_html(inline_styles=True)
        assert "#800080" in html.lower()


class TestCriticalThemeOverride:
    """Theme(critical=Level(...)) overrides the default style and marker for critical()."""

    def test_critical_marker_override(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify Theme(critical=Level(marker='X ')) replaces the default marker."""
        # Given an Emitter with a custom critical marker
        theme = Theme(critical=Level(marker="X "))
        e, _, err = make_recording_emitter(theme=theme)

        # When critical is emitted
        e.critical("hi")

        # Then the custom marker appears and the default does not
        text = err.export_text()
        assert "X hi" in text or "X  hi" in text  # tolerate spacing differences
        assert "‼" not in text
