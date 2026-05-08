"""Emitter class and module-level API for nclutils.pp's console output.

Construct an `Emitter` directly when you need isolated configuration - typically
in tests or when a library wants to coexist with a host CLI's output settings.
The module-level functions (`info`, `error`, `step`, etc.) delegate to a shared
default emitter, which is what most CLI authors want: one configuration, one
terminal, no instance threading.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.pretty import Pretty
from rich.protocol import is_renderable
from rich.spinner import Spinner
from rich.text import Text
from rich.theme import Theme as RichTheme

from ._logsink import _LogSink, _render_renderable_to_plain
from .constants import LogLevel, Verbosity

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from rich.console import AlignMethod, ConsoleOptions, RenderableType, RenderResult


# Level keys (`info`, `success`, etc.) duplicate `_DEFAULT_STYLES` and are NOT
# consulted for level rendering - that path uses inline-resolved styles via
# `Emitter._resolve`. They remain here so `Console(theme=THEME)` keeps working
# for users capturing default output. `header`, `header.rule`, and `sub.pipe`
# are still the only entries actively resolved at render time.
THEME = RichTheme(
    {
        "error": "bold red",
        "error.detail": "red",
        "critical": "bold white on red",
        "critical.detail": "red",
        "warning": "bold yellow",
        "warning.detail": "yellow",
        "info": "bold default",
        "info.detail": "default",
        "debug": "bold cyan",
        "debug.detail": "cyan",
        "dryrun": "bold magenta",
        "dryrun.detail": "magenta",
        "trace": "bold bright_black",
        "trace.detail": "bright_black",
        "success": "bold green",
        "success.detail": "green",
        "header": "cyan",
        "header.rule": "cyan dim",
        "sub.pipe": "bright_black",
    }
)


@dataclass(frozen=True, slots=True)
class Level:
    """Per-level theme override.

    Any field left as None inherits nclutils.pp's built-in default. `marker=""` is
    a real value meaning "no marker"; only `None` falls back to the default.
    """

    style: str | None = None
    detail_style: str | None = None
    marker: str | None = None


@dataclass(frozen=True, slots=True)
class Theme:
    """Per-level overrides for nclutils.pp output.

    Any level field left as None keeps that level's defaults entirely.
    Successive `configure(theme=...)` calls accumulate at the field level -
    overrides are not reset between calls. To fully reset, construct a new
    `Emitter` or call `set_default(Emitter())`.
    """

    info: Level | None = None
    success: Level | None = None
    warning: Level | None = None
    error: Level | None = None
    critical: Level | None = None
    debug: Level | None = None
    trace: Level | None = None
    dryrun: Level | None = None


_DEFAULT_STYLES: dict[str, tuple[str, str]] = {
    "info": ("bold default", "default"),
    "success": ("bold green", "green"),
    "warning": ("bold yellow", "yellow"),
    "error": ("bold red", "red"),
    "critical": ("bold white on red", "red"),
    "debug": ("bold cyan", "cyan"),
    "trace": ("bold bright_black", "bright_black"),
    "dryrun": ("bold magenta", "magenta"),
}

_DEFAULT_MARKERS: dict[str, str] = {
    "info": "",
    "success": "✓ ",
    "warning": "! ",
    "error": "✗ ",
    "critical": "‼ ",
    "debug": "› ",  # noqa: RUF001
    "trace": "· ",
    "dryrun": "~ ",
}

_LEVEL_NAMES: tuple[str, ...] = tuple(_DEFAULT_STYLES)

_LEVEL_TO_LOG_SEVERITY: dict[str, int] = {
    "trace": LogLevel.TRACE,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "success": logging.INFO,
    "dryrun": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def _merge_theme(base: Theme, overlay: Theme) -> Theme:
    """Return a new Theme with overlay's non-None fields applied on top of base.

    Overlay's `None` levels preserve base's level entirely. When both base and
    overlay have a Level for the same name, each field is taken from overlay
    if non-None, else from base.
    """
    merged: dict[str, Level | None] = {}
    for level_name in _LEVEL_NAMES:
        base_level: Level | None = getattr(base, level_name)
        overlay_level: Level | None = getattr(overlay, level_name)
        if overlay_level is None:
            merged[level_name] = base_level
        elif base_level is None:
            merged[level_name] = overlay_level
        else:
            merged[level_name] = Level(
                style=overlay_level.style if overlay_level.style is not None else base_level.style,
                detail_style=(
                    overlay_level.detail_style
                    if overlay_level.detail_style is not None
                    else base_level.detail_style
                ),
                marker=(
                    overlay_level.marker if overlay_level.marker is not None else base_level.marker
                ),
            )
    return Theme(**merged)


def _clamp_verbosity(level: int | Verbosity) -> Verbosity:
    """Coerce an int or Verbosity into the valid Verbosity range.

    CLI flag handlers commonly do `verbosity=verbose_count` where `verbose_count`
    can exceed TRACE; clamping keeps the public API forgiving.
    """
    clamped = min(max(int(level), Verbosity.INFO), Verbosity.TRACE)
    return Verbosity(clamped)


def _build_message_text(
    message: str | RenderableType,
    *,
    style: str,
    marker: str = "",
    tag_part: str = "",
    markup: bool = False,
) -> Text | None:
    """Compose marker + tag + message into a single Text with the level style applied.

    Returns None for renderables that are neither `str` nor `Text` so callers can
    render those through-as-is - the level chrome (marker, tag, level style) only
    composes cleanly with text-shaped messages.
    """
    if isinstance(message, str):
        msg = message if markup else escape(message)
        return Text.from_markup(f"[{style}]{marker}[/]{tag_part}[{style}]{msg}[/]")
    if isinstance(message, Text):
        body = Text.from_markup(f"[{style}]{marker}[/]{tag_part}")
        # Apply the level style as a base; spans on `message` override per-character.
        styled = Text(style=style)
        styled.append_text(message)
        body.append_text(styled)
        return body
    return None


def _message_to_log_text(message: str | RenderableType, *, markup: bool) -> str:
    """Render `message` to the plain string the logfile records.

    Strips Rich markup from strings when `markup=True` so the audit trail reflects
    what the terminal showed, not the raw markup. `Text` instances log via `.plain`.
    Other renderables are rendered through the shared no-color helper.
    """
    if isinstance(message, str):
        return Text.from_markup(message).plain if markup else message
    if isinstance(message, Text):
        return message.plain
    return _render_renderable_to_plain(message).rstrip("\n")


def _print_level(  # noqa: PLR0913
    target: Console,
    *,
    style: str,
    detail_style: str,
    marker: str,
    message: str | RenderableType,
    markup: bool = False,
    details: list[Any] | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    **kwargs: Any,
) -> None:
    """Render one styled message and any indented detail lines to `target`.

    Args:
        target: The console to print to.
        style: The fully-resolved Rich style string for the message
            (e.g. "bold green"). Interpolated directly into markup -
            not a theme key.
        detail_style: The fully-resolved Rich style string for indented
            detail lines (e.g. "green").
        marker: Leading glyph (e.g. `✓ `, `! `) shown before the message.
            Empty string suppresses the marker.
        message: The message content. A `str` is escaped (or parsed as Rich
            markup when `markup=True`) and wrapped in the level style. A
            `rich.text.Text` keeps its own spans and is prefixed with the
            level marker/tag. Any other Rich renderable is printed as-is -
            the level chrome (marker, tag, level style, right_tag) is
            skipped because it cannot be inlined alongside a multi-line
            renderable.
        markup: When True, Rich markup in `message` and any string item in
            `details` is parsed instead of escaped.
        details: Optional follow-up items, rendered as a tree beneath the
            message with `├─` prefixed on non-final items and `└─` on the
            final item. Strings are escaped (or parsed when `markup=True`)
            and rendered with `detail_style`. Rich renderables (e.g. `JSON`,
            `Syntax`, `Table`) pass through and render with their own
            coloring. Any other Python object is wrapped in `Pretty()` so
            dicts, lists, dataclasses, and arbitrary objects render with
            Rich's syntax-aware highlighting. `detail_style` does not apply
            to non-string items.
        tag: Optional dim metadata tag rendered between marker and message
            on the first line only. Caller is responsible for escaping any
            Rich markup characters in the tag.
        right_tag: Optional dim metadata tag right-aligned to the console
            width on the first line only. Caller is responsible for escaping
            any Rich markup characters in the tag.
        **kwargs: Additional keyword arguments to pass to the console.print method.
    """
    tag_part = f"[dim]{tag}[/] " if tag else ""
    body = _build_message_text(
        message, style=style, marker=marker, tag_part=tag_part, markup=markup
    )

    if body is not None:
        if right_tag:
            right = Text.from_markup(f"[dim]{right_tag}[/]")
            # max(1, ...) keeps at least one space between message and tag when
            # the line would otherwise overflow; the terminal handles wrapping.
            padding = max(1, target.width - body.cell_len - right.cell_len)
            body.append(" " * padding)
            body.append_text(right)
        target.print(body, **kwargs)
    else:
        # right_tag is dropped here - it can't compose with multi-line
        # renderables; the logfile still records it via the caller's emit path.
        target.print(message, **kwargs)

    if details:
        target.print(
            _DetailTree(details, detail_style=detail_style, markup=markup),
            **kwargs,
        )


class Step:
    """Live-updating display for a step's spinner header and streamed sub-items."""

    def __init__(
        self,
        message: str | RenderableType,
        *,
        header_style: str,
        logsink: _LogSink | None = None,
        markup: bool = False,
    ) -> None:
        header_text = _build_message_text(message, style=header_style, markup=markup)
        self.header: RenderableType = Spinner(
            "dots",
            text=header_text if header_text is not None else message,
        )
        self._subs: list[Text] = []
        self._logsink: _LogSink | None = logsink

    def sub(self, text: str | Text, *, markup: bool = False) -> None:
        """Append a sub-item rendered beneath the active step's spinner.

        Strings render as escaped text by default; pass `markup=True` to embed
        Rich markup. A `Text` instance keeps its own styling. Each sub-item is
        also written to the logfile (as an indented continuation line at INFO)
        so file consumers see sub-items in real time, mirroring the spinner
        display.

        Args:
            text: Sub-item content. Strings are escaped unless `markup=True`.
            markup: When True, parses Rich markup in `text` instead of escaping.
        """
        if isinstance(text, str):
            sub_markup = text if markup else escape(text)
            sub_text = Text.from_markup(sub_markup)
        else:
            sub_text = text
        self._subs.append(sub_text)
        if self._logsink is not None:
            # 2-space indent matches the visual nesting under the parent step.
            self._logsink.emit(
                level=_LEVEL_TO_LOG_SEVERITY["info"],
                message=f"  {sub_text.plain}",
                details=None,
            )

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """Yield header then sub-items. Live drives this on every refresh tick."""
        yield self.header
        # Connectors are derived at render time so the last item always shows
        # `└─` after each refresh tick - no need to mutate prior items on add.
        last = len(self._subs) - 1
        for i, sub_text in enumerate(self._subs):
            connector = "└─" if i == last else "├─"
            line = Text.from_markup(f"  [sub.pipe]{connector}[/] ")
            line.append_text(sub_text)
            yield line


