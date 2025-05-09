"""Shared fixtures for tests."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from rich.console import Console

console = Console()


@pytest.fixture
def clean_stdout(capsys: pytest.CaptureFixture[str]) -> Callable[[], str]:
    r"""Return a function that cleans ANSI escape sequences from captured stdout.

    This fixture is useful for testing CLI output where ANSI color codes and other escape sequences need to be stripped to verify the actual text content. The returned callable captures stdout using pytest's capsys fixture and removes all ANSI escape sequences, making it easier to write assertions against the cleaned output.

    Args:
        capsys (pytest.CaptureFixture[str]): Pytest fixture that captures stdout/stderr streams

    Returns:
        Callable[[], str]: A function that when called returns the current stdout with all ANSI escape sequences removed

    Example:
        def test_cli_output(clean_stdout):
            print("\033[31mRed Text\033[0m")  # Colored output
            assert clean_stdout() == "Red Text"  # Test against clean text
    """
    ansi_chars = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")

    def _get_clean_stdout() -> str:
        return ansi_chars.sub("", capsys.readouterr().out)

    return _get_clean_stdout


@pytest.fixture
def debug() -> Callable[[str | Path, str, bool, int], bool]:
    """Return a debug printing function for test development and troubleshooting.

    Create and return a function that prints formatted debug output to the console during test development and debugging. The returned function allows printing variables, file contents, or directory structures with clear visual separation and optional breakpoints.

    Returns:
        Callable[[str | Path, str, bool, int], bool]: A function that prints debug info with
            the following parameters:
            - value: The data to debug print (string or Path)
            - label: Optional header text for the output
            - breakpoint: Whether to pause execution after printing
            - width: Maximum output width in characters

    Example:
        def test_complex_data(debug):
            result = process_data()
            debug(result, "Processed Data", breakpoint=True)
    """

    def _debug_inner(
        value: str | Path, label: str = "", breakpoint: bool = False, width: int = 80
    ) -> bool:
        """Print debug information during test development and debugging sessions.

        Print formatted debug output to the console with optional breakpoints. This is particularly useful when developing or debugging tests to inspect variables, file contents, or directory structures. The output is formatted with a labeled header and footer rule for clear visual separation.

        Args:
            value (Union[str, Path]): The value to debug print. If a Path to a directory is provided, recursively prints all files in that directory tree.
            label (str): Optional header text to display above the debug output for context.
            breakpoint (bool, optional): If True, raises a pytest.fail() after printing to pause execution. Defaults to False.
            width (int, optional): Maximum width in characters for the console output. Matches pytest's default width of 80 when running without the -s flag. Defaults to 80.

        Returns:
            bool: Always returns True unless breakpoint=True, in which case raises pytest.fail()

        Example:
            def test_something(debug):
                # Print contents of a directory
                debug(Path("./test_data"), "Test Data Files")

                # Print a variable with a breakpoint
                debug(my_var, "Debug my_var", breakpoint=True)
        """
        console.rule(label or "")

        # If a directory is passed, print the contents
        if isinstance(value, Path) and value.is_dir():
            for p in value.rglob("*"):
                console.print(p, width=width)
        else:
            console.print(value, width=width)

        console.rule()

        if breakpoint:
            return pytest.fail("Breakpoint")

        return True

    return _debug_inner


# def pytest_assertrepr_compare(config, op, left, right):
#     """Replace tabs and spaces with [tab] and [space] in the assertion message to troubleshoot test failures with whitespace."""
#     left = left.replace(" ", "[space]").replace("\t", "[tab]")
#     right = right.replace(" ", "[space]").replace("\t", "[tab]")
#     return [f"{left} {op} {right} failed!"]
