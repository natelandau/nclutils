# `nclutils.ask` / `nclutils.net` / `nclutils.text` / `nclutils.utils` reference

## `nclutils.ask`

Interactive prompts built on [`questionary`](https://github.com/tmbo/questionary).

```python
V = TypeVar("V", bound=Path | str | int | float | bool)
T = TypeVar("T")

choose_one_from_list(choices: list[V], message: str) -> V | None
choose_one_from_list(choices: list[tuple[str, T]], message: str) -> T | None
choose_one_from_list(choices: list[dict[str, T]], message: str) -> T | None

choose_multiple_from_list(choices: list[V], message: str) -> list[V] | None
choose_multiple_from_list(choices: list[tuple[str, T]], message: str) -> list[T] | None
choose_multiple_from_list(choices: list[dict[str, T]], message: str) -> list[T] | None
```

`@overload`s narrow the return type by choice shape. Use one shape per call; mixed shapes run but lose narrowing.

| Choice shape | Label shown | Value returned |
| --- | --- | --- |
| `Path` | `path.name` | the `Path` |
| `str`, `int`, etc. | `str(value)` | the value |
| `(label, value)` | `label` | `value` |
| `{label: value}` | first key (insertion order) | its value |

```python
from nclutils.ask import choose_one_from_list

target = choose_one_from_list([("US prod", "us-east-1"), ("EU prod", "eu-west-1")], "Deploy to")
if target is None:
    ...  # cancelled, or no choices
```

Returns `None` when:

- `choices` is empty.
- User presses Ctrl-C (Esc does not cancel).
- `choose_multiple_from_list`: user submits with nothing selected. Never returns `[]`.

## `nclutils.net`

```python
network_available(address: str = "8.8.4.4", port: int = 53, timeout: int = 5) -> bool
```

- `True` if `socket.create_connection((address, port), timeout=timeout)` succeeds; closes the connection.
- Any exception (unresolvable host, refused, timeout) -> `False`. Never raises.
- Plain TCP connect, not a DNS query. A hostname `address` is resolved first.

```python
from nclutils.net import network_available

network_available(address="github.com", port=443, timeout=2)
```

## `nclutils.text`

In-place file edits, UTF-8 read and write. Both return `True` if the content changed, else `False`. Both rewrite the file even when nothing changed. Diagnostics go to the `nclutils.text` stdlib logger.

### `replace_in_file`

```python
replace_in_file(path: str | Path, replacements: dict[str, str], *, use_regex: bool = False) -> bool
```

- `use_regex=False`: `str.replace` for each key -> value.
- `use_regex=True`: each key is a pattern, `re.sub(key, value, content, flags=re.MULTILINE)`. Values accept backreferences (`r"\1"`).
- Applied in dict order; each replacement sees the output of the previous one.
- Missing file -> logs `ERROR`, returns `False`.
- Other `OSError` on read or write -> logs the exception, returns `False`.
- Invalid pattern with `use_regex=True` -> raises `re.error`.

### `ensure_lines_in_file`

```python
ensure_lines_in_file(path: str | Path, lines: list[str], *, at_top: bool = False) -> bool
```

Adds each line not already present. A line is present when a whole line of the file equals it exactly (no regex). `at_top=True` prepends. Writes only when a line is added.

Gotchas:

- Appended lines keep the file's trailing-newline convention: `"a\n"` -> `"a\nb\n"`, `"a"` -> `"a\nb"`, `""` -> `"b"`. Duplicate input lines are added once.
- `at_top=True` prepends each line in turn, so multiple lines land in reverse order: `["a", "b"]` -> `"b\na\n..."`.
- Raises `FileNotFoundError` and other `OSError` (unlike `replace_in_file`).

```python
from nclutils.text import ensure_lines_in_file

ensure_lines_in_file(".gitignore", [".env", "build/"])
```

## `nclutils.utils`

```python
iso_timestamp(*, microseconds: bool = False) -> str
format_iso_timestamp(datetime_obj: datetime, *, microseconds: bool = False) -> str
new_uid(bits: int = 64) -> str
new_timestamp_uid(bits: int = 32) -> str
unique_id(prefix: str = "") -> str
check_python_version(major: int, minor: int) -> bool
```

### Timestamps

- ISO 8601 in UTC with a `Z` suffix: `"2026-05-04T18:32:01Z"`; `microseconds=True` -> `"2026-05-04T18:32:01.847239Z"`.
- `iso_timestamp`: current time.
- `format_iso_timestamp`: calls `datetime_obj.astimezone(UTC)` first. Naive datetimes are read as local time, then converted.

### IDs

| Function | Output |
| --- | --- |
| `new_uid(bits)` | Lowercase letters and digits, length `int(bits / 5.16) + 1`: 7 for 32, 13 for 64, 25 for 128. `random.SystemRandom`, safe for secrets and filenames. |
| `new_timestamp_uid(bits)` | `"YYYYMMDDTHHMMSS-" + new_uid(bits)`, UTC. Sorts by creation second. Default suffix: 7 chars. |
| `unique_id(prefix)` | `f"{prefix}{n}"`, `n` a process-wide counter starting at 1: `"1"`, `"id_2"`, `"3"`. |

`unique_id` gotchas: counter shared by all callers, not thread-safe (duplicates under concurrency), resets on restart. Use `new_uid` for IDs that must be unique across threads, processes, or runs.

### `check_python_version`

Returns `sys.version_info >= (major, minor)`. Package minimum is Python 3.11.

```python
from nclutils.utils import check_python_version

if check_python_version(3, 12):
    ...  # 3.12+ only code path
```
