---
name: nclutils
description: Use whenever writing or editing Python code in a project that depends on the `nclutils` package. Trigger on any `import nclutils` or `from nclutils.*` line, and whenever about to hand roll filesystem operations, subprocess/shell calls, console output, interactive prompts, case conversion, ISO timestamps, or git automation
---

# nclutils

`nclutils` is a small Python package of utility helpers: filesystem ops, shell execution, console output, interactive prompts, string transforms, git operations, and a few odds and ends. This skill exists to help an agent edit a downstream project that has `nclutils` as a dependency. If `nclutils` is not installed, this skill does not apply.

## Import patterns

The ONLY symbol re-exported from the top-level `nclutils` namespace is `pp`. Everything else must be imported from its submodule.

```python
# This is the ONE shape of bare-namespace import that works:
from nclutils import pp

pp.info("hello")
pp.success("done")
```

Every other symbol lives under a submodule:

```python
from nclutils.ask import choose_one_from_list, choose_multiple_from_list
from nclutils.fs import (
    copy_file, copy_directory, backup_path, clean_directory,
    find_files, find_subdirectories, directory_tree, find_user_home_dir,
)
from nclutils.git import (
    get_repo_state, sync_branch, fetch, stashed,
    add_worktree, prunable_branches, delete_branches, run_git,
    is_empty_branch, stash_counts,
    PrunableBranch, PruneReason, DeleteOutcome,
    NotARepoError,
)
from nclutils.net import network_available
from nclutils.sh import (
    run_command, run_interactive, which,
    CompletedCommand,
    ShellCommandError, ShellCommandNotFoundError,
    ShellCommandFailedError, ShellCommandTimeoutError,
)
from nclutils.strings import (
    camel_case, kebab_case, pascal_case, separator_case, snake_case,
    deburr, list_words, split_camel_case, strip_ansi,
    pad, pad_start, pad_end,
    random_string, int_to_emoji, human_size,
)
from nclutils.text import replace_in_file, ensure_lines_in_file
from nclutils.utils import (
    iso_timestamp, format_iso_timestamp,
    new_uid, new_timestamp_uid, unique_id,
    check_python_version,
)
```

`pp` symbols can also be pulled directly when the call site reads better that way:

```python
from nclutils.pp import info, success, step, configure, Verbosity
```

### Wrong-import patterns to avoid

```python
# WRONG — these symbols don't exist on the bare nclutils namespace
from nclutils import copy_file        # use nclutils.fs.copy_file
from nclutils import run_command       # use nclutils.sh.run_command
from nclutils import snake_case        # use nclutils.strings.snake_case

# DEPRECATED — emit DeprecationWarning and will be removed in v4.0.0
from nclutils.questions import ...     # use nclutils.ask instead
from nclutils.network import ...       # use nclutils.net instead
from nclutils.text_processing import ... # use nclutils.text instead
```

## What lives where

A task → module lookup. When you are about to write code for one of these, reach for the listed helper first.

