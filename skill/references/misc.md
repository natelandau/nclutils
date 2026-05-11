# `nclutils.ask` / `nclutils.net` / `nclutils.text` / `nclutils.utils` reference

The smaller modules. One reference page covers them all.

---

## `nclutils.ask`

Two thin wrappers around [`questionary`](https://github.com/tmbo/questionary).

```python
from nclutils.ask import choose_one_from_list, choose_multiple_from_list

color = choose_one_from_list(["red", "green", "blue"], "Pick a color")
if color is None:
    print("cancelled")
```

Both return `None` when the user cancels (Esc / Ctrl-C), the choices list is empty, OR (for `choose_multiple_from_list`) the user submits without selecting anything. The source check is `if selection is None or not selection: return None` — an empty selection yields `None`, NOT `[]`.

### Signatures (overloaded)

Both functions are `@overload`-decorated so the return type narrows by the input shape:

```python
V = TypeVar("V", bound=Path | str | int | float | bool)
T = TypeVar("T")

# choose_one_from_list
@overload
def choose_one_from_list(choices: list[V], message: str) -> V | None: ...
@overload
def choose_one_from_list(choices: list[tuple[str, T]], message: str) -> T | None: ...
@overload
def choose_one_from_list(choices: list[dict[str, T]], message: str) -> T | None: ...

# choose_multiple_from_list
@overload
def choose_multiple_from_list(choices: list[V], message: str) -> list[V] | None: ...
@overload
def choose_multiple_from_list(choices: list[tuple[str, T]], message: str) -> list[T] | None: ...
@overload
def choose_multiple_from_list(choices: list[dict[str, T]], message: str) -> list[T] | None: ...
```

Practical effect: pass a plain `list[Path]` → typed as `Path | None`. Pass `list[tuple[str, MyEnum]]` → typed as `MyEnum | None`. The runtime implementation accepts any of the three shapes; the overloads are purely for type narrowing.

### Choice formats

Three accepted input shapes — pick ONE per prompt (mixing works at runtime but loses type narrowing):

```python
# 1. Plain values — display string is str() of value, except Path which uses path.name
choose_one_from_list([Path("./conf/dev.toml"), Path("./conf/prod.toml")], "Pick")

# 2. (label, value) tuples — display the label, return the value
choose_one_from_list(
    [("US prod", Profile(region="us-east-1")), ("EU prod", Profile(region="eu-west-1"))],
    "Deployment target",
)

# 3. Single-key dicts — same as tuple form. For multi-key dicts, only the FIRST key (insertion order, via `next(iter(...))`) is used.
choose_multiple_from_list(
    [{"Frontend": "fe"}, {"Backend": "be"}, {"Infra": "infra"}],
    "Which teams?",
)
```

Internally, every choice becomes a `questionary.Choice(title=..., value=...)`. `Path` instances render their `.name`; other primitives use `str(value)`.

> [!NOTE]
> The legacy import `nclutils.questions` still works but is deprecated and will be removed in v4.0.0. New code should use `nclutils.ask`.

---

## `nclutils.net`

Lightweight TCP reachability check.

### Signature

```python
network_available(
    address: str = "8.8.4.4",
    port: int = 53,
    timeout: int = 5,
) -> bool
```

Returns `True` if `socket.create_connection((address, port), timeout=timeout)` succeeds within `timeout` seconds. ANY exception (including DNS failures, connection refused, timeout) is caught and returns `False`. This is a plain TCP socket connect — NOT a DNS lookup of `address`.

```python
from nclutils.net import network_available

if network_available():  # defaults: 8.8.4.4:53, timeout=5
    fetch_remote_data()

# Custom target
network_available(address="github.com", port=443, timeout=2)
```

> [!NOTE]
> Legacy `nclutils.network` is deprecated; use `nclutils.net`.

---

## `nclutils.text`

In-place file edits. Both helpers return `True` if the file changed, `False` otherwise. Diagnostic logging is under the `nclutils.text` logger; silent until the host attaches a handler.

### `replace_in_file`

```python
replace_in_file(
    path: str | Path,
    replacements: dict[str, str],
    *,
    use_regex: bool = False,
) -> bool
```

Apply a dict of replacements to a file in place. Reads as UTF-8, writes as UTF-8.

```python
from nclutils.text import replace_in_file

# Plain substring replacement
replace_in_file("config.toml", {"old": "new"})

# Regex mode — each KEY is a pattern; matches use re.MULTILINE
replace_in_file("config.toml", {r"^old": "new"}, use_regex=True)
```

Failure handling (does NOT raise):

- File missing → logs at `ERROR`, returns `False`.
- Read or write `OSError` (permissions, disk full, etc.) → logs via `logger.exception`, returns `False`.

Replacements are applied in dict iteration order (insertion order, Python 3.7+). Earlier replacements affect what later replacements see — if you need atomic substitution, build the final string yourself.

### `ensure_lines_in_file`

```python
ensure_lines_in_file(
    path: str | Path,
    lines: list[str],
    *,
    at_top: bool = False,
) -> bool
```

Idempotent: add lines to a file if they aren't already present. `at_top=True` prepends instead of appending.

```python
from nclutils.text import ensure_lines_in_file

ensure_lines_in_file(".gitignore", [".env", "*.pyc"])
```

> [!WARNING]
> Each item in `lines` is interpolated INTO A REGEX (`rf"^{line}$"` with `re.MULTILINE`) for the "already present?" check. Lines with regex metacharacters (`.`, `*`, `[`, `(`, etc.) will be matched as regex patterns, NOT as literal strings. `*.pyc` works by coincidence (`.` matches any char, `*` is a quantifier on `.`); `foo.bar` would also match `fooXbar`. If you need literal matching, escape with `re.escape` before passing in.

Raises `FileNotFoundError`/`OSError` directly (unlike `replace_in_file`, which logs and returns False).

> [!NOTE]
> Legacy `nclutils.text_processing` is deprecated; use `nclutils.text`.

---

## `nclutils.utils`

Timestamps, unique IDs, Python version check.

### Timestamps

```python
iso_timestamp(*, microseconds: bool = False) -> str
format_iso_timestamp(datetime_obj: datetime, *, microseconds: bool = False) -> str
```

```python
from nclutils.utils import iso_timestamp, format_iso_timestamp

iso_timestamp()                       # "2026-05-04T18:32:01Z"
iso_timestamp(microseconds=True)      # "2026-05-04T18:32:01.847239Z"
```

The `+00:00` suffix is replaced with a trailing `Z` for consistency across timezones.

```python
from datetime import datetime, timezone

dt = datetime(2026, 5, 4, 18, 32, 1, tzinfo=timezone.utc)
format_iso_timestamp(dt)              # "2026-05-04T18:32:01Z"
```

`format_iso_timestamp` calls `datetime_obj.astimezone(timezone.utc)` before formatting, so:

- Naive datetimes are interpreted as LOCAL time and converted to UTC.
- Aware datetimes in any zone are converted to UTC.

### Unique IDs

```python
new_uid(bits: int = 64) -> str
new_timestamp_uid(bits: int = 32) -> str
unique_id(prefix: str = "") -> str
```

Three helpers for three needs:

```python
from nclutils.utils import new_uid, new_timestamp_uid, unique_id

# Random base-36, case-insensitive, no hyphens. Uses random.SystemRandom (os.urandom) —
# cryptographically secure, safe for filenames, cache keys, anything where collision matters.
# Length = int(bits / 5.16) + 1.
new_uid()              # 64 bits, ~13 chars: "kgk5mznp7q3xz"
new_uid(bits=128)      # ~25 chars

# Timestamp prefix + random suffix. Lexicographically sortable by creation time.
# Format: f"{YYYYMMDDTHHMMSS}-{new_uid(bits)}". Used by nclutils.fs.backup_path.
new_timestamp_uid()    # "20260504T183201-kgk5mzn"
new_timestamp_uid(bits=64)

# Process-wide incrementing counter. Backed by a module-global ID_COUNTER int.
unique_id()            # "1"
unique_id("id_")       # "id_2"
unique_id()            # "3"
```

> [!WARNING]
> `unique_id` is NOT thread-safe. The `ID_COUNTER += 1` increment in `utils.py` is unprotected; concurrent callers can observe duplicate IDs. NOT safe across processes or restarts either (counter resets to 0). Use for short-lived single-threaded labels (test fixtures, in-memory IDs). Prefer `new_uid` for anything else.

### Python version check

```python
check_python_version(major: int, minor: int) -> bool
```

Returns `sys.version_info >= (major, minor)`. Use to gate features that need newer language or stdlib features rather than raising the project's Python floor.

```python
from nclutils.utils import check_python_version

if not check_python_version(3, 12):
    raise RuntimeError("Python 3.12+ required")
```

## API reference (signatures only)

```python
# ask
choose_one_from_list(choices, message) -> V | T | None       # overloaded; see signatures section
choose_multiple_from_list(choices, message) -> list[V|T] | None

# net
network_available(address="8.8.4.4", port=53, timeout=5) -> bool

# text
replace_in_file(path, replacements, *, use_regex=False) -> bool
ensure_lines_in_file(path, lines, *, at_top=False) -> bool

# utils
iso_timestamp(*, microseconds=False) -> str
format_iso_timestamp(datetime_obj, *, microseconds=False) -> str
new_uid(bits=64) -> str
new_timestamp_uid(bits=32) -> str
unique_id(prefix="") -> str
check_python_version(major, minor) -> bool
```
