# Shell commands

Use `nclutils.sh` to run external commands from Python. `run_command` returns a typed `CompletedCommand` with the exit code and the captured output, and each failure raises a specific exception class. Streamed output goes directly to `sys.stdout` and `sys.stderr`. It does not go through the `nclutils.pp` console.

```python
from nclutils.sh import run_command, which

# Run git only if it is installed
if which("git"):
    result = run_command(["git", "status", "--short"])
    if result.stdout:
        print("dirty working tree")
```

## Running commands

`run_command(argv, ...)` takes the command and all its arguments as one list. It runs the process and returns a `CompletedCommand`. By default, the output is captured and nothing is shown in the terminal. To show the output while the command runs, pass `stream=True`.

```python
from nclutils.sh import run_command

result = run_command(["git", "log", "--oneline", "-5"])
print(result.stdout)
```

The list goes to the operating system as-is. No shell parses it, so pipes, redirects, and `~` have no special meaning. To use shell syntax, run the shell: `run_command(["sh", "-c", "ls | wc -l"])`.

## The result object

`run_command` returns a `CompletedCommand`. It is a frozen dataclass, so all fields are read-only. `stdout` and `stderr` are always captured separately.

| Field          | Type                   | Description                                                             |
| -------------- | ---------------------- | ----------------------------------------------------------------------- |
| `argv`         | `tuple[str, ...]`      | The full argument list that ran, including `sudo` when `sudo=True`.     |
| `returncode`   | `int`                  | The exit code of the process.                                           |
| `stdout`       | `str`                  | Captured standard output. Trailing newlines are removed.                |
| `stderr`       | `str`                  | Captured standard error. Trailing newlines are removed.                 |
| `duration`     | `float`                | Wall-clock seconds that the process ran.                                |
| `cwd`          | `Path \| None`         | The resolved working directory, or `None` if the parent's was used.     |
| `ok`           | `bool` (property)      | `True` when `returncode == 0`.                                          |
| `command_line` | `str` (property)       | `argv` joined with `shlex.join`. You can paste it into a shell.         |
| `stdout_lines` | `list[str]` (property) | `stdout.splitlines()`.                                                  |
| `stderr_lines` | `list[str]` (property) | `stderr.splitlines()`.                                                  |

> [!NOTE]
> Trailing newlines are removed from `stdout` and `stderr`, so `result.stdout == "hello"`, not `"hello\n"`. Newlines between lines stay. To iterate line by line, use `stdout_lines` or `stderr_lines`.

## Streaming output

Pass `stream=True` to show output in the terminal as it arrives. The output is also captured in the result.

```python
from nclutils.sh import run_command

result = run_command(["rsync", "-av", "src/", "dst/"], stream=True)
print(f"finished in {result.duration:.1f}s")
```

> [!NOTE]
> `run_command` reads stdout and stderr separately. Lines keep their order within each stream, but the order between the two streams is not fixed. If you need one stream in the order that the command wrote it, run the command through `sh -c "... 2>&1"` and read `result.stdout`.

## Options

All options are keyword-only.

### `cwd=`: working directory

Pass a `Path` or `str` to run the command in a different directory. `~` is expanded. The default, `None`, uses the working directory of the parent process.

```python
from pathlib import Path
from nclutils.sh import run_command

result = run_command(["pwd"], cwd=Path("/tmp"))
```

If `cwd` does not exist or is not a directory, `run_command` raises `ShellCommandFailedError` before the process starts. The `result` attribute of that exception is `None` because no command ran.

### `env=`: environment variables

A mapping passed to `env=` replaces the full environment of the child process. To add variables to the current environment, merge them:

```python
import os
from nclutils.sh import run_command

result = run_command(
    ["printenv", "MY_VAR"],
    env={**os.environ, "MY_VAR": "hello"},
)
```

The default, `None`, gives the child the parent's environment.

### `input=`: stdin

Pass a `str` or `bytes` to write it to the stdin of the child process. A `str` is encoded as UTF-8. Without `input=`, stdin is connected to the null device, so a command that prompts for input reads end-of-file.

