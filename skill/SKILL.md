---
name: nclutils
description: Use when writing or editing Python code in a project that depends on the `nclutils` package. Trigger on any `import nclutils` or `from nclutils.` line, and before hand-writing filesystem copies or backups, subprocess calls, console output, interactive prompts, case conversion, ISO timestamps, or git automation in such a project.
---

# nclutils

Python 3.11+ utility package: filesystem, shell, console output, prompts, strings, git, timestamps. Applies only when `nclutils` is a dependency of the project.

## Imports

Only `pp` is re-exported from the package root. Import everything else from its module.

```python
from nclutils import pp                    # then pp.info(...), pp.step(...)
from nclutils.pp import info, step         # also valid
from nclutils.fs import copy_file          # every other symbol: from its module
from nclutils import fs                    # module import also works: fs.copy_file(...)
```

| Module | Public symbols |
| --- | --- |
| `nclutils.pp` | `info`, `success`, `warning`, `error`, `critical`, `dryrun`, `debug`, `trace`, `header`, `kv`, `step`, `configure`, `console`, `err_console`, `get_default`, `set_default`, `Emitter`, `Theme`, `THEME`, `Level`, `LogLevel`, `Verbosity` |
| `nclutils.ask` | `choose_one_from_list`, `choose_multiple_from_list` |
| `nclutils.fs` | `copy_file`, `copy_directory`, `backup_path`, `clean_directory`, `find_files`, `find_subdirectories`, `directory_tree`, `find_user_home_dir` |
| `nclutils.git` | Workflows: `get_repo_state`, `sync_branch`, `fetch`, `stashed`, `prunable_branches`, `delete_branches`. Branches: `current_branch`, `default_branch`, `branch_exists`, `tracking_branch`, `all_local_branches`, `merged_branches`, `gone_branches`, `is_empty_branch`, `ahead_behind`. Repo: `is_git_installed`, `is_git_repo`, `repo_root`, `is_dirty`, `is_rebase_in_progress`, `primary_remote`, `stash_counts`, `run_git`. Worktrees: `add_worktree`, `create_worktree`, `list_worktrees`, `remove_worktree`. Types: `RepoState`, `SyncResult`, `Worktree`, `Remote`, `PrunableBranch`, `PruneReason`, `DeleteOutcome`, `NotARepoError` |
| `nclutils.net` | `network_available` |
| `nclutils.sh` | `run_command`, `run_interactive`, `which`, `CompletedCommand`, `ShellCommandError`, `ShellCommandNotFoundError`, `ShellCommandFailedError`, `ShellCommandTimeoutError` |
| `nclutils.strings` | `snake_case`, `camel_case`, `kebab_case`, `pascal_case`, `separator_case`, `deburr`, `list_words`, `split_camel_case`, `strip_ansi`, `pad`, `pad_start`, `pad_end`, `random_string`, `int_to_emoji`, `human_size` |
| `nclutils.text` | `replace_in_file`, `ensure_lines_in_file` |
| `nclutils.utils` | `iso_timestamp`, `format_iso_timestamp`, `new_uid`, `new_timestamp_uid`, `unique_id`, `check_python_version` |

Wrong imports:

| Wrong | Right |
| --- | --- |
| `from nclutils import copy_file` | `from nclutils.fs import copy_file` (same for every non-`pp` symbol) |
| `nclutils.questions` | `nclutils.ask` (old name is deprecated, raises `DeprecationWarning`) |
| `nclutils.network` | `nclutils.net` (deprecated, raises `DeprecationWarning`) |
| `nclutils.text_processing` | `nclutils.text` (deprecated, raises `DeprecationWarning`) |

## Task lookup

Before writing code for one of these tasks, use the listed helper.

