"""Filesystem utilities for directory and file operations."""

import os
import platform
import re
import shutil
from pathlib import Path

from rich.filesize import decimal
from rich.markup import escape
from rich.progress import Progress, TaskID
from rich.text import Text
from rich.tree import Tree

from nclutils.logging import logger
from nclutils.sh import ShellCommandFailedError, run_command
from nclutils.utils import check_python_version, new_timestamp_uid

# how many bytes to read at once?
# shutil.copy uses 1024 * 1024 if _WINDOWS else 64 * 1024
# however, in my testing on MacOS with SSD, I've found a much larger buffer is faster
IO_BUFFER_SIZE = 4096 * 1024


def _do_copy_file(
    src: Path, dst: Path, *, progress_bar: Progress | None = None, task: TaskID | None = None
) -> None:
    """Copy file contents in chunks with optional progress tracking.

    Args:
        src (Path): Source file to read from
        dst (Path): Destination file to write to
        progress_bar (Progress | None, optional): Progress bar instance for tracking. Defaults to None
        task (TaskID | None, optional): Task ID for progress updates. Defaults to None
    """
    with src.open("rb") as src_bytes, dst.open("wb") as dst_bytes:
        total_bytes_copied = 0
        while True:
            buf = src_bytes.read(IO_BUFFER_SIZE)
            if not buf:
                break
            dst_bytes.write(buf)
            total_bytes_copied += len(buf)
            if progress_bar is not None and task is not None:
                progress_bar.update(task, completed=total_bytes_copied)


def backup_path(
    src: Path,
    backup_suffix: str = "",
    *,
    raise_on_missing: bool = False,
    with_progress: bool = False,
    transient: bool = True,
) -> Path | None:
    """Create a backup copy of a file/directory by appending a suffix to the original name. If no suffix is provided, generate one using a timestamp. Skip if the source path doesn't exist.

    Args:
        src (Path): Path to the file or directory to back up
        backup_suffix (str, optional): Custom suffix to append to the backup name.
        raise_on_missing (bool, optional): Whether to raise an error if the source path does not exist. Defaults to False.
        with_progress (bool, optional): Show a progress bar during copy. Defaults to False
        transient (bool, optional): Remove the progress bar after completion. Defaults to True

    Returns:
        Path | None: Path to the created backup file/directory, or None if source doesn't exist

    Raises:
        FileNotFoundError: If the source path does not exist and raise_on_missing is True
    """
    if not src.exists() and raise_on_missing:
        msg = f"skip backup: does not exist `{src}`"
        logger.error(msg)
        raise FileNotFoundError(msg)

    if not src.exists():
        msg = f"skip backup: does not exist `{src}`"
        logger.warning(msg)
        return None

    if not backup_suffix:
        backup_suffix = "." + new_timestamp_uid() + ".bak"

    backup_path = src.with_name(src.name + backup_suffix)

    # Clear the target of the backup in case it already exists.
    # Note this isn't perfectly atomic, if another thread does a backup
    # to an identical backup directory but this would be very rare.
    if backup_path.is_symlink():
        logger.trace(f"unlink {backup_path}")
        backup_path.unlink()
    elif backup_path.is_dir():
        logger.trace(f"rmtree {backup_path}")
        shutil.rmtree(backup_path)

    if src.is_dir():
        logger.debug(f"copytree {src} {backup_path}")
        shutil.copytree(src, backup_path)
    elif with_progress:
        with Progress(transient=transient) as progress_bar:
            copy_task = progress_bar.add_task(f"Backup {src.name}", total=src.stat().st_size)
            logger.debug(f"copyfile {src} {backup_path}")
            _do_copy_file(src, backup_path, progress_bar=progress_bar, task=copy_task)
    else:
        logger.debug(f"copyfile {src} {backup_path}")
        _do_copy_file(src, backup_path)

    return backup_path


