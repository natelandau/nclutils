"""Emitter class and module-level API for nclutils.pp's console output.

Construct an `Emitter` directly when you need isolated configuration - typically
in tests or when a library wants to coexist with a host CLI's output settings.
The module-level functions (`info`, `error`, `step`, etc.) delegate to a shared
default emitter, which is what most CLI authors want: one configuration, one
terminal, no instance threading.
"""

from __future__ import annotations

import logging
import sys
import time
import traceback as _traceback
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

_ASCII_MARKERS: dict[str, str] = {
    "info": "",
    "success": "+ ",
    "warning": "! ",
    "error": "x ",
    "critical": "!! ",
    "debug": "> ",
    "trace": ". ",
    "dryrun": "~ ",
}


def _ascii_required(console: Console) -> bool:
    """Return True when the console's encoding can't produce our default unicode glyphs.

    Probes by attempting to encode the connector and marker glyphs together.
    Any `UnicodeEncodeError` or `LookupError` indicates the console can't
    display them safely; in that case callers should fall back to ASCII
    rendering for both connectors and default markers.
    """
    try:
        "├─└─│✓✗‼›·".encode(console.encoding, errors="strict")  # noqa: RUF001
    except (UnicodeEncodeError, LookupError):
        return True
    return False


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


def _apply_tag_to_logmsg(tag: str | None, message: str) -> str:
    """Prepend `[tag] ` to a log message body when tag is set.

    Keeps caller-supplied audit metadata visible in the logfile so grep over
    file output finds the same labels the operator saw on the console.
    """
    if tag:
        return f"[{tag}] {message}"
    return message


def _resolve_exception(exception: BaseException | bool) -> BaseException | None:  # noqa: FBT001 -- bool is a real value in the public contract (mirrors logging.exception)
    """Resolve the `exception=` kwarg to an actual exception instance or None.

    `False` returns None. `True` calls `sys.exc_info()` and returns the active
    exception (None if there isn't one, matching `logging.exception()` semantics
    so callers outside an `except` block become a silent no-op). A
    `BaseException` instance is returned as-is.
    """
    if exception is False:
        return None
    if exception is True:
        _, exc, _ = sys.exc_info()
        return exc
    return exception


def _attach_exception_to_details(
    details: list[Any] | None,
    exception: BaseException | bool,  # noqa: FBT001 -- bool is a real value in the public contract
    *,
    show_locals: bool,
) -> list[Any] | None:
    """Append a Rich Traceback for `exception` to `details`.

    Returns a new list with the Traceback renderable as the final item, or
    `details` unchanged when `exception` resolves to no traceback. Imports
    `rich.traceback.Traceback` lazily so callers that never use this kwarg
    don't pay the import cost at module load time.
    """
    exc = _resolve_exception(exception)
    if exc is None:
        return details
    # Lazy import: callers without exception= avoid the rich.traceback module cost.
    from rich.traceback import Traceback  # noqa: PLC0415

    rich_tb = Traceback.from_exception(
        type(exc),
        exc,
        exc.__traceback__,
        show_locals=show_locals,
    )
    new_details = list(details) if details else []
    new_details.append(rich_tb)
    return new_details


