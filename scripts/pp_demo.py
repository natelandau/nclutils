# ruff: noqa: INP001
"""Demonstrate every output style nclutils.pp provides.

Developer-only tool. Not part of the public API and not exported as a
console entrypoint. Run from the repository root:

    uv run scripts/pp_demo.py

The script prints every visual section pp can produce, in order, so
maintainers can spot visual regressions after changes to the module.
"""

from __future__ import annotations

from nclutils import pp
from nclutils.pp import Emitter, Level, Theme, Verbosity


def _levels() -> None:
    """Print one line at every built-in level."""
    pp.header("Levels", align="left")
    pp.info("info: informational message")
    pp.success("success: operation completed")
    pp.warning("warning: something to watch")
    pp.error("error: operation failed")
    pp.critical("critical: system on fire")
    pp.debug("debug: only at -v")
    pp.trace("trace: only at -vv")
    pp.dryrun("dryrun: would have happened")


def _headers() -> None:
    """Print headers with each alignment plus a bare rule."""
    pp.header("Headers", align="left")
    pp.header("centered title")
    pp.header("left title", align="left")
    pp.header("right title", align="right")
    pp.header()


def _steps() -> None:
    """Demonstrate the success, failure, and ephemeral step paths."""
    pp.header("Steps", align="left")

    with pp.step("success path") as s:
        s.sub("first sub-item")
        s.sub("second sub-item")

    try:
        with pp.step("failure path") as s:
            s.sub("attempted this")
            msg = "boom"
            raise RuntimeError(msg)  # noqa: TRY301 -- intentional, exercises step() failure branch
    except RuntimeError:
        pass

    with pp.step("ephemeral path", ephemeral=True) as s:
        s.sub("disappears on success")


def _details_simple() -> None:
    """Demonstrate details with tree connectors: single, multiple, and markup."""
    pp.header("Details (tree connectors)", align="left")
    pp.info("one detail", details=["only-item"])
    pp.success("multiple details", details=["first", "second", "third"])
    pp.warning(
        "with markup",
        details=["[underline]parsed[/] markup"],
        markup=True,
    )


def _details_multiline() -> None:
    """Demonstrate `│` continuation under non-final and blank gutter under final."""
    pp.header("Multi-line details", align="left")
    pp.info(
        "multi-line string in non-final position",
        details=["line one\nline two\nline three", "trailing item"],
    )
    pp.info(
        "dict in final position",
        details=["leading", {"status": 200, "items": [1, 2, 3], "meta": {"x": "y"}}],
    )


def _per_call_overrides() -> None:
    """Demonstrate per-call style, marker, and detail_style overrides."""
    pp.header("Per-call overrides", align="left")
    pp.info("custom marker", marker="→ ", details=["one"])
    pp.info(
        "custom style",
        style="bold magenta",
        detail_style="magenta",
        details=["styled"],
    )
    pp.info("no marker (suppressed)", marker="", details=["bare"])


def _per_call_tags() -> None:
    """Demonstrate per-call tag and right_tag kwargs."""
    pp.header("Per-call tags", align="left")
    pp.info("with left tag only", tag="api")
    pp.info("with right tag only", right_tag="200ms")
    pp.info("with both tags", tag="api", right_tag="200ms")
    pp.success("operation done", tag="deploy", right_tag="3.2s")
    pp.error("upload failed", tag="uploader")
    pp.dryrun("would push image", tag="deploy")
    pp.debug("custom right tag overrides elapsed", right_tag="db: 1.2s")
    pp.debug("auto elapsed (default)")


def _theme_override() -> None:
    """Demonstrate a custom Theme via a dedicated Emitter."""
    pp.header("Theme override", align="left")
    e = Emitter(
        verbosity=Verbosity.TRACE,
        theme=Theme(
            info=Level(style="bold cyan", detail_style="cyan", marker="ℹ "),  # noqa: RUF001
            success=Level(marker="✔ "),
        ),
    )
    e.info("info via custom Theme", details=["one", "two"])
    e.success("success via custom Theme")


def _verbosity_matrix() -> None:
    """Show what's visible at each verbosity setting and under quiet."""
    pp.header("Verbosity/quiet matrix", align="left")

    e_info = Emitter(verbosity=Verbosity.INFO)
    e_info.info("INFO emitter: debug and trace are suppressed")
    e_info.debug("you should NOT see this debug line")
    e_info.trace("you should NOT see this trace line")

    e_debug = Emitter(verbosity=Verbosity.DEBUG)
    e_debug.info("DEBUG emitter: debug visible, trace still suppressed")
    e_debug.debug("debug visible")
    e_debug.trace("you should NOT see this trace line")

    e_trace = Emitter(verbosity=Verbosity.TRACE)
    e_trace.info("TRACE emitter: debug and trace both visible")
    e_trace.debug("debug visible")
    e_trace.trace("trace visible")

    e_quiet = Emitter(quiet=True)
    e_quiet.info("you should NOT see this (info silenced under quiet)")
    e_quiet.success("you should NOT see this (success silenced under quiet)")
    e_quiet.warning("warnings still appear under quiet")
    e_quiet.dryrun("dryrun bypasses quiet")
    e_quiet.error("errors always appear")


def main() -> None:
    """Run every demo section in order."""
    pp.configure(verbosity=Verbosity.TRACE)
    _levels()
    _headers()
    _steps()
    _details_simple()
    _details_multiline()
    _per_call_overrides()
    _per_call_tags()
    _theme_override()
    _verbosity_matrix()


if __name__ == "__main__":
    main()
