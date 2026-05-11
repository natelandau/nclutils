# `nclutils.strings` reference

Case conversions, padding, tokenizing, normalization.

## Case conversions

All five accept arbitrary text and tokenize the same way: `list_words` splits on word boundaries, contractions are folded, accents stripped via `deburr` before joining.

```python
from nclutils.strings import camel_case, kebab_case, pascal_case, separator_case, snake_case

camel_case("FOO BAR_bAz")          # "fooBarBaz"
kebab_case("The b c_d-e!f")         # "the-b-c-d-e-f"
pascal_case("FOO BAR_bAz")          # "FooBarBaz"
separator_case("a!!b___c.d", "_")   # "a_b_c_d"
snake_case("This is Snake!")        # "this_is_snake"
snake_case("crème brûlée")          # "creme_brulee"
```

`separator_case(text, separator="-")` is the generic version; the others are presets.

## Tokenizing

### `list_words(text, pattern="", *, strip_apostrophes=False) -> list[str]`

Split text into words on word boundaries while keeping contractions intact.

```python
list_words("a b, c; d-e")                            # ["a", "b", "c", "d", "e"]
list_words("Jim's horse is fast")                    # ["Jim's", "horse", "is", "fast"]
list_words("Jim's horse is fast", strip_apostrophes=True)  # ["Jims", ...]
list_words("fred, barney, & pebbles", "[^, ]+")      # ["fred", "barney", "&", "pebbles"]
list_words("this_is_a_test")                         # ["this", "is", "a", "test"]
```

### `split_camel_case(string_list, match_case_list=()) -> list[str]`

Break camelCase tokens, preserving acronyms and an optional allowlist of strings that shouldn't be split.

```python
split_camel_case(["CamelCase", "SomethingElse", "hello", "CEO"])
# ["Camel", "Case", "Something", "Else", "hello", "CEO"]

split_camel_case(["I have a camelCase", "SomethingElse"], ("SomethingElse",))
# ["I", "have", "a", "camel", "Case", "SomethingElse"]
```

## Normalizing

- `deburr(text)` — strip Latin-1 diacritical marks: `é` → `e`, `ñ` → `n`, `ß` → `ss`. Does NOT transliterate non-Latin scripts.
- `strip_ansi(text)` — remove ANSI escape sequences. Handy after capturing terminal output.

## Padding

- `pad(text, length, chars=" ")` — pad both sides. Right gets the extra char on odd lengths.
- `pad_start(text, length, chars=" ")` — left-pad.
- `pad_end(text, length, chars=" ")` — right-pad.

If text is already at or beyond `length`, returned unchanged. Multi-char `chars` repeats and truncates to fit (`pad("abc", 5, "...")` → `".abc."`).

## Misc

- `random_string(length)` — random ASCII letter string. Uses `random.choice`, NOT cryptographically secure. For secure IDs, use `nclutils.utils.new_uid`.
- `int_to_emoji(num, *, markdown=False, images=False)` — render 0–10 as keycap emoji.
    - Default: Discord `:name:` codes (`:one:`, `:keycap_ten:`).
    - `images=True`: actual Unicode glyphs (`🔟`).
    - Numbers outside 0–10 come back as plain strings; `markdown=True` wraps them in backticks.

## Signatures

```python
# Case conversions
camel_case(text: str) -> str
kebab_case(text: str) -> str
pascal_case(text: str) -> str
separator_case(text: str, separator: str = "-") -> str
snake_case(text: str) -> str

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

# Misc
int_to_emoji(num: int, *, markdown: bool = False, images: bool = False) -> str
random_string(length: int) -> str
```