def _format_exception_for_logfile(exception: BaseException | bool) -> list[str] | None:  # noqa: FBT001 -- bool is a real value in the public contract
    """Format an exception's traceback as a list of strings for logfile continuation lines.

    Returns None when there's nothing to attach (`exception=False` or
    `exception=True` with no active exception). The resulting strings have no
    color codes; the logfile path strips Rich coloring anyway.

    The returned strings are pre-escaped for Rich markup so that any bracket
    characters in the exception message survive the logfile path's
    string-as-markup rendering in `_render_details_to_lines`. Without escaping,
    a message like `KeyError: ['missing_key']` would have the bracketed portion
    silently stripped by Rich's markup parser.
    """
    exc = _resolve_exception(exception)
    if exc is None:
        return None
    return [
        escape(line.rstrip("\n"))
        for chunk in _traceback.format_exception(type(exc), exc, exc.__traceback__)
        for line in chunk.splitlines()
    ]


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
    # ASCII fallback: substitute the default unicode marker only when the console
    # can't encode it AND the marker is the built-in default (not a user override).
    if _ascii_required(target):
        for level_name, default in _DEFAULT_MARKERS.items():
            # `default != ""` skips info's empty default so the loop is a true no-op
            # for info; user-supplied overrides won't equal any default and pass through.
            if marker == default and default != "":
                marker = _ASCII_MARKERS[level_name]
                break
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
        if _ascii_required(console):
            # ASCII fallback: simple `- ` prefix on every sub-item, no tree connectors.
            for sub_text in self._subs:
                line = Text("  - ")
                line.append_text(sub_text)
                yield line
            return
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
        if _ascii_required(console):
            # ASCII fallback: simple `- ` prefix on every line, no tree connectors.
            # 4 = "  - " width on the first line; continuation lines use the same indent.
            sub_options = options.update(width=max(1, options.max_width - 4))
            for item in self._items:
                rendered = self._wrap(item)
                for line_idx, segments in enumerate(console.render_lines(rendered, sub_options)):
                    line = Text("  ")
                    line.append("- " if line_idx == 0 else "  ")
                    for seg in segments:
                        if seg.text:
                            line.append(seg.text, style=seg.style if seg.style is not None else "")
                    yield line
            return

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


