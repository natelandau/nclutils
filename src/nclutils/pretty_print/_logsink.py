"""Private file-logging substrate for nclutils.pretty_print.

Each `Emitter` constructs one `_LogSink`. The sink owns a stdlib
`logging.Logger` (named `nclutils.pretty_print._{id(emitter)}`, with `propagate=False`)
plus a single `FileHandler` opened lazily on first emit. Console
rendering and file rendering are independent - the file ignores
`quiet`/`verbosity`, the console ignores `loglevel`.

Importing this module registers `TRACE=5` with stdlib `logging` once.
`CRITICAL=50` is already named by stdlib and needs no registration.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.pretty import Pretty
from rich.protocol import is_renderable
from rich.text import Text

if TYPE_CHECKING:
    from typing import Any


# Register TRACE once at import. addLevelName is a no-op when the same
# (level, name) pair is registered twice, so re-import is safe.
logging.addLevelName(5, "TRACE")


_DEFAULT_LOGFMT = "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Fixed render width for plain-text serialization - file consumers don't
# have a terminal width, so a stable column lets diffs and grep stay sane.
_PLAIN_RENDER_WIDTH = 120


def _render_renderable_to_plain(renderable: object) -> str:
    """Render a Rich renderable (or arbitrary object via `Pretty`) into plain text.

    Anything that's not already a Rich renderable is wrapped in `Pretty()` first.
    """
    target = renderable if is_renderable(renderable) else Pretty(renderable)
    buf = io.StringIO()
    Console(
        file=buf,
        no_color=True,
        force_terminal=False,
        width=_PLAIN_RENDER_WIDTH,
        record=False,
    ).print(target)
    return buf.getvalue()


def _render_details_to_lines(details: list[Any]) -> list[str]:
    """Flatten each `details` item into one or more indented text lines.

    Strings are markup-stripped via `Text.from_markup(s).plain` and split on
    newlines. Rich renderables are rendered through a private no-color
    Console. Anything else is wrapped in `Pretty(item)` and rendered the same
    way. Each output line is prefixed with two spaces so the file visually
    nests continuation records under their parent.

    Args:
        details: List of items to flatten into indented text lines.

    Returns:
        list[str]: Indented text lines, one per logical output line.
    """
    out: list[str] = []
    # Rich Console construction probes terminal capabilities, so reuse one
    # buffered console across non-string items rather than per-item setup.
    buf_io: io.StringIO | None = None
    buf_console: Console | None = None
    for item in details:
        if isinstance(item, str):
            plain = Text.from_markup(item).plain
            out.extend(f"  {line}" for line in (plain.splitlines() or [plain]))
        else:
            if buf_console is None:
                buf_io = io.StringIO()
                buf_console = Console(
                    file=buf_io,
                    no_color=True,
                    force_terminal=False,
                    width=_PLAIN_RENDER_WIDTH,
                    record=False,
                )
            assert buf_io is not None  # noqa: S101  -- paired with buf_console init
            target = item if is_renderable(item) else Pretty(item)
            buf_io.seek(0)
            buf_io.truncate(0)
            buf_console.print(target)
            rendered = buf_io.getvalue()
            out.extend(f"  {line.rstrip()}" for line in rendered.splitlines())
    return out


class _LogSink:
    """Per-emitter file-logging sink. No-op when `logfile is None`.

    Constructed once per `Emitter`. Emit calls funnel through `emit()`,
    which lazily opens the configured logfile on first use. The sink
    holds its own private logger (not propagated to the root logger) so
    multiple emitters and the host application's logging stack stay
    isolated from each other.
    """

    def __init__(
        self,
        *,
        logfile: Path | str | None = None,
        loglevel: int = logging.INFO,
        logfmt: str | None = None,
    ) -> None:
        self._logfile: Path | None = Path(logfile) if logfile is not None else None
        self._loglevel: int = loglevel
        self._logfmt: str | None = logfmt
        self._logger: logging.Logger | None = None
        self._handler: logging.FileHandler | None = None

    def emit(
        self,
        *,
        level: int,
        message: str,
        details: list[Any] | None = None,
    ) -> None:
        """Write one record (plus continuation records for `details`) to the logfile.

        No-op when `logfile is None`. Lazily opens the file on first call;
        subsequent calls reuse the open handler. Continuation records are
        emitted at the same level as the parent so a level-filter cutoff
        drops a logical event whole.

        Args:
            level: stdlib logging level integer (e.g. `logging.INFO`).
            message: The primary log message string.
            details: Optional list of additional items. Strings have Rich markup
                stripped; Rich renderables are rendered no-color; anything else
                is wrapped in Pretty(). Each item emits as its own record.
        """
        if self._logfile is None:
            return
        logger = self._ensure_logger()
        logger.log(level, message)
        if details:
            for line in _render_details_to_lines(details):
                logger.log(level, line)

    def close(self) -> None:
        """Flush and close the FileHandler, releasing the underlying file descriptor.

        Safe to call multiple times. After closing, the sink can no longer
        write records - this is intended for teardown only (e.g. when
        `Emitter.configure()` swaps in a new logfile).
        """
        if self._handler is not None:
            self._handler.close()
            if self._logger is not None:
                self._logger.removeHandler(self._handler)
            self._handler = None
            self._logger = None

    def __del__(self) -> None:
        # Ensure the file descriptor is released on GC even if close() was never called.
        self.close()

    def swap_logfile(self, logfile: Path | str | None) -> None:
        """Reconfigure the sink to write to a new logfile (or stop writing).

        A no-op if `logfile` resolves to the same path as the current logfile.
        Otherwise closes the current handler (if any) and stages the new path
        for lazy reopen on next emit. Passing `None` disables file writes; the
        Emitter contract treats `configure(logfile=None)` as a no-op, so this
        method is reached only when the caller has already established intent
        to disable.
        """
        new_path: Path | None = Path(logfile) if logfile is not None else None
        if (
            self._logfile is not None
            and new_path is not None
            and self._logfile.resolve() == new_path.resolve()
        ):
            return
        self.close()
        self._logfile = new_path

    def set_level(self, level: int) -> None:
        """Update the active filter cutoff. Lazy-applied if no handler is open yet."""
        self._loglevel = level
        if self._logger is not None:
            self._logger.setLevel(level)
        if self._handler is not None:
            self._handler.setLevel(level)

    def set_format(self, fmt: str | None) -> None:
        """Update the active format string. Lazy-applied if no handler is open yet."""
        self._logfmt = fmt
        if self._handler is not None:
            active = fmt if fmt is not None else _DEFAULT_LOGFMT
            self._handler.setFormatter(logging.Formatter(active, datefmt=_DEFAULT_DATEFMT))

    def _ensure_logger(self) -> logging.Logger:
        """Lazily build the per-emitter logger and attach a FileHandler.

        Raises whatever the FileHandler raises if the path is not openable
        (permission denied, missing parent dir, full disk). This is
        deliberate - silently failing to write an audit log is worse than
        crashing loudly and pointing at the call site that tried to open it.

        Returns:
            logging.Logger: The configured per-sink logger with its FileHandler attached.
        """
        if self._logger is not None:
            return self._logger
        # `logfile is None` is handled by the caller (`emit`); this method
        # is only invoked when `_logfile` is a real Path.
        if self._logfile is None:  # pragma: no cover
            msg = "_ensure_logger called with no logfile; this is a bug"
            raise RuntimeError(msg)
        name = f"nclutils.pretty_print._{id(self)}"
        logger = logging.getLogger(name)
        # Close and remove any stale handlers from a prior instance that shared
        # this logger name via id() reuse - avoids ResourceWarning on GC.
        for h in logger.handlers[:]:
            h.close()
            logger.removeHandler(h)
        logger.propagate = False
        logger.setLevel(self._loglevel)
        # Line-buffered append so partial-flush on crash doesn't lose lines.
        handler = logging.FileHandler(
            self._logfile,
            mode="a",
            encoding="utf-8",
        )
        if handler.stream is not None:
            handler.stream.reconfigure(line_buffering=True)
        handler.setLevel(self._loglevel)
        fmt = self._logfmt if self._logfmt is not None else _DEFAULT_LOGFMT
        handler.setFormatter(logging.Formatter(fmt, datefmt=_DEFAULT_DATEFMT))
        logger.addHandler(handler)
        self._logger = logger
        self._handler = handler
        return logger