| Task | Use | Notes |
| --- | --- | --- |
| User-facing console output | `pp.info` / `success` / `warning` / `error` / `critical` / `dryrun` | Rich-based, verbosity gates, optional logfile. `critical` does not raise. |
| Long-running step with a spinner | `with pp.step("...") as s: s.sub("...")` | Does not nest; use `s.sub()` for sub-items. |
| Section header | `pp.header("title")` | Rule line with optional title. |
| Aligned key/value summary | `pp.kv({"Branch": "main"})` | Hidden on console by `quiet=True`; still logged. |
| Pick one or several items interactively | `ask.choose_one_from_list` / `choose_multiple_from_list` | Returns `None` on Ctrl-C. `choose_one_from_list` also returns `None` for a falsy choice value (`0`, `False`, `""`). |
| Copy a file | `fs.copy_file(src, dst)` | Backs up an existing `dst` by default. Keeps mode, not modification time. Returns `dst`. |
| Copy a directory | `fs.copy_directory(src, dst)` | Not `shutil.copytree`: an existing `dst` is backed up and replaced, not merged into. Follows symlinks. |
| Back up a path before changing it | `fs.backup_path(path)` | Writes `path.<timestamp>-<uid>.bak`. Returns `Path \| None`. Does not expand `~`. |
| Empty a directory, keep the directory | `fs.clean_directory(path)` | Deletes all contents. |
| Find files by glob | `fs.find_files(root, globs=["*.py"])` | Sorted, deduplicated. `ignore_dotfiles=True` skips dotfiles. Does not expand `~`. |
| Walk subdirectories by depth and regex | `fs.find_subdirectories(root, depth=2, filter_regex=...)` | `depth` must be `>= 1`. |
| Show a directory tree | `fs.directory_tree(path)` | Returns `rich.tree.Tree`; print with `pp.console().print(...)`. |
| Home directory of the real user | `fs.find_user_home_dir(username=None)` | Uses `SUDO_USER` under sudo. |
| Run an external command | `sh.run_command(["git", "status"])` | Returns `CompletedCommand`; raises typed errors. See gotcha 2. |
| Show output live and capture it | `sh.run_command([...], stream=True)` | Writes to the terminal and captures. |
| Run an editor, SSH, or interactive shell | `sh.run_interactive([...])` | Inherits stdin/stdout/stderr. Returns the exit code. |
| Find a binary on PATH | `sh.which("rg")` | Returns `Path \| None`. |
| Read repo state in one call | `git.get_repo_state()` | Returns `RepoState`: branch, ahead/behind, dirty counts, stash count, rebase flag. |
| Pull or rebase the current branch | `git.sync_branch()` | Stashes, fast-forwards or rebases, returns `SyncResult`. Refuses detached HEAD. |
| Stash around a risky operation | `with git.stashed() as did_stash: ...` | Yields `bool`; pops on exit. |
| Create a worktree | `git.add_worktree(path, branch, new_branch=True)` | Returns `Worktree`. Pass an absolute, expanded `path`. `track=False` skips upstream tracking. |
| Find and delete merged or gone branches | `git.prunable_branches()`, then `git.delete_branches([b.name for b in candidates])` | `prunable_branches` returns `list[PrunableBranch]`; `delete_branches` takes names. |
| Detect branches with no commits | `git.is_empty_branch(branch)` or `prunable_branches(include_empty=True)` | Empty: zero commits ahead of the default branch. |
| Count stashes on every branch | `git.stash_counts()` | `dict[branch, count]`. `RepoState.stash_count` covers the current branch only. |
| Any other git command | `git.run_git("log", "--oneline", "-5")` | Returns `CompletedCommand`. |
| Check TCP reachability | `net.network_available()` | Default `8.8.4.4:53`, 5-second timeout. |
| Replace text in a file | `text.replace_in_file(path, {"old": "new"})` | `use_regex=True` for regex keys. Returns `True` if the file changed. |
| Add lines to a file if missing | `text.ensure_lines_in_file(path, ["build", "dist"])` | Each line is also a regex matched as `^line$`, and is written as given. If a line has regex metacharacters (`*.pyc`), check for and append it yourself. Returns `True` if changed. |
| Convert case | `strings.snake_case(text)` (also `camel_case`, `kebab_case`, `pascal_case`, `separator_case`) | Removes accents and apostrophes, splits on underscores. Does not split camelCase: `snake_case("fooBar")` -> `"foobar"`. |
| Remove accents | `strings.deburr(text)` | Latin-1 letters only. |
| Remove ANSI escape codes | `strings.strip_ansi(text)` |  |
| Split text into words | `strings.list_words(text)` | Optional regex `pattern` as the second argument. |
| Pad a string | `strings.pad` / `pad_start` / `pad_end` | Multi-character `chars` repeats and truncates to fit. |
| Byte count for people | `strings.human_size(size_bytes, decimals=1)` | Base 1000: `B`, `kB`, `MB`, ... `YB`. Keeps the sign of negatives. |
| Current UTC time as ISO 8601 | `utils.iso_timestamp()` | `"2026-05-04T18:32:01Z"`. `microseconds=True` for sub-second precision. |
| Format a datetime as ISO 8601 | `utils.format_iso_timestamp(dt)` | Converts to UTC; a naive datetime counts as local time. |
| Random ID safe for file names | `utils.new_uid(bits=64)` | Lowercase letters and digits, 13 characters at 64 bits. |
| Sortable ID with a timestamp prefix | `utils.new_timestamp_uid()` | `"20260504T183201-kgk5mzn"`. Sorts by time to the second. |
| Gate code on the Python version | `utils.check_python_version(3, 13)` | Returns `bool`. |

## Gotchas

### 1. `pp` and stdlib `logging` are separate

- `pp`: user-facing output (Rich console, level markers, spinners, optional logfile). The host CLI sets it up with `pp.configure(...)`.
- stdlib `logging`: diagnostics from `nclutils.fs`, `nclutils.text`, and `nclutils.sh` (git commands log through `nclutils.sh`). Silent until the host attaches a handler.

Do not send `pp` output into a `logging.Handler`, and do not call `pp` from library code that must stay silent. To see diagnostics:

