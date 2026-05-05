"""Modules for script utilities.

The top-level package surfaces the high-frequency console output and logging
helpers. Everything else lives in its submodule (e.g. `nclutils.fs`,
`nclutils.strings`) and must be imported from there.
"""

from .logging import logger
from .pretty_print import (
    THEME,
    Emitter,
    Level,
    LogLevel,
    Theme,
    Verbosity,
    configure,
    console,
    critical,
    debug,
    dryrun,
    err_console,
    error,
    get_default,
    header,
    info,
    set_default,
    step,
    success,
    trace,
    warning,
)

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
    "logger",
    "set_default",
    "step",
    "success",
    "trace",
    "warning",
]
