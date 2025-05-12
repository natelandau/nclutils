[![PyPI version](https://badge.fury.io/py/nclutils.svg)](https://badge.fury.io/py/nclutils) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nclutils) [![Tests](https://github.com/natelandau/nclutils/actions/workflows/test.yml/badge.svg)](https://github.com/natelandau/nclutils/actions/workflows/test.yml) [![codecov](https://codecov.io/gh/natelandau/nclutils/graph/badge.svg?token=Nl1V9jnI60)](https://codecov.io/gh/natelandau/nclutils)

# nclutils

Collection of convenience functions used in Python packages and scripts. These are written and maintained for my own personal use. Comprehensive tests are included but I make no guarantees about the quality or correctness of the code.

## Features

-   **Pretty Printing**: Rich text formatting for console output with customizable styles
-   **Shell Commands**: Safe execution of shell commands with proper error handling
-   **Filesystem Utilities**: Common filesystem operations
-   **Questions**: Short-cut functions for asking questions and getting user input using the [questionary library](https://github.com/tmbo/questionary).
-   **Network**: Helper functions for working with network connections.
-   Other miscellaneous utilities.

## Requirements

-   Python 3.10 or higher
-   Dependencies are managed with [uv](https://github.com/astral-sh/uv)

### Dependencies

nclutils has a few dependencies that are included in the project.

-   [questionary](https://github.com/tmbo/questionary) - For asking questions
-   [rich](https://github.com/Textualize/rich) - For pretty printing
-   [sh](https://github.com/amoffat/sh) - For running shell commands
-   [Loguru](https://github.com/Delgan/loguru) - For logging

## Installation

Install using `uv`:

```bash
uv add git+https://github.com/natelandau/nclutils.git
```

## Included Modules

### Filesystem Utilities

-   **`backup_path(path: Path, raise_on_missing: bool = False, with_progress: bool = False, transient: bool = True) -> Path | None`**

    Create a backup of a file or directory. Silently returns `None` if the source path does not exist by default.

-   **`copy_directory(src: Path, dst: Path, with_progress: bool = False, transient: bool = True, keep_backup: bool = True) -> Path`**

    Copy a directory with an optional progress bar for each file. If the destination directory already exists, it will be backed up with a timestamped suffix.

-   **`copy_file(src: Path, dst: Path, with_progress: bool = False, transient: bool = True, keep_backup: bool = True) -> Path`**

    Copy a file with a progress bar. If the destination file already exists, it will be backed up with a timestamped suffix.

    Raises `FileNotFoundError` if the source file does not exist or is not a file.

-   **`directory_tree(directory: Path, show_hidden: bool = False) -> Tree`**

    Build a [rich.tree](https://rich.readthedocs.io/en/stable/tree.html) representation of a directory's contents.

-   **`find_files(path: Path, globs: list[str] | None = None, ignore_dotfiles: bool = False) -> list[Path]`**

    Search for files within a directory optionally matching specific glob patterns.

-   **`find_subdirectories(directory: Path, depth: int = 1, filter_regex: str = "", ignore_dotfiles: bool = False, leaf_dirs_only: bool = False) -> list[Path]`**

    Find and filter subdirectories with granular control:

    ```python
    from pathlib import Path
    from nclutils import find_subdirectories

    root_directory = Path(".")

    # Find subdirectories with specific criteria
    subdirs = find_subdirectories(
        root_directory,
        depth=2, # How deep to search
        filter_regex=r"^a", # Only dirs starting with 'a'
        leaf_dirs_only=True, # Furthest down directories only
        ignore_dotfiles=True # Skip hidden directories
    )
    ```

-   **`find_user_home_dir(username: str | None = None) -> Path | None`**

    Find the home directory for a requested user or the current user if no user is requested. When running under sudo, the home directory for the sudo user is returned.

### Logging

-   **`logger`**

    A wrapper around the [Loguru](https://github.com/Delgan/loguru) logger with configurable log levels and custom styles. See the [logging docs](docs/logging.md) for more information.

### Network

-   **`network_available(address: str = "8.8.4.4", port: int = 53, timeout: int = 5) -> bool`**

    Check if a network connection is available.

### Pretty Printing

The pretty printing module provides styled console output with configurable log levels and custom styles. See the [pretty_print docs](docs/pretty_print.md) for more information.

-   **`PrettyPrinter(Class)`**

    Styled console output with configurable levels and custom styles.

-   **`print_debug(envar_prefix: str = None, custom: list[dict] = None, packages: list[str] = None, all_packages: bool = False) -> None`**

    Print debug information about the current environment.

### Pytest Fixtures

The `nclutils.pytest_fixtures` module contains convenience functions and fixtures that are useful for testing. See the [pytest_fixtures docs](docs/pytest_fixtures.md) for more information.

-   **`clean_stdout`** Clean the stdout of the console output by creating a wrapper around `capsys` to capture console output.
-   **`debug`** Prints debug information to the console. Useful for writing and debugging tests.
-   **`pytest_assertrepr_compare`** Patches the default pytest behavior of hiding whitespace differences in assertion failure messages. Replaces spaces and tabs with `[space]` and `[tab]` markers.

### Questions

Convenience functions for working with the [questionary](https://github.com/tmbo/questionary) library.

See the [questions docs](docs/questions.md) for more information.

-   **`choose_one_from_list(choices: list[T] | list[tuple[str, T]] | list[dict[str, T]], message: str) -> T | None`**

    Presents a list of options to the user and returns a single selected option.

-   **`choose_multiple_from_list(choices: list[T] | list[tuple[str, T]] | list[dict[str, T]], message: str) -> list[T] | None`**

    Presents a list of options to the user and returns a list of selected options.

### Shell Commands

Convenience functions built on top of the [sh](https://github.com/amoffat/sh) module. See the [shell_commands docs](docs/shell_commands.md) for more information.

-   **`run_command(cmd: str, args: list[str] = [], quiet: bool = False, pushd: str | Path | None = None, okay_codes: list[int] | None = None, exclude_regex: str | None = None, sudo: bool = False) -> str`**

    Execute shell commands with proper error handling and output control.

-   **`which(cmd: str) -> str | None`**

    Check if a command exists in the PATH. Returns the absolute path to the command if found, otherwise `None`.

### Strings

-   **`camel_case(text: str) -> str`**

    Convert a string to camel case. (`hello world -> helloWorld`)

-   **`deburr(text: str) -> str`**

    Deburr a string. (`crème brûlée -> creme brulee`)

-   **`kebab_case(text: str) -> str`**

    Convert a string to kebab case. (`hello world -> hello-world`)

-   **`list_words(text: str, pattern: str = "", strip_apostrophes: bool = False) -> list[str]`**

    Extract words from text by splitting on word boundaries and handling contractions. Optionally use a custom regex pattern for more control over word splitting. Handles apostrophes, underscores, and mixed case text intelligently.

    ```python
    from nclutils import list_words

    print(list_words("Jim's horse is fast"))
    # ["Jim's", 'horse', 'is', 'fast']

    print(list_words("Jim's horse is fast", strip_apostrophes=True))
    # ['Jims', 'horse', 'is', 'fast']

    print(list_words("fred, barney, & pebbles", "[^, ]+"))
    # ['fred', 'barney', '&', 'pebbles']
    ```

-   **`random_string(length: int) -> str`**

    Generate a random string of ASCII letters with the specified length.

-   **`pad(text: str, length: int, chars: str = " ") -> str`**

    Pad a string with a character.

-   **`pad_end(text: str, length: int, chars: str = " ") -> str`**

    Pad a string on the right side.

-   **`pad_start(text: str, length: int, chars: str = " ") -> str`**

    Pad a string on the left side.

-   **`pascal_case(text: str) -> str`**

    Convert a string to pascal case. (`Hello World -> HelloWorld`)

-   **`separator_case(text: str, separator: str = "-") -> str`**

    Convert a string to separator case. (`hello world -> hello-world`)

-   **`snake_case(text: str) -> str`**

    Convert a string to snake case. (`hello world -> hello_world`)

-   **`strip_ansi(text: str) -> str`**

    Strip ANSI escape sequences from a string. (`\x1b[31mHello, World!\x1b[0m -> Hello, World!`)

-   **`split_camel_case(string_list: list[str], match_case_list: tuple[str, ...] = ()) -> list[str]`**

    Split camel case strings into into separate words returning a list of words. Optionally, provide a list of strings that should not be split.

### Utils

-   **`check_python_version(major: int, minor: int) -> bool`**

    Check if the current Python version meets minimum requirements.

-   **`format_iso_timestamp(datetime_obj: datetime, microseconds: bool = True) -> str`**

    Formats a given datetime object as an ISO 8601 timestamp, ensuring UTC formatting with a trailing Z.

-   **`iso_timestamp(microseconds: bool = False) -> str`**

    Returns an ISO 8601 timestamp in UTC for the current time. (`2024-03-15T12:34:56Z`)

-   **`new_timestamp_uid(bits: int = 32) -> str`**

    Generate a unique ID with an ISO 8601 timestamp prefix. (`0240315T123456Z-789012-kgk5mzn`)

-   **`new_uid(bits: int = 64) -> str`**

    Generate a unique ID with the specified number of bits. (`kgk5mzn`)

-   **`unique_id(prefix: str = "") -> str`**

    Generate consecutive unique IDs with an optional prefix.

    ```python
    from nclutils import unique_id

    print(unique_id())
    # 1
    print(unique_id("id_"))
    # id_2
    print(unique_id())
    # 3
    ```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.
