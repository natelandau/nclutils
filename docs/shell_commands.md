# Shell commands

A thin wrapper over stdlib `subprocess` for running external commands. Imported from `nclutils.sh`. Results come back as a typed `CompletedCommand` dataclass rather than raw strings, and every failure mode maps to a specific exception class. Output goes to `sys.stdout`/`sys.stderr` directly; `nclutils.sh` does not route through `nclutils.pp`'s console.

```python
from pathlib import Path
from nclutils.sh import run_command, which

# Check a tool is present before using it
if which("git"):
    result = run_command(["git", "status", "--short"])
    if result.stdout.strip():
        print("dirty working tree")
```

## Running commands

`run_command(argv, ...)` takes the command and all its arguments as a single list, runs the process, and returns a `CompletedCommand`. By default output is captured silently; pass `stream=True` to tee it to the terminal in real time.

```python
from nclutils.sh import run_command

result = run_command(["git", "log", "--oneline", "-5"])
print(result.stdout)
```

## The result object

Every call to `run_command` returns a `CompletedCommand`, a frozen dataclass. It carries six data fields and four computed properties:

```python
@dataclass(frozen=True, slots=True)
class CompletedCommand:
    argv: tuple[str, ...]    # full argument list that was executed
    returncode: int          # process exit code
    stdout: str              # captured stdout, trailing newline stripped
    stderr: str              # captured stderr, trailing newline stripped
    duration: float          # wall-clock seconds the process ran
    cwd: Path | None         # resolved working directory, or None if inherited

    @property
    def ok(self) -> bool: ...                 # True when returncode == 0
    @property
    def command_line(self) -> str: ...        # argv joined with shlex.join, shell-safe
    @property
    def stdout_lines(self) -> list[str]: ...  # stdout.splitlines()
    @property
    def stderr_lines(self) -> list[str]: ...  # stderr.splitlines()
```

The instance is frozen, so every field is read-only once the call returns. `stdout` and `stderr` are always captured separately; nothing is folded together.

| Field          | Type                  | Description                                                                  |
| -------------- | --------------------- | ---------------------------------------------------------------------------- |
| `argv`         | `tuple[str, ...]`     | The full argument list that was executed.                                    |
| `returncode`   | `int`                 | The process exit code.                                                       |
| `stdout`       | `str`                 | Captured standard output. Trailing newlines stripped; embedded ones kept.    |
| `stderr`       | `str`                 | Captured standard error (always separate). Trailing newlines stripped.       |
| `duration`     | `float`               | Wall-clock seconds the process ran.                                          |
| `cwd`          | `Path \| None`        | Resolved working directory, or `None` if inherited.                          |
| `ok`           | `bool` (property)     | `True` when `returncode == 0`.                                               |
| `command_line` | `str` (property)      | `argv` rendered with `shlex.join`, shell-safe and copy-pasteable.            |
| `stdout_lines` | `list[str]` (property)| `stdout.splitlines()`, convenience for iterating output.                     |
| `stderr_lines` | `list[str]` (property)| `stderr.splitlines()`.                                                       |

> [!NOTE]
> The single trailing newline most commands print is stripped from `stdout` and `stderr`, so `result.stdout == "hello"` rather than `"hello\n"`. Use `stdout_lines` / `stderr_lines` when you want to iterate without splitting manually.

## Streaming output

Pass `stream=True` to print output to the terminal as it arrives while still capturing it:

```python
from nclutils.sh import run_command

result = run_command(["rsync", "-av", "src/", "dst/"], stream=True)
print(f"finished in {result.duration:.1f}s")
```

> [!NOTE]
> stdout and stderr are drained by separate threads. Within each stream lines stay in order, but the relative interleaving between stdout and stderr is not deterministic. For true chronological interleaving, run the command via `sh -c "... 2>&1"` and inspect `result.stdout`.

## Options

### `cwd=`: working directory

Pass a `Path` or `str` to run the command from a different directory. `None` (the default) inherits the parent process's working directory.

```python
from pathlib import Path
from nclutils.sh import run_command

result = run_command(["pwd"], cwd=Path("/tmp"))
```

If `cwd` is missing or is not a directory, `run_command` raises `ShellCommandFailedError` before the process starts. `result` is `None` on that exception because no command actually ran. A failure to spawn the process itself, such as a permission error, raises the same exception, also with `result` set to `None`.

