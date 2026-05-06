"""Tests for Emitter behavior: level methods, gates, configure, header, and step lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rich.console import Console
from rich.json import JSON
from rich.pretty import Pretty
from rich.text import Text

from nclutils.pp.emitter import Emitter, Level, LogLevel, Theme, Verbosity

if TYPE_CHECKING:
    from pathlib import Path

    from .conftest import RecordingEmitterFactory


class TestLevelMethodMarkers:
    """Each Emitter level method renders with its built-in default marker."""

    @pytest.mark.parametrize(
        ("method", "expected_marker", "to_stderr"),
        [
            ("success", "✓", False),
            ("warning", "!", True),
            ("error", "✗", True),
            ("dryrun", "~", False),
            ("debug", "›", False),  # noqa: RUF001
            ("trace", "·", False),
        ],
    )
    def test_renders_default_marker_in_correct_stream(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
        expected_marker: str,
        *,
        to_stderr: bool,
    ) -> None:
        """Verify each level emits its built-in default marker on the appropriate stream."""
        # Given an Emitter at TRACE verbosity wired to recording stdout/stderr consoles
        e, out, err = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When the level method is called
        getattr(e, method)("hello")

        # Then the default marker appears in the appropriate stream alongside the message
        target_text = err.export_text() if to_stderr else out.export_text()
        assert expected_marker in target_text
        assert "hello" in target_text

    def test_info_renders_message_without_marker(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify info() prints the message and uses no marker glyph."""
        # Given a default Emitter wired to a recording console
        e, out, _ = make_recording_emitter()

        # When info is emitted
        e.info("hello")

        # Then the message appears with no level marker glyph
        text = out.export_text()
        assert "hello" in text
        for glyph in ("✓", "✗", "!", "›", "·", "~"):  # noqa: RUF001
            assert glyph not in text


class TestQuietGate:
    """`quiet=True` suppresses info, success, and header output."""

    @pytest.mark.parametrize("method", ["info", "success", "header"])
    def test_method_emits_nothing_when_quiet(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
    ) -> None:
        """Verify quiet=True suppresses the given level method entirely."""
        # Given an Emitter with quiet enabled
        e, out, _ = make_recording_emitter(quiet=True)

        # When the method is called
        getattr(e, method)("hidden")

        # Then no output is captured
        assert out.export_text() == ""


class TestVerbosityGate:
    """`verbosity` independently gates debug and trace output."""

    @pytest.mark.parametrize(
        ("method", "verbosity"),
        [
            ("debug", Verbosity.INFO),
            ("trace", Verbosity.INFO),
            ("trace", Verbosity.DEBUG),
        ],
    )
    def test_method_suppressed_below_threshold(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
        verbosity: Verbosity,
    ) -> None:
        """Verify debug/trace emit nothing when verbosity is below their threshold."""
        # Given an Emitter at the supplied verbosity
        e, out, _ = make_recording_emitter(verbosity=verbosity)

        # When the verbose-only method is called
        getattr(e, method)("hidden")

        # Then no output is captured
        assert "hidden" not in out.export_text()


