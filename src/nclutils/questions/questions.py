"""Provide utilities for interactive user prompts and selections."""

from pathlib import Path
from typing import TypeAlias, TypeVar, overload

import questionary

from nclutils.constants import CHOICE_STYLE

V = TypeVar("V", bound=Path | str | int | float | bool)
T = TypeVar("T")
ConfigTuple: TypeAlias = tuple[str, T]
ConfigDict: TypeAlias = dict[str, T]


@overload
def choose_one_from_list(
    choices: list[V],
    message: str,
) -> V | None: ...


@overload
def choose_one_from_list(
    choices: list[ConfigTuple[T]],
    message: str,
) -> T | None: ...


@overload
def choose_one_from_list(
    choices: list[ConfigDict[T]],
    message: str,
) -> T | None: ...


def choose_one_from_list(
    choices: list[V] | list[ConfigTuple[T]] | list[ConfigDict[T]],
    message: str,
) -> V | T | None:
    """Present an interactive single-choice selection prompt to the user.

    Displays a list of choices and allows the user to select one option. The choices can be provided in different formats:
    - A list of simple values (Path, str, int, float, bool)
    - A list of tuples where first element is display text and second is the value
    - A list of single-key dictionaries mapping display text to values

    For Path objects, the filename is automatically used as the display text.
    The prompt uses questionary's select widget with custom styling.

    Args:
        choices: List of options to choose from. Can be:
            - list[V]: Direct list of values
            - list[tuple[str, T]]: List of (display_text, value) tuples
            - list[dict[str, T]]: List of {display_text: value} dicts
        message: The prompt text shown to the user

    Returns:
        The selected value from the choices list, or None if:
        - No selection was made
        - The choices list is empty
        - The user cancelled the selection
    """
    if not choices:
        return None

    select_list = []

    for c in choices:
        if isinstance(c, Path):
            select_list.append(questionary.Choice(title=c.name, value=c))
        elif isinstance(c, tuple):
            select_list.append(questionary.Choice(title=c[0], value=c[1]))
        elif isinstance(c, dict):
            key = next(iter(c.keys()))
            value = c[key]
            select_list.append(questionary.Choice(title=key, value=value))
        else:
            select_list.append(questionary.Choice(title=str(c), value=c))

    selection = questionary.select(message, choices=select_list, style=CHOICE_STYLE, qmark="").ask()

    if selection is None or not selection:
        return None

    return selection


@overload
def choose_multiple_from_list(
    choices: list[V],
    message: str,
) -> list[V] | None: ...


@overload
def choose_multiple_from_list(
    choices: list[ConfigTuple[T]],
    message: str,
) -> list[T] | None: ...


@overload
def choose_multiple_from_list(
    choices: list[ConfigDict[T]],
    message: str,
) -> list[T] | None: ...


def choose_multiple_from_list(
    choices: list[V] | list[ConfigTuple[T]] | list[ConfigDict[T]],
    message: str,
) -> list[V] | list[T] | None:
    """Allow selection of multiple items from a list through an interactive checkbox prompt.

    Convert input choices into questionary.Choice objects with appropriate titles and values. Display an interactive checkbox prompt allowing users to select multiple items from the list. For Path objects, use the filename as the display title.

    Args:
        choices (list[V] | list[ConfigTuple[T]] | list[ConfigDict[T]]): Available options to select from. Can be a list of Path, str, int, float, bool values or a list of tuples/dicts mapping display text to values.
        message (str): Prompt text shown to the user

    Returns:
        list[V | T] | None: List of selected items from the choices list. Returns None if no selections are made or choices list is empty.
    """
    if not choices:
        return None

    select_list = []

    for c in choices:
        if isinstance(c, Path):
            select_list.append(questionary.Choice(title=c.name, value=c))
        elif isinstance(c, tuple):
            select_list.append(questionary.Choice(title=c[0], value=c[1]))
        elif isinstance(c, dict):
            key = next(iter(c.keys()))
            value = c[key]
            select_list.append(questionary.Choice(title=key, value=value))
        else:
            select_list.append(questionary.Choice(title=str(c), value=c))

    selection = questionary.checkbox(
        message, choices=select_list, style=CHOICE_STYLE, qmark=""
    ).ask()

    if selection is None or not selection:
        return None

    return selection