```python
from nclutils.sh import run_command

result = run_command(["wc", "-w"], input="hello world")
print(result.stdout.strip())  # "2"
```

> [!WARNING]
> Do not pass more than about 64 KB to `input=` when the command also writes output. `run_command` writes all of stdin before it reads stdout, so the call can deadlock. Use shell redirection instead, for example `run_command(["sh", "-c", "wc -l < large.txt"])`.

### `timeout=`: time limit

Pass a number of seconds. If the process runs longer, `run_command` kills it and raises `ShellCommandTimeoutError`. The timeout error is raised also when `check=False`.

```python
from nclutils.sh import ShellCommandTimeoutError, run_command

try:
    run_command(["sleep", "10"], timeout=2.0)
except ShellCommandTimeoutError as e:
    print(f"killed after {e.timeout}s")
    print(f"partial stdout: {e.result.stdout!r}")
```

### `exclude_regex=`: filter lines

`run_command` removes lines that match this regular expression from the streamed output and from the captured `stdout` and `stderr`. The match uses `re.search`, so the pattern can match anywhere in the line. Use it to hide noisy warnings:

```python
from nclutils.sh import run_command

run_command(["npm", "install"], stream=True, exclude_regex=r"^npm warn deprecated")
```

### `check=False`: skip the exit code check

By default, `run_command` raises `ShellCommandFailedError` when the exit code is not in `okay_codes`. Pass `check=False` to get the result for every exit code and read `returncode` yourself:

```python
from nclutils.sh import run_command

result = run_command(["false"], check=False)
print(result.returncode)  # 1
```

### `okay_codes=`: accepted exit codes

Some commands use a non-zero exit code to report data. `grep` returns `1` when no lines match, and `diff` returns `1` when the files are different. Pass a tuple of the exit codes that count as success. The default is `(0,)`.

```python
from nclutils.sh import run_command

# Exit 0 (match) and 1 (no match) are success. Exit 2 or more raises.
result = run_command(
    ["grep", "pattern", "file.txt"],
    okay_codes=(0, 1),
)
```

### `sudo=True`: run as root

`run_command` adds `sudo` to the start of the argument list. It uses cached credentials and never runs `sudo -k`. The command needs an interactive terminal for the password prompt, or `NOPASSWD` in the sudoers file. Without one of these, as in CI, the call can hang or fail.

```python
from nclutils.sh import run_command

run_command(["systemctl", "restart", "nginx"], sudo=True)
```

## Error handling

All exception classes in `nclutils.sh` inherit from `ShellCommandError`. One `except ShellCommandError` catches every command failure:

```python
from nclutils.sh import ShellCommandError, run_command

try:
    run_command(["git", "push", "origin", "main"])
except ShellCommandError as e:
    print(f"command failed: {e}")
```

| Exception                   | When raised                                                                                                 |
| --------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `ShellCommandNotFoundError` | The executable in `argv[0]` is not found.                                                                   |
| `ShellCommandFailedError`   | The exit code is not in `okay_codes`, `cwd` is not a directory, or the operating system cannot start the process. |
| `ShellCommandTimeoutError`  | The process ran longer than `timeout=` and was killed.                                                      |
| `ShellCommandError`         | The base class of the three exceptions above.                                                               |

`run_command` decodes output as UTF-8. If a command writes bytes that are not valid UTF-8, `run_command` raises `UnicodeDecodeError`, which is not a `ShellCommandError`.

### `ShellCommandNotFoundError`

The `argv` attribute holds the argument list as a tuple.

```python
from nclutils.sh import ShellCommandNotFoundError, run_command

try:
    run_command(["not-a-real-command", "--help"])
except ShellCommandNotFoundError as e:
    print(e.argv[0])
```

### `ShellCommandFailedError`

The `result` attribute holds the `CompletedCommand`. It is `None` when the process did not start, because `cwd` is not a directory or the operating system cannot start the process. In that case, the original `OSError` is available as `__cause__`.