### `env=`: environment variables

When `env=` is provided it *replaces* the child's entire environment. To extend the current environment, merge it explicitly:

```python
import os
from nclutils.sh import run_command

result = run_command(
    ["printenv", "MY_VAR"],
    env={**os.environ, "MY_VAR": "hello"},
)
```

Passing `env=None` (the default) inherits the parent's environment unchanged.

### `input=`: stdin

Pass a string or bytes to write to the child's stdin:

```python
from nclutils.sh import run_command

result = run_command(["wc", "-w"], input="hello world")
print(result.stdout.strip())  # "2"
```

> [!WARNING]
> For inputs over ~64 KB where the child also produces output, a deadlock is possible because stdin is fully written before stdout starts draining. Pipe via shell redirection in that case (e.g., `run_command(["sh", "-c", "cat large.txt | wc -l"])`).

### `timeout=`: time limit

Pass a number of seconds. If the process runs longer, it is killed and `ShellCommandTimeoutError` is raised:

```python
from nclutils.sh import ShellCommandTimeoutError, run_command

try:
    run_command(["sleep", "10"], timeout=2.0)
except ShellCommandTimeoutError as e:
    print(f"killed after {e.timeout}s")
    print(f"partial stdout: {e.result.stdout!r}")
```

### `exclude_regex=`: filter lines

Lines matching this regex are dropped from both the streamed output and the captured strings. Useful for suppressing noisy warnings:

```python
from nclutils.sh import run_command

run_command(["npm", "install"], stream=True, exclude_regex=r"^npm warn deprecated")
```

### `check=False`: skip failure check

By default `run_command` raises `ShellCommandFailedError` on any non-zero exit. Pass `check=False` to suppress this and inspect the return code yourself:

```python
from nclutils.sh import run_command

result = run_command(["false"], check=False)
print(result.returncode)  # 1
```

### `okay_codes=`: acceptable exit codes

Some commands use non-zero exits as data. `grep` returns `1` when no lines match; `diff` returns `1` for non-identical files. Pass `okay_codes=` to treat additional codes as success:

```python
from nclutils.sh import run_command

# Exit 0 (matched) and 1 (no match) are both fine; only 2+ raises
result = run_command(
    ["grep", "pattern", "file.txt"],
    okay_codes=(0, 1),
)
```

### `sudo=True`: run as root

Prepends `["sudo"]` to the argument list. Cached credentials are used; `sudo -k` is never called. Either an interactive TTY (for the password prompt) or `NOPASSWD` in sudoers is required. The call will hang or fail in non-interactive contexts such as CI.

```python
from nclutils.sh import run_command

run_command(["systemctl", "restart", "nginx"], sudo=True)
```

## Error handling

All errors from `nclutils.sh` inherit from `ShellCommandError`, so a single `except ShellCommandError` catches every failure:

```python
from nclutils.sh import ShellCommandError, run_command

try:
    run_command(["git", "push", "origin", "main"])
except ShellCommandError as e:
    print(f"command failed: {e}")
```

The four exception classes and when each is raised:

| Exception                   | When raised                                                      |
| --------------------------- | ---------------------------------------------------------------- |
| `ShellCommandNotFoundError` | `argv[0]` is not on PATH.                                        |
| `ShellCommandFailedError`   | Process exited outside `okay_codes`, or the process could not be started (bad `cwd` or spawn error). |
| `ShellCommandTimeoutError`  | Process exceeded `timeout=` and was killed.                      |
| `ShellCommandError`         | Base class; catch this to handle all three above uniformly.      |

### `ShellCommandNotFoundError`

```python
from nclutils.sh import ShellCommandNotFoundError, run_command

try:
    run_command(["not-a-real-command", "--help"])
except ShellCommandNotFoundError as e:
    print(e)
```

### `ShellCommandFailedError`

