# Filesystem

Common filesystem operations on top of `pathlib`, `shutil`, and Rich. Imported from `nclutils.fs`.

```python
from pathlib import Path
from nclutils.fs import copy_file, find_files

for src in find_files(Path("src"), globs=["*.py"]):
    copy_file(src, Path("backup") / src.name, with_progress=True)
```

## Copying files and directories

`copy_file` and `copy_directory` are drop-in replacements for `shutil.copy` / `shutil.copytree` with two extras: an optional Rich progress bar and automatic backup of an existing destination.

```python
from pathlib import Path
from nclutils.fs import copy_file, copy_directory

# File copy with a transient progress bar
copy_file(Path("dist/app.tar.gz"), Path("releases/app.tar.gz"), with_progress=True)

# Directory copy
copy_directory(Path("./build"), Path("./public"))
```

When the destination already exists, the original is moved aside with a timestamped suffix (e.g. `app.tar.gz.20260504T143201-kgk5mzn.bak`). Pass `keep_backup=False` to overwrite without backing up.

```python
copy_file(src, dst, keep_backup=False)
```

`with_progress=True` shows a Rich progress bar; `transient=True` (the default) clears the bar after the copy completes.

For `copy_directory(..., with_progress=True)`, the bar shows the total bytes across all files plus a recycled per-file subtask. When `keep_backup=True` and the destination already exists, you'll see two sequential phases: a Backup phase (snapshotting the existing destination) that dismisses on completion, then a Copy phase. Each phase has its own progress bar.

Pass `console=` to route the progress bar through your own Rich `Console` instead of Rich's global default. This is useful when you want the bar to share a console with `pp.console()`:

```python
from nclutils import pp
from nclutils.fs import copy_file

copy_file(src, dst, with_progress=True, console=pp.console())
```

> [!NOTE]
> `copy_directory` and the directory variant of `backup_path` both follow symlinks: a symlink to a directory inside the source tree is materialized as a real directory in the destination, with the symlink target's contents copied recursively. This matches `shutil.copytree(symlinks=False)` (the default).

> [!NOTE]
> By default, same-source-and-destination and parent/child copy attempts return the source path and log a warning. Pass `strict=True` to raise `shutil.SameFileError` or `ValueError` instead.

> [!NOTE]
> `copy_file` raises `IsADirectoryError` when the source is a directory and `OSError` for any other non-regular file. `~` is expanded in both `src` and `dst` before validation, so `Path("~/foo")` resolves correctly. `copy_directory` preserves the source directory's permission bits (mode) through `shutil.copystat`; modification times are not preserved because file writes during copy bump the mirrored directory's mtime.

## Standalone backups

Use `backup_path` directly when you want to snapshot a path without copying it somewhere else. The default suffix is `.<timestamp>-<rand>.bak`; pass `backup_suffix=` to override.

```python
from pathlib import Path
from nclutils.fs import backup_path

# Snapshot before mutating
original = Path("config.toml")
backup = backup_path(original)
# config.toml -> config.toml.20260504T143201-kgk5mzn.bak

# Custom suffix
backup_path(original, backup_suffix=".pre-migration.bak")
```

By default `backup_path` returns `None` when the source doesn't exist. Pass `strict=True` to raise `FileNotFoundError` instead.

> [!NOTE]
> File backups preserve the source's permission bits (mode); file timestamps are not preserved. Directory backups walk the tree with `os.walk(followlinks=True)`, mirror directory mode and timestamps via `shutil.copystat`, and follow symlinks (including symlinked subdirectories) so the backup contains resolved contents. This matches `shutil.copytree(src, target)` defaults.

## Cleaning a directory

`clean_directory` empties a directory in place: files are unlinked and subdirectories are removed recursively, but the directory itself stays.

```python
from pathlib import Path
from nclutils.fs import clean_directory

clean_directory(Path("./tmp"))
```

If the path isn't an existing directory, the call is a no-op and a warning is logged. Pass `strict=True` to raise `NotADirectoryError` instead. Symlinks inside the directory (including dangling links and links pointing at directories) are removed via `unlink()`; their targets are not modified.

## Searching

### `find_files`

Return files in a directory, optionally matching a list of globs. Without `globs`, returns every file in the top level (no recursion).

```python
from pathlib import Path
from nclutils.fs import find_files

# All files in src/, excluding dotfiles
find_files(Path("src"), ignore_dotfiles=True)

# Only Python and TOML files
find_files(Path("."), globs=["*.py", "*.toml"])
```

Globs are passed through to `Path.glob`, so `**/*.py` works for recursive matching.