```python
from nclutils.sh import ShellCommandFailedError, run_command

try:
    run_command(["git", "push", "origin", "main"])
except ShellCommandFailedError as e:
    if e.result is not None:
        print(f"exit {e.result.returncode}")
        print(e.result.stderr)
```

### `ShellCommandTimeoutError`

The `result` attribute holds the output that was captured before the process was killed. The `timeout` attribute holds the limit that you set.

```python
from nclutils.sh import ShellCommandTimeoutError, run_command

try:
    run_command(["sleep", "60"], timeout=5.0)
except ShellCommandTimeoutError as e:
    print(f"timed out after {e.timeout}s")
    print(f"stdout so far: {e.result.stdout!r}")
```

## Interactive commands

Use `run_interactive` for commands that need a real terminal: editors, pagers, and SSH sessions. The child process uses the stdin, stdout, and stderr of the parent. Nothing is captured.

```python
from nclutils.sh import run_interactive

exit_code = run_interactive(["vim", "notes.txt"])
```

`run_interactive` accepts `cwd=`, `env=`, `sudo=`, and `check=` with the same meaning as in `run_command`. It returns the exit code of the child process as an `int`. When `check=True` (the default), a non-zero exit code raises `ShellCommandFailedError`. In that exception, `result.stdout` and `result.stderr` are empty strings because no output was captured. A missing executable raises `ShellCommandNotFoundError`.

## Looking up a command

`which(cmd)` returns the `Path` of an executable on `PATH`, or `None` if it is not found. Use it to turn on optional features without an exception:

```python
from nclutils.sh import which

rg = which("rg")
if rg:
    print(f"ripgrep is at {rg}")
else:
    print("ripgrep not installed, using grep")
```

## Diagnostic logging

`run_command` writes one `DEBUG` record for each command through stdlib `logging`, under the `nclutils.sh` logger. The message is the final argument list, including `sudo` when `sudo=True`, joined with `shlex.join` so that you can paste it into a shell. The record does not contain stdout, stderr, or the exit code. The returned `CompletedCommand` holds those. `run_interactive` does not log.

```python
import logging

logging.getLogger("nclutils.sh").setLevel(logging.DEBUG)
logging.basicConfig()
```

The logger shows nothing until the host application attaches a handler. It is separate from `nclutils.pp`. Code that calls `run_command`, such as `nclutils.git.run_git`, gets the same log records.

## API reference

- `run_command(argv: Sequence[str], *, cwd: Path | str | None = None, env: Mapping[str, str] | None = None, input: str | bytes | None = None, timeout: float | None = None, exclude_regex: str | None = None, stream: bool = False, check: bool = True, okay_codes: tuple[int, ...] = (0,), sudo: bool = False) -> CompletedCommand`. Run a non-interactive command and return the captured output. Raises `ShellCommandNotFoundError`, `ShellCommandFailedError`, or `ShellCommandTimeoutError`.
- `run_interactive(argv: Sequence[str], *, cwd: Path | str | None = None, env: Mapping[str, str] | None = None, sudo: bool = False, check: bool = True) -> int`. Run a command in the parent's terminal and return the exit code. Raises `ShellCommandNotFoundError` or `ShellCommandFailedError`.
- `which(cmd: str) -> Path | None`. Return the path of an executable on `PATH`, or `None` if it is not found.
- `CompletedCommand`. Frozen dataclass returned by `run_command`. Fields: `argv`, `returncode`, `stdout`, `stderr`, `duration`, `cwd`. Properties: `ok`, `command_line`, `stdout_lines`, `stderr_lines`.
- `ShellCommandError`. Base class for all `nclutils.sh` exceptions.
- `ShellCommandNotFoundError`. Raised when the executable is not found. Has `argv: tuple[str, ...]`.
- `ShellCommandFailedError`. Raised when the exit code is not accepted or the process cannot start. Has `result: CompletedCommand | None`.
- `ShellCommandTimeoutError`. Raised when the process runs longer than `timeout=`. Has `result: CompletedCommand` and `timeout: float`.
