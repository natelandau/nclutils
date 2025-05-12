"""Logger module."""

import sys
from collections.abc import Callable
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

from loguru import logger as _logger

F = TypeVar("F", bound=Callable[..., Any])


class LogLevel(Enum):
    """Log level enum."""

    TRACE = 5
    DEBUG = 10
    INFO = 20
    SUCCESS = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    NOTSET = 60

    @classmethod
    def from_name(cls, name: str) -> "LogLevel":
        """Convert a string name into its corresponding LogLevel enum value.

        Args:
            name (str): The name of the log level to convert (case insensitive)

        Returns:
            LogLevel: The LogLevel enum value matching the provided name

        Examples:
            >>> LogLevel.from_name("trace")
            <LogLevel.TRACE: 5>
            >>> LogLevel.from_name("DEBUG")
            <LogLevel.DEBUG: 10>
            >>> LogLevel.from_name("Info")
            <LogLevel.INFO: 20>
        """
        return cls[name.upper()]


class Logger:
    """Logger class. A wrapper around the Loguru logger."""

    _instance = None
    _initialized = False

    def __new__(cls) -> "Logger":
        """Create a new Logger instance if it doesn't exist."""
        if cls._instance is None:
            _logger.remove()
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the Logger instance."""
        if not Logger._initialized:
            self.log_level = LogLevel.NOTSET
            self.log_file: str | None = None
            self.rotation = "10 MB"
            self.retention = 3
            self.enqueue = False
            self.path_to_log_file: Path | None = None
            Logger._initialized = True

    def configure(
        self,
        log_level: str,
        log_file: str | None = None,
        rotation: str = "5 MB",
        retention: int = 3,
        *,
        stderr: bool = True,
        enqueue: bool = False,
        stderr_timestamp: bool = False,
    ) -> None:
        """Configure and initialize a Loguru logger with console and optional file output.

        Set up logging to stderr with colorized output and optionally to a log file with rotation and retention policies. Creates any missing parent directories for the log file path.

        Args:
            log_level (str): Controls verbosity of logging output. Defaults to NOTSET which disables logging.
            stderr (bool): Whether to log to stderr. Defaults to True.
            log_file (str | None): Path to write log file. If None, only logs to console. Defaults to None.
            rotation (str, int, datetime.time, datetime.timedelta or callable, optional): A condition indicating whenever the current logged file should be closed and a new one started. Defaults to "10 MB".
            retention (str, int, datetime.timedelta or callable, optional): A directive filtering old files that should be removed during rotation or end of program. Defaults to 3.
            enqueue (bool): Whether the messages to be logged should first pass through a multiprocessing-safe queue before reaching the sink. This is useful while logging to a file through multiple processes. This also has the advantage of making logging calls non-blocking
            stderr_timestamp (bool): Whether to include a timestamp in the stderr output. Defaults to False.
        """
        self.log_level = LogLevel.from_name(log_level)
        self.log_file = log_file
        self.rotation = rotation
        self.retention = retention
        self.enqueue = enqueue
        self.stderr_timestamp = stderr_timestamp
        if self.log_level == LogLevel.NOTSET:
            return

        _logger.remove()

        if stderr:
            _logger.add(
                sys.stderr,
                level=self.log_level.name,
                format=self._stderr_log_formatter,  # type: ignore [arg-type]
                enqueue=enqueue,
            )

        if log_file:
            self.path_to_log_file = Path(log_file).expanduser().resolve()

            if not self.path_to_log_file.parent.exists():
                self.path_to_log_file.parent.mkdir(parents=True, exist_ok=True)

            _logger.add(
                str(self.path_to_log_file),
                format=self._log_file_formatter,  # type: ignore [arg-type]
                level=self.log_level.name,
                rotation=rotation,
                retention=retention,
                compression="zip",
                enqueue=enqueue,
            )

    def _stderr_log_formatter(self, record: dict) -> str:
        """Format log records for stderr output with color and metadata.

        Format log records with timestamp, level, message, extra fields, and source location. Prints the raw record for debugging and returns a formatted string with color tags for the level and metadata.

        Args:
            record (Record): The loguru Record object containing log event data.

        Returns:
            str: A formatted log string with color tags and metadata.
        """
        extras = " | <level>{extra}</level>" if record["extra"] else ""
        exception = "\n{exception}" if record["exception"] else ""
        timestamp = "{time:YYYY-MM-DD HH:mm:ss} | " if self.stderr_timestamp else ""

        return f"{timestamp}<level>{{level: <8}}</level> | <level>{{message}}</level>{extras} | <fg #c5c5c5>{{name}}:{{function}}:{{line}}</fg #c5c5c5>{exception}\n"

    @staticmethod
    def _log_file_formatter(record: dict) -> str:
        """Format log records for log file output with color and metadata.

        Format log records with timestamp, level, message, extra fields, and source location. Prints the raw record for debugging and returns a formatted string with color tags for the level and metadata.

        Args:
            record (Record): The loguru Record object containing log event data.

        Returns:
            str: A formatted log string with color tags and metadata.
        """
        extras = " | {extra}" if record["extra"] else ""
        exception = "\n{exception}" if record["exception"] else ""

        return f"{{time:YYYY-MM-DD HH:mm:ss}} | {{level: <8}} | {{message}}{extras} | {{name}}:{{function}}:{{line}}{exception}\n"

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Create logging methods dynamically based on style names.

        Enable method-style logging (e.g., logger.info("message")) by automatically generating logging functions for each defined style.

        Args:
            name (str): Style name to create a logging method for
            kwargs (dict): Keyword arguments to pass to the logging method

        Returns:
            Callable[[str], None]: Function that logs messages with the specified style
        """
        if self.log_level == LogLevel.NOTSET:
            return lambda *args, **kwargs: None  # noqa: ARG005

        try:
            attr = getattr(_logger, name)

            if name == "catch":
                # Special handling for the catch decorator to preserve type information
                @wraps(attr)
                def catch_wrapper(func: F) -> F:
                    return cast("F", attr(func))

                return catch_wrapper

        except AttributeError:
            # If the requested logging method doesn't exist, return a no-op
            return lambda *args, **kwargs: None  # noqa: ARG005

        return attr


logger = Logger()
