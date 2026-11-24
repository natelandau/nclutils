# `nclutils.sh` reference

Wrapper over stdlib `subprocess`. Typed result, typed errors. Never runs through a shell. Independent of `nclutils.pp`.

## Signatures

```python
run_command(
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    input: str | bytes | None = None,
    timeout: float | None = None,
    exclude_regex: str | None = None,
    stream: bool = False,
    check: bool = True,
    okay_codes: tuple[int, ...] = (0,),
    sudo: bool = False,
) -> CompletedCommand

run_interactive(
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    sudo: bool = False,
    check: bool = True,
) -> int

which(cmd: str) -> Path | None
```

`argv` is one list: executable plus every argument. `run_command(["git", "log", "-5"])`, not `run_command("git log -5")`.

## `run_command`

Run a non-interactive command, capture stdout and stderr separately, return a `CompletedCommand`.

| Kwarg | Behavior |
| --- | --- |
| `cwd` | Working directory; `None` inherits. `~` expanded. Not a directory -> `ShellCommandFailedError` before start. |
| `env` | Replaces the child environment. Extend with `{**os.environ, "KEY": "value"}`. |
| `input` | Written to stdin, then stdin closed. `str` encoded UTF-8. Without `input`, stdin is the null device. Over ~64 KB of input with a child that also writes output can deadlock; use shell redirection instead. |
| `timeout` | Seconds. On overrun: process killed, `ShellCommandTimeoutError` raised, also with `check=False`. |
| `exclude_regex` | Drops every line where `re.search` matches, from captured output and streamed output. |
| `stream` | `True`: copy output live to `sys.stdout` / `sys.stderr` while capturing. Order within each stream is kept; interleaving between them is not. For one ordered stream: `["sh", "-c", "cmd 2>&1"]`. |
| `check` | `True`: exit code outside `okay_codes` raises `ShellCommandFailedError`. `False`: no exit-code check. |
| `okay_codes` | Exit codes accepted when `check=True`. `(0, 1)` for `grep` (no match) or `diff` (files differ). |
| `sudo` | Prepends `"sudo"` to `argv`. Requires cached credentials, `NOPASSWD`, or a TTY for the password prompt. |

Output must be valid UTF-8. Otherwise `UnicodeDecodeError` is raised, which is not a `ShellCommandError`.

### `CompletedCommand`

Frozen dataclass.

| Field | Type | Value |
| --- | --- | --- |
| `argv` | `tuple[str, ...]` | Arguments run, including `"sudo"` when `sudo=True`. |
| `returncode` | `int` | Exit code. Negative signal number if killed (`-9` after a timeout). |
| `stdout` | `str` | Trailing newlines stripped, inner newlines kept: `"hello"`, not `"hello\n"`. |
| `stderr` | `str` | Same stripping as `stdout`. |
| `duration` | `float` | Wall-clock seconds. |
| `cwd` | `Path \| None` | Resolved working directory, or `None` if inherited. |
| `ok` | `bool` (property) | `returncode == 0`, regardless of `okay_codes`. |
| `command_line` | `str` (property) | `shlex.join(argv)`, safe to paste into a shell. |
| `stdout_lines` | `list[str]` (property) | `stdout.splitlines()`, rebuilt on each access. |
| `stderr_lines` | `list[str]` (property) | `stderr.splitlines()`, rebuilt on each access. |

## `run_interactive`

For commands that need the terminal (editors, pagers, `ssh`). Inherits stdin, stdout, and stderr; captures nothing. Returns the exit code.

- `cwd`, `env`, `sudo`: same as `run_command`.
- `check=True`: any non-zero exit raises `ShellCommandFailedError`; its `result` has empty `stdout` and `stderr`. No `okay_codes`, `timeout`, or `input`.

```python
exit_code = run_interactive(["vim", "notes.txt"], check=False)
```

## `which`

Absolute `Path` of `cmd` on `PATH` (via `shutil.which`), or `None`. Use to gate optional tools without catching an error.

## Errors

All inherit from `ShellCommandError`, except `UnicodeDecodeError` from undecodable output.

| Exception | Raised when | Attributes |
| --- | --- | --- |
| `ShellCommandError` | Base class. | - |
| `ShellCommandNotFoundError` | Executable not found (`argv[0]`, or `sudo` with `sudo=True`). | `argv: tuple[str, ...]`, including `"sudo"` when `sudo=True`. |
| `ShellCommandFailedError` | Exit code rejected by `check`; `cwd` not a directory; process failed to start for another `OSError` (such as permission denied). | `result: CompletedCommand \| None`. `None` for the `cwd` and start failures; a start failure keeps the `OSError` as `__cause__`. |
| `ShellCommandTimeoutError` | `timeout` exceeded; process killed. | `result: CompletedCommand` (output before the kill), `timeout: float`. |

```python
try:
    run_command(["git", "push"], timeout=30.0)
except ShellCommandFailedError as e:
    if e.result is not None:
        print(e.result.returncode, e.result.stderr)
except ShellCommandTimeoutError as e:
    print(e.timeout, e.result.stdout)
except ShellCommandError as e:
    print(e)
```

## Logging

`run_command` logs each final `argv` (after the `sudo` prepend) as `shlex.join` at `DEBUG` on the stdlib logger `nclutils.sh`. `run_interactive` does not log. Silent until the host attaches a handler. `nclutils.git` commands run through `run_command` and log the same way.

```python
logging.basicConfig()
logging.getLogger("nclutils.sh").setLevel(logging.DEBUG)
```

## Patterns

```python
# Branch on exit code without raising
result = run_command(["diff", "-q", a, b], check=False)
identical = result.returncode == 0

# grep: exit 1 means no match, not failure
found = run_command(["grep", "needle", "file"], okay_codes=(0, 1)).returncode == 0

# Hide noisy lines while streaming
run_command(["npm", "install"], stream=True, exclude_regex=r"^npm warn deprecated")

# Extend the environment
run_command(["printenv"], env={**os.environ, "MY_VAR": "hello"})
# Wrong: env={"MY_VAR": "hello"} leaves the child with only MY_VAR
```
