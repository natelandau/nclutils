# Filesystem

Use `nclutils.fs` to copy, back up, clean, and search files and directories, with optional Rich progress bars. Import the functions from `nclutils.fs`.

```python
from pathlib import Path
from nclutils.fs import copy_file, find_files

for src in find_files(Path("src"), globs=["*.py"]):
    copy_file(src, Path("backup") / src.name, with_progress=True)
```

## Copying files and directories

`copy_file` copies one file. `copy_directory` copies a directory and all its contents. Both functions can show a Rich progress bar, and both back up a destination that already exists before they replace it. Each function returns the destination path.

```python
from pathlib import Path
from nclutils.fs import copy_file, copy_directory

# File copy with a progress bar that clears when the copy completes
copy_file(Path("dist/app.tar.gz"), Path("releases/app.tar.gz"), with_progress=True)

# Directory copy
copy_directory(Path("./build"), Path("./public"))
```

Both functions expand `~` in `src` and `dst`. `copy_file` makes the parent directories of `dst` if they do not exist. The copies keep the permission bits (mode) of the source files and directories. They do not keep modification times.

### Existing destinations

If the destination exists, the function first copies it to a backup next to it, with a timestamped suffix, for example `app.tar.gz.20260504T143201-kgk5mzn.bak`. Then it replaces the destination with the copy.

> [!CAUTION]
> Pass `keep_backup=False` only if you can lose the destination. The function then replaces an existing destination with no backup. For `copy_directory`, it deletes the full destination tree first, including files that are not in the source. For `copy_file`, it deletes a directory at `dst`.

```python
from pathlib import Path
from nclutils.fs import copy_file

copy_file(Path("config.toml"), Path("deploy/config.toml"), keep_backup=False)
```

### Progress bars

Pass `with_progress=True` to show a Rich progress bar. With `transient=True` (the default), the bar clears when the copy completes. Pass `transient=False` to keep it on screen.

For `copy_directory`, the bar shows the total bytes of all files and the progress of the current file. If the destination exists and `keep_backup=True`, two bars show one after the other: one for the backup, then one for the copy.

Pass `console=` to show the bar on your own Rich `Console` instead of Rich's default console. For example, use the same console as `nclutils.pp`:

```python
from pathlib import Path
from nclutils import pp
from nclutils.fs import copy_file

copy_file(Path("dist/app.tar.gz"), Path("releases/app.tar.gz"), with_progress=True, console=pp.console())
```

### Symlinks

`copy_directory` follows symlinks. A symlink to a file or directory inside the source tree becomes a real file or directory in the destination, with the contents of the target. This is the same as the default behavior of `shutil.copytree`.

### Errors

`copy_file` raises `FileNotFoundError` if `src` does not exist, `IsADirectoryError` if `src` is a directory, and `OSError` if `src` is another type of non-regular file. `copy_directory` raises `FileNotFoundError` if `src` does not exist or is not a directory.

Some copies are not possible: a file to itself, a directory to itself, or a directory into its own parent or child. By default, the function does not copy, logs a warning, and returns the source path. Pass `strict=True` to raise an exception instead:

| Function         | Condition                                | Exception with `strict=True` |
| ---------------- | ---------------------------------------- | ---------------------------- |
| `copy_file`      | `src` and `dst` are the same file        | `shutil.SameFileError`       |
| `copy_directory` | `src` and `dst` are the same directory   | `shutil.SameFileError`       |
| `copy_directory` | `src` is a parent or child of `dst`      | `ValueError`                 |

Both functions raise `RuntimeError` if a copied file has a different size from its source.

## Standalone backups

Use `backup_path` to make a copy of a file or directory next to the original, without a copy to a different location. The default suffix is `.<timestamp>-<random>.bak`. Pass `backup_suffix=` to use a different suffix. `backup_path` returns the path of the backup.

```python
from pathlib import Path
from nclutils.fs import backup_path

# Back up before you change the file
original = Path("config.toml")
backup = backup_path(original)
# config.toml -> config.toml.20260504T143201-kgk5mzn.bak

# Custom suffix
backup_path(original, backup_suffix=".pre-migration.bak")
```

> [!CAUTION]
> Use a suffix that no other file uses. If a file or directory with the backup name exists, `backup_path` deletes it before it writes the backup.

If the source does not exist, `backup_path` logs a warning and returns `None`. Pass `strict=True` to raise `FileNotFoundError` instead. `backup_path` accepts `with_progress=`, `transient=`, and `console=` with the same meaning as `copy_file`. It does not expand `~`.

A backup keeps the permission bits of the source, but not the modification times. A directory backup follows symlinks, the same as `copy_directory`.

## Cleaning a directory

`clean_directory` deletes all contents of a directory and keeps the directory. It deletes files, symlinks, and subdirectories with all their contents. For a symlink, it deletes the link and does not change the target.

> [!CAUTION]
> Make sure that the path is correct before you call `clean_directory`. It deletes the contents with no backup and no confirmation.

```python
from pathlib import Path
from nclutils.fs import clean_directory

clean_directory(Path("./tmp"))
```

If the path is not an existing directory, `clean_directory` logs a warning and does nothing. Pass `strict=True` to raise `NotADirectoryError` instead.

## Searching

### `find_files`

`find_files` returns a sorted list of the files in a directory that match one or more glob patterns. A file that matches more than one pattern shows only once. Without `globs`, it returns all files in the top level of the directory, with no recursion.

```python
from pathlib import Path
from nclutils.fs import find_files

# All files in src/, without dotfiles
find_files(Path("src"), ignore_dotfiles=True)

# Only Python and TOML files
find_files(Path("."), globs=["*.py", "*.toml"])

# Python files in all subdirectories
find_files(Path("."), globs=["**/*.py"])
```