class _KVBlock:
    """Render aligned key/value pairs as a column block.

    Keys render dim and are padded to the widest key's width before the
    separator. Values render in the console's default style. Multi-line
    string values align continuation lines under the value column. Rich
    renderables render below the key, indented to the value column.
    """

    def __init__(
        self,
        items: list[tuple[str, Any]],
        *,
        indent: int,
        separator: str,
        markup: bool,
    ) -> None:
        self._items = items
        self._indent = indent
        self._separator = separator
        self._markup = markup

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        if not self._items:
            return
        widest = max(len(k) for k, _ in self._items)
        prefix = " " * self._indent
        # Pad the (key + separator) cell so values align in a single column.
        cell_width = widest + len(self._separator)
        cont_indent = self._indent + cell_width

        for key, value in self._items:
            key_part = self._key_text(key, cell_width)
            if not isinstance(value, (str, Text)) and is_renderable(value):
                yield from self._render_renderable_row(
                    console, options, prefix, key_part, value, cont_indent
                )
                continue
            yield from self._render_text_row(prefix, key_part, value, cont_indent)

    def _key_text(self, key: str, cell_width: int) -> Text:
        # Keys render dim; the separator + alignment padding stay in the
        # default style so the colon visually anchors to the key text.
        pad = " " * (cell_width - len(key) - len(self._separator))
        key_part = Text(key, style="dim")
        key_part.append(self._separator)
        key_part.append(pad)
        return key_part

    def _value_text(self, value: Any) -> Text:
        if isinstance(value, str):
            return Text.from_markup(value) if self._markup else Text(escape(value))
        if isinstance(value, Text):
            return value
        return Text(str(value))

    def _render_text_row(
        self, prefix: str, key_part: Text, value: Any, cont_indent: int
    ) -> RenderResult:
        value_text = self._value_text(value)
        lines = value_text.split("\n", allow_blank=True)
        first = Text(prefix)
        first.append_text(key_part)
        first.append_text(lines[0])
        yield first
        for line in lines[1:]:
            cont = Text(" " * cont_indent)
            cont.append_text(line)
            yield cont

    def _render_renderable_row(
        self,
        console: Console,
        options: ConsoleOptions,
        prefix: str,
        key_part: Text,
        value: Any,
        cont_indent: int,
    ) -> RenderResult:
        # Rich renderable: render below the key on its own line(s),
        # indented to the value column.
        head = Text(prefix)
        head.append_text(key_part)
        yield head
        sub_options = options.update(width=max(1, options.max_width - cont_indent))
        for sub_line in console.render_lines(value, sub_options):
            out_line = Text(" " * cont_indent)
            for seg in sub_line:
                if seg.text:
                    out_line.append(
                        seg.text,
                        style=seg.style if seg.style is not None else "",
                    )
            yield out_line


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

    def info(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
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

        `tag` adds a dim left-side metadata tag rendered between marker and
        message (e.g. `[api] ✓ saved`). The tag is recorded inline in the
        logfile message as `[tag] msg` so audit grep stays useful. The caller
        is responsible for escaping any Rich markup characters in the tag.

        `right_tag` adds a dim right-aligned metadata tag on the first line
        only. It is presentation-only and is NOT recorded in the logfile. The
        caller is responsible for escaping any Rich markup characters in the
        tag.

        `exception` attaches a styled Rich Traceback below the message. Pass
        an explicit exception instance, or `True` inside an `except` block to
        grab `sys.exc_info()`. Outside an except block, `exception=True` is a
        silent no-op (matches `logging.exception()` behavior). The formatted
        traceback is also written to the logfile as continuation lines under
        the parent record at the same severity. `show_locals=True` flows
        through to Rich's Traceback for verbose dumps.
        """
        log_message = _apply_tag_to_logmsg(tag, _message_to_log_text(message, markup=markup))
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["info"],
            message=log_message,
            details=log_details or None,
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
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=tag,
            right_tag=right_tag,
            **kwargs,
        )

    def success(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print success-level output to stdout. Suppressed when `quiet` is True.

        `details` items render below the message as indented continuation
        items. Strings are escaped unless `markup=True`; Rich renderables
        (`JSON`, `Syntax`, `Table`, …) pass through unchanged; anything else
        is wrapped in `Pretty()`.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`,
        `tag`/`right_tag`, and `exception`/`show_locals` semantics.
        """
        log_message = _apply_tag_to_logmsg(tag, _message_to_log_text(message, markup=markup))
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["success"],
            message=log_message,
            details=log_details or None,
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
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=tag,
            right_tag=right_tag,
            **kwargs,
        )

    def debug(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print debug-level output to stdout. Shown with `-v` or higher.

        Right-aligns a dim `[+s.fffs]` timestamp at the console edge measuring
        elapsed monotonic seconds since verbose logging began. The right tag
        is dropped from the console line when `message` is a non-Text
        renderable (still recorded in the logfile).

        Pass `right_tag` to override the auto-elapsed marker on the console
        for one call (e.g. `right_tag="db: 1.2s"`); the logfile still records
        the auto-elapsed `[+s.fffs]` marker so the audit timeline is preserved.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`,
        `tag`/`right_tag`, and `exception`/`show_locals` semantics.
        """
        elapsed = self._elapsed_tag()
        log_message = _apply_tag_to_logmsg(
            tag,
            f"{_message_to_log_text(message, markup=markup)}  {elapsed}",
        )
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["debug"],
            message=log_message,
            details=log_details or None,
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
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=tag,
            right_tag=right_tag if right_tag is not None else elapsed,
            **kwargs,
        )

    def trace(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print trace-level output to stdout. Shown with `-vv`.

        Pass `right_tag` to override the auto-elapsed marker on the console
        for one call; the logfile still records the auto-elapsed `[+s.fffs]`
        marker so the audit timeline is preserved.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`,
        `tag`/`right_tag`, and `exception`/`show_locals` semantics, and
        `Emitter.debug` for the right-aligned elapsed tag.
        """
        elapsed = self._elapsed_tag()
        log_message = _apply_tag_to_logmsg(
            tag,
            f"{_message_to_log_text(message, markup=markup)}  {elapsed}",
        )
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["trace"],
            message=log_message,
            details=log_details or None,
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
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=tag,
            right_tag=right_tag if right_tag is not None else elapsed,
            **kwargs,
        )

    def dryrun(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print a dry-run notice to stdout. Always shown, even when `quiet`.

        Bypasses `quiet` because a dry-run notice describes an action that
        would otherwise have happened - silencing it defeats the purpose.

        When `tag` is supplied, it renders before the existing `[dry-run]`
        marker (e.g. `[deploy] [dry-run] would push`) on both the console
        and in the logfile.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`,
        `tag`/`right_tag`, and `exception`/`show_locals` semantics.
        """
        # Include [dry-run] inline in the file message for grep-ability, and
        # prepend any caller-supplied tag so audit grep finds the same labels
        # the operator saw on the console.
        log_body = f"[dry-run] {_message_to_log_text(message, markup=markup)}"
        log_body = _apply_tag_to_logmsg(tag, log_body)
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["dryrun"],
            message=log_body,
            details=log_details or None,
        )
        style, detail_style, marker = self._resolve_with_overrides(
            "dryrun", style=style, detail_style=detail_style, marker=marker
        )
        # Escape the leading [ so Rich doesn't parse "[dry-run]" as a markup
        # tag; the same escape applies when combining with a caller tag.
        combined_tag = f"{tag} \\[dry-run]" if tag else "\\[dry-run]"
        _print_level(
            self.console,
            style=style,
            detail_style=detail_style,
            marker=marker,
            message=message,
            markup=markup,
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=combined_tag,
            right_tag=right_tag,
            **kwargs,
        )

    def warning(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print warning output to stderr. Always shown, even when `quiet`.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`,
        `tag`/`right_tag`, and `exception`/`show_locals` semantics.
        """
        log_message = _apply_tag_to_logmsg(tag, _message_to_log_text(message, markup=markup))
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["warning"],
            message=log_message,
            details=log_details or None,
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
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=tag,
            right_tag=right_tag,
            **kwargs,
        )

    def error(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print error output to stderr. Always shown, even when `quiet`.

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`,
        `tag`/`right_tag`, and `exception`/`show_locals` semantics. The
        `exception=` kwarg is particularly natural here: pass `True` from
        inside an `except` block to attach the active traceback alongside the
        message.
        """
        log_message = _apply_tag_to_logmsg(tag, _message_to_log_text(message, markup=markup))
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["error"],
            message=log_message,
            details=log_details or None,
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
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=tag,
            right_tag=right_tag,
            **kwargs,
        )

    def critical(  # noqa: PLR0913
        self,
        message: str | RenderableType,
        *,
        details: list[Any] | None = None,
        markup: bool = False,
        style: str | None = None,
        detail_style: str | None = None,
        marker: str | None = None,
        tag: str | None = None,
        right_tag: str | None = None,
        exception: BaseException | bool = False,
        show_locals: bool = False,
        **kwargs: Any,
    ) -> None:
        """Print critical output to stderr. Always shown, even when `quiet`.

        Severity-only - does NOT raise. Use this for "the world is broken"
        notices that warrant a more emphatic visual than `error()`. Routes to
        `err_console`, prepends a blank line for breathing room, and renders
        with the level's resolved style, detail style, and marker (default
        `‼ `, customizable via `Theme(critical=Level(...))`).

        See `Emitter.info` for `message`/`markup`/`style`/`detail_style`/`marker`,
        `tag`/`right_tag`, and `exception`/`show_locals` semantics.
        """
        log_message = _apply_tag_to_logmsg(tag, _message_to_log_text(message, markup=markup))
        log_details = list(details) if details else []
        tb_lines = _format_exception_for_logfile(exception)
        if tb_lines:
            log_details.extend(tb_lines)
        self._logsink.emit(
            level=_LEVEL_TO_LOG_SEVERITY["critical"],
            message=log_message,
            details=log_details or None,
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
            details=_attach_exception_to_details(details, exception, show_locals=show_locals),
            tag=tag,
            right_tag=right_tag,
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

    def kv(
        self,
        items: dict[str, Any] | list[tuple[str, Any]],
        *,
        indent: int = 2,
        separator: str = ": ",
        markup: bool = False,
    ) -> None:
        """Render aligned key/value pairs as a section block.

        Useful for status summaries and final-state output. Keys are padded
        to the widest key's width and joined to the value with `separator`.
        Suppressed on the console when `quiet=True`, but each pair is still
        recorded in the logfile so the audit trail stays complete.

        Args:
            items: dict (insertion order preserved) or list of `(key, value)`
                tuples. Use the list form when you need duplicate keys or
                explicit ordering.
            indent: Leading spaces before each rendered line. Defaults to `2`.
            separator: String between the padded key and the value. Defaults
                to `": "`.
            markup: When True, parses Rich markup in string values. Keys are
                always escaped (treated as identifiers).
        """
        pair_list: list[tuple[str, Any]] = (
            list(items.items()) if isinstance(items, dict) else list(items)
        )
        if not pair_list:
            return

        widest = max(len(k) for k, _ in pair_list)
        prefix = " " * indent
        cell_width = widest + len(separator)
        cont_prefix = " " * (indent + cell_width)
        for key, value in pair_list:
            # Project the value to plain text for the logfile so each visual
            # line shows up as a discrete INFO record with the same alignment
            # the user saw on the console.
            if isinstance(value, str):
                log_value = Text.from_markup(value).plain if markup else value
            elif isinstance(value, Text):
                log_value = value.plain
            elif is_renderable(value):
                log_value = _render_renderable_to_plain(value).rstrip("\n")
            else:
                log_value = str(value)

            key_cell = (key + separator).ljust(cell_width)
            value_lines = log_value.splitlines() or [""]
            first_line = prefix + key_cell + value_lines[0]
            self._logsink.emit(
                level=_LEVEL_TO_LOG_SEVERITY["info"],
                message=first_line,
                details=None,
            )
            for line in value_lines[1:]:
                self._logsink.emit(
                    level=_LEVEL_TO_LOG_SEVERITY["info"],
                    message=cont_prefix + line,
                    details=None,
                )

        if self.quiet:
            return
        self.console.print(_KVBlock(pair_list, indent=indent, separator=separator, markup=markup))

    @contextmanager
    def step(
        self,
        message: str | RenderableType,
        *,
        ephemeral: bool = False,
        markup: bool = False,
        success_msg: str | RenderableType | None = None,
        failure_msg: str | RenderableType | None = None,
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

        `success_msg` overrides the success-state header; defaults to the
        original `message` styled as success. `failure_msg` overrides the
        failure-state header; defaults to the original `message` styled as
        error. Either side may be omitted independently. The single `markup=`
        flag covers all three messages. The succeeded:/failed: log lines also
        use the override messages when provided so the audit trail matches
        what the user saw on the console.

        Args:
            message: Title shown next to the spinner. Strings are escaped by
                default; pass `markup=True` to embed Rich markup. A `Text`
                preserves its own styling. Other Rich renderables pass
                through to `Spinner.text` unchanged.
            ephemeral: If True, clear sub-items and the success marker on completion.
            markup: When True, parses Rich markup in a `str` `message`
                instead of escaping.
            success_msg: Optional message to display on success in place of
                the original `message`. Falls back to `message` when None.
            failure_msg: Optional message to display on failure in place of
                the original `message`. Falls back to `message` when None.

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
        success_text = (
            _message_to_log_text(success_msg, markup=markup)
            if success_msg is not None
            else log_text
        )
        failure_text = (
            _message_to_log_text(failure_msg, markup=markup)
            if failure_msg is not None
            else log_text
        )
        success_message = success_msg if success_msg is not None else message
        failure_message = failure_msg if failure_msg is not None else message

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
                            failure_message,
                            style=error_style,
                            marker=error_marker,
                            markup=markup,
                        )
                        # _build_message_text returns None for non-(str|Text) renderables;
                        # fall back to the original renderable so the override is not silently dropped.
                        s.header = error_header if error_header is not None else failure_message
                    raise
                if not ephemeral:
                    success_header = _build_message_text(
                        success_message,
                        style=success_style,
                        marker=success_marker,
                        markup=markup,
                    )
                    # _build_message_text returns None for non-(str|Text) renderables;
                    # fall back to the original renderable so the override is not silently dropped.
                    s.header = success_header if success_header is not None else success_message
        finally:
            self._active_step = False
            if failed_exc is not None:
                self._logsink.emit(
                    level=_LEVEL_TO_LOG_SEVERITY["error"],
                    message=f"failed: {failure_text}",
                    details=[f"{type(failed_exc).__name__}: {failed_exc}"],
                )
                if ephemeral:
                    # Pass the original renderable (not the plain-text strip) so styling/markup is preserved.
                    self.error(failure_message)
            else:
                self._logsink.emit(
                    level=_LEVEL_TO_LOG_SEVERITY["info"],
                    message=f"succeeded: {success_text}",
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


def info(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print info-level output via the default emitter.

    See `Emitter.info` for full kwarg semantics including `tag`/`right_tag`
    and `exception`/`show_locals`.
    """
    _default.info(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
        **kwargs,
    )