> [!NOTE]
> When `ignore_dotfiles=True`, files reached through a hidden directory (such as `**/.cache/foo.py`) are also excluded. The user-supplied root path is never filtered, so passing a hidden directory like `Path("~/.config")` as the search root works as expected. If multiple globs match the same file, it appears only once in the result.

### `find_subdirectories`

Search a directory tree with depth control, regex filtering, and an optional leaf-only mode.

```python
from pathlib import Path
from nclutils.fs import find_subdirectories

# Immediate subdirs only
find_subdirectories(Path("."))

# Up to two levels deep, names starting with 'a', skip hidden, leaves only
find_subdirectories(
    Path("."),
    depth=2,
    filter_regex=r"^a",
    leaf_dirs_only=True,
    ignore_dotfiles=True,
)
```

`leaf_dirs_only=True` filters the result so that directories which still contain matching subdirectories within the depth limit are excluded. The result is sorted by path.

> [!NOTE]
> `depth` must be 1 or greater; passing 0 or a negative value raises `ValueError`. The `filter_regex` is applied with `re.search`, so it matches if the pattern is found anywhere in a directory's name. Anchor with `^` or `$` for whole-name matching. When `ignore_dotfiles=True`, the user-supplied root directory is never filtered out; only descendants whose own name starts with `.` are excluded.

## Building a directory tree

`directory_tree` returns a [`rich.tree.Tree`](https://rich.readthedocs.io/en/stable/tree.html) that renders nicely in a Rich `Console`.

```python
from pathlib import Path
from rich.console import Console
from nclutils.fs import directory_tree

Console().print(directory_tree(Path("./src"), show_hidden=False))
```

Pair it with `pp.console()` to render through the same console that the rest of `nclutils` uses:

```python
from nclutils import pp
pp.console().print(directory_tree(Path("./src")))
```

## Looking up a user's home directory

`find_user_home_dir` resolves a home directory in a way that's friendly to scripts running under `sudo`. POSIX lookups go through the standard library `pwd` module (`pwd.getpwnam(username).pw_dir`), so no subprocess is spawned.

```python
from nclutils.fs import find_user_home_dir

# When run normally: same as Path.home()
# When run under sudo: returns the invoking user's home, not /root
find_user_home_dir()

# Look up a specific user
find_user_home_dir("alice")
```

Returns `None` if the user isn't found, or if the platform does not provide `pwd` (Windows). Pass `strict=True` to raise `KeyError` when the user is unknown. The `pwd` unavailability path always returns `None` regardless of `strict`, since it represents a platform limitation rather than a runtime error. On platforms without `pwd` a warning is logged.

## Diagnostic logging

`nclutils.fs` emits `DEBUG`/`WARNING`/`ERROR` messages through the stdlib `logging` module under the `nclutils.fs` logger. To see them:

```python
import logging
logging.getLogger("nclutils.fs").setLevel(logging.DEBUG)
logging.basicConfig()
```

This is independent of `nclutils.pp`. It covers internal operations like "starting a copy" or "skipping a backup because the source is missing."

## API reference

- `backup_path(src, backup_suffix="", *, with_progress=False, transient=True, console=None, strict=False)`. Snapshot a file or directory with a timestamped suffix, preserving the source's permission bits. Raises `FileNotFoundError` if `strict=True` and source is missing.
- `clean_directory(directory, *, strict=False)`. Recursively empty a directory in place. Raises `NotADirectoryError` if `strict=True` and target is not a directory.
- `copy_file(src, dst, *, with_progress=False, transient=True, keep_backup=True, console=None, strict=False)`. Copy a file with optional progress and destination backup. Raises `IsADirectoryError` if `src` is a directory; raises `shutil.SameFileError` if `strict=True` and src equals dst.
- `copy_directory(src, dst, *, with_progress=False, transient=True, keep_backup=True, console=None, strict=False)`. Recursively copy a directory, preserving directory permission bits. Raises `shutil.SameFileError` or `ValueError` if `strict=True` and src/dst are the same or nested.
- `directory_tree(directory, *, show_hidden=False)`. Build a `rich.tree.Tree` view of a directory.
- `find_files(path, globs=None, *, ignore_dotfiles=False)`. List files in a directory matching globs. Duplicate matches across overlapping globs are deduped.
- `find_subdirectories(directory, depth=1, filter_regex="", *, ignore_dotfiles=False, leaf_dirs_only=False)`. Search subdirectories with depth and regex filtering. `depth` must be >= 1.
- `find_user_home_dir(username=None, *, strict=False)`. Resolve a user's home directory, honoring `SUDO_USER` when running under sudo. Raises `KeyError` if `strict=True` and user is unknown.
