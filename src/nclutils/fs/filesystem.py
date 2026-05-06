"""Filesystem utilities for directory and file operations."""

import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.filesize import decimal
from rich.markup import escape
from rich.progress import Progress, TaskID
from rich.text import Text
from rich.tree import Tree

from nclutils.utils import check_python_version, new_timestamp_uid

logger = logging.getLogger(__name__)

# how many bytes to read at once?
# shutil.copy uses 1024 * 1024 if _WINDOWS else 64 * 1024
# however, in my testing on MacOS with SSD, I've found a much larger buffer is faster
IO_BUFFER_SIZE = 4096 * 1024


def _do_copy_file(
    src: Path, dst: Path, *, progress_bar: Progress | None = None, task: TaskID | None = None
) -> None:
    """Copy a file's contents in chunks, preserving permissions, with optional progress tracking.

    Args:
        src (Path): Source file to read from.
        dst (Path): Destination file to write to.
        progress_bar (Progress | None, optional): Progress bar instance for tracking. Defaults to None.
        task (TaskID | None, optional): Task ID for progress updates. Defaults to None.

    Raises:
        RuntimeError: If the destination file size does not match the source after the copy.
    """
    src_size = src.stat().st_size

    with src.open("rb") as src_bytes, dst.open("wb") as dst_bytes:
        bytes_copied = 0
        while True:
            buf = src_bytes.read(IO_BUFFER_SIZE)
            if not buf:
                break
            dst_bytes.write(buf)
            bytes_copied += len(buf)
            if progress_bar is not None and task is not None:
                progress_bar.update(task, completed=bytes_copied)

    dst_size = dst.stat().st_size
    if dst_size != src_size:
        msg = f"copy incomplete: expected {src_size} bytes, destination has {dst_size} bytes"
        logger.error(msg)
        raise RuntimeError(msg) from None

    shutil.copymode(src, dst)


def _sum_bytes(root: Path) -> tuple[int, int]:
    """Return (total_bytes, file_count) for every file under root.

    Used by `_Copier` to drive a determinate progress bar when `with_progress=True`.
    The extra `os.stat` per file is the cost of an accurate ETA and percentage; callers
    that pass `with_progress=False` never trigger this walk.
    """
    total = 0
    count = 0
    for current_root, _, files in os.walk(root):
        base = Path(current_root)
        for name in files:
            total += (base / name).stat().st_size
            count += 1
    return total, count


@dataclass(frozen=True, kw_only=True)
class _Copier:
    """Internal helper holding shared copy/backup configuration.

    Public functions (`copy_file`, `copy_directory`, `backup_path`) build a one-shot
    instance and delegate. Not exported.
    """

    with_progress: bool = False
    transient: bool = True
    console: Console | None = None
    strict: bool = False

    def copy_file(self, src: Path, dst: Path, *, keep_backup: bool = True) -> Path:
        """Stub. Filled in by Task 4."""
        raise NotImplementedError

    def copy_directory(self, src: Path, dst: Path, *, keep_backup: bool = True) -> Path:
        """Stub. Filled in by Tasks 5 and 6."""
        raise NotImplementedError

    def backup(
        self, src: Path, backup_suffix: str = "", *, raise_on_missing: bool = False
    ) -> Path | None:
        """Create a backup copy of `src` by appending `backup_suffix` to its name.

        If `backup_suffix` is empty, generates a timestamped suffix. Skips silently when
        `src` does not exist (or raises `FileNotFoundError` if `raise_on_missing`).
        """
        if not src.exists():
            msg = f"skip backup: does not exist `{src}`"
            if raise_on_missing:
                logger.error(msg)
                raise FileNotFoundError(msg) from None
            logger.warning(msg)
            return None

        if not backup_suffix:
            backup_suffix = "." + new_timestamp_uid() + ".bak"

        target = src.with_name(src.name + backup_suffix)

        # Clear the target if anything is already there. This isn't atomic across processes,
        # but the timestamped default suffix makes a real collision very rare.
        if target.is_symlink() or target.is_file():
            logger.debug("unlink %s", target)
            target.unlink()
        elif target.is_dir():
            logger.debug("rmtree %s", target)
            shutil.rmtree(target)

        if src.is_dir():
            logger.debug("copytree %s %s", src, target)
            shutil.copytree(src, target)
        elif self.with_progress:
            with Progress(transient=self.transient, console=self.console) as progress_bar:
                copy_task = progress_bar.add_task(f"Backup {src.name}", total=src.stat().st_size)
                logger.debug("copyfile %s %s", src, target)
                _do_copy_file(src, target, progress_bar=progress_bar, task=copy_task)
        else:
            logger.debug("copyfile %s %s", src, target)
            _do_copy_file(src, target)

        return target


