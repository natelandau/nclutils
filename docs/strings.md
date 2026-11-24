# Strings

String transformations for case conversion, padding, tokenizing, normalizing, and formatting. Import them from `nclutils.strings`.

```python
from nclutils.strings import deburr, list_words, snake_case

snake_case("Café Résumé Builder")  # "cafe_resume_builder"
list_words("fred's horse is fast")  # ["fred's", "horse", "is", "fast"]
deburr("crème brûlée")  # "creme brulee"
```

## Case conversions

The five case helpers accept any text and split it into words the same way. Each one removes accents with `deburr`, splits the text with `list_words`, and removes apostrophes before it joins the words.

| Function         | Example input        | Output            |
| ---------------- | -------------------- | ----------------- |
| `camel_case`     | `"FOO BAR_bAz"`      | `"fooBarBaz"`     |
| `kebab_case`     | `"The b c_d-e!f"`    | `"the-b-c-d-e-f"` |
| `pascal_case`    | `"FOO BAR_bAz"`      | `"FooBarBaz"`     |
| `separator_case` | `"a!!b___c.d"` (`_`) | `"a_b_c_d"`       |
| `snake_case`     | `"This is Snake!"`   | `"this_is_snake"` |

`separator_case` takes a second argument, the separator, which defaults to `-`. Use it to join lowercase words with a separator other than `_` or `-`.

```python
from nclutils.strings import camel_case, separator_case, snake_case

camel_case("read CSV file")  # "readCsvFile"
separator_case("hello world", ".")  # "hello.world"
snake_case("crème brûlée")  # "creme_brulee"
```

## Tokenizing

Two functions split text into words.

### `list_words`

Split text into words on word boundaries. Underscores count as word boundaries, and contractions stay as one word. To remove apostrophes first, pass `strip_apostrophes=True`. To use a different tokenizer, pass a regex pattern as the second argument.

```python
from nclutils.strings import list_words

list_words("a b, c; d-e")
# ["a", "b", "c", "d", "e"]

list_words("Jim's horse is fast")
# ["Jim's", "horse", "is", "fast"]

list_words("Jim's horse is fast", strip_apostrophes=True)
# ["Jims", "horse", "is", "fast"]

# Custom pattern: split on commas and spaces, keep '&'
list_words("fred, barney, & pebbles", "[^, ]+")
# ["fred", "barney", "&", "pebbles"]

list_words("this_is_a_test")
# ["this", "is", "a", "test"]
```

### `split_camel_case`

Split each string in a list on camelCase boundaries and return one flat list. Strings in all capitals, such as acronyms, stay intact. Strings in the optional `match_case_list` tuple also stay intact.

```python
from nclutils.strings import split_camel_case

split_camel_case(["CamelCase", "SomethingElse", "hello", "CEO"])
# ["Camel", "Case", "Something", "Else", "hello", "CEO"]

# Keep a known string intact
split_camel_case(["I have a camelCase", "SomethingElse"], ("SomethingElse",))
# ["I", "have", "a", "camel", "Case", "SomethingElse"]
```

## Normalizing

Two functions remove characters that get in the way of plain-text matching.

### `deburr`

Convert letters with diacritical marks to basic Latin letters: `é` becomes `e`, `ñ` becomes `n`, and `ß` becomes `ss`. Use it to make slugs or to match text against ASCII. `deburr` covers only the Latin-1 Supplement block. It does not transliterate non-Latin scripts.

```python
from nclutils.strings import deburr

deburr("déjà vu")  # "deja vu"
deburr("crème brûlée")  # "creme brulee"
```

### `strip_ansi`

Remove ANSI escape sequences from text. Use it to get plain text from captured terminal output.

```python
from nclutils.strings import strip_ansi

strip_ansi("\x1b[31mHello, World!\x1b[0m")  # "Hello, World!"
```

## Padding

