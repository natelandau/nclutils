"""String utilities."""

import math
import random
import re
import string

# Used to compose capture groups.
RS_APOS = "['\u2019]"
DEBURRED_LETTERS = {
    "\xc0": "A",
    "\xc1": "A",
    "\xc2": "A",
    "\xc3": "A",
    "\xc4": "A",
    "\xc5": "A",
    "\xe0": "a",
    "\xe1": "a",
    "\xe2": "a",
    "\xe3": "a",
    "\xe4": "a",
    "\xe5": "a",
    "\xc7": "C",
    "\xe7": "c",
    "\xd0": "D",
    "\xf0": "d",
    "\xc8": "E",
    "\xc9": "E",
    "\xca": "E",
    "\xcb": "E",
    "\xe8": "e",
    "\xe9": "e",
    "\xea": "e",
    "\xeb": "e",
    "\xcc": "I",
    "\xcd": "I",
    "\xce": "I",
    "\xcf": "I",
    "\xec": "i",
    "\xed": "i",
    "\xee": "i",
    "\xef": "i",
    "\xd1": "N",
    "\xf1": "n",
    "\xd2": "O",
    "\xd3": "O",
    "\xd4": "O",
    "\xd5": "O",
    "\xd6": "O",
    "\xd8": "O",
    "\xf2": "o",
    "\xf3": "o",
    "\xf4": "o",
    "\xf5": "o",
    "\xf6": "o",
    "\xf8": "o",
    "\xd9": "U",
    "\xda": "U",
    "\xdb": "U",
    "\xdc": "U",
    "\xf9": "u",
    "\xfa": "u",
    "\xfb": "u",
    "\xfc": "u",
    "\xdd": "Y",
    "\xfd": "y",
    "\xff": "y",
    "\xc6": "Ae",
    "\xe6": "ae",
    "\xde": "Th",
    "\xfe": "th",
    "\xdf": "ss",
    "\xd7": " ",
    "\xf7": " ",
}


# Compiled regexes
RE_APOS = re.compile(RS_APOS)
RS_LATIN1 = re.compile(r"[\xc0-\xff]")
ANSI_CHARS = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")


def camel_case(text: str) -> str:
    """Converts `text` to camel case.

    Args:
        text: String to convert.

    Returns:
        String converted to camel case.

    Example:
        >>> camel_case("FOO BAR_bAz")
        'fooBarBaz'
    """
    text = "".join(word.title() for word in list_words(deburr(text), strip_apostrophes=True))
    return text[:1].lower() + text[1:]


def deburr(text: str) -> str:
    """Convert latin-1 supplementary letters to basic latin letters.

    Convert accented characters and other latin-1 supplementary letters to their basic latin letter equivalents. Use this function to normalize text by removing diacritical marks while preserving the base characters.

    Inspired by https://github.com/dgilland/pydash/

    Args:
        text (str): The text containing latin-1 supplementary letters to convert.

    Returns:
        str: The text with latin-1 supplementary letters converted to basic latin equivalents.

    Examples:
        >>> deburr("déjà vu")
        'deja vu'
        >>> deburr("crème brûlée")
        'creme brulee'
    """
    return RS_LATIN1.sub(lambda match: DEBURRED_LETTERS.get(match.group(), match.group()), text)


def kebab_case(text: str) -> str:
    """Convert text to kebab case by joining words with hyphens in lowercase.

    Transform text into a kebab case string by splitting on word boundaries, converting to lowercase, and joining with hyphens. Also known as spinal case, this format is commonly used in URLs and HTML attributes.

    Args:
        text (str): The text to convert to kebab case.

    Returns:
        str: The text converted to kebab case with words joined by hyphens.

    Example:
        >>> kebab_case("The b c_d-e!f")
        'the-b-c-d-e-f'
    """
    return "-".join(
        word.lower() for word in list_words(deburr(text), strip_apostrophes=True) if word
    )