| Task                                               | Reach for                                                                                               | Notes                                                                                 |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| User-facing console output (info, success, errors) | `nclutils.pp.info` / `pp.success` / `pp.warning` / `pp.error` / `pp.critical` / `pp.dryrun`             | Rich-based. Has verbosity gates and an optional file logger.                          |
| Long-running step with a spinner                   | `with pp.step("...") as s: s.sub("...")`                                                                | Cannot nest. Use `s.sub()` for sub-items.                                             |
| Section header                                     | `pp.header("title")`                                                                                    | Rule line with optional centered title.                                               |
| Aligned key/value summary                          | `pp.kv({"Branch": "main", "Commit": "abc"})`                                                            | Suppressed by `quiet=True` on console; still logged.                                  |
| Interactive single/multi prompt                    | `nclutils.ask.choose_one_from_list` / `choose_multiple_from_list`                                       | `questionary` widget. Returns `None` on cancel.                                       |
| Copy a file (with optional progress + backup)      | `nclutils.fs.copy_file(src, dst)`                                                                       | Drop-in for `shutil.copy`. Backs up existing dst by default.                          |
| Copy a directory recursively                       | `nclutils.fs.copy_directory(src, dst)`                                                                  | Follows symlinks, preserves dir mode + times. File mtimes not preserved.              |
| Snapshot a path before mutating                    | `nclutils.fs.backup_path(path)`                                                                         | Creates `path.<ts>-<rand>.bak`. Returns the backup path.                              |
| Empty a directory in place                         | `nclutils.fs.clean_directory(path)`                                                                     | Removes contents, not the directory itself.                                           |
| Find files by glob                                 | `nclutils.fs.find_files(root, globs=["*.py"])`                                                          | Sorted, deduped, dotfile filter.                                                      |
| Walk subdirectories with depth + regex             | `nclutils.fs.find_subdirectories(root, depth=2, filter_regex=...)`                                      | `depth` must be `>= 1`.                                                               |
| Render a tree of a directory                       | `nclutils.fs.directory_tree(path)`                                                                      | Returns a `rich.tree.Tree`. Print with `pp.console().print(...)`.                     |
| Resolve a user's home (sudo-aware)                 | `nclutils.fs.find_user_home_dir(username=None)`                                                         | Honors `SUDO_USER`.                                                                   |
| Run an external command                            | `nclutils.sh.run_command(["git", "status"])`                                                            | Returns `CompletedCommand`; raises typed errors on failure.                           |
| Stream output as it arrives                        | `run_command([...], stream=True)`                                                                       | Tees to terminal AND captures.                                                        |
| Run an editor / SSH / interactive shell            | `nclutils.sh.run_interactive([...])`                                                                    | Inherits stdin/stdout/stderr. Returns exit code.                                      |
| Locate a binary on PATH                            | `nclutils.sh.which("rg")`                                                                               | Returns `Path \| None`. Prefer over `shutil.which`.                                   |
| Read repo state in one call                        | `nclutils.git.get_repo_state()`                                                                         | Returns `RepoState` (branch, ahead/behind, dirty counts, stash, rebase flag).         |
| Pull/rebase the current branch                     | `nclutils.git.sync_branch()`                                                                            | Auto-stashes, ff-or-rebase, returns `SyncResult`. Refuses detached HEAD.              |
| Stash around a risky operation                     | `with nclutils.git.stashed(): ...`                                                                      | Yields `bool` (was a stash created). Pops on exit.                                    |
| Create a worktree                                  | `nclutils.git.add_worktree(path, branch, new_branch=True)`                                              | Returns a populated `Worktree` record.                                                |
| Create a worktree without auto-tracking            | `nclutils.git.add_worktree(path, branch, new_branch=True, track=False)`                                 | Pass `track=False` to suppress upstream tracking for short-lived branches.            |
| Find / delete merged or gone branches              | `nclutils.git.prunable_branches()` then `delete_branches([pb.name for pb in ...])`                      | Returns `list[PrunableBranch]`; extract `.name` before passing to `delete_branches`.  |
| Detect empty (never-written) branches              | `nclutils.git.is_empty_branch(branch)` or `prunable_branches(include_empty=True)`                       | "Empty" means zero commits ahead of the default branch.                               |
| Count stashes across all branches                  | `nclutils.git.stash_counts()`                                                                           | Returns `dict[branch, count]`. `RepoState.stash_count` covers current branch only.    |
| Any other git subcommand                           | `nclutils.git.run_git("log", "--oneline", "-5")`                                                        | Escape hatch. Returns `CompletedCommand`.                                             |
| TCP reachability check                             | `nclutils.net.network_available()`                                                                      | Defaults to 8.8.4.4:53, 5-second timeout.                                             |
| Replace text in a file in place                    | `nclutils.text.replace_in_file(path, {"old": "new"})`                                                   | `use_regex=True` for regex keys. Returns `True` if changed.                           |
| Ensure lines exist in a file                       | `nclutils.text.ensure_lines_in_file(path, [".env", "*.pyc"])`                                           | Idempotent. Returns `True` if changed.                                                |
| Convert case                                       | `nclutils.strings.snake_case(text)` (or `camel_case` / `kebab_case` / `pascal_case` / `separator_case`) | Tokenizes, strips accents via `deburr`, folds contractions.                           |
| Strip diacritics                                   | `nclutils.strings.deburr(text)`                                                                         | Latin-1 only; does not transliterate non-Latin scripts.                               |
| Strip ANSI escape sequences                        | `nclutils.strings.strip_ansi(text)`                                                                     | Useful after capturing terminal output.                                               |
| Tokenize into words                                | `nclutils.strings.list_words(text)`                                                                     | Preserves contractions. Custom regex pattern accepted.                                |
| Pad / left-pad / right-pad a string                | `nclutils.strings.pad` / `pad_start` / `pad_end`                                                        | Multi-char `chars` repeats and truncates to fit.                                      |
| Format a byte count for humans                     | `nclutils.strings.human_size(size_bytes, *, decimals=1)`                                                | SI base 1000, units `B`/`kB`/`MB`/`GB`/`TB`/`PB`/`EB`/`ZB`/`YB`. Negatives keep sign. |
| Current UTC time as ISO-8601 string                | `nclutils.utils.iso_timestamp()`                                                                        | `"2026-05-04T18:32:01Z"`. Pass `microseconds=True` for sub-second precision.          |
| Format an existing datetime as ISO-8601            | `nclutils.utils.format_iso_timestamp(dt)`                                                               | Converts to UTC; naive datetimes are treated as local.                                |
| Filename-safe random ID                            | `nclutils.utils.new_uid(bits=64)`                                                                       | Base-36, case-insensitive, no hyphens. Uses `random.SystemRandom`.                    |
| Sortable timestamp-prefixed ID                     | `nclutils.utils.new_timestamp_uid()`                                                                    | `"20260504T183201-kgk5mzn"`. Lexicographically sortable.                              |
| Python version gate                                | `nclutils.utils.check_python_version(3, 12)`                                                            | Returns `bool`. Use to gate features that need newer stdlib.                          |