```python
import logging

logging.basicConfig()
logging.getLogger("nclutils").setLevel(logging.DEBUG)  # or "nclutils.sh", "nclutils.fs"
```

### 2. `run_command` takes one argv list, returns an object, and raises on failure

```python
from nclutils.sh import run_command

result = run_command(["git", "status", "--short"])
result.stdout        # str, trailing newlines stripped
result.stderr        # str, captured separately
result.returncode    # int
result.ok            # bool, returncode == 0
result.duration      # float seconds
result.argv          # tuple[str, ...], includes "sudo" when sudo=True
result.command_line  # str, shlex.join(argv)
result.stdout_lines  # list[str]
result.stderr_lines  # list[str]
```

| Wrong | Right |
| --- | --- |
| `run_command("git", ["status"])` | `run_command(["git", "status"])` |
| `if "modified" in run_command([...]):` | `if "modified" in run_command([...]).stdout:` |
| `run_command(["grep", "x", "f"])` where 1 means "no match" | `run_command(["grep", "x", "f"], okay_codes=(0, 1))`, or `check=False` |
| `run_command([...], env={"MY_VAR": "x"})` (replaces the whole environment) | `run_command([...], env={**os.environ, "MY_VAR": "x"})` |

Errors, all subclasses of `ShellCommandError`:

| Exception | Raised when | Attributes |
| --- | --- | --- |
| `ShellCommandNotFoundError` | `argv[0]` not on PATH | `argv` |
| `ShellCommandFailedError` | exit code not in `okay_codes` (default `(0,)`), or `cwd` unreachable | `result: CompletedCommand \| None` |
| `ShellCommandTimeoutError` | `timeout=` exceeded, even with `check=False` | `result: CompletedCommand`, `timeout: float` |

`except ShellCommandError` catches all three. Output that is not valid UTF-8 raises `UnicodeDecodeError`, which is not a `ShellCommandError`.

### 3. Use the helper instead of hand-written code

The helpers add backups, separate stdout/stderr capture, typed errors, and debug logging.

| Instead of | Use |
| --- | --- |
| A hand-written `snake_case` or `camel_case` | `strings.snake_case`, `strings.camel_case` |
| `shutil.copy` plus progress or backup code | `fs.copy_file(src, dst, with_progress=True)` |
| `shutil.copytree` plus progress or backup | `fs.copy_directory(src, dst)` |
| `shutil.which` | `sh.which` |
| A `subprocess.run` wrapper | `sh.run_command` |
| Chains of `subprocess.run(["git", ...])` | `git.get_repo_state`, `git.sync_branch`, or `git.run_git` |
| `datetime.now(timezone.utc).isoformat()` | `utils.iso_timestamp()` (writes `Z`, not `+00:00`) |
| `uuid.uuid4().hex` for file names | `utils.new_uid` (shorter) or `utils.new_timestamp_uid` (sortable) |
| `input()` over a list of options | `ask.choose_one_from_list` |
| `socket.create_connection` reachability test | `net.network_available(address, port, timeout)` |

### 4. `pp.step()` does not nest

A nested `pp.step()` on the same emitter raises `RuntimeError`. Use `Step.sub()`:

```python
with pp.step("running migrations") as s:
    for migration in pending:
        apply(migration)
        s.sub(f"applied {migration.name}")
```

### 5. Verbosity and quiet are independent

- `pp.Verbosity` (`INFO`, `DEBUG`, `TRACE`) gates only `debug` and `trace`.
- `quiet=True` hides `info`, `success`, `header`, and `kv` on the console.
- `warning`, `error`, `critical`, `dryrun`, and `step()` always show.

```python
pp.configure(verbosity=args.verbose, quiet=args.quiet)  # args.verbose: count of -v flags
```

### 6. Long lines in captured output

`soft_wrap` defaults to `None`: lines fold on a terminal and stay whole when output is captured (`VALUE=$(myapp path)`). Force it with `pp.configure(soft_wrap=True)` or per call, `pp.info(msg, soft_wrap=False)`. Do not build a `Console(soft_wrap=True, markup=False)` for this: `pp` already escapes markup, and a console without `theme=pp.THEME` loses the styles. A soft-wrapping `pp.step()` shows no spinner and draws once when the block exits.

## References

Read a file only when the task needs more than the tables above.

- `references/pp.md`: every `pp` function, tags, exceptions in steps, `kv`, logfile, themes, ASCII fallback, soft wrap, isolated `Emitter`s.
- `references/sh.md`: `run_command` and `run_interactive` options, errors, sudo, streaming.
- `references/git.md`: every `nclutils.git` function, behavior outside a repository, dataclass fields (`RepoState`, `SyncResult`, `Worktree`, `Remote`, `PrunableBranch`, `DeleteOutcome`).
- `references/fs.md`: copy and backup behavior, symlinks, search options.
- `references/strings.md`: every case, tokenizer, and padding signature.
- `references/misc.md`: `ask`, `net`, `text`, `utils`.
