# `nclutils.fs` reference

Filesystem helpers built on `pathlib`, `shutil`, and Rich. No console output except optional progress bars; pass `console=` to render them through a shared Rich `Console` (for example `pp.console()`).

## Signatures

```python
copy_file(src: Path, dst: Path, *, with_progress: bool = False, transient: bool = True, keep_backup: bool = True, console: Console | None = None, strict: bool = False) -> Path
copy_directory(src: Path, dst: Path, *, with_progress: bool = False, transient: bool = True, keep_backup: bool = True, console: Console | None = None, strict: bool = False) -> Path
backup_path(src: Path, backup_suffix: str = "", *, with_progress: bool = False, transient: bool = True, console: Console | None = None, strict: bool = False) -> Path | None
clean_directory(directory: Path, *, strict: bool = False) -> None
find_files(path: Path, globs: list[str] | None = None, *, ignore_dotfiles: bool = False) -> list[Path]
find_subdirectories(directory: Path, depth: int = 1, filter_regex: str = "", *, ignore_dotfiles: bool = False, leaf_dirs_only: bool = False) -> list[Path]
directory_tree(directory: Path, *, show_hidden: bool = False) -> rich.tree.Tree
find_user_home_dir(username: str | None = None, *, strict: bool = False) -> Path | None
```

Arguments after `*` are keyword-only. `Console` is `rich.console.Console`.

Shared keyword arguments of the copy and backup functions:

| Kwarg | Effect |
| --- | --- |
| `with_progress` | Show a Rich progress bar. |
| `transient` | Clear the progress bar when done. |
| `keep_backup` | Copy functions only. If `dst` exists, back it up with `backup_path` before replacing it. |
| `console` | Rich `Console` the progress bar renders through. |
| `strict` | Raise instead of logging a warning and returning, on the conditions listed per function. |

## Copying

Not drop-in replacements for `shutil.copy` / `shutil.copytree`:

- An existing directory at `dst` is deleted and replaced, not copied into. Pass the full target path.
- Permission bits are kept. Modification times are not, for files or directories.
- `~` is expanded and both paths are resolved.

### `copy_file`

- Creates missing parent directories of `dst`.
- Existing `dst` with `keep_backup=True`: backed up to `<dst name>.<YYYYMMDDTHHMMSS>-<random>.bak` in the same directory, then replaced.
- Returns `dst`. If `src` and `dst` are the same file and `strict=False`: logs a warning, copies nothing, returns `src`.

| Raises | When |
| --- | --- |
| `FileNotFoundError` | `src` does not exist. |
| `IsADirectoryError` | `src` is a directory. Use `copy_directory`. |
| `OSError` | `src` is not a regular file (socket, device). |
| `shutil.SameFileError` | `src` and `dst` are the same file and `strict=True`. |
| `RuntimeError` | Destination size differs from source after copy. |

### `copy_directory`

- Follows symlinks; a symlink to a directory becomes a real directory with the target's contents.
- Existing `dst` with `keep_backup=True`: backed up (same naming as `copy_file`), then deleted. A symlink at `dst` is unlinked.
- Existing regular file at `dst`: raises `FileExistsError` (after the backup, if any).
- `with_progress=True`: walks the tree once first to total the bytes. With a backup, shows two bars in sequence: Backup, then Copy.
- Returns `dst`. If `src == dst` or one contains the other and `strict=False`: logs a warning, copies nothing, returns `src`.

| Raises | When |
| --- | --- |
| `FileNotFoundError` | `src` does not exist or is not a directory. |
| `shutil.SameFileError` | `src == dst` and `strict=True`. |
| `ValueError` | `src` is inside `dst` or `dst` inside `src`, and `strict=True`. |
| `RuntimeError` | A copied file's size differs from its source. |

## `backup_path`

Copy a file or directory to a sibling named `src.name + backup_suffix`. Returns the backup path.

- Default suffix: `.<YYYYMMDDTHHMMSS>-<random>.bak`. A custom suffix is used literally, with no timestamp: `backup_suffix=".bak"` -> `config.toml.bak`.
- An existing file, symlink, or directory at the backup path is deleted first.
- `~` is not expanded. Call `.expanduser()` first.
- Directories: follows symlinks. Permission bits kept, modification times not.
- `src` missing: `strict=False` logs a warning and returns `None`; `strict=True` raises `FileNotFoundError`.

## `clean_directory`

Delete everything inside `directory`; the directory itself stays. Symlinks (including links to directories) are unlinked, not followed.

- `directory` not an existing directory: `strict=False` logs a warning and returns; `strict=True` raises `NotADirectoryError`.

## `find_files`

Return files under `path` matching any glob in `globs`, sorted and deduplicated.

- Globs go to `Path.glob`: `"*.py"` matches the top level only, `"**/*.py"` recurses.
- `globs=None`: every file at the top level of `path`, no recursion.
- Directories are never returned.
- `ignore_dotfiles=True`: skips a file if any path component below `path` starts with `.`. `path` itself is not checked, so a root like `Path.home() / ".config"` works.
- `~` is not expanded. A missing `path` returns `[]`.

## `find_subdirectories`

Return directories under `directory` up to `depth` levels, sorted.

- `depth=1`: immediate children only. `depth < 1` raises `ValueError`.
- `filter_regex`: `re.search` against each directory's name, unanchored. Use `^` / `$` for whole-name matches. `""` matches all. Non-matching directories are still descended into.
- `ignore_dotfiles=True`: skips directories whose name starts with `.` and does not descend into them. `directory` itself is not checked.
- `leaf_dirs_only=True`: drops any result that is an ancestor of another result.
- A missing `directory` returns `[]`.

## `directory_tree`

Return a `rich.tree.Tree` of `directory`, recursive. Directories before files, each group by lowercase name. Names starting with `.` are skipped unless `show_hidden=True`. Files show their size in SI units (base 1000, `"1.5 kB"`).

```python
pp.console().print(directory_tree(Path("src")))
```

## `find_user_home_dir`

Return a user's home directory, looked up with `pwd.getpwnam(username).pw_dir`.

- `username=None`: uses `SUDO_USER` if set, so a script under `sudo` gets the invoking user's home, not `/root`. Without `SUDO_USER`: returns `Path.home()`.
- Unknown user: `strict=False` returns `None`; `strict=True` raises `KeyError`.
- No `pwd` module (Windows) and a username to look up: returns `None` and logs a warning, regardless of `strict`.

## Logging

Diagnostics go to the stdlib logger `nclutils.fs` (debug, warning, error), silent until the host attaches a handler. Every `strict=False` warning above goes there, not to the console.

```python
logging.basicConfig()
logging.getLogger("nclutils.fs").setLevel(logging.DEBUG)
```
