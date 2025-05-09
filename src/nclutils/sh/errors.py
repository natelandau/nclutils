"""Custom errors for script utilities."""


class ShellCommandFailedError(Exception):
    """Raised when a shell command fails."""

    def __init__(
        self,
        msg: str | None = None,
        e: Exception | None = None,
        *args: str | int,
        **kwargs: int | str | bool,
    ):
        self.exit_code: int | None = None
        self.stderr: str | None = None
        self.stdout: str | None = None
        self.full_cmd: str | None = None

        msg = msg or "Shell command failed."

        if e:
            msg += f"\nRaised from: {e.__class__.__name__}: {e}"

            # Map error attributes to class attributes with proper decoding
            attr_mapping = {
                "exit_code": (lambda x: x, None),  # No decoding needed
                "stderr": (self._decode_output, "Stderr"),
                "stdout": (self._decode_output, "Stdout"),
                "full_cmd": (lambda x: str(x).strip(), "Full command"),
            }

            for attr, (processor, label) in attr_mapping.items():
                if hasattr(e, attr):
                    value = getattr(e, attr)
                    setattr(self, attr, processor(value))
                    if label and getattr(
                        self, attr
                    ):  # Only add to message if we have a label and value
                        msg += f"\n{label}: {getattr(self, attr)}"

        super().__init__(msg, *args, **kwargs)

    @staticmethod
    def _decode_output(output: bytes | str) -> str:
        """Decode command output to string and strip whitespace.

        Args:
            output: The output to decode, either bytes or string

        Returns:
            str: The decoded and stripped output
        """
        if isinstance(output, bytes):
            try:
                return output.decode("utf-8").strip()
            except UnicodeDecodeError:  # pragma: no cover
                return str(output).strip()
        return str(output).strip()


class ShellCommandNotFoundError(Exception):
    """Raised when a shell command is not found."""

    def __init__(
        self,
        msg: str | None = None,
        e: Exception | None = None,
        *args: str | int,
        **kwargs: int | str | bool,
    ):
        if not msg:
            msg = "Shell command not found."

        if e:
            msg += f"\nRaised from: {e.__class__.__name__}:\n{e}"

        super().__init__(msg, *args, **kwargs)