def backup_path(
    src: Path,
    backup_suffix: str = "",
    *,
    raise_on_missing: bool = False,
    with_progress: bool = False,
    transient: bool = True,
    console: Console | None = None,
) -> Path | None:
    """Create a backup copy of a file/directory by appending a suffix to the original name. If no suffix is provided, generate one using a timestamp. Skip if the source path doesn't exist.

    Args:
        src (Path): Path to the file or directory to back up.
        backup_suffix (str, optional): Custom suffix to append to the backup name. Defaults to a timestamp-based suffix.
        raise_on_missing (bool, optional): Raise if the source path does not exist. Defaults to False.
        with_progress (bool, optional): Show a progress bar during file copies. Defaults to False.
        transient (bool, optional): Remove the progress bar after completion. Defaults to True.
        console (Console | None, optional): Rich `Console` to render the progress bar through. Defaults to None (Rich's default global console).

    Returns:
        Path | None: Path to the created backup file/directory, or None if the source does not exist and `raise_on_missing` is False.

    Raises:
        FileNotFoundError: If the source path does not exist and `raise_on_missing` is True.
    """
    return _Copier(with_progress=with_progress, transient=transient, console=console).backup(
        src, backup_suffix, raise_on_missing=raise_on_missing
    )


def clean_directory(directory: Path) -> None:
    """Recursively cleans up the contents of a directory, deleting all files and subdirectories without deleting the directory itself.

    Args:
        directory (Path): The directory to clean up.
    """
    if not directory.is_dir():
        msg = f"{directory} is not a directory. Did not clean up."
        logger.warning(msg)
        return

    for child in directory.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)


def copy_file(
    src: Path,
    dst: Path,
    *,
    with_progress: bool = False,
    transient: bool = True,
    keep_backup: bool = True,
    console: Console | None = None,
) -> Path:
    """Copy a file to a destination with optional progress tracking.

    Copy files with granular control over progress display and file conflict handling. Preserve original file permissions while providing visual feedback for long-running operations.

    Args:
        src (Path): Source file to copy.
        dst (Path): Destination path for the copy.
        with_progress (bool, optional): Show a progress bar during copy. Defaults to False.
        transient (bool, optional): Remove the progress bar after completion. Defaults to True.
        keep_backup (bool, optional): Keep a backup of the destination file if it already exists. Defaults to True.
        console (Console | None, optional): Rich `Console` to render the progress bar through. Defaults to None (Rich's default global console).

    Returns:
        Path: Path to the destination file after copy completion

    Raises:
        FileNotFoundError: If the source path does not exist
        IsADirectoryError: If the source path is a directory
        OSError: If the source path exists but is not a regular file
    """
    src = src.expanduser().resolve()
    dst = dst.expanduser().resolve()

    if not src.exists():
        msg = f"source file `{src}` does not exist. Did not copy."
        logger.error(msg)
        raise FileNotFoundError(msg) from None

    if src.is_dir():
        msg = f"source `{src}` is a directory, not a file. Did not copy."
        logger.error(msg)
        raise IsADirectoryError(msg) from None

    if not src.is_file():
        msg = f"source `{src}` is not a regular file. Did not copy."
        logger.error(msg)
        raise OSError(msg) from None

    if src == dst or (dst.exists() and src.samefile(dst)):
        msg = f"source file `{src}` and destination file `{dst}` are the same file. Did not copy."
        logger.warning(msg)
        return src

    if dst.exists() and keep_backup:
        logger.debug("backup %s", dst)
        backup_path(dst, with_progress=with_progress, transient=transient, console=console)

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.is_symlink():
        logger.debug("unlink %s", dst)
        dst.unlink()
    elif dst.is_dir():
        logger.debug("rmtree %s", dst)
        shutil.rmtree(dst)

    if with_progress:
        with Progress(transient=transient, console=console) as progress_bar:
            copy_task = progress_bar.add_task(f"Copy {src.name}", total=src.stat().st_size)
            _do_copy_file(src, dst, progress_bar=progress_bar, task=copy_task)
            logger.debug("copyfile %s %s", src, dst)
    else:
        _do_copy_file(src, dst)
        logger.debug("copyfile %s %s", src, dst)

    return dst


