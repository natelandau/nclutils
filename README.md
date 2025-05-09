# nclutils

Small Python utility functions and syntactic sugar for creating packages and scripts, written and maintained for my own personal use.

## Features

-   **Pretty Printing**: Rich text formatting for console output with customizable styles
-   **Shell Commands**: Safe execution of shell commands with proper error handling
-   **Filesystem Utilities**: Common filesystem operations
-   **Questions**: Short-cut functions for asking questions and getting user input using the [questionary library](https://github.com/tmbo/questionary).
-   **Network**: Helper functions for working with network connections.
-   Other miscellaneous utilities.

## Requirements

-   Python 3.11 or higher
-   Dependencies are managed with [uv](https://github.com/astral-sh/uv)

### Dependencies

nclutils has a few dependencies that are included in the project.

-   [questionary](https://github.com/tmbo/questionary) - For asking questions
-   [rich](https://github.com/Textualize/rich) - For pretty printing
-   [sh](https://github.com/amoffat/sh) - For running shell commands

## Installation

Install using `uv`:

```bash
uv add git+https://github.com/natelandau/nclutils.git
```

## Usage

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

### Network

-   **`network_available(address: str = "8.8.4.4", port: int = 53, timeout: int = 5) -> bool`**

    Check if a network connection is available.

### Pretty Printing

The pretty printing module provides styled console output with configurable log levels and custom styles.

```python
from nclutils import pp, console

#Configure logging levels
pp.configure(debug=True, trace=True)

# Basic message types
pp.info("Hello, world!")
pp.debug("This is a debug message")
pp.trace("This is a trace message")
pp.success("This is a success message")
pp.warning("This is a warning message")
pp.error("This is an error message")
pp.critical("This is a critical message")
pp.dryrun("This is a dry run message")
pp.notice("This is a notice message")
pp.secondary("This is a secondary message")
pp.rule("This is a horizontal rule")
console.print("This is a console message")
console.log("This is a log message")
```

#### Confirming verbosity state

The `pp` object has attributes `is_debug` and `is_trace` that can be used to check the current verbosity state.

```python
print(pp.is_debug)
print(pp.is_trace)
```

#### Customizing Styles

Create new styles or modify existing ones using the `PrintStyle` class:

```python
from nclutils import PrintStyle, pp

# Create custom styles
new_style = PrintStyle(name="new_style", prefix=":smile: ", suffix=" :rocket:")
new_error = PrintStyle(name="error", style="bold green")

# Apply custom styles
pp.configure(styles=[new_style, new_error])

# Use custom styles
pp.new_style("I am new style")
pp.error("This error message is now bold green")
```

#### View All Styles

A debug method is available to view all available styles.

```python
pp.all_styles()
```

### Print Debug Information

**`print_debug(envar_prefix: str | None = None, custom: list[dict[str, dict[str, str]] | dict[str, str]] | None = None, packages: list[str] | None = None, all_packages: bool = False) -> None`**

```python
from nclutils import print_debug

config_as_dict = {
    "Configuration": {
        "key": "value",
        "key2": "value2",
        "key3": "value3",
    }
}

cli_args_as_dict = {
    "somevar": "somevalue",
    "anothervar": "anothervalue",
}

print_debug(custom=[config_as_dict, cli_args_as_dict], envar_prefix="NCLUTILS_", packages=["nclutils"])
```

### Pytest Fixtures

The `nclutils.pytest_fixtures` module contains convenience functions and fixtures that are useful for testing.

For use in your tests, import these into your `conftest.py` file:

```python
# tests/conftest.py

# import specific fixtures
from nclutils.pytest_fixtures import clean_stdout, debug

# or import all fixtures
from nclutils.pytest_fixtures import *
```

-   **`clean_stdout`**

    Clean the stdout of the console output by creating a wrapper around `capsys` to capture console output.

    ```python
    def test_something(clean_stdout):
        print("Hello, world!")
        output = clean_stdout()
        assert output == "Hello, world!"
    ```

-   **`debug`**

    Prints debug information to the console. Useful for writing and debugging tests.

    ```python
    def test_something(debug):
        something = some_complicated_function()

        debug(something)

        assert something == expected
    ```

-   **`pytest_assertrepr_compare`**

    Patches the default pytest behavior of hiding whitespace differences in assertion failure messages. Replaces spaces and tabs with `[space]` and `[tab]` markers.

### Questions

-   **`choose_one_from_list(choices: list[T] | list[tuple[str, T]] | list[dict[str, T]], message: str) -> T | None`**

    Choose one item from a list of items:

    ```python
    from nclutils import choose_one_from_list

    choices = ["test", "test2", "test3"]
    result = choose_one_from_list(choices, "Choose a string")
    ```

    To use objects, send a list of tuples as choices. The first element of the tuple is the display title, the second element is the object to return.

    ```python
    from nclutils import choose_from_list

    @dataclass
    class Something:
        name: str
        number: int

    choices = [
        ("test1", Something(name="test1", number=1)),
        ("test2", Something(name="test2", number=2)),
    ]
    result = choose_from_list(choices, "Choose one")
    ```

-   **`choose_multiple_from_list(choices: list[T] | list[tuple[str, T]] | list[dict[str, T]], message: str) -> list[T] | None`**

    Choose multiple items from a list of items.

### Shell Commands

-   **`run_command(cmd: str, args: list[str] = [], quiet: bool = False, pushd: str | Path | None = None, okay_codes: list[int] | None = None, exclude_regex: str | None = None, sudo: bool = False) -> str`**

    Execute shell commands with proper error handling and output control.

    ```python
    from nclutils import run_command

    # Execute a command and print the output to the console
    run_command("ls", ["-la", "/some/path"])

    # Run quietly (suppress output to console)
    output = run_command("git", ["status"], quiet=True)
    ```

    **Changing Directories**

    The `run_command` function can change directories before running a command.

    ```python
    from nclutils import run_command

    # Change to a temporary directory and then run the command
    run_command("pwd", [], pushd=Path("/tmp"))
    ```

    **Errors**

    The `run_command` function raises `ShellCommandFailedError` if the command fails and `ShellCommandNotFoundError` if the command is not found.

    ```python
    from nclutils import ShellCommandFailedError, ShellCommandNotFoundError

    try:
        run_command("nonexistent", ["arg1"])
    except ShellCommandNotFoundError as e:
        print(e)
    except ShellCommandFailedError as e:
        print(e.exit_code)
        print(e.stderr)
        print(e.stdout)
        print(e.full_cmd)

    # To mark exit codes as successful, pass a list of integers to the `okay_codes` parameter.
    run_command("ls", ["-l", "/Users"], okay_codes=[0,1])
    ```

-   **`which(cmd: str) -> str | None`**

    Check if a command exists in the PATH. Returns the absolute path to the command if found, otherwise None.

    ```python
    from nclutils import which

    # Check if a command exists in the PATH
    result = which("ls")

    # If the command exists, print the path
    if result:
        print(result)
    ```

### Strings

-   **`camel_case(text: str) -> str`**

    Convert a string to camel case. (`hello world -> helloWorld`)

-   **`deburr(text: str) -> str`**

    Deburr a string. (`crème brûlée -> creme brulee`)

-   **`kebab_case(text: str) -> str`**

    Convert a string to kebab case. (`hello world -> hello-world`)

-   **`list_words(text: str, pattern: str = "", strip_apostrophes: bool = False) -> list[str]`**

    Split a string into a list of words.

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