## Top gotchas

### 1. `pp` and stdlib `logging` are separate output paths. Do not bridge them.

The project has two intentional, independent output channels:

- **`nclutils.pp`** writes user-facing output (Rich console, colored level markers, spinners, optional logfile). The host CLI configures it via `pp.configure(...)`.
- **stdlib `logging`** is used internally by `nclutils.fs`, `nclutils.text`, `nclutils.sh`, and `nclutils.git` for diagnostic messages, under loggers `nclutils.fs`, `nclutils.text`, `nclutils.sh`. These are silent until the host attaches a handler.

Do NOT pipe `pp` into a stdlib `logging.Handler`, and do NOT call `pp.info(...)` from a library module that should be silent by default. Keep them separate.

If you want to see internal diagnostics during development:

```python
import logging
logging.getLogger("nclutils").setLevel(logging.DEBUG)  # or "nclutils.sh", "nclutils.fs", etc.
logging.basicConfig()
```

### 2. `sh.run_command` returns an object, raises on failure, and takes one argv list

```python
from nclutils.sh import run_command, ShellCommandError

result = run_command(["git", "status", "--short"])
result.stdout         # str — captured stdout (trailing newlines stripped)
result.stderr         # str — captured stderr, separate from stdout (trailing newlines stripped)
result.returncode     # int
result.ok             # bool — True if returncode == 0
result.duration       # float — wall-clock seconds
result.argv           # tuple[str, ...] — what actually ran
result.command_line   # str — argv rendered via shlex.join, shell-safe
result.stdout_lines   # list[str] — stdout.splitlines(), for iteration
result.stderr_lines   # list[str]
```

Common wrong patterns:

```python
# WRONG — no positional cmd/args form. Pass full argv as one list:
run_command("git", ["status"])

# WRONG — the return value is CompletedCommand, not a string:
output = run_command(["git", "status"])
if "modified" in output: ...           # TypeError-adjacent; use .stdout

# WRONG — default raises on non-zero exit. grep returning 1 is a typed error:
result = run_command(["grep", "needle", "file"])  # raises if no match
# Right: opt into 1 as data
result = run_command(["grep", "needle", "file"], okay_codes=(0, 1))
# Or, less surgical: skip the failure check entirely
result = run_command(["grep", "needle", "file"], check=False)

# WRONG — env= REPLACES the environment; child sees nothing else:
run_command(["printenv", "PATH"], env={"MY_VAR": "x"})
# Right: merge with parent env
import os
run_command(["printenv", "PATH"], env={**os.environ, "MY_VAR": "x"})
```

Error hierarchy (all inherit from `ShellCommandError`):

| Exception                   | When                                                       | Carries                                      |
| --------------------------- | ---------------------------------------------------------- | -------------------------------------------- |
| `ShellCommandNotFoundError` | `argv[0]` is not on PATH                                   | message only                                 |
| `ShellCommandFailedError`   | non-zero exit (outside `okay_codes`), or `cwd` unreachable | `result: CompletedCommand \| None`           |
| `ShellCommandTimeoutError`  | `timeout=` exceeded                                        | `result: CompletedCommand`, `timeout: float` |