def copy_directory(
    src: Path,
    dst: Path,
    *,
    with_progress: bool = False,
    transient: bool = True,
    keep_backup: bool = True,
    console: Console | None = None,
) -> Path:
    """Copy a directory and its contents to a new destination path.

    Recursively copy all files and subdirectories from the source directory to the destination, preserving the directory structure. Display an optional progress bar for each file being copied.

    Args:
        src (Path): Source directory to copy from
        dst (Path): Destination directory to copy to
        with_progress (bool, optional): Show progress bar while copying files. Defaults to False.
        transient (bool, optional): Clear progress bar after completion. Defaults to True.
        keep_backup (bool, optional): Keep a backup of the destination directory if it already exists. Defaults to True.
        console (Console | None, optional): Rich `Console` to render the progress bar through. Defaults to None (Rich's default global console).

    Returns:
        Path: Path to the destination directory

    Raises:
        FileNotFoundError: If source directory does not exist or is not a directory
        ValueError: If Python version is less than 3.12
    """
    if not check_python_version(3, 12):
        msg = "Copy file requires a minimum of Python version 3.12"
        logger.error(msg)
        raise ValueError(msg) from None

    src = src.expanduser().resolve()
    dst = dst.expanduser().resolve()

    if not src.exists() or not src.is_dir():
        msg = f"source directory `{src}` does not exist or is not a directory. Did not copy."
        logger.error(msg)
        raise FileNotFoundError(msg) from None

    # Prevent copying a directory to itself or into itself to avoid infinite recursion
    if src == dst:
        msg = f"source directory `{src}` and destination directory `{dst}` are the same directory. Did not copy."
        logger.warning(msg)
        return src

    if src in dst.parents or dst in src.parents:
        msg = f"source directory `{src}` and destination directory `{dst}` have parent/child relationship. Did not copy."
        logger.warning(msg)
        return src

    if dst.exists() and keep_backup:
        logger.debug("backup %s", dst)
        backup_path(dst, with_progress=with_progress, transient=transient, console=console)

    if dst.is_symlink():
        logger.debug("unlink %s", dst)
        dst.unlink()
    elif dst.is_dir():
        logger.debug("rmtree %s", dst)
        shutil.rmtree(dst)

    logger.debug("walk %s", src)
    for root, _, files in src.walk():
        rel = root.relative_to(src)
        new_parent = dst / rel
        new_parent.mkdir(parents=True, exist_ok=True)
        shutil.copystat(root, new_parent)

        for file in files:
            copy_file(
                src=root / file,
                dst=new_parent / file,
                with_progress=with_progress,
                transient=transient,
                console=console,
            )

    return dst


def directory_tree(directory: Path, *, show_hidden: bool = False) -> Tree:
    """Build a tree representation of a directory's contents.

    Create a visual tree structure showing files and subdirectories within the given directory. Files are displayed with size and icons, directories are shown with folder icons.

    Inspired by https://github.com/Textualize/rich/blob/master/examples/tree.py

    Args:
        directory (Path): The root directory to build the tree from
        show_hidden (bool, optional): Whether to include hidden files and directories in the tree. Defaults to False.

    Returns:
        Tree: A rich Tree object containing the directory structure
    """

    def _walk_directory(directory: Path, tree: Tree, *, show_hidden: bool = False) -> None:
        """Recursively build a Tree with directory contents."""
        # Sort dirs first then by filename
        paths = sorted(
            Path(directory).iterdir(),
            key=lambda path: (path.is_file(), path.name.lower()),
        )
        for path in paths:
            if not show_hidden and path.name.startswith("."):
                continue

            if path.is_dir():
                style = "dim" if path.name.startswith("__") or path.name.startswith(".") else ""
                branch = tree.add(
                    f"[bold magenta]:open_file_folder: [link file://{path}]{escape(path.name)}",
                    style=style,
                    guide_style=style,
                )
                _walk_directory(path, branch, show_hidden=show_hidden)
            else:
                text_filename = Text(path.name, "green")
                text_filename.highlight_regex(r"\..*$", "bold red")
                text_filename.stylize(f"link file://{path}")
                file_size = path.stat().st_size
                text_filename.append(f" ({decimal(file_size)})", "blue")
                icon = "📄 "
                tree.add(Text(icon) + text_filename)

    tree = Tree(
        f":open_file_folder: [link file://{directory}]{directory}",
        guide_style="bright_blue",
    )
    _walk_directory(Path(directory), tree, show_hidden=show_hidden)
    return tree


