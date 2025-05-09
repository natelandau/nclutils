# Shell Commands

Convenience functions built on top of the [sh](https://github.com/amoffat/sh) module.

## Run Command

`run_command(cmd: str, args: list[str] = [], quiet: bool = False, pushd: str | Path | None = None, okay_codes: list[int] | None = None, exclude_regex: str | None = None, sudo: bool = False) -> str`

Execute shell commands with proper error handling and output control.

**Arguments:**

-   `cmd`: str. The command to execute
-   `args`: list[str]. The command arguments
-   `quiet`: bool. Whether to suppress output to console (default: False)
-   `pushd`: str | Path. The directory to change to before running the command (default: None)
-   `okay_codes`: list[int]. A list of exit codes that are considered successful (default: None)
-   `exclude_regex`: str | None. A regex to exclude lines from the output (default: None)
-   sudo: bool. Whether to run the command with sudo (default: False)

```python
from script_utilities import run_command

# Execute a command and print the output to the console
run_command("ls", ["-la", "/some/path"])

# Run quietly (suppress output to console)
output = run_command("git", ["status"], quiet=True)
```

### Changing Directories

The run_command function can change directories before running a command.

```python
from script_utilities import run_command

# Change to a temporary directory and then run the command
run_command("pwd", [], pushd=Path("/tmp"))
```

### Errors

The run_command function raises `ShellCommandFailedError` if the command fails and `ShellCommandNotFoundError` if the command is not found.

`ShellCommandFailedError` has the following attributes:

-   `exit_code`: The exit code of the command
-   `stderr`: The stderr output of the command
-   `stdout`: The stdout output of the command
-   `full_cmd`: The full command that was run

```python
from script_utilities import ShellCommandFailedError, ShellCommandNotFoundError

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

## which

`which(cmd: str) -> str | None`

Check if a command exists in the PATH. Returns the absolute path to the command if found, otherwise None.

```python
from script_utilities import which

# Check if a command exists in the PATH
result = which("ls")

# If the command exists, print the path
if result:
    print(result)
```
