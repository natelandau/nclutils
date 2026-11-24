"""Document utilities."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def replace_in_file(
    path: str | Path, replacements: dict[str, str], *, use_regex: bool = False
) -> bool:
    """Replace text in a file with a dictionary of replacements.

    Args:
        path (str): Path to the file to replace text in.
        replacements (dict[str, str]): Dictionary of old text to new text.
        use_regex (bool): Whether to use regex for replacements. Defaults to False.

    Returns:
        bool: True if replacements were made, False otherwise.
    """
    path = Path(path) if not isinstance(path, Path) else path

    try:
        original_content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Use error (not exception): missing file is an expected case; the traceback adds noise.
        logger.error("File %s does not exist", path)  # noqa: TRY400
        return False
    except OSError:
        logger.exception("Error processing %s", path)
        return False

    new_content = original_content
    for search_text, replace_text in replacements.items():
        if use_regex:
            new_content = re.sub(search_text, replace_text, new_content, flags=re.MULTILINE)
        else:
            new_content = new_content.replace(search_text, replace_text)

    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError:
        logger.exception("Error processing %s", path)
        return False

    return original_content != new_content


def ensure_lines_in_file(path: str | Path, lines: list[str], *, at_top: bool = False) -> bool:
    """Add each line that the file does not already contain, for idempotent edits to config files such as `.gitignore`.

    A line counts as present only when a whole line of the file equals it exactly. Appended lines keep the file's trailing-newline convention.

    Args:
        path (str | Path): Path to the file to edit.
        lines (list[str]): The lines that must be present in the file.
        at_top (bool): Insert missing lines at the top of the file instead of the end. Lines inserted at the top appear in reverse order. Defaults to False.

    Returns:
        bool: True if lines were added, False otherwise.
    """
    path = Path(path) if not isinstance(path, Path) else path

    original_content = path.read_text(encoding="utf-8")
    present = set(original_content.splitlines())
    missing = [line for line in dict.fromkeys(lines) if line not in present]
    if not missing:
        return False

    if at_top:
        new_content = "".join(f"{line}\n" for line in reversed(missing)) + original_content
    else:
        ends_with_newline = original_content.endswith("\n")
        separator = "\n" if original_content and not ends_with_newline else ""
        new_content = original_content + separator + "\n".join(missing)
        if ends_with_newline:
            new_content += "\n"

    path.write_text(new_content, encoding="utf-8")
    return True
