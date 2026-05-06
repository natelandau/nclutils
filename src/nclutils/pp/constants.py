"""Constants for the nclutils.pp package."""

from enum import IntEnum


class Verbosity(IntEnum):
    """Output verbosity levels."""

    INFO = 0
    DEBUG = 1
    TRACE = 2


class LogLevel(IntEnum):
    """File-logging severity levels, aligned with stdlib `logging` numerics.

    Use as the `loglevel=` kwarg on `Emitter` / `configure()` to set the
    minimum severity that gets written to the configured logfile. The
    numerics match stdlib `logging` (`DEBUG=10`, `INFO=20`, …) so nclutils.pp's
    file substrate composes cleanly with stdlib tooling. `TRACE=5` is
    nclutils.pp-specific and is registered with `logging.addLevelName` at
    import time of `nclutils.pp._logsink`.
    """

    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