Catch `ShellCommandError` to handle all three uniformly.

For interactive commands (editors, SSH, anything that drives the terminal), use `run_interactive(argv)` instead — it inherits the parent's streams and returns the exit code as an int.

### 3. Don't reinvent what `nclutils` already does

When the project depends on `nclutils`, prefer the existing helper over a hand-rolled equivalent. The package was written precisely so callers don't have to:

| Don't write                                  | Use instead                                                                         |
| -------------------------------------------- | ----------------------------------------------------------------------------------- |
| A `snake_case` / `camel_case` / `kebab_case` | `nclutils.strings.snake_case` / `camel_case` / `kebab_case`                         |
| `shutil.copy` with progress / backup logic   | `nclutils.fs.copy_file(src, dst, with_progress=True)`                               |
| `shutil.copytree` with progress / backup     | `nclutils.fs.copy_directory(...)`                                                   |
| `shutil.which`                               | `nclutils.sh.which`                                                                 |
| `subprocess.run(...)` wrapper                | `nclutils.sh.run_command` — already logs at DEBUG, raises typed errors              |
| `subprocess.run(["git", ...])` chains        | `nclutils.git` composites (`get_repo_state`, `sync_branch`, etc.) or `run_git(...)` |
| `datetime.now(timezone.utc).isoformat()`     | `nclutils.utils.iso_timestamp()` (writes `Z` instead of `+00:00`)                   |
| `uuid.uuid4().hex` for filename IDs          | `nclutils.utils.new_uid` (base-36, shorter) or `new_timestamp_uid` (sortable)       |
| `input("Pick one: ")` over a list            | `nclutils.ask.choose_one_from_list`                                                 |
| `socket.create_connection(...)` reachability | `nclutils.net.network_available(host, port, timeout)`                               |
| A handwritten `replace_in_file`              | `nclutils.text.replace_in_file(path, replacements)`                                 |
| A handwritten "ensure lines in file"         | `nclutils.text.ensure_lines_in_file(path, lines)`                                   |

This is not about style; the helpers do extra work (timestamped backups, separate stdout/stderr capture, typed exceptions, debug logging, dotfile filtering) that hand-rolled code tends to skip.

### 4. `pp.step()` does not nest

Rich's `Live` rendering cannot stack. `pp.step()` raises `RuntimeError` if you try.

```python
# WRONG
with pp.step("outer") as outer:
    with pp.step("inner") as inner:   # RuntimeError
        ...

# Right — use Step.sub() for hierarchical progress under a single Live
with pp.step("running migrations") as s:
    for m in pending:
        run(m)
        s.sub(f"applied {m.name}")
```

### 5. `pp` verbosity and quiet are independent

`pp.Verbosity` is an `IntEnum` (`INFO`, `DEBUG`, `TRACE`) that only gates `debug` and `trace`. `quiet=True` separately suppresses `info` / `success` / `header` / `kv` on the console. They compose: `pp.configure(verbosity=pp.Verbosity.DEBUG, quiet=True)` shows debug output without routine info chatter.

```python
import argparse
from nclutils import pp

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="count", default=0)
parser.add_argument("-q", "--quiet", action="store_true")
args = parser.parse_args()

pp.configure(verbosity=args.verbose, quiet=args.quiet)
```

Warnings, errors, dryrun notices, and `step()` always render. `pp.critical` is severity-only and does NOT raise.

## Deeper module references

When you need API details beyond the table above, read the relevant file in `references/`. Don't load them eagerly; read on demand.

- `references/pp.md` — full pretty-printer surface (per-call tags, exceptions, kv, file logger, themes, ASCII fallback, isolated emitters)
- `references/sh.md` — `run_command` options, error hierarchy, migration from the old `sh`-package API
- `references/git.md`: composites (`get_repo_state`, `sync_branch`, `stashed`, `add_worktree`), primitives, dataclass field tables (`RepoState`, `SyncResult`, `Worktree`, `Remote`, `PrunableBranch`, `DeleteOutcome`)
- `references/fs.md` — copy/backup semantics, symlink handling, search edge cases
- `references/strings.md` — every case-conversion / tokenizer / padding signature
- `references/misc.md` — `ask`, `net`, `text`, `utils` reference

## Python compatibility

`nclutils` supports Python 3.10+. Use `nclutils.utils.check_python_version(major, minor)` to gate any new code that needs newer language or stdlib features, rather than raising the package's Python floor.