Three functions pad text to a target length: `pad` pads both sides, `pad_end` pads the right, and `pad_start` pads the left. Each takes the text, the target length, and an optional padding string that defaults to a space.

```python
from nclutils.strings import pad, pad_start, pad_end

pad("abc", 5)  # " abc "
pad("abc", 6, "x")  # "xabcxx"   (the right side gets the extra character)
pad_end("abc", 5, ".")  # "abc.."
pad_start("abc", 5, ".")  # "..abc"
```

If the text is already at or longer than the target length, the function returns it unchanged. A multi-character padding string repeats and is cut to fit, so `pad("abc", 5, "...")` returns `".abc."`.

## Other helpers

These functions make random strings and format numbers for display.

### `random_string`

Make a random string of ASCII letters of a given length. It uses `random.choice`, so it is not cryptographically secure. For a secure random identifier, use `nclutils.utils.new_uid`.

```python
from nclutils.strings import random_string

random_string(10)  # a 10-letter string, for example "AbCdEfGhIj"
```

### `human_size`

Format a byte count as a human-readable string. The unit is the largest of `B`, `kB`, `MB`, `GB`, `TB`, `PB`, `EB`, `ZB`, and `YB` that keeps the value less than 1000. Bytes show as integers. The other units show `decimals` decimal places, which defaults to 1. Negative values keep their sign, so you can format a difference between two sizes.

```python
from nclutils.strings import human_size

human_size(512)  # "512 B"
human_size(1500)  # "1.5 kB"
human_size(1000**4)  # "1.0 TB"
human_size(1500, decimals=2)  # "1.50 kB"
human_size(-1500)  # "-1.5 kB"
```

`human_size` uses SI base 1000 and SI unit labels. For binary IEC labels (`KiB`, `MiB` with base 1024), format the value yourself.

### `int_to_emoji`

Convert an integer from 0 to 10 to a keycap emoji. Other integers return as plain strings. With `markdown=True`, the function wraps those strings in Markdown code formatting.

```python
from nclutils.strings import int_to_emoji

int_to_emoji(1)  # ":one:"
int_to_emoji(10)  # ":keycap_ten:"
int_to_emoji(11)  # "11"
int_to_emoji(11, markdown=True)  # "`11`"
int_to_emoji(10, images=True)  # "🔟"
```

By default the output uses Discord-style `:name:` codes, which chat clients show as emoji. With `images=True`, the output uses the Unicode keycap characters.

## API reference

Case conversions:

- `camel_case(text)`. `"hello world"` becomes `"helloWorld"`.
- `kebab_case(text)`. `"hello world"` becomes `"hello-world"`.
- `pascal_case(text)`. `"hello world"` becomes `"HelloWorld"`.
- `separator_case(text, separator="-")`. Split into lowercase words and join them with `separator`.
- `snake_case(text)`. `"hello world"` becomes `"hello_world"`.

Tokenizing:

- `list_words(text, pattern="", *, strip_apostrophes=False) -> list[str]`. Split text into words.
- `split_camel_case(string_list, match_case_list=()) -> list[str]`. Split camelCase strings, and keep the listed strings intact.

Normalizing:

- `deburr(text)`. Convert Latin-1 letters with diacritical marks to basic Latin letters.
- `strip_ansi(text)`. Remove ANSI escape sequences.

Padding:

- `pad(text, length, chars=" ")`. Pad on both sides.
- `pad_end(text, length, chars=" ")`. Pad on the right.
- `pad_start(text, length, chars=" ")`. Pad on the left.

Other helpers:

- `human_size(size_bytes, *, decimals=1)`. Format a byte count with an SI unit from `B` to `YB`, base 1000.
- `int_to_emoji(num, *, markdown=False, images=False)`. Convert 0 to 10 to a keycap emoji.
- `random_string(length)`. Random string of ASCII letters, not cryptographically secure.

All functions return `str` unless the signature shows a different type.
