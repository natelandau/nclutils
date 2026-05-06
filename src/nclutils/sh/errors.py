"""Custom errors for script utilities."""


def _decode(output: bytes | str | None) -> str | None:
    """Decode subprocess output bytes to a stripped string.

    Args:
        output: Raw output from a subprocess (bytes), an already-decoded string, or None.

    Returns:
        str | None: The decoded and stripped output, or None if the input was None.
    """
    if output is None:
        return None
    if isinstance(output, bytes):
        try:
            return output.decode("utf-8").strip()
        except UnicodeDecodeError:  # pragma: no cover
            return str(output).strip()
    return str(output).strip()


class ShellCommandFailedError(Exception):
    """Raised when a shell command fails."""

    def __init__(self, msg: str | None = None, *, e: Exception | None = None) -> None:
        self.exit_code: int | None = getattr(e, "exit_code", None)
        self.stderr: str | None = _decode(getattr(e, "stderr", None))
        self.stdout: str | None = _decode(getattr(e, "stdout", None))
        full_cmd = getattr(e, "full_cmd", None)
        self.full_cmd: str | None = str(full_cmd).strip() if full_cmd is not None else None

        parts = [msg or "Shell command failed."]
        if e is not None:
            parts.append(f"Raised from: {e.__class__.__name__}: {e}")
            if self.stderr:
                parts.append(f"Stderr: {self.stderr}")
            if self.stdout:
                parts.append(f"Stdout: {self.stdout}")
            if self.full_cmd:
                parts.append(f"Full command: {self.full_cmd}")

        super().__init__("\n".join(parts))


class ShellCommandNotFoundError(Exception):
    """Raised when a shell command is not found."""

    def __init__(self, msg: str | None = None, *, e: Exception | None = None) -> None:
        parts = [msg or "Shell command not found."]
        if e is not None:
            parts.append(f"Raised from: {e.__class__.__name__}:\n{e}")
        super().__init__("\n".join(parts))