def copy_file(
    src: Path,
    dst: Path,
    *,
    with_progress: bool = False,
    transient: bool = True,
    keep_backup: bool = True,
) -> Path:
    """Copy a file to a destination with optional progress tracking.

    Copy files with granular control over progress display and file conflict handling. Preserve original file permissions while providing visual feedback for long-running operations.

    Args:
        src (Path): Source file to copy
        dst (Path): Destination path for the copy
        with_progress (bool, optional): Show a progress bar during copy. Defaults to False
        transient (bool, optional): Remove the progress bar after completion. Defaults to True
        keep_backup (bool, optional): Keep a backup of the destination file if it already exists. Defaults to True

    Returns:
        Path: Path to the destination file after copy completion

    Raises:
        FileNotFoundError: If source file does not exist or is not a regular file
    """
    if not src.exists():
        msg = f"source file `{src}` does not exist. Did not copy."
        logger.error(msg)
        raise FileNotFoundError(msg)

    if not src.is_file():
        msg = f"source file `{src}` is not a file. Did not copy."
        logger.error(msg)
        raise FileNotFoundError(msg)

    dst = dst.parent.expanduser().resolve() / dst.name

    # Check if source and destination are the same to avoid unnecessary copy
    if src == dst or (dst.exists() and src.samefile(dst)):
        msg = f"source file `{src}` and destination file `{dst}` are the same file. Did not copy."
        logger.warning(msg)
        return src

    # Generate unique filename if destination exists and overwrite is disabled
    if dst.exists() and keep_backup:
        logger.debug(f"backup {dst}")
        backup_path(dst, with_progress=with_progress, transient=transient)

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.is_symlink():
        logger.trace(f"unlink {dst}")
        dst.unlink()
    elif dst.is_dir():
        logger.trace(f"rmtree {dst}")
        shutil.rmtree(dst)

    # Copy file in chunks with progress bar to handle large files efficiently
    if with_progress:
        with Progress(transient=transient) as progress_bar:
            copy_task = progress_bar.add_task(f"Copy {src.name}", total=src.stat().st_size)
            logger.debug(f"copyfile {src} {dst}")
            _do_copy_file(src, dst, progress_bar=progress_bar, task=copy_task)
    else:
        logger.debug(f"copyfile {src} {dst}")
        _do_copy_file(src, dst)

    # Preserve original file permissions
    shutil.copymode(str(src), str(dst))

    return dst