def list_words(text: str, pattern: str = "", *, strip_apostrophes: bool = False) -> list[str]:
    r"""Split text into a list of words using regex pattern matching.

    Extract words from text by splitting on word boundaries and handling contractions. Optionally use a custom regex pattern for more control over word splitting. Handles apostrophes, underscores, and mixed case text intelligently.

    Args:
        text (str): String to split into words.
        pattern (str): Custom regex pattern to split words on. If not provided, splits on word boundaries. Defaults to "".
        strip_apostrophes (bool): Whether to strip apostrophes from the text before splitting. Defaults to False.

    Returns:
        list[str]: List of words extracted from the text.

    Examples:
        >>> list_words("a b, c; d-e")
        ['a', 'b', 'c', 'd', 'e']
        >>> list_words("fred, barney, & pebbles", "[^, ]+")
        ['fred', 'barney', '&', 'pebbles']
        >>> list_words("fred's horse is fast", strip_apostrophes=True)
        ['freds', 'horse', 'is', 'fast']
        >>> list_words("fred's horse is fast")
        ["fred's", 'horse', 'is', 'fast']
        >>> list_words("this_is_a_test")
        ['this', 'is', 'a', 'test']
        >>> list_words("'They're 1st on the_hunt'")
        ["They're", '1st', 'on', 'the', 'hunt']
    """
    p = (
        re.compile(pattern)
        if pattern
        else re.compile(
            r"""
            \b # word boundary
            (\w+(?:'\w+)?) # word characters including apostrophes followed by parts of word
            \b # word boundary
            """,
            re.VERBOSE | re.IGNORECASE,
        )
    )

    if strip_apostrophes:
        return p.findall(text.replace("_", " ").replace("'", ""))

    return p.findall(text.replace("_", " "))


def pad(text: str, length: int, chars: str = " ") -> str:
    """Pad text on both sides with characters to reach specified length.

    Add padding characters evenly to the left and right sides of the text until it reaches the target length. If the padding cannot be divided evenly, the right side receives the extra character. Truncate the padding characters if they don't divide evenly into the padding length.

    Args:
        text (str): The text to pad on both sides
        length (int): The total desired length of the padded string
        chars (str, optional): The characters to use for padding. Defaults to " "

    Returns:
        str: The text padded on both sides to reach the specified length

    Example:
        >>> pad("abc", 5)
        ' abc '
        >>> pad("abc", 6, "x")
        'xabcxx'
        >>> pad("abc", 5, "...")
        '.abc.'
        >>> pad("abcdefg", 5, "...")
        'abcdefg'
    """
    text_len = len(text)

    if text_len >= length:
        return text

    mid = (length - text_len) / 2.0
    left_len = math.floor(mid)
    right_len = math.ceil(mid)
    chars = pad_end("", right_len, chars)

    return chars[:left_len] + text + chars


def pad_end(text: str, length: int, chars: str = " ") -> str:
    """Pad text on the right side with characters to reach specified length.

    Add padding characters to the right side of the text until it reaches the target length. Truncate the padding characters if they don't divide evenly into the padding length.

    Args:
        text (str): The text to pad on the right side
        length (int): The total desired length of the padded string
        chars (str, optional): The characters to use for padding. Defaults to " "

    Returns:
        str: The text padded on the right side to reach the specified length

    Example:
        >>> pad_end("abc", 5)
        'abc  '
        >>> pad_end("abc", 5, ".")
        'abc..'
    """
    # pylint: disable=redefined-outer-name
    length = max((length, len(text)))
    return (text + chars * int(length))[:length]


def pad_start(text: str, length: int, chars: str = " ") -> str:
    """Pad text on the left side with characters to reach specified length.

    Add padding characters to the left side of the text until it reaches the target length. Truncate the padding characters if they don't divide evenly into the padding length.

    Args:
        text (str): The text to pad on the left side
        length (int): The total desired length of the padded string
        chars (str, optional): The characters to use for padding. Defaults to " "

    Returns:
        str: The text padded on the left side to reach the specified length

    Example:
        >>> pad_start("abc", 5)
        '  abc'
        >>> pad_start("abc", 5, ".")
        '..abc'
    """
    # pylint: disable=redefined-outer-name
    length = max(length, len(text))
    return (chars * int(length) + text)[-length:]