The `result` attribute holds a `CompletedCommand` (or `None` if `cwd` couldn't be entered):

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

`result` contains the partial output captured before the process was killed, and `timeout` holds the limit you set:

```python
from nclutils.sh import ShellCommandTimeoutError, run_command

try:
    run_command(["sleep", "60"], timeout=5.0)
except ShellCommandTimeoutError as e:
    print(f"timed out after {e.timeout}s")
    print(f"stdout so far: {e.result.stdout!r}")
```

## Interactive commands

Use `run_interactive` for commands that need a real terminal: editors, pagers, SSH sessions, anything that drives the terminal directly. The child inherits stdin, stdout, and stderr from the parent; nothing is captured.

```python
from nclutils.sh import run_interactive

exit_code = run_interactive(["vim", "notes.txt"])
```

```python
from nclutils.sh import run_interactive

run_interactive(["ssh", "user@host"])
```

`run_interactive` accepts `cwd=`, `env=`, and `sudo=` with the same meaning as `run_command`. It returns the child's integer exit code. When `check=True` (the default), a non-zero exit raises `ShellCommandFailedError`. The `result.stdout` and `result.stderr` fields will be empty strings because no capture took place.

## Looking up a command

`which(cmd)` returns the absolute `Path` to an executable on PATH, or `None` if it's not found. Use it to gate optional functionality without raising:

```python
from nclutils.sh import which

rg = which("rg")
if rg:
    print(f"ripgrep is at {rg}")
else:
    print("ripgrep not installed; falling back to grep")
```

## Diagnostic logging

`run_command` emits a `DEBUG` record for every invocation through stdlib `logging` under the `nclutils.sh` logger. The message is the final argv (after any `sudo=True` prepend), formatted with `shlex.join` so it can be pasted back into a shell. Nothing is logged about stdout, stderr, or the return code; the returned `CompletedCommand` already carries those.

```python
import logging

logging.getLogger("nclutils.sh").setLevel(logging.DEBUG)
logging.basicConfig()
```

The logger is silent until the host application attaches a handler, so importing `nclutils.sh` never produces output on its own. This is independent of `nclutils.pp`. Anything built on top of `run_command` (including `nclutils.git.run_git`) inherits this logging for free; callers do not need to log invocations themselves.

## Migrating from the old API

The previous `nclutils.sh` module was a thin wrapper around the third-party `sh` package. The new implementation uses stdlib `subprocess` directly.

| Old usage                                                     | New usage                                                     |
| ------------------------------------------------------------- | ------------------------------------------------------------- |
| `run_command("git", ["status"])`                              | `run_command(["git", "status"])`                              |
| `output = run_command(...)` (returned `str`)                  | `result = run_command(...)` then `result.stdout`              |
| `pushd=Path("/tmp")`                                          | `cwd=Path("/tmp")`                                            |
| `quiet=True` (captured silently)                              | Default behavior; `stream=False` is the default               |
| `quiet=False` (streamed to console)                           | `stream=True`                                                 |
| `err_to_out=True`                                             | **Default behavior change.** The old default `err_to_out=True` folded stderr into the returned string. The new return value gives you `result.stdout` and `result.stderr` separately. If you previously did `output = run_command("foo", ["--bar"])` and your code expected stderr to be in `output`, switch to `result.stdout + result.stderr` after the call (or invoke `sh -c "foo --bar 2>&1"` if you need true interleaving). |
| `fg=True` (interactive, no capture)                           | `run_interactive([...])`                                      |
| `e.exit_code`, `e.stdout`, `e.stderr`, `e.full_cmd`           | `e.result.returncode`, `e.result.stdout`, `e.result.stderr`   |

## API reference

- `run_command(argv, *, cwd=None, env=None, input=None, timeout=None, exclude_regex=None, stream=False, check=True, okay_codes=(0,), sudo=False) -> CompletedCommand`. Run a non-interactive command and return captured output.
- `run_interactive(argv, *, cwd=None, env=None, sudo=False, check=True) -> int`. Run a command with a real terminal. Returns the exit code.
- `which(cmd) -> Path | None`. Resolve an executable name to its absolute path, or `None` if not found.
- `CompletedCommand`. Frozen dataclass returned by `run_command`. Fields: `argv`, `returncode`, `stdout`, `stderr`, `duration`, `cwd`. Properties: `ok`, `command_line`, `stdout_lines`, `stderr_lines`. Trailing newlines on `stdout` and `stderr` are stripped.
- `ShellCommandError`. Base exception for all `nclutils.sh` failures.
- `ShellCommandNotFoundError`. Raised when `argv[0]` is not on PATH.
- `ShellCommandFailedError`. Raised on non-zero exit or unreachable `cwd`. Carries `result: CompletedCommand | None`.
- `ShellCommandTimeoutError`. Raised when `timeout=` is exceeded. Carries `result: CompletedCommand` and `timeout: float`.