class _DetailTree:
    """Render a `details` list with tree connectors prefixed on every line.

    Wrap each item (str -> escaped+styled Text, Rich renderable -> as-is,
    other -> Pretty) and prefix every rendered line with the appropriate
    tree glyph: `├─` for non-final items, `└─` for the final item, `│ `
    for continuation lines under a non-final item, two spaces under the
    final item.

    The connector glyphs use the `sub.pipe` theme key, matching `Step.sub()`
    so theme retuning happens in one place.
    """

    def __init__(self, items: list[Any], *, detail_style: str, markup: bool) -> None:
        self._items = items
        self._detail_style = detail_style
        self._markup = markup

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        last = len(self._items) - 1
        # 5 = 2 leading spaces + 2-cell glyph (├─/└─/│ ) + 1 trailing space
        sub_options = options.update(width=max(1, options.max_width - 5))
        for i, item in enumerate(self._items):
            is_last = i == last
            head = "└─" if is_last else "├─"
            cont = "  " if is_last else "│ "

            rendered = self._wrap(item)
            for line_idx, segments in enumerate(console.render_lines(rendered, sub_options)):
                line = Text("  ")
                line.append(head if line_idx == 0 else cont, style="sub.pipe")
                line.append(" ")
                for seg in segments:
                    if seg.text:
                        line.append(seg.text, style=seg.style if seg.style is not None else "")
                yield line

    def _wrap(self, item: Any) -> RenderableType:
        if isinstance(item, str):
            text = item if self._markup else escape(item)
            return Text.from_markup(f"[{self._detail_style}]{text}[/]")
        if is_renderable(item):
            return item
        return Pretty(item)


