# `nclutils.fs` reference

Filesystem helpers built on `pathlib`, `shutil`, and Rich.

## Copying

`copy_file(src, dst, *, with_progress=False, transient=True, keep_backup=True, console=None, strict=False)` — drop-in for `shutil.copy` with:

- Optional Rich progress bar (`with_progress=True`; `transient=True` clears the bar on completion).
- Timestamped backup of an existing destination by default (`keep_backup=True`). Backup format: `dst.<timestamp>-<rand>.bak` (same scheme as `new_timestamp_uid`).
- `console=` to share a Rich `Console` with `pp.console()`.
- `~` is expanded in both `src` and `dst`.
- Raises `IsADirectoryError` if `src` is a directory; `OSError` for any other non-regular file. With `strict=True`, same-source-and-destination raises `shutil.SameFileError` (otherwise warns and returns src). With `strict=False` (default), parent/child copy attempts return src with a warning; `strict=True` raises `ValueError`.

`copy_directory(src, dst, ...)` — same surface for directories. Requires Python 3.12+ (uses `Path.walk`). Progress bar shows total bytes across all files plus a recycled per-file subtask. When `keep_backup=True` and destination exists, you see two sequential phases (Backup, then Copy), each with its own bar. Preserves source directory's permission bits via `shutil.copystat`; mtimes are NOT preserved because writes during copy bump the mirrored directory's mtime.

Both helpers follow symlinks (matching `shutil.copytree(symlinks=False)` default): a symlink to a directory inside the source tree is materialized as a real directory with target contents copied recursively.

## Standalone backup

`backup_path(src, backup_suffix="", *, with_progress=False, transient=True, console=None, strict=False)` — snapshot a path without copying it elsewhere. Default suffix is `.<timestamp>-<rand>.bak`; override with `backup_suffix=".pre-migration.bak"`.

Returns `None` when source doesn't exist (default). `strict=True` raises `FileNotFoundError`. File backups preserve permission bits but not timestamps. Directory backups walk via `Path.walk(follow_symlinks=True)`, mirror directory mode and timestamps via `shutil.copystat`, and follow symlinks.

## Cleaning

`clean_directory(directory, *, strict=False)` — empties a directory in place. Files unlinked, subdirectories removed recursively, the directory itself stays. Symlinks (including dangling links and links to directories) are removed via `unlink()`; targets are not modified. If the path isn't an existing directory, no-op + warning. `strict=True` raises `NotADirectoryError`.

## Searching

### `find_files(path, globs=None, *, ignore_dotfiles=False) -> list[Path]`

Files in a directory, optionally matching a list of globs. Without `globs`, returns every file in the top level (no recursion). Globs pass through to `Path.glob`, so `**/*.py` works for recursive matching.

- Sorted, deduplicated (if multiple globs match the same file, it appears once).
- `ignore_dotfiles=True` also excludes files reached through hidden directories (e.g. `**/.cache/foo.py`). The user-supplied ROOT is never filtered, so passing `Path("~/.config")` as the search root works.

### `find_subdirectories(directory, depth=1, filter_regex="", *, ignore_dotfiles=False, leaf_dirs_only=False) -> list[Path]`

Search subdirectories with depth and regex filtering.

- `depth` must be `>= 1`; passing `0` or negative raises `ValueError`.
- `filter_regex` applied with `re.search` — anchor with `^`/`$` for whole-name matching.
- `leaf_dirs_only=True` excludes directories that still contain matching subdirectories within the depth limit.
- `ignore_dotfiles=True` filters descendants whose own name starts with `.`. The user-supplied root is never filtered.

## Building a tree

`directory_tree(directory, *, show_hidden=False) -> rich.tree.Tree`

```python
from nclutils import pp
from nclutils.fs import directory_tree

pp.console().print(directory_tree(Path("./src")))
```

## Sudo-aware home lookup

`find_user_home_dir(username=None, *, strict=False) -> Path | None`

Resolves a home directory. Honors `SUDO_USER` when running under `sudo`, so it returns the invoking user's home, not `/root`. POSIX lookups go through `pwd.getpwnam(username).pw_dir`; no subprocess.

Returns `None` if user not found or `pwd` is unavailable (Windows). `strict=True` raises `KeyError` when user is unknown (but the platform-unavailability path always returns `None`, since that's not a runtime error). A warning is logged on platforms without `pwd`.

## Diagnostic logging

`nclutils.fs` emits `DEBUG`/`WARNING`/`ERROR` through stdlib `logging` under the `nclutils.fs` logger. Silent until the host attaches a handler.

```python
import logging
logging.getLogger("nclutils.fs").setLevel(logging.DEBUG)
logging.basicConfig()
```

Covers internal operations like "starting a copy" or "skipping a backup because source is missing." Independent of `nclutils.pp`.