def copy_directory(
    src: Path,
    dst: Path,
    *,
    with_progress: bool = False,
    transient: bool = True,
    keep_backup: bool = True,
) -> Path:
    """Copy a directory and its contents to a new destination path.

    Recursively copy all files and subdirectories from the source directory to the destination, preserving the directory structure. Display an optional progress bar for each file being copied.

    Args:
        src (Path): Source directory to copy from
        dst (Path): Destination directory to copy to
        with_progress (bool, optional): Show progress bar while copying files. Defaults to False.
        transient (bool, optional): Clear progress bar after completion. Defaults to True.
        keep_backup (bool, optional): Keep a backup of the destination directory if it already exists. Defaults to True.

    Returns:
        Path: Path to the destination directory

    Raises:
        FileNotFoundError: If source directory does not exist or is not a directory
        ValueError: If Python version is less than 3.12
    """
    # Verify Python version requirement for Path.walk() method
    if not check_python_version(3, 12):
        msg = "Copy file requires a minimum of Python version 3.12"
        logger.error(msg)
        raise ValueError(msg)

    src = src.expanduser().resolve()
    dst = dst.expanduser().resolve()

    # Validate source directory exists and is actually a directory
    if not src.exists() or not src.is_dir():
        msg = f"source directory `{src}` does not exist or is not a directory. Did not copy."
        logger.error(msg)
        raise FileNotFoundError(msg)

    # Prevent copying a directory to itself or into itself to avoid infinite recursion
    if src == dst:
        msg = f"source directory `{src}` and destination directory `{dst}` are the same directory. Did not copy."
        logger.warning(msg)
        return src

    if src in dst.parents or dst in src.parents:
        msg = f"source directory `{src}` and destination directory `{dst}` have parent/child relationship. Did not copy."
        logger.warning(msg)
        return src

    # Generate unique destination name if it exists and we're not overwriting
    if dst.exists() and keep_backup:
        logger.debug(f"backup {dst}")
        backup_path(dst, with_progress=with_progress, transient=transient)

    if dst.is_symlink():
        logger.trace(f"unlink {dst}")
        dst.unlink()
    elif dst.is_dir():
        logger.trace(f"rmtree {dst}")
        shutil.rmtree(dst)

    # Walk the source directory tree and copy each file while preserving structure
    logger.debug(f"walk {src}")
    for root, _, files in src.walk():
        new_parent = dst if root == src else dst / root.relative_to(src)
        new_parent.mkdir(parents=True, exist_ok=True)

        for file in files:
            src_file = root / file if root == src else src / root.relative_to(src) / file
            copy_file(
                src=src_file,
                dst=new_parent / file,
                with_progress=with_progress,
                transient=transient,
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
    - How deep to search (depth parameter)
    - Which directories to include (regex filtering)
    - Whether to include hidden directories
    - Whether to return only leaf directories (those without subdirectories)

    This is particularly useful for tasks like:
    - Finding all project directories in a workspace
    - Locating leaf directories for processing
    - Selective directory traversal with pattern matching

    Args:
        directory (Path): Root directory to begin the search
        depth (int, optional): Maximum directory depth to traverse. Depth of 1 means immediate subdirectories only. Defaults to 1
        filter_regex (str, optional): Regular expression pattern to filter directory names. Only matching directories are included. Defaults to ""
        ignore_dotfiles (bool, optional): Skip directories starting with a dot (hidden directories). Defaults to False
        leaf_dirs_only (bool, optional): Return only directories that have no subdirectories within the specified depth. Defaults to False

    Returns:
        list[Path]: Sorted list of directory paths matching the specified criteria
    """
    # Collect subdirectories for all depths up to the specified depth
    subdirs = []
    for current_depth in range(1, depth + 1):
        pattern = f"{'*/' * current_depth}"
        current_level = [
            p
            for p in directory.glob(pattern)
            if p.is_dir()
            and (not ignore_dotfiles or not any(part.startswith(".") for part in p.parts))
            and (not filter_regex or re.search(filter_regex, p.name))
        ]
        subdirs.extend(current_level)

    if leaf_dirs_only:
        # Keep only directories that don't have subdirectories within our depth limit
        result = []
        for p in subdirs:
            # Check if this directory has any subdirectories in our collection
            is_parent = any(other != p and str(other).startswith(str(p)) for other in subdirs)
            if not is_parent:
                result.append(p)
        return sorted(result)

    return sorted(subdirs)


def find_files(
    path: Path, globs: list[str] | None = None, *, ignore_dotfiles: bool = False
) -> list[Path]:
    """Find files in a specified directory that match a list of glob patterns.

    Search the given `path` for files matching any of the glob patterns provided in `globs`. If no globs are provided, returns all files in the directory.

    Args:
        path (Path): The root directory where the search will be conducted.
        globs (list[str] | None, optional): A list of glob patterns to match files (e.g., "*.txt", "*.py"). If None, returns all files. Defaults to None.
        ignore_dotfiles (bool, optional): Whether to ignore files that start with a dot. Defaults to False.

    Returns:
        list[Path]: A list of Path objects representing the files that match the glob patterns.
    """

    def is_valid_file(p: Path) -> bool:
        return p.is_file() and (not ignore_dotfiles or not p.name.startswith("."))

    if globs is None:
        return sorted([p for p in path.glob("*") if is_valid_file(p)])

    files: list[Path] = []
    for g in globs:
        files.extend(p for p in path.glob(g) if is_valid_file(p))

    return sorted(files)


def find_user_home_dir(username: str | None = None) -> Path | None:
    """Locate and return the home directory path for a given or current user.

    Search for the home directory using system-specific commands. If no username is provided, check for sudo user first, then fall back to current user's home. For Linux, use getent passwd. For macOS, use dscl to look up NFSHomeDirectory.

    Args:
        username (str | None, optional): Username to find home directory for. If None, use sudo user or current user. Defaults to None.

    Returns:
        Path | None: Home directory path for the specified or current user, or None if not found
    """
    if username is None:
        if sudo_user := os.getenv("SUDO_USER"):
            username = sudo_user
        else:
            return Path.home()

    if platform.system() == "Linux":
        try:
            return Path(
                run_command("getent", ["passwd", username], quiet=True)
                .strip()
                .split(":")[5]
                .strip()
            )
        except ShellCommandFailedError:
            return None

    if platform.system() == "Darwin":
        try:
            return Path(
                run_command(
                    "dscl", [".", "-read", f"/Users/{username}", "NFSHomeDirectory"], quiet=True
                )
                .strip()
                .split(":")[1]
                .strip()
            )
        except ShellCommandFailedError:
            return None

    return None
