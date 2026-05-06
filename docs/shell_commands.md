# Shell commands

Run external commands with consistent error handling and live output. A small layer over the [sh](https://github.com/amoffat/sh) module. Imported from `nclutils.sh`.

```python
from nclutils.sh import run_command, which

if which("git"):
    run_command("git", ["status", "--short"])
```

## Running commands

`run_command(cmd, args, ...)` runs a command, streams its output to the console as it arrives, and returns the full captured output as a string. ANSI color codes are preserved.

```python
from nclutils.sh import run_command

# Print output to the console as it streams
run_command("ls", ["-la", "/some/path"])

# Capture quietly and inspect after
output = run_command("git", ["status", "--short"], quiet=True)
if output.strip():
    print("dirty working tree")
```

### Changing directory

Pass `pushd=` to run the command from a different working directory. Empty string (the default) means "use the current directory."

```python
from pathlib import Path
from nclutils.sh import run_command

run_command("pwd", [], pushd=Path("/tmp"))
```

If `pushd` cannot be entered (missing, not a directory, or no permission), `run_command` raises `ShellCommandFailedError` with the underlying OS error in the message.

### Allowing non-zero exit codes

Some commands use exit codes as data — `grep` returns `1` when there are no matches, `diff` returns `1` for differences. Pass `okay_codes=` to whitelist additional codes.

```python
from nclutils.sh import run_command

# 0 (matched) and 1 (no match) are both fine; only 2+ raise
run_command("grep", ["pattern", "file.txt"], okay_codes=(0, 1))
```

`okay_codes` defaults to `(0,)`. An empty value falls back to `[0]`.

### Filtering output

`exclude_regex=` skips lines that match the given regex. Skipped lines are dropped from both the streamed console output and the returned string.

```python
from nclutils.sh import run_command

run_command("npm", ["install"], exclude_regex=r"^npm warn deprecated")
```

### Other options

- `quiet=True`. Collect output without printing it to the console.
- `sudo=True`. Run under `sudo`. Requires either an interactive TTY for the password prompt or `NOPASSWD` configured in `sudoers`; will hang or fail in non-interactive contexts (CI, daemons) otherwise.
- `err_to_out=True` (the default). Fold stderr into the captured stdout. Set to `False` to suppress stderr from both the streamed console output and the returned string.
- `fg=True`. Run the command in the foreground without capturing output. Use this for interactive commands like `vim` or `less`. The return value is always an empty string.

## Errors

Failures from `run_command` come back as one of two exception types.

### `ShellCommandNotFoundError`

The command wasn't found in `PATH`.

```python
from nclutils.sh import ShellCommandNotFoundError, run_command

try:
    run_command("not-a-real-command", [])
except ShellCommandNotFoundError as e:
    print(e)
```

### `ShellCommandFailedError`

The command ran but exited with a status not in `okay_codes`. The exception exposes the relevant context as attributes:

| Attribute    | Meaning                                                                |
| ------------ | ---------------------------------------------------------------------- |
| `exit_code`  | The exit status returned by the command.                               |
| `stdout`     | The stdout output captured by `sh`.                                    |
| `stderr`     | The stderr output captured by `sh`.                                    |
| `full_cmd`   | The full command string that was executed.                             |

```python
from nclutils.sh import ShellCommandFailedError, run_command

try:
    run_command("git", ["push"])
except ShellCommandFailedError as e:
    print(f"git push exited {e.exit_code}")
    print(e.stderr)
```

The exception is also raised when `pushd=` cannot be entered (missing, not a directory, or no permission). In that case the four attributes above are all `None` because no command actually ran; the underlying `OSError` is chained as `__cause__` and its description is included in the message.

## Looking up a command

`which(cmd)` returns the absolute path of an executable in `PATH`, or `None` if the command isn't found. Use it to gate optional features without try/except.

```python
from nclutils.sh import which

if which("docker"):
    run_command("docker", ["ps"])
else:
    print("docker not installed; skipping container checks")
```

## API reference

- `run_command(cmd, args, pushd="", okay_codes=(0,), exclude_regex=None, *, quiet=False, sudo=False, err_to_out=True, fg=False) -> str`. Run a command and return its captured output.
- `which(cmd) -> str | None`. Resolve a command name to an absolute path, or `None`.
- `ShellCommandFailedError`. Raised on non-zero exit. Exposes `exit_code`, `stdout`, `stderr`, `full_cmd`.
- `ShellCommandNotFoundError`. Raised when the command isn't in `PATH`.
