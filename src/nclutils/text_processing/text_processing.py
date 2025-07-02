"""Document utilities."""

import re
from pathlib import Path

from nclutils.logging.logging import logger


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
        if not path.exists():
            logger.error(f"File {path} does not exist")
            return False

        original_content = path.read_text(encoding="utf-8")
        new_content = original_content

        for search_text, replace_text in replacements.items():
            if use_regex:
                new_content = re.sub(search_text, replace_text, new_content, flags=re.MULTILINE)
            else:
                new_content = new_content.replace(search_text, replace_text)

        path.write_text(new_content, encoding="utf-8")

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error processing {path}: {e}")
        return False

    return original_content != new_content


def ensure_lines_in_file(path: str | Path, lines: list[str], *, at_top: bool = False) -> bool:
    """Ensure lines are in a file.

    Args:
        path (str): Path to the file to ensure the line is in.
        lines (list[str]): The lines to ensure are in the file.
        at_top (bool): Whether to add the lines at the top of the file. Defaults to False.

    Returns:
        bool: True if lines were added, False otherwise.
    """
    path = Path(path) if not isinstance(path, Path) else path

    original_content = path.read_text(encoding="utf-8")
    new_content = original_content

    for line in lines:
        if not re.search(rf"^{line}$", new_content, flags=re.MULTILINE):
            if at_top:
                new_content = f"{line}\n{new_content}"
            else:
                new_content += f"\n{line}"

    path.write_text(new_content, encoding="utf-8")

    return original_content != new_content
