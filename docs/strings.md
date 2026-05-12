# Strings

A grab bag of string transformations: case conversions, padding, tokenizing, and a few small helpers. Imported from `nclutils.strings`.

```python
from nclutils.strings import deburr, list_words, snake_case

snake_case("Café Résumé Builder")  # "cafe_resume_builder"
list_words("fred's horse is fast")  # ["fred's", "horse", "is", "fast"]
deburr("crème brûlée")              # "creme brulee"
```

## Case conversions

All five case helpers accept arbitrary text and tokenize it the same way: `list_words` splits on word boundaries, contractions are folded, and accents are stripped via `deburr` before joining.

| Function         | Example input        | Output            |
| ---------------- | -------------------- | ----------------- |
| `camel_case`     | `"FOO BAR_bAz"`      | `"fooBarBaz"`     |
| `kebab_case`     | `"The b c_d-e!f"`    | `"the-b-c-d-e-f"` |
| `pascal_case`    | `"FOO BAR_bAz"`      | `"FooBarBaz"`     |
| `separator_case` | `"a!!b___c.d"` (`_`) | `"a_b_c_d"`       |
| `snake_case`     | `"This is Snake!"`   | `"this_is_snake"` |

`separator_case` takes a second argument, the joiner character, and defaults to `-`. Use it when you want a separator other than `_` or `-` without writing your own join.

```python
from nclutils.strings import camel_case, separator_case, snake_case

camel_case("read CSV file")             # "readCsvFile"
separator_case("hello world", ".")      # "hello.world"
snake_case("crème brûlée")              # "creme_brulee"
```

## Tokenizing

### `list_words`

Split text into words on word boundaries while keeping contractions intact. Pass a custom regex pattern to override the default tokenizer.

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

Break camelCase tokens into separate words while preserving acronyms and an optional list of strings that shouldn't be split.

```python
from nclutils.strings import split_camel_case

split_camel_case(["CamelCase", "SomethingElse", "hello", "CEO"])
# ["Camel", "Case", "Something", "Else", "hello", "CEO"]

# Preserve a known token
split_camel_case(["I have a camelCase", "SomethingElse"], ("SomethingElse",))
# ["I", "have", "a", "camel", "Case", "SomethingElse"]
```

## Normalizing

### `deburr`

Strip Latin-1 diacritical marks: `é` becomes `e`, `ñ` becomes `n`, `ß` becomes `ss`, and so on. Useful for slug generation and case-insensitive matching against ASCII.

```python
from nclutils.strings import deburr

deburr("déjà vu")        # "deja vu"
deburr("crème brûlée")   # "creme brulee"
```

`deburr` covers the Latin-1 supplementary block. It does not transliterate non-Latin scripts.

### `strip_ansi`

Remove ANSI escape sequences from text. Handy when you've captured terminal output and want plain text back.

```python
from nclutils.strings import strip_ansi

strip_ansi("\x1b[31mHello, World!\x1b[0m")  # "Hello, World!"
```

## Padding

Three variants: pad on both sides (`pad`), the right (`pad_end`), or the left (`pad_start`). All take the target length and an optional padding string.

```python
from nclutils.strings import pad, pad_start, pad_end

pad("abc", 5)              # " abc "
pad("abc", 6, "x")         # "xabcxx"   (right gets the extra char)
pad_end("abc", 5, ".")     # "abc.."
pad_start("abc", 5, ".")   # "..abc"
```

If the text is already at or beyond the target length, the original string is returned unchanged. Multi-character `chars` are repeated and truncated to fit, so `pad("abc", 5, "...")` becomes `".abc."`.

## Misc

### `random_string`

Generate a random ASCII letter string of a given length. Uses `random.choice`, so it's not cryptographically secure; for that, use `nclutils.utils.new_uid` instead.

```python
from nclutils.strings import random_string

random_string(10)  # e.g. "AbCdEfGhIj"
```

### `human_size`

Format a byte count as a human-readable string. Picks the largest of `B`, `KB`, `MB`, `GB`, `TB`, `PB`, `EB`, `ZB`, `YB` at which the value falls below the next 1024-multiple, and renders with one decimal place by default. Bytes are always rendered as integers; the `decimals` kwarg controls precision for the rest. Negative inputs keep their sign, which is handy for byte-count diffs.

```python
from nclutils.strings import human_size

human_size(512)              # "512 B"
human_size(1536)             # "1.5 KB"
human_size(1024 ** 4)        # "1.0 TB"
human_size(1024 ** 5)        # "1.0 PB"
human_size(1024 ** 8)        # "1.0 YB"
human_size(1536, decimals=2) # "1.50 KB"
human_size(-1536)            # "-1.5 KB"
```

Values past YB stay on the YB unit rather than rolling over, so `human_size(1024 ** 9)` returns `"1024.0 YB"`. Uses base 1024 with traditional unit labels (`KB`, `MB`, etc.); if your context requires strict IEC labeling (`KiB`, `MiB`), format the value yourself.

### `int_to_emoji`

Render integers 0–10 as keycap emoji. Numbers outside that range come back as plain strings, optionally wrapped in Markdown code formatting.

```python
from nclutils.strings import int_to_emoji

int_to_emoji(1)                  # ":one:"
int_to_emoji(10)                 # ":keycap_ten:"
int_to_emoji(11)                 # "11"
int_to_emoji(11, markdown=True)  # "`11`"
int_to_emoji(10, images=True)    # "🔟"
```

Without `images=True`, the output uses Discord-style `:name:` codes that render in chat clients. With `images=True`, the output uses the actual Unicode keycap glyphs.

## API reference

Case conversions:

- `camel_case(text)`. `"hello world"` becomes `"helloWorld"`.
- `kebab_case(text)`. `"hello world"` becomes `"hello-world"`.
- `pascal_case(text)`. `"hello world"` becomes `"HelloWorld"`.
- `separator_case(text, separator="-")`. Generic split-and-rejoin with a configurable separator.
- `snake_case(text)`. `"hello world"` becomes `"hello_world"`.

Tokenizing:

- `list_words(text, pattern="", *, strip_apostrophes=False)`. Split text into words.
- `split_camel_case(string_list, match_case_list=())`. Break camelCase tokens, optionally preserving listed strings.

Normalizing:

- `deburr(text)`. Strip Latin-1 diacritical marks.
- `strip_ansi(text)`. Remove ANSI escape sequences.

Padding:

- `pad(text, length, chars=" ")`. Pad on both sides.
- `pad_end(text, length, chars=" ")`. Pad on the right.
- `pad_start(text, length, chars=" ")`. Pad on the left.

Misc:

- `human_size(size_bytes, *, decimals=1)`. Format a byte count as `B`/`KB`/`MB`/`GB`/`TB`/`PB`/`EB`/`ZB`/`YB`. Base 1024.
- `int_to_emoji(num, *, markdown=False, images=False)`. Render 0–10 as keycap emoji.
- `random_string(length)`. Random ASCII letter string (not cryptographically secure).
