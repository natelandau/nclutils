"""Tests for the rewritten nclutils.sh module."""

from __future__ import annotations

from pathlib import Path

import pytest

from nclutils.sh import (
    CompletedCommand,
    ShellCommandError,
    ShellCommandFailedError,
    ShellCommandNotFoundError,
    ShellCommandTimeoutError,
)


class TestCompletedCommand:
    """Tests for the CompletedCommand dataclass."""

    def test_fields_and_ok_property(self) -> None:
        """Verify CompletedCommand exposes argv/returncode/stdout/stderr/duration/cwd and ok."""
        # Given: a CompletedCommand built with returncode 0
        result = CompletedCommand(
            argv=("echo", "hi"),
            returncode=0,
            stdout="hi\n",
            stderr="",
            duration=0.01,
            cwd=Path("/tmp"),  # noqa: S108
        )

        # Then: every field is reachable and ok is True
        assert result.argv == ("echo", "hi")
        assert result.returncode == 0
        assert result.stdout == "hi\n"
        assert result.stderr == ""
        assert result.duration == 0.01
        assert result.cwd == Path("/tmp")  # noqa: S108
        assert result.ok is True

    def test_ok_false_on_nonzero(self) -> None:
        """Verify ok is False when returncode is non-zero."""
        # Given: a CompletedCommand with returncode 2
        result = CompletedCommand(
            argv=("false",),
            returncode=2,
            stdout="",
            stderr="",
            duration=0.0,
            cwd=None,
        )

        # Then: ok is False
        assert result.ok is False

    def test_frozen_and_hashable(self) -> None:
        """Verify CompletedCommand is frozen and hashable."""
        # Given: a CompletedCommand
        result = CompletedCommand(
            argv=("ls",), returncode=0, stdout="", stderr="", duration=0.0, cwd=None
        )

        # When: attempting to mutate, it raises; hashing succeeds
        with pytest.raises(Exception):  # noqa: B017, PT011  # FrozenInstanceError or AttributeError
            result.returncode = 1  # type: ignore[misc]
        assert isinstance(hash(result), int)


class TestErrorHierarchy:
    """Tests for the unified ShellCommandError hierarchy."""

    def test_all_subclasses_inherit_from_base(self) -> None:
        """Verify every concrete error inherits from ShellCommandError."""
        # Given: the three concrete error classes
        # Then: each is a subclass of the base
        assert issubclass(ShellCommandNotFoundError, ShellCommandError)
        assert issubclass(ShellCommandFailedError, ShellCommandError)
        assert issubclass(ShellCommandTimeoutError, ShellCommandError)

    def test_failed_carries_result(self) -> None:
        """Verify ShellCommandFailedError exposes the CompletedCommand it would have returned."""
        # Given: a CompletedCommand and an error built from it
        result = CompletedCommand(
            argv=("git", "push"),
            returncode=1,
            stdout="",
            stderr="rejected",
            duration=0.5,
            cwd=Path("/tmp"),  # noqa: S108
        )
        err = ShellCommandFailedError(result=result)

        # Then: the result is reachable via attribute and the message includes context
        assert err.result is result
        assert "git push" in str(err)
        assert "exit code 1" in str(err)
        assert "rejected" in str(err)

    def test_failed_with_no_result_for_cwd_error(self) -> None:
        """Verify ShellCommandFailedError accepts result=None when cwd was unreachable."""
        # Given: an error raised before the command ran
        err = ShellCommandFailedError(
            msg="Cannot enter directory /no/such/dir: not a directory", result=None
        )

        # Then: result is None and the message is preserved
        assert err.result is None
        assert "Cannot enter directory /no/such/dir" in str(err)

    def test_timeout_carries_partial_result(self) -> None:
        """Verify ShellCommandTimeoutError exposes partial output and the exceeded timeout."""
        # Given: partial output captured before kill and a 1.5s timeout
        partial = CompletedCommand(
            argv=("sleep", "10"),
            returncode=-9,
            stdout="started\n",
            stderr="",
            duration=1.5,
            cwd=None,
        )
        err = ShellCommandTimeoutError(result=partial, timeout=1.5)

        # Then: the partial result and the timeout value are both reachable
        assert err.result is partial
        assert err.timeout == 1.5
        assert "1.5" in str(err)

    def test_not_found_message_uses_argv(self) -> None:
        """Verify ShellCommandNotFoundError reports the missing executable name."""
        # Given: an error built for a missing binary
        err = ShellCommandNotFoundError(argv=("not-a-real-command", "--help"))

        # Then: the executable name is in the message
        assert "not-a-real-command" in str(err)