def pascal_case(text: str) -> str:
    """Convert a string to PascalCase format by capitalizing the first letter of each word.

    Transform the input string into PascalCase by first converting to camelCase and then capitalizing the first letter. PascalCase is commonly used for class names in many programming languages.

    Args:
        text (str): The string to convert to PascalCase

    Returns:
        str: The input string converted to PascalCase format

    Example:
        >>> pascal_case("FOO BAR_bAz")
        'FooBarBaz'
    """
    text = camel_case(text)
    return text[:1].upper() + text[1:]


def random_string(length: int) -> str:
    """Generate a random string of ASCII letters with the specified length.

    Create a string by randomly selecting characters from ASCII letters (a-z, A-Z). Useful for generating random identifiers, test data, or temporary names.

    Args:
        length (int): The desired length of the generated string

    Returns:
        str: A string of random ASCII letters with the specified length
    """
    return "".join(random.choice(string.ascii_letters) for _ in range(length))


def separator_case(text: str, separator: str = "-") -> str:
    """Split text into lowercase words and join them with a separator character.

    Convert text into a separated lowercasestring by splitting on word boundaries and joining with the specified separator. Useful for creating consistent string formats like kebab-case or snake_case.

    Args:
        text (str): The text to split and join with separators
        separator (str, optional): Character to join words with. Defaults to "-"

    Returns:
        str: The text split into words and joined with the separator

    Example:
        >>> separator_case("a!!B___c.d")
        'a-b-c-d'
        >>> separator_case("a!!b___c.d", "_")
        'a_b_c_d'
    """
    return separator.join(
        word.lower() for word in list_words(deburr(text), strip_apostrophes=True) if word
    )


def snake_case(text: str) -> str:
    """Convert text to snake case by joining lowercase words with underscores.

    Transform text into a snake case string by splitting on word boundaries, converting to lowercase, and joining with underscores. Snake case is commonly used for variable and function names in Python.

    Args:
        text (str): The text to convert to snake case

    Returns:
        str: The text converted to snake case with words joined by underscores

    Example:
        >>> snake_case("This is Snake Case!")
        'this_is_snake_case'
    """
    return "_".join(
        word.lower() for word in list_words(deburr(text), strip_apostrophes=True) if word
    )


def strip_ansi(text: str) -> str:
    r"""Remove ANSI escape sequences from a string to get plain text output.

    Clean up text that contains ANSI color codes and other escape sequences by removing them while preserving the actual content. Useful when processing terminal output or logs that contain formatting.

    Args:
        text (str): The text containing ANSI escape sequences to remove.

    Returns:
        str: The cleaned text with all ANSI escape sequences removed.

    Example:
        >>> strip_ansi("\x1b[31mHello, World!\x1b[0m")
        'Hello, World!'
    """
    return ANSI_CHARS.sub("", text)


def split_camel_case(string_list: list[str], match_case_list: tuple[str, ...] = ()) -> list[str]:
    """Split strings containing camelCase words into separate words.

    Split each string in the input list into separate words based on camelCase boundaries. Preserve acronyms and any strings specified in match_case_list. For example, 'camelCase' becomes ['camel', 'Case'] but 'CEO' remains intact.

    Args:
        string_list (list[str]): List of strings to split on camelCase boundaries.
        match_case_list (tuple[str, ...], optional): Strings that should not be split. Defaults to ().

    Returns:
        list[str]: List of strings with camelCase words split into separate components.

    Examples:
        >>> split_camel_case(["CamelCase", "SomethingElse", "hello", "CEO"])
        ['Camel', 'Case', 'Something', 'Else', 'hello', 'CEO']
        >>> split_camel_case(["I have a camelCase", "SomethingElse"], ("SomethingElse",))
        ['I', 'have', 'a', 'camel', 'Case', 'SomethingElse']
    """
    result = []
    for item in string_list:
        if item in match_case_list:
            result.append(item)
            continue

        if item.isupper():
            result.append(item)
            continue

        words = re.findall(
            r"[A-Z]{2,}(?=[A-Z][a-z]+|$|[^a-zA-Z])|[A-Z]?[a-z]+|[A-Z](?=[^A-Z]|$)", item
        )

        if len(words) > 1:
            result.extend(words)
        else:
            result.append(item)

    return result
