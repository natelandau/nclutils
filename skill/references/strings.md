# `nclutils.strings` reference

```python
# Case conversion
camel_case(text: str) -> str
pascal_case(text: str) -> str
kebab_case(text: str) -> str
snake_case(text: str) -> str
separator_case(text: str, separator: str = "-") -> str

# Tokenizing
list_words(text: str, pattern: str = "", *, strip_apostrophes: bool = False) -> list[str]
split_camel_case(string_list: list[str], match_case_list: tuple[str, ...] = ()) -> list[str]

# Normalizing
deburr(text: str) -> str
strip_ansi(text: str) -> str

# Padding
pad(text: str, length: int, chars: str = " ") -> str
pad_start(text: str, length: int, chars: str = " ") -> str
pad_end(text: str, length: int, chars: str = " ") -> str

# Other
human_size(size_bytes: float, *, decimals: int = 1) -> str
int_to_emoji(num: int, *, markdown: bool = False, images: bool = False) -> str
random_string(length: int) -> str
```

## Case conversion

All five run `deburr`, then `list_words(..., strip_apostrophes=True)`, then join. `separator_case` is the general form; `kebab_case` and `snake_case` are `separator_case` with `-` and `_`.

```python
camel_case("FOO BAR_bAz")         # "fooBarBaz"
pascal_case("FOO BAR_bAz")        # "FooBarBaz"
kebab_case("The b c_d-e!f")       # "the-b-c-d-e-f"
snake_case("Jim's crème brûlée")  # "jims_creme_brulee"
separator_case("a!!b___c.d", "_") # "a_b_c_d"
```

Gotchas:

- camelCase input is not split: `snake_case("fooBar")` -> `"foobar"`. Run `split_camel_case` on the words first.
- Only ASCII `'` is removed. A curly apostrophe (U+2019) splits the word: `kebab_case("Jim’s")` -> `"jim-s"`.
- `camel_case` and `pascal_case` use `str.title()` per word: `camel_case("1st place")` -> `"1StPlace"`.

## Tokenizing

### `list_words`

- Default pattern: `\b(\w+(?:'\w+)?)\b`, keeps contractions (`"Jim's"`).
- Underscores are word boundaries (replaced with spaces before matching).
- `pattern` (second positional arg): custom regex; returns `re.findall` matches.
- `strip_apostrophes=True`: removes ASCII `'` before matching (`"Jim's"` -> `"Jims"`).

```python
list_words("a b, c; d-e")                         # ["a", "b", "c", "d", "e"]
list_words("this_is_a_test")                      # ["this", "is", "a", "test"]
list_words("fred, barney, & pebbles", "[^, ]+")   # ["fred", "barney", "&", "pebbles"]
```

### `split_camel_case`

Takes a list of strings, returns one flat list.

- Item in `match_case_list` or all uppercase -> kept whole.
- Otherwise split on camelCase boundaries and whitespace; acronyms stay together (`"HTTPServer"` -> `["HTTP", "Server"]`).
- Digits and punctuation are dropped when an item splits: `"abc123Def"` -> `["abc", "Def"]`.

```python
split_camel_case(["CamelCase", "hello", "CEO"])                         # ["Camel", "Case", "hello", "CEO"]
split_camel_case(["I have a camelCase", "SomethingElse"], ("SomethingElse",))
# ["I", "have", "a", "camel", "Case", "SomethingElse"]
```

## Normalizing

- `deburr`: maps Latin-1 letters (U+00C0 to U+00FF) to ASCII: `é` -> `e`, `ß` -> `ss`, `Æ` -> `Ae`; `×` and `÷` -> space. Other scripts pass through unchanged.
- `strip_ansi`: removes ANSI escape sequences.

## Padding

- `pad`: both sides; odd remainder goes to the right.
- `pad_start`: left. `pad_end`: right.
- `text` at or past `length` -> returned unchanged.
- Multi-char `chars` repeats and is truncated to fit: `pad("abc", 5, "...")` -> `".abc."`.

## Other

- `human_size`: SI units, base 1000: `B`, `kB`, `MB`, `GB`, `TB`, `PB`, `EB`, `ZB`, `YB`. Bytes render as integers (`"512 B"`); larger units use `decimals` (`human_size(1500)` -> `"1.5 kB"`). Negatives keep the sign. Past YB stays on YB: `human_size(1000 ** 9)` -> `"1000.0 YB"`.
- `int_to_emoji`: 0 to 10 -> Discord codes (`":one:"`, `":keycap_ten:"`); `images=True` -> Unicode keycap glyphs. Other numbers -> `str(num)`; with `markdown=True`, wrapped in backticks (`` "`11`" ``).
- `random_string`: ASCII letters (a-z, A-Z) via `random.choice`, not cryptographically secure. For secure IDs use `nclutils.utils.new_uid`.