class Emitter:
    """Configurable console output emitter for CLI scripts.

    Holds the verbosity, quiet flag, and stdout/stderr consoles for one logical
    output stream. Construct directly to isolate configuration (e.g. in tests
    or when a library should not share global state with its host CLI). For
    typical single-process CLI use, prefer the module-level functions which
    delegate to a shared default emitter.

    Quiet semantics: `quiet=True` suppresses `info` and `success`. Warnings,
    errors, and dry-run notices always render. Debug and trace are gated by
    `verbosity` independently of `quiet`, so combining `--verbose --quiet`
    still surfaces requested debug output.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        verbosity: int | Verbosity = Verbosity.INFO,
        quiet: bool = False,
        console: Console | None = None,
        err_console: Console | None = None,
        theme: Theme | None = None,
        logfile: Path | str | None = None,
        loglevel: LogLevel = LogLevel.INFO,
        logfmt: str | None = None,
    ) -> None:
        self.verbosity: Verbosity = _clamp_verbosity(verbosity)
        self.quiet: bool = quiet
        self.console: Console = console if console is not None else Console(theme=THEME)
        self.err_console: Console = (
            err_console if err_console is not None else Console(theme=THEME, stderr=True)
        )
        self._theme: Theme = theme if theme is not None else Theme()
        self._active_step: bool = False
        self._log_t0: float | None = None
        self._logsink: _LogSink = _LogSink(
            logfile=logfile,
            loglevel=int(loglevel),
            logfmt=logfmt,
        )

    def configure(  # noqa: PLR0913
        self,
        *,
        verbosity: int | Verbosity | None = None,
        quiet: bool | None = None,
        console: Console | None = None,
        err_console: Console | None = None,
        theme: Theme | None = None,
        logfile: Path | str | None = None,
        loglevel: LogLevel | None = None,
        logfmt: str | None = None,
    ) -> None:
        """Apply a partial configuration update.

        Only fields explicitly passed are updated; omitted kwargs leave the
        existing value untouched. Use after construction to wire CLI flags
        (`-v`, `--quiet`) into the emitter without rebuilding it. Theme
        overrides accumulate at the field level across successive calls.

        `logfile`, `loglevel`, and `logfmt` reach into the emitter's internal
        `_LogSink`. Passing `logfile=None` is a no-op (omitted = leave as-is),
        matching the existing partial-update contract - there is no "disable
        logfile" sentinel; construct a fresh emitter or call
        `set_default(Emitter())` to stop logging.

        Args:
            verbosity: New verbosity level; clamped to the valid range.
            quiet: When True, suppresses info and success output.
            console: Replacement stdout console (typically only set in tests).
            err_console: Replacement stderr console (typically only set in tests).
            theme: Per-level style and marker overrides. Merged onto the
                emitter's existing theme - see `_merge_theme`.
            logfile: Replacement logfile path. Swaps the sink entirely so the
                old file is closed and a new one is opened on next emit.
            loglevel: Minimum severity written to the logfile.
            logfmt: Override for the stdlib logging format string.
        """
        if verbosity is not None:
            self.verbosity = _clamp_verbosity(verbosity)
        if quiet is not None:
            self.quiet = quiet
        if console is not None:
            self.console = console
        if err_console is not None:
            self.err_console = err_console
        if theme is not None:
            self._theme = _merge_theme(self._theme, theme)
        if logfile is not None:
            self._logsink.swap_logfile(logfile)
        if loglevel is not None:
            self._logsink.set_level(int(loglevel))
        if logfmt is not None:
            self._logsink.set_format(logfmt)

    def _resolve(self, level_name: str) -> tuple[str, str, str]:
        """Return (style, detail_style, marker) for `level_name` after applying overrides.

        Every field uses `is not None` rather than truthiness so that empty-string
        overrides survive - `Level(marker="")` hides the marker, and an empty style
        passes through to Rich rather than falling back to the default.
        """
        overrides: Level | None = getattr(self._theme, level_name)
        main_default, detail_default = _DEFAULT_STYLES[level_name]
        marker_default = _DEFAULT_MARKERS[level_name]
        if overrides is None:
            return main_default, detail_default, marker_default
        return (
            overrides.style if overrides.style is not None else main_default,
            overrides.detail_style if overrides.detail_style is not None else detail_default,
            overrides.marker if overrides.marker is not None else marker_default,
        )

    def _resolve_with_overrides(
        self,
        level_name: str,
        *,
        style: str | None,
        detail_style: str | None,
        marker: str | None,
    ) -> tuple[str, str, str]:
        """Return the (style, detail_style, marker) triple for one call.

        Layers per-call kwargs on top of `_resolve()` so a level method can let
        callers override styling for a single emit without mutating the stored
        theme. `is not None` keeps empty-string overrides - `marker=""` hides
        the marker for that call only.
        """
        base_style, base_detail, base_marker = self._resolve(level_name)
        return (
            style if style is not None else base_style,
            detail_style if detail_style is not None else base_detail,
            marker if marker is not None else base_marker,
        )

    def _elapsed_tag(self) -> str:
        """Return a Rich-escaped right-aligned timestamp tag for verbose logging.

        Lazy-initializes the reference clock on first call so timestamps reflect
        when verbose logging actually began rather than emitter construction.
        Shared by debug() and trace() so their timelines stay aligned at -vv.
        """
        if self._log_t0 is None:
            self._log_t0 = time.monotonic()
        return f"\\[+{time.monotonic() - self._log_t0:.3f}s]"

    def info(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print info-level output to stdout. Suppressed when `quiet` is True.

        `message` accepts a `str` (escaped by default; pass `markup=True` to
        embed Rich markup), a `rich.text.Text` (its own styling is preserved
        and the level marker is prefixed), or any other Rich renderable
        (rendered as-is without the level chrome).

        `details` items render below the message as indented continuation
        items. Strings are escaped unless `markup=True` and colored with the
        level's `detail_style`; Rich renderables (`JSON`, `Syntax`, `Table`, …)
        pass through unchanged; anything else is wrapped in `Pretty()` for
        syntax-aware highlighting.

        `style`, `detail_style`, and `marker` override the resolved theme for
        this call only - useful for one-off emphasis without restyling the
        whole emitter. `marker=""` suppresses the marker for the call. The
        logfile record is unaffected; these are presentation-only.
        """
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["info"],
            message=_message_to_log_text(message, markup=markup),
            details=details,
        )
        if self.quiet:
            return
        style, detail_style, marker = self._resolve_with_overrides(
            "info", style=style, detail_style=detail_style, marker=marker
        )
        _print_level(
            self.console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            **kwargs,
        )

    def success(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print success-level output to stdout. Suppressed when `quiet` is True.

        `details` items render below the message as indented continuation
        items. Strings are escaped unless `markup=True`; Rich renderables
        (`JSON`, `Syntax`, `Table`, …) pass through unchanged; anything else
        is wrapped in `Pretty()`.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
        semantics.
        """
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["success"],
            message=_message_to_log_text(message, markup=markup),
            details=details,
        )
        if self.quiet:
            return
        style, detail_style, marker = self._resolve_with_overrides(
            "success", style=style, detail_style=detail_style, marker=marker
        )
        _print_level(
            self.console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            **kwargs,
        )

    def debug(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print debug-level output to stdout. Shown with `-v` or higher.

        Right-aligns a dim `[+s.fffs]` timestamp at the console edge measuring
        elapsed monotonic seconds since verbose logging began. The right tag
        is dropped from the console line when `message` is a non-Text
        renderable (still recorded in the logfile).

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
        semantics.
        """
        elapsed = self._elapsed_tag()
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["debug"],
            message=f"{_message_to_log_text(message, markup=markup)}  {elapsed}",
            details=details,
        )
        if self.verbosity < Verbosity.DEBUG:
            return
        style, detail_style, marker = self._resolve_with_overrides(
            "debug", style=style, detail_style=detail_style, marker=marker
        )
        _print_level(
            self.console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            right_tag=elapsed,
            **kwargs,
        )

    def trace(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print trace-level output to stdout. Shown with `-vv`.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
        semantics, and `Emitter.debug` for the right-aligned elapsed tag.
        """
        elapsed = self._elapsed_tag()
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["trace"],
            message=f"{_message_to_log_text(message, markup=markup)}  {elapsed}",
            details=details,
        )
        if self.verbosity < Verbosity.TRACE:
            return
        style, detail_style, marker = self._resolve_with_overrides(
            "trace", style=style, detail_style=detail_style, marker=marker
        )
        _print_level(
            self.console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            right_tag=elapsed,
            **kwargs,
        )

    def dryrun(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print a dry-run notice to stdout. Always shown, even when `quiet`.

        Bypasses `quiet` because a dry-run notice describes an action that
        would otherwise have happened - silencing it defeats the purpose.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
        semantics.
        """
        # Include [dry-run] inline in the file message for grep-ability.
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["dryrun"],
            message=f"[dry-run] {_message_to_log_text(message, markup=markup)}",
            details=details,
        )
        style, detail_style, marker = self._resolve_with_overrides(
            "dryrun", style=style, detail_style=detail_style, marker=marker
        )
        # Escape the leading [ so Rich doesn't parse "[dry-run]" as a markup tag.
        _print_level(
            self.console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            tag="\\[dry-run]",
            **kwargs,
        )

    def warning(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print warning output to stderr. Always shown, even when `quiet`.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
        semantics.
        """
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["warning"],
            message=_message_to_log_text(message, markup=markup),
            details=details,
        )
        style, detail_style, marker = self._resolve_with_overrides(
            "warning", style=style, detail_style=detail_style, marker=marker
        )
        # Blank line before the header gives the warning block visual breathing
        # room so it doesn't blur into surrounding output.
        self.err_console.print()
        _print_level(
            self.err_console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            **kwargs,
        )

    def error(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print error output to stderr. Always shown, even when `quiet`.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
        semantics.
        """
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["error"],
            message=_message_to_log_text(message, markup=markup),
            details=details,
        )
        style, detail_style, marker = self._resolve_with_overrides(
            "error", style=style, detail_style=detail_style, marker=marker
        )
        self.err_console.print()
        _print_level(
            self.err_console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            **kwargs,
        )

    def critical(
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Print critical output to stderr. Always shown, even when `quiet`.

        Severity-only - does NOT raise. Use this for "the world is broken"
        notices that warrant a more emphatic visual than `error()`. Routes to
        `err_console`, prepends a blank line for breathing room, and renders
        with the level's resolved style, detail style, and marker (default
        `‼ `, customizable via `Theme(critical=Level(...))`).

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
        semantics.
        """
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["critical"],
            message=_message_to_log_text(message, markup=markup),
            details=details,
        )
        style, detail_style, marker = self._resolve_with_overrides(
            "critical", style=style, detail_style=detail_style, marker=marker
        )
        self.err_console.print()
        _print_level(
            self.err_console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=details,
            **kwargs,
        )

    def header(
        self,
        message: str | Text = "",
        *,
        align: AlignMethod = "center",
        markup: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print a horizontal rule with an optional title to delimit output sections.

        Wraps `Console.rule()` and frames it with blank lines so long-running
        scripts produce scannable, well-spaced sections. Suppressed when
        `quiet` is True so structural separators disappear alongside the
        info/success output they organize.

        Unlike the level methods, `message` is `str | Text` rather than
        `str | RenderableType` because `Console.rule()` itself only accepts
        a string or `Text` title - there is no sensible meaning for a `Table`
        or `Panel` rendered inline in a rule line.

        Args:
            message: Title rendered over the rule. Strings are escaped by
                default; pass `markup=True` to embed Rich markup. A `Text`
                instance keeps its own styling and is wrapped with the
                `header` style as a base.
            align: How to align the title - "left", "center", or "right".
            markup: When True, parses Rich markup in a `str` `message`
                instead of escaping.
            **kwargs: Additional keyword arguments forwarded to `Console.rule()`
                (e.g. `characters` for the line glyph, `style` for the line
                color).
        """
        if self.quiet:
            return
        title: str | Text = ""
        if isinstance(message, Text):
            base = Text.from_markup("[header]")
            base.append_text(message)
            title = base
        elif message:
            text = message if markup else escape(message)
            title = Text.from_markup(f"[header]{text}[/]")
        kwargs.setdefault("style", "header.rule")
        self.console.print()
        self.console.rule(title, align=align, **kwargs)
        self.console.print()

    @contextmanager
    def step(
        self,
        message: str | RenderableType,
        *,
        ephemeral: bool = False,
        markup: bool = False,
    ) -> Generator[Step]:
        """Show a spinner while the block runs, then a completion marker.

        On success, prints the customized (or default) success marker followed
        by the message in the success style. On any exception (including
        typer.Exit), prints the error marker then re-raises. Sub-items added
        via `Step.sub()` render beneath the spinner during the step and remain
        on screen beneath the final marker.

        When `ephemeral` is True the spinner and sub-items are cleared from the
        console on completion. Success leaves no trace; failure prints only the
        error marker so errors are not silently hidden.

        Args:
            message: Title shown next to the spinner. Strings are escaped by
                default; pass `markup=True` to embed Rich markup. A `Text`
                preserves its own styling. Other Rich renderables pass
                through to `Spinner.text` unchanged.
            ephemeral: If True, clear sub-items and the success marker on completion.
            markup: When True, parses Rich markup in a `str` `message`
                instead of escaping.

        Yields:
            A `Step` whose `sub()` method appends sub-items beneath the spinner.

        Raises:
            RuntimeError: If called inside another `step()` on the same emitter;
                rich.live.Live does not stack and a nested step would silently
                corrupt the parent's display.
        """
        if self._active_step:
            msg = "step() cannot be nested; use sequential steps instead."
            raise RuntimeError(msg)
        self._active_step = True
        info_style, _, _ = self._resolve("info")
        success_style, _, success_marker = self._resolve("success")
        error_style, _, error_marker = self._resolve("error")
        log_text = _message_to_log_text(message, markup=markup)

        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["info"],
            message=f"starting: {log_text}",
            details=None,
        )

        s = Step(message, header_style=info_style, logsink=self._logsink, markup=markup)
        failed_exc: BaseException | None = None
        try:
            with Live(s, console=self.console, refresh_per_second=12.5, transient=ephemeral):
                try:
                    yield s
                except BaseException as exc:
                    failed_exc = exc
                    if not ephemeral:
                        error_header = _build_message_text(
                            message, style=error_style, marker=error_marker, markup=markup
                        )
                        if error_header is not None:
                            s.header = error_header
                    raise
                if not ephemeral:
                    success_header = _build_message_text(
                        message, style=success_style, marker=success_marker, markup=markup
                    )
                    if success_header is not None:
                        s.header = success_header
        finally:
            self._active_step = False
            if failed_exc is not None:
                self._logsink.emit(
                    level=_LEVEL_TO_LOG_SEVERITY["error"],
                    message=f"failed: {log_text}",
                    details=[f"{type(failed_exc).__name__}: {failed_exc}"],
                )
                if ephemeral:
                    self.error(log_text)
            else:
                self._logsink.emit(
                    level=_LEVEL_TO_LOG_SEVERITY["info"],
                    message=f"succeeded: {log_text}",
                    details=None,
                )