def success(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print success-level output via the default emitter.

    See `Emitter.success` for full kwarg semantics including `tag`/`right_tag`
    and `exception`/`show_locals`.
    """
    _default.success(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
        **kwargs,
    )


def debug(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print debug-level output via the default emitter.

    See `Emitter.debug` for full kwarg semantics including `tag`/`right_tag`
    and `exception`/`show_locals`.
    """
    _default.debug(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
        **kwargs,
    )


def trace(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print trace-level output via the default emitter.

    See `Emitter.trace` for full kwarg semantics including `tag`/`right_tag`
    and `exception`/`show_locals`.
    """
    _default.trace(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
        **kwargs,
    )


def dryrun(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print a dry-run notice via the default emitter.

    See `Emitter.dryrun` for full kwarg semantics including `tag`/`right_tag`
    and `exception`/`show_locals`.
    """
    _default.dryrun(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
        **kwargs,
    )


def warning(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print warning output via the default emitter.

    See `Emitter.warning` for full kwarg semantics including `tag`/`right_tag`
    and `exception`/`show_locals`.
    """
    _default.warning(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
        **kwargs,
    )


def error(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print error output via the default emitter.

    See `Emitter.error` for full kwarg semantics including `tag`/`right_tag`
    and `exception`/`show_locals`.
    """
    _default.error(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
        **kwargs,
    )


def critical(  # noqa: PLR0913
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,
) -> None:
    """Print critical output via the default emitter. Always shown, even when `quiet`.

    Severity-only; does not raise. See `Emitter.critical` for full semantics
    including `tag`/`right_tag` and `exception`/`show_locals`.
    """
    _default.critical(
        message,
        details=details,
        markup=markup,
        style=style,
        detail_style=detail_style,
        marker=marker,
        tag=tag,
        right_tag=right_tag,
        exception=exception,
        show_locals=show_locals,
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


def kv(
    items: dict[str, Any] | list[tuple[str, Any]],
    *,
    indent: int = 2,
    separator: str = ": ",
    markup: bool = False,
) -> None:
    """Render aligned key/value pairs via the default emitter.

    See `Emitter.kv` for full kwarg semantics.
    """
    _default.kv(items, indent=indent, separator=separator, markup=markup)


@contextmanager
def step(
    message: str | RenderableType,
    *,
    ephemeral: bool = False,
    markup: bool = False,
    success_msg: str | RenderableType | None = None,
    failure_msg: str | RenderableType | None = None,
) -> Generator[Step]:
    """Run a spinner-driven step on the default emitter.

    See `Emitter.step` for `message`/`markup`/`success_msg`/`failure_msg` semantics.
    """
    with _default.step(
        message,
        ephemeral=ephemeral,
        markup=markup,
        success_msg=success_msg,
        failure_msg=failure_msg,
    ) as s:
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
    "kv",
    "set_default",
    "step",
    "success",
    "trace",
    "warning",
]