The patterns go to `Path.glob`, so `**/*.py` matches recursively. With `ignore_dotfiles=True`, `find_files` skips files whose name starts with `.` and files inside a directory whose name starts with `.`. The directory that you pass is never filtered, so `Path("~/.config").expanduser()` works as a search root.

### `find_subdirectories`

`find_subdirectories` returns a sorted list of subdirectories, with a depth limit, a name filter, and an option to return only the deepest matches.

```python
from pathlib import Path
from nclutils.fs import find_subdirectories

# Immediate subdirectories only
find_subdirectories(Path("."))

# Up to two levels deep, names that start with "a", no hidden directories, leaves only
find_subdirectories(
    Path("."),
    depth=2,
    filter_regex=r"^a",
    leaf_dirs_only=True,
    ignore_dotfiles=True,
)
```

The parameters work as follows:

- `depth` is the number of levels to search. `1` (the default) returns only the immediate subdirectories. A value less than `1` raises `ValueError`.
- `filter_regex` is matched against each directory name with `re.search`, so it matches anywhere in the name. Use `^` and `$` to match the full name. The default, `""`, matches all names.
- `ignore_dotfiles=True` skips directories whose name starts with `.` and does not search inside them. The directory that you pass is never filtered.
- `leaf_dirs_only=True` removes each directory that contains another match within the depth limit.

## Building a directory tree

`directory_tree` returns a [`rich.tree.Tree`](https://rich.readthedocs.io/en/stable/tree.html) of a directory and all its contents. Directories come first, and each file shows its size. Hidden files and directories are left out unless you pass `show_hidden=True`.

```python
from pathlib import Path
from rich.console import Console
from nclutils.fs import directory_tree

Console().print(directory_tree(Path("./src")))
```

To render the tree on the same console as the rest of `nclutils`, use `pp.console()`:

```python
from pathlib import Path
from nclutils import pp
from nclutils.fs import directory_tree

pp.console().print(directory_tree(Path("./src"), show_hidden=True))
```

## Looking up a user's home directory

`find_user_home_dir` returns a home directory, and gives the correct result for scripts that run under `sudo`.

```python
from nclutils.fs import find_user_home_dir

# Without sudo: the same as Path.home()
# Under sudo: the home of the user who ran sudo, not /root
find_user_home_dir()

# A specific user
find_user_home_dir("alice")
```

Without `username`, the function uses the `SUDO_USER` environment variable. If `SUDO_USER` is not set, it returns `Path.home()`. A user name is looked up with the standard library `pwd` module.

If the user is not found, the function returns `None`. Pass `strict=True` to raise `KeyError` instead. On platforms without `pwd`, such as Windows, a user name lookup logs a warning and returns `None`, also with `strict=True`.

## Diagnostic logging

`nclutils.fs` writes `DEBUG`, `WARNING`, and `ERROR` records through stdlib `logging`, under the `nclutils.fs` logger. Each skipped operation logs a warning, and each exception logs an error before it is raised. To show the records:

```python
import logging

logging.getLogger("nclutils.fs").setLevel(logging.DEBUG)
logging.basicConfig()
```

The logger is separate from `nclutils.pp` and shows nothing until the host application attaches a handler.

## API reference

- `backup_path(src: Path, backup_suffix: str = "", *, with_progress: bool = False, transient: bool = True, console: Console | None = None, strict: bool = False) -> Path | None`. Copy a file or directory to the same name with a suffix. Returns the backup path, or `None` if `src` does not exist. Raises `FileNotFoundError` if `strict=True` and `src` does not exist.
- `clean_directory(directory: Path, *, strict: bool = False) -> None`. Delete all contents of a directory and keep the directory. Raises `NotADirectoryError` if `strict=True` and `directory` is not an existing directory.
- `copy_file(src: Path, dst: Path, *, with_progress: bool = False, transient: bool = True, keep_backup: bool = True, console: Console | None = None, strict: bool = False) -> Path`. Copy a file, and back up an existing destination. Returns `dst`, or `src` if no copy was made. Raises `FileNotFoundError`, `IsADirectoryError`, or `OSError` for a bad `src`, `shutil.SameFileError` if `strict=True` and `src` is `dst`, and `RuntimeError` if the copy is incomplete.
- `copy_directory(src: Path, dst: Path, *, with_progress: bool = False, transient: bool = True, keep_backup: bool = True, console: Console | None = None, strict: bool = False) -> Path`. Copy a directory tree, and back up an existing destination. Returns `dst`, or `src` if no copy was made. Raises `FileNotFoundError` if `src` is not a directory. If `strict=True`, raises `shutil.SameFileError` when `src` is `dst` and `ValueError` when one contains the other. Raises `RuntimeError` if a file copy is incomplete.
- `directory_tree(directory: Path, *, show_hidden: bool = False) -> rich.tree.Tree`. Build a Rich tree of a directory.
- `find_files(path: Path, globs: list[str] | None = None, *, ignore_dotfiles: bool = False) -> list[Path]`. Return the sorted, unique files that match the glob patterns.
- `find_subdirectories(directory: Path, depth: int = 1, filter_regex: str = "", *, ignore_dotfiles: bool = False, leaf_dirs_only: bool = False) -> list[Path]`. Return the sorted subdirectories that match the filters. Raises `ValueError` if `depth` is less than 1.
- `find_user_home_dir(username: str | None = None, *, strict: bool = False) -> Path | None`. Return the home directory of a user, or of the user who ran `sudo`. Returns `None` if the user is not found. Raises `KeyError` if `strict=True` and the user is not found.
