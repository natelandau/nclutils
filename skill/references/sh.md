# `nclutils.sh` reference

Thin wrapper over stdlib `subprocess`. Returns typed results, raises typed errors. Output goes to `sys.stdout`/`sys.stderr` directly and is independent of `nclutils.pp`.

## `run_command(argv, ...)`

```python
from nclutils.sh import run_command

result = run_command(["git", "log", "--oneline", "-5"])
print(result.stdout)
```

Takes the command and all its arguments as ONE list. Returns a `CompletedCommand`:

| Field        | Type              | Description                                          |
| ------------ | ----------------- | ---------------------------------------------------- |
| `argv`       | `tuple[str, ...]` | Full argument list executed.                         |
| `returncode` | `int`             | Process exit code.                                   |
| `stdout`     | `str`             | Captured standard output.                            |
| `stderr`     | `str`             | Captured standard error (always separate).           |
| `duration`   | `float`           | Wall-clock seconds the process ran.                  |
| `cwd`        | `Path \| None`    | Resolved working directory, or `None` if inherited.  |
| `ok`         | `bool` (property) | `True` when `returncode == 0`.                       |

### Options

| Kwarg            | Default     | Behavior                                                                              |
| ---------------- | ----------- | ------------------------------------------------------------------------------------- |
| `cwd=`           | `None`      | `Path` / `str` working dir. `None` inherits. `~` expanded. Unreachable → `ShellCommandFailedError` before the process starts. |
| `env=`           | `None`      | REPLACES child env. Merge with `{**os.environ, ...}` to extend.                       |
| `input=`         | `None`      | `str` or `bytes` to write to stdin. >~64 KB plus output can deadlock — use shell redirection instead. |
| `timeout=`       | `None`      | Seconds. Process killed and `ShellCommandTimeoutError` raised on overrun. The error's `result` carries partial output. |
| `exclude_regex=` | `None`      | Drops matching lines from both streamed output and captured strings.                  |
| `stream=`        | `False`     | `True` tees stdout/stderr to terminal while still capturing. stdout/stderr drained by separate threads — within each stream order is preserved, but interleaving between them is non-deterministic. For chronological interleaving, run via `sh -c "... 2>&1"`. |
| `check=`         | `True`      | `False` skips the failure-on-nonzero check. Inspect `result.returncode` yourself.     |
| `okay_codes=`    | `(0,)`      | Treat additional exit codes as success. E.g. `(0, 1)` for `grep` (1 = no match) or `diff` (1 = differ). |
| `sudo=`          | `False`     | Prepends `["sudo"]`. Cached credentials used. `sudo -k` never called. Requires interactive TTY or `NOPASSWD` — will hang in non-interactive contexts (CI). |

## `run_interactive(argv, ...)`

For commands that need a real terminal (editors, pagers, SSH, anything driving the terminal). Inherits stdin/stdout/stderr from parent; nothing is captured.

```python
exit_code = run_interactive(["vim", "notes.txt"])
run_interactive(["ssh", "user@host"])
```

Accepts `cwd=`, `env=`, `sudo=`, and `check=` (default `True`, raises `ShellCommandFailedError` on non-zero exit). Returns the integer exit code. `result.stdout` / `result.stderr` are empty strings because no capture took place.

## `which(cmd) -> Path | None`

Returns the absolute `Path` to an executable on PATH, or `None` if not found. Use to gate optional functionality without raising:

```python
rg = which("rg")
if rg:
    use_ripgrep(rg)
else:
    use_grep()
```

## Error hierarchy

All errors inherit from `ShellCommandError`. Catching the base class handles every failure mode.

| Exception                   | When raised                                                                  | Carries                                                |
| --------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------ |
| `ShellCommandError`         | Base class.                                                                  | —                                                      |
| `ShellCommandNotFoundError` | `argv[0]` is not on PATH.                                                    | message only                                           |
| `ShellCommandFailedError`   | Process exited outside `okay_codes`, OR `cwd` couldn't be entered.          | `result: CompletedCommand \| None` (`None` when cwd unreachable) |
| `ShellCommandTimeoutError`  | Process exceeded `timeout=` and was killed.                                  | `result: CompletedCommand` (partial output), `timeout: float` |

```python
from nclutils.sh import (
    ShellCommandError,
    ShellCommandFailedError,
    ShellCommandTimeoutError,
    run_command,
)

try:
    run_command(["git", "push", "origin", "main"], timeout=30.0)
except ShellCommandFailedError as e:
    if e.result is not None:
        print(f"exit {e.result.returncode}\n{e.result.stderr}")
except ShellCommandTimeoutError as e:
    print(f"killed after {e.timeout}s; stdout so far: {e.result.stdout!r}")
except ShellCommandError as e:
    print(f"command failed: {e}")
```

## Diagnostic logging

`run_command` emits a `DEBUG` record for every invocation through stdlib `logging` under the `nclutils.sh` logger. The message is the final `argv` (after any `sudo=True` prepend), formatted with `shlex.join` so it can be pasted back into a shell.

```python
import logging
logging.getLogger("nclutils.sh").setLevel(logging.DEBUG)
logging.basicConfig()
```

The logger is silent until the host attaches a handler — importing `nclutils.sh` never produces output on its own. Anything built on top of `run_command` (including `nclutils.git.run_git`) inherits this logging for free.

## Common patterns

### Inspect exit code without raising

```python
result = run_command(["diff", "-q", a, b], check=False)
if result.returncode == 0:
    print("identical")
elif result.returncode == 1:
    print("differ")
```

### Treat known non-zero codes as success

```python
# grep returns 1 on no match. Don't silence — treat 1 as data:
result = run_command(["grep", "needle", "file"], okay_codes=(0, 1))
found = result.returncode == 0
```

### Suppress noisy lines

```python
run_command(["npm", "install"], stream=True, exclude_regex=r"^npm warn deprecated")
```

### Extend the parent environment

```python
import os
run_command(
    ["printenv"],
    env={**os.environ, "MY_VAR": "hello"},
)
# WRONG: env={"MY_VAR": "hello"} — child sees ONLY that variable
```
