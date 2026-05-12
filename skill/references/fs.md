# `nclutils.fs` reference

Filesystem helpers built on `pathlib`, `shutil`, and Rich. Emits diagnostics through stdlib `logging` (logger name: `nclutils.fs`); never writes to the console directly — pass `console=` to share a Rich `Console` with `pp.console()`.

## Copying

### `copy_file`

```python
copy_file(
    src: Path,
    dst: Path,
    *,
    with_progress: bool = False,
    transient: bool = True,
    keep_backup: bool = True,
    console: Console | None = None,
    strict: bool = False,
) -> Path
```

Drop-in for `shutil.copy` with progress and backup. Both paths have `~` expanded and are `.resolve()`d. Returns the destination `Path` on success.

Behavior:

- `with_progress=True` shows a Rich progress bar. `transient=True` clears it on completion.
- `keep_backup=True` (default) snapshots an existing destination via `backup_path` BEFORE overwriting. Backup name: `dst.<timestamp_uid>.bak`.
- `console=` lets you pass a shared Rich `Console`.
- Same-source-and-destination (`src == dst` or `samefile`): with `strict=True` raises `shutil.SameFileError`; with `strict=False` (default) logs a warning and returns `src`.
- Reads in 4 MiB chunks (`IO_BUFFER_SIZE = 4096 * 1024`). Preserves source mode via `shutil.copymode`. Mtimes NOT preserved (the write itself bumps mtime).

Raises:

- `FileNotFoundError` — `src` does not exist.
- `IsADirectoryError` — `src` is a directory (use `copy_directory`).
- `OSError` — `src` exists but is not a regular file (e.g. socket, device).
- `shutil.SameFileError` — `src` and `dst` resolve to the same file, AND `strict=True`.
- `RuntimeError` — internal: destination byte count doesn't match source after the copy (should not happen in practice).

### `copy_directory`

```python
copy_directory(
    src: Path,
    dst: Path,
    *,
    with_progress: bool = False,
    transient: bool = True,
    keep_backup: bool = True,
    console: Console | None = None,
    strict: bool = False,
) -> Path
```

Recursively copy a directory tree. Same kwargs and progress/backup semantics as `copy_file`. Returns destination `Path`.

> [!NOTE]
> No Python-version gate. The implementation uses `os.walk(followlinks=True)`, not `Path.walk`. (Older docs claiming 3.12+ are stale.)

Behavior:

- Approximates `shutil.copytree(src, dst)` (no kwargs): follows symlinks (including to directories — they materialize as real directories with target contents), preserves directory mode AND timestamps via `shutil.copystat`, preserves file mode via `shutil.copymode`. File mtimes NOT preserved.
- With `with_progress=True`, pre-walks the tree once to compute total bytes (extra `stat` per file), then drives a single `Progress` with an outer total-bytes bar and a recycled per-file subtask. With `keep_backup=True` AND destination exists, you see two sequential phases (Backup, then Copy), each with its own bar.
- Existing destination handling: symlink → `unlink`; directory → `rmtree` (after the backup, if any).

Raises:

- `FileNotFoundError` — `src` does not exist or is not a directory.
- `shutil.SameFileError` — `src == dst`, AND `strict=True` (else warns and returns `src`).
- `ValueError` — `src` is inside `dst` or vice versa (parent/child), AND `strict=True` (else warns and returns `src`).

## Standalone backup

### `backup_path`

```python
backup_path(
    src: Path,
    backup_suffix: str = "",
    *,
    with_progress: bool = False,
    transient: bool = True,
    console: Console | None = None,
    strict: bool = False,
) -> Path | None
```

Snapshot a path in place. Returns the backup path, or `None` when `src` is missing and `strict=False`.

- Default suffix is `"." + new_timestamp_uid() + ".bak"`. Override with `backup_suffix=".pre-migration.bak"` (LITERAL string — no timestamp added). The suffix is appended to the existing name with `with_name(src.name + backup_suffix)`.
- Pre-existing target (collision) is cleared first (`unlink` for files/symlinks, `rmtree` for dirs). Not atomic across processes; the timestamped default makes collisions very rare.
- File backups: `shutil.copymode` only (no mtime).
- Directory backups: `os.walk(followlinks=True)`, mirror directory mode + timestamps via `shutil.copystat`, follow symlinks.

Raises `FileNotFoundError` only when `src` is missing AND `strict=True`.

## Cleaning

### `clean_directory`

```python
clean_directory(directory: Path, *, strict: bool = False) -> None
```