class TestElapsedTag:
    """`_elapsed_tag` lazy-initializes the reference clock and reuses it."""

    def test_initializes_t0_lazily_on_first_use(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify _log_t0 is unset until the first verbose-level call."""
        # Given an Emitter that has not yet emitted at debug/trace
        e, _, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When the emitter is freshly constructed
        # Then the reference clock is unset
        assert e._log_t0 is None

    def test_reuses_t0_on_subsequent_calls(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify _log_t0 is set once and remains stable across additional debug calls."""
        # Given an Emitter at TRACE verbosity wired to a recording console
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When debug is called twice
        e.debug("first")
        t0_after_first = e._log_t0
        e.debug("second")

        # Then the clock was set on the first call and unchanged on the second
        assert t0_after_first is not None
        assert e._log_t0 == t0_after_first
        text = out.export_text()
        assert "first" in text
        assert "second" in text


class TestConfigure:
    """Emitter.configure() applies partial updates without resetting omitted fields."""

    def test_quiet_only_updates_quiet_field(self) -> None:
        """Verify configure(quiet=...) updates quiet without touching verbosity."""
        # Given a default Emitter
        e = Emitter()

        # When quiet is updated
        e.configure(quiet=True)

        # Then quiet flips and verbosity stays at the default
        assert e.quiet is True
        assert e.verbosity == Verbosity.INFO

    @pytest.mark.parametrize("attr", ["console", "err_console"])
    def test_console_kwarg_replaces_attribute(self, attr: str) -> None:
        """Verify configure(<attr>=...) installs the supplied console instance."""
        # Given a default Emitter and a fresh replacement console
        e = Emitter()
        replacement = Console()

        # When the attribute is updated via configure
        e.configure(**{attr: replacement})

        # Then the emitter's attribute is the replacement
        assert getattr(e, attr) is replacement


class TestHeader:
    """`header()` renders an aligned, framed rule when not quiet."""

    def test_renders_title_text(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify header() prints the supplied title within the rule output."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When a header with a title is emitted
        e.header("Section A")

        # Then the title appears in the captured output
        assert "Section A" in out.export_text()

    def test_emits_rule_when_no_message_supplied(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify header() with no title still emits a non-empty rule line."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When header() is called with no message
        e.header()

        # Then some content (the rule glyphs and surrounding blank lines) is captured
        assert out.export_text().strip() != ""

    @pytest.mark.parametrize("align", ["left", "center", "right"])
    def test_forwards_alignment_to_console_rule(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        align: str,
    ) -> None:
        """Verify header() accepts each alignment value without errors."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When header() is called with the supplied alignment
        e.header("Section A", align=align)

        # Then the title still appears in the output
        assert "Section A" in out.export_text()


class TestStepRendering:
    """`Step` (the sub-item renderable yielded by `step()`) draws a tree of sub-items."""

    def test_sub_renders_tree_connectors_for_multiple_items(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify sub-items render with ├─ for inner items and └─ for the last."""
        # Given a default Emitter wired to a recording console
        e, out, _ = make_recording_emitter()

        # When a step adds two sub-items
        with e.step("compiling") as s:
            s.sub("part one")
            s.sub("part two")

        # Then both items render and the tree connectors appear
        text = out.export_text()
        assert "part one" in text
        assert "part two" in text
        assert "├─" in text
        assert "└─" in text

    def test_sub_escapes_rich_markup_in_user_text(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify Step.sub() escapes user text so bracket sequences cannot inject styling."""
        # Given a default Emitter wired to a recording console
        e, out, _ = make_recording_emitter()

        # When a sub-item contains Rich-markup-like brackets
        with e.step("compiling") as s:
            s.sub("[red]raw[/]")

        # Then the bracketed text appears verbatim rather than being parsed as markup
        assert "[red]raw[/]" in out.export_text()


class TestStepLifecycle:
    """`step()` enforces no-nesting, supports ephemeral mode, and resets active state."""

    def test_raises_runtime_error_when_nested_on_same_emitter(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify entering step() inside an active step raises RuntimeError."""
        # Given an Emitter with an active outer step
        e, _, _ = make_recording_emitter()

        # When a nested step is opened on the same emitter
        # Then RuntimeError is raised explaining nesting is unsupported.
        # `pytest.raises` opens before `e.step("inner")`, so the inner step's
        # __enter__ raises while still inside the raises context.
        with (
            e.step("outer"),
            pytest.raises(RuntimeError, match="cannot be nested"),
            e.step("inner"),
        ):
            pass

    def test_ephemeral_success_skips_success_marker_render(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify ephemeral=True does not emit a success-marker line on completion."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When an ephemeral step completes successfully
        with e.step("compiling", ephemeral=True):
            pass

        # Then the success marker is never written.
        # (Console(record=True) captures spinner writes even though Live's
        # `transient` mode wipes them from the terminal at runtime, so the right
        # signal is the absence of the success-state header that the
        # non-ephemeral path produces.)
        assert "✓" not in out.export_text()

    def test_ephemeral_failure_emits_error_to_stderr(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify ephemeral failure clears the spinner but surfaces an error on stderr."""
        # Given a default Emitter wired to recording consoles
        e, _, err = make_recording_emitter()

        # When an ephemeral step body raises
        err_msg = "boom"
        with pytest.raises(RuntimeError, match=err_msg), e.step("compiling", ephemeral=True):
            raise RuntimeError(err_msg)

        # Then an error with the step message lands on stderr with the default error marker
        err_text = err.export_text()
        assert "compiling" in err_text
        assert "✗" in err_text

    def test_active_flag_resets_after_successful_completion(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a fresh step() can run after a prior step completes successfully."""
        # Given an Emitter that already ran one step
        e, _, _ = make_recording_emitter()
        with e.step("first"):
            pass

        # When a second step is opened
        # Then it does not raise (proves _active_step was reset)
        with e.step("second"):
            pass

    def test_active_flag_resets_after_exception(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a fresh step() can run after a prior step's body raised."""
        # Given an Emitter whose first step body raised
        e, _, _ = make_recording_emitter()
        err_msg = "boom"
        with pytest.raises(RuntimeError, match=err_msg), e.step("first"):
            raise RuntimeError(err_msg)

        # When a second step is opened
        # Then it does not raise (proves _active_step was reset by the finally block)
        with e.step("second"):
            pass


class TestPrettyDetails:
    """Non-string details auto-render as Rich Pretty; renderables pass through."""

    def test_dict_detail_renders_via_pretty(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a dict in details is rendered through Pretty, not the string path."""
        # Given an Emitter with a debug.detail_style color Rich's Pretty
        # highlighter never uses - any occurrence in the HTML proves the
        # str branch ran instead of Pretty
        e, out, _ = make_recording_emitter(
            verbosity=Verbosity.TRACE,
            theme=Theme(debug=Level(detail_style="#abcdef")),
        )

        # When debug is emitted with a dict in details
        e.debug("payload", details=[{"status": 200, "kind": "ok"}])

        # Then the dict's keys and values appear in the rendered output
        text = out.export_text()
        assert "status" in text
        assert "200" in text
        assert "kind" in text
        assert "ok" in text

        # And the discriminator color is absent from the HTML
        html = out.export_html(inline_styles=True)
        assert "#abcdef" not in html

    def test_rich_renderable_detail_passes_through(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a Rich renderable like JSON passes through and renders."""
        # Given an Emitter at TRACE verbosity wired to a recording stdout
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When debug is emitted with a JSON renderable in details
        e.debug("response", details=[JSON('{"a": 1}')])

        # Then the JSON content appears in the rendered output
        text = out.export_text()
        assert '"a"' in text
        assert "1" in text

    def test_mixed_details_all_indent_to_same_column(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify str, dict, and Rich renderable details all indent uniformly."""
        # Given an Emitter at TRACE verbosity wired to a recording stdout
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When debug is emitted with mixed-type details
        e.debug(
            "mixed",
            details=["plain string", {"k": "v"}, JSON('{"x": 2}')],
        )

        # Then every non-empty content line below the header begins with the
        # 2-space indent supplied by Padding.indent
        lines = out.export_text().splitlines()
        content_lines = [ln for ln in lines[1:] if ln.strip()]
        assert content_lines, "expected at least one detail line"
        for ln in content_lines:
            assert ln.startswith("  "), f"detail line not indented: {ln!r}"


class TestCriticalLevel:
    """`critical()` prints to stderr with its own marker, ignores quiet, and respects theme overrides."""

    def test_renders_default_marker_on_stderr(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify critical() prints with the default marker on err_console."""
        # Given a default Emitter wired to recording consoles
        e, _, err = make_recording_emitter()

        # When critical is emitted
        e.critical("the disk is on fire")

        # Then the default critical marker and the message appear on stderr
        text = err.export_text()
        assert "‼" in text
        assert "the disk is on fire" in text

    def test_renders_when_quiet(self, make_recording_emitter: RecordingEmitterFactory) -> None:
        """Verify critical() always renders, regardless of quiet=True."""
        # Given a quiet Emitter
        e, _, err = make_recording_emitter(quiet=True)

        # When critical is emitted
        e.critical("still important")

        # Then the message still appears (quiet does not gate critical)
        assert "still important" in err.export_text()

    def test_does_not_render_to_stdout(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify critical() routes only to err_console, not console."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When critical is emitted
        e.critical("server down")

        # Then nothing about the message appears on stdout
        assert "server down" not in out.export_text()


class TestLogLevelEnum:
    """`LogLevel` aligns with stdlib logging numerics so the file substrate composes cleanly."""

    def test_loglevel_numerics_match_stdlib(self) -> None:
        """Verify each LogLevel member has the expected stdlib-aligned numeric value."""
        # When inspecting each member's value
        # Then the numerics match stdlib logging's standard severities, with TRACE=5
        assert LogLevel.TRACE == 5
        assert LogLevel.DEBUG == 10
        assert LogLevel.INFO == 20
        assert LogLevel.WARNING == 30
        assert LogLevel.ERROR == 40
        assert LogLevel.CRITICAL == 50

    def test_loglevel_is_intenum_for_int_comparison(self) -> None:
        """Verify LogLevel is an IntEnum so users can compare with int filter cutoffs."""
        # When comparing them with int operators
        # Then ordering works as expected
        assert LogLevel.WARNING > LogLevel.INFO
        assert LogLevel.DEBUG < LogLevel.WARNING
        assert int(LogLevel.INFO) == 20


class TestPerCallStyleOverrides:
    """Per-call `style`, `detail_style`, and `marker` kwargs override the resolved theme for one call."""

    def test_info_accepts_style_kwarg_without_collision(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify info(message, style=...) does not collide with _print_level's style parameter."""
        # Given a default Emitter wired to a recording stdout
        e, out, _ = make_recording_emitter()

        # When info is called with a style kwarg
        e.info("test", style="bold green")

        # Then the message renders without raising
        assert "test" in out.export_text()

    @pytest.mark.parametrize(
        ("method", "to_stderr"),
        [
            ("info", False),
            ("error", True),
        ],
    )
    def test_per_call_style_appears_in_html_export(
        self,
        make_recording_emitter: RecordingEmitterFactory,
        method: str,
        *,
        to_stderr: bool,
    ) -> None:
        """Verify a per-call style kwarg propagates to the message's rendered color."""
        # Given an Emitter with no theme overrides
        e, out, err = make_recording_emitter()
        target = err if to_stderr else out

        # When the level is emitted with a per-call style override (Rich maps "blue" → #000080)
        getattr(e, method)("hello", style="blue")

        # Then the resolved color appears in the inline-styled HTML
        assert "#000080" in target.export_html(inline_styles=True)

    def test_per_call_detail_style_applies_to_continuation_lines(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a per-call detail_style override colors the indented detail items."""
        # Given an Emitter with no theme overrides
        e, out, _ = make_recording_emitter()

        # When info is emitted with a detail_style override and string details
        # (Rich maps "magenta" → #800080)
        e.info("hello", details=["one", "two"], detail_style="magenta")

        # Then the detail color appears in the inline-styled HTML
        assert "#800080" in out.export_html(inline_styles=True)

    def test_per_call_marker_replaces_default(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a per-call marker override replaces the level's default marker."""
        # Given an Emitter with default success styling
        e, out, _ = make_recording_emitter()

        # When success is emitted with a custom marker for this call only
        e.success("done", marker="🎉 ")

        # Then the custom marker prefixes the message and the default ✓ does not appear
        text = out.export_text()
        assert "🎉 done" in text
        assert "✓" not in text

    def test_per_call_marker_empty_string_suppresses(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify marker='' on a call renders no marker prefix for that call."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When success is emitted with an explicit empty marker
        e.success("done", marker="")

        # Then the message renders with no ✓ glyph
        text = out.export_text()
        assert "done" in text
        assert "✓" not in text

    def test_per_call_overrides_do_not_mutate_emitter_theme(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a per-call override does not leak into subsequent calls or stored theme."""
        # Given an Emitter with default styling
        e, out, _ = make_recording_emitter()

        # When success is emitted once with overrides, then again without
        e.success("first", style="blue", marker="🎉 ")
        e.success("second")

        # Then the second call uses defaults: stored theme is unchanged and ✓ marker reappears
        assert e._theme == Theme()
        text = out.export_text()
        assert "🎉 first" in text
        assert "✓ second" in text

    def test_per_call_overrides_layer_on_theme(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a per-call override beats the stored theme override for one call only."""
        # Given an Emitter with success.style=blue baked into the theme
        e, out, _ = make_recording_emitter(theme=Theme(success=Level(style="blue")))

        # When success is emitted with a different per-call style (Rich maps "magenta" → #800080)
        e.success("done", style="magenta")

        # Then the per-call color (magenta) appears, not the theme's blue (#000080)
        html = out.export_html(inline_styles=True)
        assert "#800080" in html
        assert "#000080" not in html

    def test_per_call_overrides_do_not_change_logfile_output(self, tmp_path: Path) -> None:
        """Verify cosmetic per-call style/detail_style/marker do not alter logfile content."""
        # Given two Emitters writing to separate logfiles
        plain_log = tmp_path / "plain.log"
        styled_log = tmp_path / "styled.log"
        plain = Emitter(logfile=plain_log)
        styled = Emitter(logfile=styled_log)

        # When the same message is emitted, one with cosmetic overrides
        plain.info("hello", details=["one"])
        styled.info(
            "hello", details=["one"], style="bold blue", marker="🎉 ", detail_style="magenta"
        )

        # Then the logfile records carry identical INFO content (cosmetic kwargs are presentation-only)
        plain_lines = plain_log.read_text(encoding="utf-8").splitlines()
        styled_lines = styled_log.read_text(encoding="utf-8").splitlines()
        plain_payload = [ln.split(" ", 2)[-1] for ln in plain_lines]
        styled_payload = [ln.split(" ", 2)[-1] for ln in styled_lines]
        assert plain_payload == styled_payload

    def test_quiet_still_suppresses_info_with_per_call_overrides(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify per-call overrides do not bypass the quiet gate on info()."""
        # Given a quiet Emitter
        e, out, _ = make_recording_emitter(quiet=True)

        # When info is called with per-call overrides
        e.info("hidden", style="bold red", marker="X ")

        # Then nothing renders; quiet still gates info regardless of cosmetic kwargs
        assert out.export_text() == ""

    def test_per_call_overrides_apply_to_all_level_methods(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify every level method on Emitter accepts per-call style/detail_style/marker."""
        # Given an Emitter at TRACE so debug and trace render
        e, out, err = make_recording_emitter(verbosity=Verbosity.TRACE)
        levels = ["info", "success", "debug", "trace", "dryrun", "warning", "error", "critical"]

        # When every level is emitted with per-call overrides
        for level in levels:
            getattr(e, level)(level, style="bold blue", detail_style="cyan", marker="X ")

        # Then no call raised, the custom marker appears, and every message reached its
        # appropriate stream. dryrun renders "X [dry-run] dryrun" so the marker and
        # message text are checked separately rather than as a contiguous slice.
        combined = out.export_text() + err.export_text()
        assert combined.count("X ") >= len(levels)
        for level in levels:
            assert level in combined


class TestLevelMethodMarkup:
    """`markup=True` lets callers embed Rich markup in level method messages."""

    def test_default_escapes_brackets_in_message(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify info() default treats [bracket] sequences as literal text."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When info is emitted with bracket-like text and no markup flag
        e.info("[bold]hello[/]")

        # Then the brackets appear verbatim (not parsed as markup)
        assert "[bold]hello[/]" in out.export_text()

    def test_markup_true_parses_brackets_as_styling(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify info(message, markup=True) interprets brackets as Rich markup."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When info is emitted with markup=True
        e.info("[underline]hello[/] world", markup=True)

        # Then the brackets are gone (parsed as styling) and an underline appears in HTML.
        # Both export_* default-clear the record buffer, so the first call must opt out.
        html = out.export_html(inline_styles=True, clear=False)
        text = out.export_text()
        assert "[underline]" not in text
        assert "[/]" not in text
        assert "hello" in text
        assert "world" in text
        assert "underline" in html

    def test_markup_false_keeps_default_escape_behavior(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify markup=False is identical to omitting the kwarg (escape applied)."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When info is emitted with markup=False
        e.info("[bold]hello[/]", markup=False)

        # Then brackets render verbatim, same as the default
        assert "[bold]hello[/]" in out.export_text()

    def test_markup_true_applies_to_string_details_too(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify markup=True parses Rich markup in string details for the same call."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When info is emitted with markup=True and bracket-laden details
        e.info("hi", details=["[underline]item[/]"], markup=True)

        # Then the detail brackets are parsed (no literal brackets in output)
        text = out.export_text()
        assert "item" in text
        assert "[underline]" not in text
        assert "[/]" not in text

    def test_markup_true_keeps_marker_and_level_style(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify markup=True still prefixes the level marker and applies the level style."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When success is emitted with inline markup
        e.success("[bold]done[/]", markup=True)

        # Then the success marker and message are present
        text = out.export_text()
        assert "✓" in text
        assert "done" in text

    def test_markup_true_compatible_with_debug_right_tag(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify debug() with markup=True still emits the right-aligned [+s] elapsed tag."""
        # Given an Emitter at TRACE so debug renders
        e, out, _ = make_recording_emitter(verbosity=Verbosity.TRACE)

        # When debug is called with markup
        e.debug("[underline]step[/]", markup=True)

        # Then both the parsed message and the elapsed tag appear
        text = out.export_text()
        assert "step" in text
        assert "[+" in text
        assert "s]" in text


class TestLevelMethodTextMessage:
    """Level methods accept `rich.text.Text` instances and preserve their inline styling."""

    def test_text_message_preserves_inline_styling(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify info(Text.from_markup(...)) renders the Text's own styling."""
        # Given a default Emitter and a Text with inline emphasis
        e, out, _ = make_recording_emitter()

        # When info is emitted with a Text instance
        e.info(Text.from_markup("[underline]important[/] note"))

        # Then the Text's content appears and its styling is reflected in HTML
        html = out.export_html(inline_styles=True, clear=False)
        text = out.export_text()
        assert "important" in text
        assert "note" in text
        assert "underline" in html

    def test_text_message_includes_level_marker(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a Text message still receives the level's marker prefix."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When success is emitted with a Text message
        e.success(Text("done"))

        # Then the success marker prefixes the rendered Text
        assert "✓ done" in out.export_text()

    def test_arbitrary_renderable_message_passes_through(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify a non-Text renderable (e.g. Pretty) renders without raising."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When info is emitted with a Pretty renderable as the message
        e.info(Pretty({"k": "v"}))

        # Then the renderable's content appears
        text = out.export_text()
        assert "k" in text
        assert "v" in text


class TestHeaderMarkup:
    """`header()` accepts a markup flag and Text instances for inline emphasis."""

    def test_default_escapes_brackets_in_title(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify header() default treats brackets as literal text in the title."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When header() is called with bracket-like text
        e.header("[bold]Section[/]")

        # Then the brackets appear verbatim
        assert "[bold]Section[/]" in out.export_text()

    def test_markup_true_parses_brackets_in_title(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify header(message, markup=True) renders brackets as Rich markup."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When header() is called with inline markup
        e.header("[underline]Section[/]", markup=True)

        # Then the brackets are gone and the styling appears in HTML
        html = out.export_html(inline_styles=True, clear=False)
        text = out.export_text()
        assert "Section" in text
        assert "[underline]" not in text
        assert "underline" in html

    def test_text_title_preserves_styling(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify header(Text(...)) renders the Text instance directly as the title."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When header() is called with a Text title
        e.header(Text.from_markup("[underline]Section[/]"))

        # Then the Text content appears and the underline styling is present
        html = out.export_html(inline_styles=True, clear=False)
        text = out.export_text()
        assert "Section" in text
        assert "underline" in html


class TestStepMarkup:
    """`step()` accepts markup=True and Text instances for the title."""

    def test_step_default_escapes_brackets_in_title(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify step() default treats title brackets as literal text."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When a step runs with bracket-like title text
        with e.step("[bold]compiling[/]"):
            pass

        # Then the brackets appear verbatim
        assert "[bold]compiling[/]" in out.export_text()

    def test_step_markup_true_parses_brackets_in_title(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify step(message, markup=True) renders the title with inline markup."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When a step runs with inline markup
        with e.step("[underline]compiling[/]", markup=True):
            pass

        # Then the brackets are gone and the styling is present
        html = out.export_html(inline_styles=True, clear=False)
        text = out.export_text()
        assert "compiling" in text
        assert "[underline]" not in text
        assert "underline" in html

    def test_step_text_title_preserves_styling(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify step(Text.from_markup(...)) renders the styled Text title."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When a step runs with a Text title
        with e.step(Text.from_markup("[underline]compiling[/]")):
            pass

        # Then the underline styling appears in the rendered output
        assert "underline" in out.export_html(inline_styles=True)


class TestSubMarkup:
    """`Step.sub()` accepts markup=True and Text instances for sub-item text."""

    def test_sub_default_escapes_brackets(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify Step.sub() default treats brackets as literal (regression coverage)."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When a sub-item contains bracket-like text and no markup flag
        with e.step("compiling") as s:
            s.sub("[red]raw[/]")

        # Then the brackets appear verbatim
        assert "[red]raw[/]" in out.export_text()

    def test_sub_markup_true_parses_brackets(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify Step.sub(text, markup=True) interprets brackets as Rich markup."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When a sub-item is added with markup=True
        with e.step("compiling") as s:
            s.sub("[underline]raw[/]", markup=True)

        # Then the brackets are gone and the styling appears in HTML
        html = out.export_html(inline_styles=True, clear=False)
        text = out.export_text()
        assert "raw" in text
        assert "[underline]" not in text
        assert "underline" in html

    def test_sub_text_instance_preserves_styling(
        self, make_recording_emitter: RecordingEmitterFactory
    ) -> None:
        """Verify Step.sub(Text.from_markup(...)) renders the styled Text content."""
        # Given a default Emitter
        e, out, _ = make_recording_emitter()

        # When a sub-item is added as a Text instance
        with e.step("compiling") as s:
            s.sub(Text.from_markup("[underline]raw[/]"))

        # Then the underline styling appears in the rendered output
        assert "underline" in out.export_html(inline_styles=True)