def find_subdirectories(
    directory: Path,
    depth: int = 1,
    filter_regex: str = "",
    *,
    ignore_dotfiles: bool = False,
    leaf_dirs_only: bool = False,
) -> list[Path]:
    """Search and filter subdirectories in a directory tree with precise depth control.

    Use this function to traverse directory structures when you need fine-grained control over:
    - How deep to search (depth parameter, must be >= 1)
    - Which directories to include (regex filtering — the regex is applied with `re.search`, so it matches if the pattern is found *anywhere* in the directory name; anchor with `^` or `$` for whole-name matching)
    - Whether to skip hidden subdirectories (the user-supplied `directory` itself is never filtered)
    - Whether to return only leaf directories (those without other matching subdirectories within the depth limit)

    Args:
        directory (Path): Root directory to begin the search.
        depth (int, optional): Maximum directory depth to traverse. Must be >= 1. A depth of 1 means immediate subdirectories only. Defaults to 1.
        filter_regex (str, optional): Regular expression pattern matched against each directory's name with `re.search`. Empty string matches everything. Defaults to "".
        ignore_dotfiles (bool, optional): Skip directories whose name starts with a dot, and do not descend into them. Defaults to False.
        leaf_dirs_only (bool, optional): Return only directories that have no matching descendant within the depth limit. Defaults to False.

    Returns:
        list[Path]: Sorted list of directory paths matching the specified criteria.

    Raises:
        ValueError: If `depth` is less than 1.
    """
    if depth < 1:
        msg = f"depth must be >= 1, got {depth}"
        raise ValueError(msg) from None

    pattern = re.compile(filter_regex) if filter_regex else None

    matches: list[Path] = []
    for current_root, dirnames, _ in os.walk(directory):
        current_path = Path(current_root)
        try:
            current_depth = len(current_path.relative_to(directory).parts)
        except ValueError:  # pragma: no cover — os.walk roots are always under `directory`
            continue

        # Stop os.walk from descending past the user-requested depth.
        if current_depth >= depth:
            dirnames[:] = []
            continue

        if ignore_dotfiles:
            # Mutating dirnames in place both filters this level and prevents descent.
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for dirname in dirnames:
            if pattern is not None and not pattern.search(dirname):
                continue
            matches.append(current_path / dirname)

    if leaf_dirs_only:
        return _filter_to_leaves(matches)

    return sorted(matches)


def _filter_to_leaves(paths: list[Path]) -> list[Path]:
    """Return only paths from `paths` that are not ancestors of any other path in `paths`.

    Builds the union of all ancestors in one pass so the filter is O(N * depth)
    instead of the O(N^2 * depth) cross-product comparison.
    """
    ancestors: set[Path] = set()
    for p in paths:
        for parent in p.parents:
            if parent in ancestors:
                break
            ancestors.add(parent)
    return sorted(p for p in paths if p not in ancestors)


def find_files(
    path: Path, globs: list[str] | None = None, *, ignore_dotfiles: bool = False
) -> list[Path]:
    """Find files in a specified directory that match a list of glob patterns.

    Search the given `path` for files matching any of the glob patterns provided in `globs`. If no globs are provided, returns all files in the directory.

    Args:
        path (Path): The root directory where the search will be conducted.
        globs (list[str] | None, optional): A list of glob patterns to match files (e.g., "*.txt", "*.py"). If None, returns all files in the top level of `path`. Defaults to None.
        ignore_dotfiles (bool, optional): Skip files whose name starts with a dot, or that are reached through a directory whose name starts with a dot. The user-supplied `path` itself is never filtered. Defaults to False.

    Returns:
        list[Path]: A sorted list of unique Path objects matching the requested patterns.
    """

    def is_valid_file(p: Path) -> bool:
        if not p.is_file():
            return False
        if not ignore_dotfiles:
            return True
        return not any(part.startswith(".") for part in p.relative_to(path).parts)

    patterns = ["*"] if globs is None else globs

    seen: set[Path] = set()
    results: list[Path] = []
    for pattern in patterns:
        for candidate in path.glob(pattern):
            if candidate in seen or not is_valid_file(candidate):
                continue
            seen.add(candidate)
            results.append(candidate)

    return sorted(results)


def find_user_home_dir(username: str | None = None) -> Path | None:
    """Locate and return the home directory path for a given or current user.

    If no username is provided, fall back to the `SUDO_USER` environment variable so
    scripts running under sudo resolve the invoking user's home rather than `/root`.
    On POSIX systems, lookups go through the standard library `pwd` module
    (`pwd.getpwnam(username).pw_dir`). On platforms without `pwd` (e.g. Windows),
    return `None` and log a warning.

    Args:
        username (str | None, optional): Username to find home directory for. If None, use SUDO_USER or the current user. Defaults to None.

    Returns:
        Path | None: Home directory path for the specified user, or None if the user is not found or the platform does not provide `pwd`.
    """
    if username is None:
        sudo_user = os.getenv("SUDO_USER")
        if not sudo_user:
            return Path.home()
        username = sudo_user

    try:
        import pwd  # noqa: PLC0415
    except ImportError:
        logger.warning("pwd module unavailable; cannot resolve home directory for `%s`", username)
        return None

    try:
        return Path(pwd.getpwnam(username).pw_dir)
    except KeyError:
        logger.debug("pwd lookup failed for `%s`", username)
        return None