Empties `directory` in place. Files and symlinks (including dangling and links-to-directories) are `unlink`ed; subdirectories are `rmtree`d; the directory itself stays.

When `directory` is not an existing directory: with `strict=False` (default), logs a warning and returns; with `strict=True`, raises `NotADirectoryError`.

## Searching

### `find_files`

```python
find_files(
    path: Path,
    globs: list[str] | None = None,
    *,
    ignore_dotfiles: bool = False,
) -> list[Path]
```

Files in `path` matching any of `globs` (passed straight to `Path.glob`, so `"**/*.py"` works for recursive matching). Without `globs`, returns every file at the top level via `path.glob("*")` (no recursion).

- Returned list is sorted (lexicographic `Path` sort) and deduplicated (a file matching multiple globs appears once).
- `ignore_dotfiles=True` excludes any file whose path-relative-to-`path` contains a component starting with `.`. The user-supplied root is NEVER filtered, so passing `Path("~/.config")` as the root works.

### `find_subdirectories`

```python
find_subdirectories(
    directory: Path,
    depth: int = 1,
    filter_regex: str = "",
    *,
    ignore_dotfiles: bool = False,
    leaf_dirs_only: bool = False,
) -> list[Path]
```

Walk subdirectories with depth + regex filtering. Returns sorted `list[Path]`.

- `depth >= 1` required; `0` or negative raises `ValueError`. `depth=1` means immediate children only.
- `filter_regex` applied with `re.search` (UNANCHORED — matches if the pattern is found anywhere in the directory name; anchor with `^`/`$` for whole-name). Empty string matches all.
- `ignore_dotfiles=True` skips dirs whose own name starts with `.` AND prevents descent into them. Root is never filtered.
- `leaf_dirs_only=True` returns only directories with no matching descendant inside the depth limit. Implemented by computing the union of all ancestors of matches and filtering anything that's an ancestor.

Raises `ValueError` if `depth < 1`.

## Tree rendering

### `directory_tree`

```python
directory_tree(directory: Path, *, show_hidden: bool = False) -> rich.tree.Tree
```

Build a `rich.tree.Tree` of `directory`'s contents. Subdirectories sorted before files; within each group, lowercase name order. Dotfiles excluded unless `show_hidden=True`. Files show their size via `nclutils.strings.human_size` (SI base 1000, e.g. `"1.5 kB"`).

```python
from nclutils import pp
from nclutils.fs import directory_tree

pp.console().print(directory_tree(Path("./src")))
```

## Sudo-aware home lookup

### `find_user_home_dir`

```python
find_user_home_dir(
    username: str | None = None,
    *,
    strict: bool = False,
) -> Path | None
```

Resolve a home directory. POSIX lookups go through `pwd.getpwnam(username).pw_dir`; no subprocess.

Resolution order when `username=None`:

1. Check `SUDO_USER` env var. If set, use it as the username.
2. Otherwise return `Path.home()` (the current process's home).

Returns `None` when:

- `username` (or the resolved SUDO_USER) is unknown AND `strict=False`.
- `pwd` is unavailable (e.g. Windows) — REGARDLESS of `strict`, since this is a platform capability rather than a runtime error. A warning is logged.

Raises `KeyError` when `username` is unknown AND `strict=True` (POSIX only).

## Diagnostic logging

`nclutils.fs` emits `DEBUG`/`WARNING`/`ERROR` through stdlib `logging` under the `nclutils.fs` logger. Silent until the host attaches a handler. Independent of `nclutils.pp`.

```python
import logging
logging.getLogger("nclutils.fs").setLevel(logging.DEBUG)
logging.basicConfig()
```

Records cover internal operations like "starting a copy", "skipping a backup because source is missing", "backup target collision cleared".

## API reference (signatures only)

```python
copy_file(src, dst, *, with_progress=False, transient=True, keep_backup=True, console=None, strict=False) -> Path
copy_directory(src, dst, *, with_progress=False, transient=True, keep_backup=True, console=None, strict=False) -> Path
backup_path(src, backup_suffix="", *, with_progress=False, transient=True, console=None, strict=False) -> Path | None
clean_directory(directory, *, strict=False) -> None
find_files(path, globs=None, *, ignore_dotfiles=False) -> list[Path]
find_subdirectories(directory, depth=1, filter_regex="", *, ignore_dotfiles=False, leaf_dirs_only=False) -> list[Path]
directory_tree(directory, *, show_hidden=False) -> rich.tree.Tree
find_user_home_dir(username=None, *, strict=False) -> Path | None
```

Every function takes positional path-like args first; kwargs are keyword-only (the `*` is real in the signatures above).
