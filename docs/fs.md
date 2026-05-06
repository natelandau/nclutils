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

> [!NOTE]
> `copy_directory` requires Python 3.12+ because it uses `Path.walk()`. Calling it on an older interpreter raises `ValueError`.

> [!WARNING]
> Refusing to copy is silent. Same source and destination, or copying a directory into itself or its parent, returns the source path and logs a warning rather than raising. Check the return value or watch the `nclutils.fs` logger if this matters.

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

By default `backup_path` returns `None` when the source doesn't exist. Pass `raise_on_missing=True` to make a missing source an error instead.

## Cleaning a directory

`clean_directory` empties a directory in place: files are unlinked and subdirectories are removed recursively, but the directory itself stays.

```python
from pathlib import Path
from nclutils.fs import clean_directory

clean_directory(Path("./tmp"))
```

If the path isn't an existing directory, the call is a no-op and a warning is logged.

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

## Building a directory tree

`directory_tree` returns a [`rich.tree.Tree`](https://rich.readthedocs.io/en/stable/tree.html) that renders nicely in a Rich `Console`.

```python
from pathlib import Path
from rich.console import Console
from nclutils.fs import directory_tree

Console().print(directory_tree(Path("./src"), show_hidden=False))
```

Pair it with `pretty_print.console()` to render through the same console that the rest of `nclutils` uses:

```python
from nclutils import console
console().print(directory_tree(Path("./src")))
```

## Looking up a user's home directory

`find_user_home_dir` resolves a home directory in a way that's friendly to scripts running under `sudo`.

```python
from nclutils.fs import find_user_home_dir

# When run normally: same as Path.home()
# When run under sudo: returns the invoking user's home, not /root
find_user_home_dir()

# Look up a specific user (Linux: getent passwd; macOS: dscl)
find_user_home_dir("alice")
```

Returns `None` if the user isn't found or the platform isn't supported (only Linux and macOS).

## Diagnostic logging

`nclutils.fs` emits `DEBUG`/`WARNING`/`ERROR` messages through the stdlib `logging` module under the `nclutils.fs` logger. To see them:

```python
import logging
logging.getLogger("nclutils.fs").setLevel(logging.DEBUG)
logging.basicConfig()
```

This is independent of `nclutils.pretty_print`. It covers internal operations like "starting a copy" or "skipping a backup because the source is missing."

## API reference

- `backup_path(src, backup_suffix="", *, raise_on_missing=False, with_progress=False, transient=True)`. Snapshot a file or directory with a timestamped suffix.
- `clean_directory(directory)`. Recursively empty a directory in place.
- `copy_file(src, dst, *, with_progress=False, transient=True, keep_backup=True)`. Copy a file with optional progress and destination backup.
- `copy_directory(src, dst, *, with_progress=False, transient=True, keep_backup=True)`. Recursively copy a directory. Requires Python 3.12+.
- `directory_tree(directory, *, show_hidden=False)`. Build a `rich.tree.Tree` view of a directory.
- `find_files(path, globs=None, *, ignore_dotfiles=False)`. List files in a directory matching globs.
- `find_subdirectories(directory, depth=1, filter_regex="", *, ignore_dotfiles=False, leaf_dirs_only=False)`. Search subdirectories with depth and regex filtering.
- `find_user_home_dir(username=None)`. Resolve a user's home directory, honoring `SUDO_USER` when running under sudo.
