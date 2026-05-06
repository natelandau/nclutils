"""Line-buffered pipe reader used by run_command's streaming path."""

from __future__ import annotations

import re  # noqa: TC003 -- runtime import to avoid future footgun if re is used in body
from typing import IO


def pump_pipe(
    pipe: IO[bytes],
    buffer: list[str],
    sink: IO[str] | None,
    exclude_pattern: re.Pattern[str] | None,
) -> None:
    """Read ``pipe`` line-by-line, decode, filter, and forward each line.

    Designed to run in a worker thread; the caller owns ``buffer`` and must
    not read it until the worker has joined.

    The sink is flushed after every line so block-buffered redirection
    (e.g., ``> file.log``) still produces real-time output.

    Args:
        pipe: A binary-mode readable pipe (stdout or stderr from a subprocess).
        buffer: Accumulator list; each decoded line is appended in order.
        sink: Optional text-mode stream to mirror output to (e.g. sys.stdout).
            Pass ``None`` to suppress forwarding.
        exclude_pattern: Pre-compiled regex; lines that match are dropped from
            both ``buffer`` and ``sink``.  Pass ``None`` to keep every line.
    """
    try:
        for raw in pipe:
            line = raw.decode("utf-8")
            if exclude_pattern is not None and exclude_pattern.search(line):
                continue
            buffer.append(line)
            if sink is not None:
                sink.write(line)
                sink.flush()
    finally:
        pipe.close()