_default = Emitter()


def get_default() -> Emitter:
    """Return the shared default emitter used by the module-level functions."""
    return _default


def set_default(emitter: Emitter) -> None:
    """Replace the shared default emitter.

    Useful in tests that want to capture output via a custom Console without
    relying on monkeypatching module globals. The module-level functions
    re-resolve the default on every call, so the swap takes effect immediately.
    """
    global _default  # noqa: PLW0603
    _default = emitter


def console() -> Console:
    """Return the default emitter's stdout Console.

    Re-resolves on every call so `set_default()` swaps take effect immediately.
    """
    return _default.console


def err_console() -> Console:
    """Return the default emitter's stderr Console.

    Re-resolves on every call so `set_default()` swaps take effect immediately.
    """
    return _default.err_console


def configure(  # noqa: PLR0913
    *,
    verbosity: int | Verbosity | None = None,
    quiet: bool | None = None,
    console: Console | None = None,
    err_console: Console | None = None,
    theme: Theme | None = None,
    logfile: Path | str | None = None,
    loglevel: LogLevel | None = None,
    logfmt: str | None = None,
) -> None:
    """Apply a partial config update to the default emitter.

    Only fields explicitly passed are updated; omitted kwargs leave the
    existing value untouched. Call after parsing CLI flags to wire `-v`,
    `--quiet`, etc. into nclutils.pp's output. Theme overrides accumulate at
    the field level across successive calls.
    """
    _default.configure(
        verbosity=verbosity,
        quiet=quiet,
        console=console,
        err_console=err_console,
        theme=theme,
        logfile=logfile,
        loglevel=loglevel,
        logfmt=logfmt,
    )


