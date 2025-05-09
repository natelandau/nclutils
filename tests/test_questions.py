"""Tests for the questions module."""

from dataclasses import dataclass
from pathlib import Path

import questionary

from nclutils import choose_multiple_from_list, choose_one_from_list


def test_choose_from_list_path(mocker):
    """Test the choose_from_list function with a list of paths."""
    # Given: A list of path choices
    choices = [
        Path("test"),
        Path("test2"),
        Path("test3"),
    ]

    # When: Mocking questionary.select and selecting "test2"
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = Path("test2")
    result = choose_one_from_list(choices, "Choose a path")

    # Then: The selected path is returned
    assert result == Path("test2")


def test_choose_from_list_tuple(mocker):
    """Test the choose_from_list function with a list of tuples."""

    @dataclass
    class Something:
        name: str
        number: int

    # Given: A list of tuple choices
    choices = [
        ("test", Something(name="test", number=1)),
        ("test2", Something(name="test2", number=2)),
        ("test3", Something(name="test3", number=3)),
    ]

    # When: Mocking questionary.select and selecting "test2"
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = Something(name="test2", number=2)
    result = choose_one_from_list(choices, "Choose a path")

    # Then: The selected path is returned
    assert result == Something(name="test2", number=2)


def test_choose_from_list_dict(mocker):
    """Test the choose_from_list function with a list of dictionaries."""

    @dataclass
    class Something:
        name: str
        number: int

    # Given: A list of tuple choices
    choices = [
        {"test": Something(name="test", number=1)},
        {"test2": Something(name="test2", number=2)},
        {"test3": Something(name="test3", number=3)},
    ]

    # When: Mocking questionary.select and selecting "test2"
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = Something(name="test2", number=2)
    result = choose_one_from_list(choices, "Choose a path")

    # Then: The selected path is returned
    assert result == Something(name="test2", number=2)


def test_choose_from_list_path_multiple(mocker):
    """Test the choose_from_list function with a list of paths."""
    # Given: A list of path choices
    choices = [
        Path("test"),
        Path("test2"),
        Path("test3"),
    ]

    # When: Mocking questionary.checkbox and selecting multiple paths
    mock_select = mocker.patch("questionary.checkbox")
    mock_select.return_value.ask.return_value = [Path("test"), Path("test2")]
    result = choose_multiple_from_list(choices, "Choose a path")

    # Then: The selected paths are returned as a list
    assert result == [Path("test"), Path("test2")]


def test_choose_from_list_tuple_multiple(mocker):
    """Test the choose_from_list function with a list of tuples."""

    @dataclass
    class Something:
        name: str
        number: int

    # Given: A list of tuple choices
    choices = [
        ("test", Something(name="test", number=1)),
        ("test2", Something(name="test2", number=2)),
        ("test3", Something(name="test3", number=3)),
    ]

    # When: Mocking questionary.select and selecting "test2"
    mock_select = mocker.patch("questionary.checkbox")
    mock_select.return_value.ask.return_value = [
        Something(name="test2", number=2),
        Something(name="test3", number=3),
    ]
    result = choose_multiple_from_list(choices, "Choose a path")

    # Then: The selected path is returned
    assert result == [
        Something(name="test2", number=2),
        Something(name="test3", number=3),
    ]


def test_choose_from_list_dict_multiple(mocker):
    """Test the choose_from_list function with a list of dictionaries."""

    @dataclass
    class Something:
        name: str
        number: int

    # Given: A list of tuple choices
    choices = [
        {"test": Something(name="test", number=1)},
        {"test2": Something(name="test2", number=2)},
        {"test3": Something(name="test3", number=3)},
    ]

    # When: Mocking questionary.select and selecting "test2"
    mock_select = mocker.patch("questionary.checkbox")
    mock_select.return_value.ask.return_value = [
        Something(name="test2", number=2),
        Something(name="test3", number=3),
    ]
    result = choose_multiple_from_list(choices, "Choose a path")

    # Then: The selected path is returned
    assert result == [
        Something(name="test2", number=2),
        Something(name="test3", number=3),
    ]


def test_choose_from_list_string(mocker):
    """Test the choose_from_list function with a list of strings."""
    # Given: A list of string choices
    choices = [
        "test",
        "test2",
        "test3",
    ]

    # When: Mocking questionary.select and selecting "test2"
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "test2"
    result = choose_one_from_list(choices, "Choose a string")

    # Then: The selected string is returned
    assert result == "test2"


def test_choose_from_list_string_multiple(mocker):
    """Test the choose_from_list function with a list of strings."""
    # Given: A list of string choices
    choices = [
        "test",
        "test2",
        "test3",
    ]

    # When: Mocking questionary.checkbox and selecting multiple strings
    mock_select = mocker.patch("questionary.checkbox")
    mock_select.return_value.ask.return_value = ["test", "test2"]
    result = choose_multiple_from_list(choices, "Choose a string")

    # Then: The selected strings are returned as a list
    assert result == ["test", "test2"]


def test_choose_from_list_choice(mocker):
    """Test the choose_from_list function with a list of choices."""
    # Given: A list of questionary Choice objects
    choices = [
        questionary.Choice(title="test", value="test"),
        questionary.Choice(title="test2", value="test2"),
        questionary.Choice(title="test3", value="test3"),
    ]

    # When: Mocking questionary.select and selecting "test"
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "test"
    result = choose_one_from_list(choices, "Choose a string")

    # Then: The selected choice value is returned
    assert result == "test"


def test_choose_from_list_no_choices(mocker):
    """Test the choose_from_list function with no choices."""
    # Given: An empty list of choices
    choices = []

    # When: Calling choose_from_list with empty choices
    result = choose_one_from_list(choices, "Choose a string")

    # Then: None is returned
    assert result is None


def test_choose_from_list_no_choices_multiple(mocker):
    """Test the choose_from_list function with no choices."""
    # Given: An empty list of choices
    choices = []

    # When: Calling choose_from_list with empty choices
    result = choose_multiple_from_list(choices, "Choose a string")

    # Then: None is returned
    assert result is None


def test_choose_from_list_no_selection(mocker):
    """Test the choose_from_list function with no selection."""
    # Given: A list of string choices
    choices = [
        "test",
        "test2",
        "test3",
    ]

    # When: Mocking questionary.select and returning None (no selection)
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = None
    result = choose_one_from_list(choices, "Choose a string")

    # Then: None is returned
    assert result is None


def test_choose_from_list_no_selection_multiple(mocker):
    """Test the choose_from_list function with no selection."""
    # Given: A list of string choices
    choices = [
        "test",
        "test2",
        "test3",
    ]

    # When: Mocking questionary.checkbox and returning None (no selection)
    mock_select = mocker.patch("questionary.checkbox")
    mock_select.return_value.ask.return_value = None
    result = choose_multiple_from_list(choices, "Choose a string")

    # Then: None is returned
    assert result is None