def info(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print info-level output via the default emitter.

    See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`
    semantics.
    """
    _default.info(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def success(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print success-level output via the default emitter.

    See `Emitter.success` for `message`/`markup`/`style`/`detail_style`/`marker`
    semantics.
    """
    _default.success(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def debug(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print debug-level output via the default emitter.

    See `Emitter.debug` for `message`/`markup`/`style`/`detail_style`/`marker`
    semantics.
    """
    _default.debug(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def trace(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print trace-level output via the default emitter.

    See `Emitter.trace` for `message`/`markup`/`style`/`detail_style`/`marker`
    semantics.
    """
    _default.trace(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def dryrun(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print a dry-run notice via the default emitter.

    See `Emitter.dryrun` for `message`/`markup`/`style`/`detail_style`/`marker`
    semantics.
    """
    _default.dryrun(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def warning(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print warning output via the default emitter.

    See `Emitter.warning` for `message`/`markup`/`style`/`detail_style`/`marker`
    semantics.
    """
    _default.warning(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def error(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print error output via the default emitter.

    See `Emitter.error` for `message`/`markup`/`style`/`detail_style`/`marker`
    semantics.
    """
    _default.error(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def critical(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    **kwargs: Any,
) -> None:
    """Print critical output via the default emitter. Always shown, even when `quiet`.

    Severity-only; does not raise. See `Emitter.critical` for full semantics.
    """
    _default.critical(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        **kwargs,
    )


def header(
    message: str | Text = "",
    *,
    align: AlignMethod = "center",
    markup: bool = False,
    **kwargs: Any,
) -> None:
    """Print a section header rule via the default emitter.

    See `Emitter.header` for `message`/`markup` semantics.
    """
    _default.header(message, align=align, markup=markup, **kwargs)


@contextmanager
def step(
    message: str | RenderableType, *, ephemeral: bool = False, markup: bool = False
) -> Generator[Step]:
    """Run a spinner-driven step on the default emitter.

    See `Emitter.step` for `message`/`markup` semantics.
    """
    with _default.step(message, ephemeral=ephemeral, markup=markup) as s:
        yield s


__all__ = [
    "THEME",
    "Emitter",
    "Level",
    "LogLevel",
    "Theme",
    "Verbosity",
    "configure",
    "console",
    "critical",
    "debug",
    "dryrun",
    "err_console",
    "error",
    "get_default",
    "header",
    "info",
    "set_default",
    "step",
    "success",
    "trace",
    "warning",
]
