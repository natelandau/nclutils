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

Both return `None` if the user cancels (Esc / Ctrl-C) or the choices list is empty. Multi-select returns `list[T] | None`.

### Choice formats

Three accepted input shapes — pick ONE per prompt (mixing works but is a smell):

```python
# 1. Plain values — display string is str() of value, except Path which uses path.name
choose_one_from_list([Path("./conf/dev.toml"), Path("./conf/prod.toml")], "Pick")

# 2. (label, value) tuples — display the label, return the value
choose_one_from_list(
    [("US prod", Profile(region="us-east-1")), ("EU prod", Profile(region="eu-west-1"))],
    "Deployment target",
)

# 3. Single-key dicts — same as tuple form
choose_multiple_from_list(
    [{"Frontend": "fe"}, {"Backend": "be"}, {"Infra": "infra"}],
    "Which teams?",
)
```

### Signatures

```python
choose_one_from_list(
    choices: list[Path | str | int | float | bool] | list[tuple[str, T]] | list[dict[str, T]],
    message: str,
) -> T | None

choose_multiple_from_list(
    choices: list[Path | str | int | float | bool] | list[tuple[str, T]] | list[dict[str, T]],
    message: str,
) -> list[T] | None
```

> [!NOTE]
> The legacy import `nclutils.questions` still works but is deprecated and will be removed in v4.0.0. New code should use `nclutils.ask`.

---

## `nclutils.net`

Lightweight TCP reachability check.

```python
from nclutils.net import network_available

if network_available():  # defaults: 8.8.4.4:53, timeout=5
    fetch_remote_data()

# Custom target
network_available(address="github.com", port=443, timeout=2)
```

### Signature

```python
network_available(
    address: str = "8.8.4.4",
    port: int = 53,
    timeout: int = 5,
) -> bool
```

Returns `True` if a TCP connection succeeds within `timeout` seconds.

> [!NOTE]
> Legacy `nclutils.network` is deprecated; use `nclutils.net`.

---

## `nclutils.text`

In-place file edits. Both helpers return `True` if the file changed, `False` otherwise.

### `replace_in_file(path, replacements, *, use_regex=False) -> bool`

Apply a dict of replacements to a file in place.

```python
from nclutils.text import replace_in_file

# Plain substring replacement
replace_in_file("config.toml", {"old": "new"})

# Regex mode — each KEY is a pattern, matches use re.MULTILINE
replace_in_file("config.toml", {r"^old": "new"}, use_regex=True)
```

### `ensure_lines_in_file(path, lines, *, at_top=False) -> bool`

Idempotent append: add lines to a file if they aren't already present. `at_top=True` prepends instead.

```python
from nclutils.text import ensure_lines_in_file

ensure_lines_in_file(".gitignore", [".env", "*.pyc"])
```

Diagnostic logging is under the `nclutils.text` logger; silent until the host attaches a handler.

> [!NOTE]
> Legacy `nclutils.text_processing` is deprecated; use `nclutils.text`.

---

## `nclutils.utils`

Timestamps, unique IDs, Python version check.

### Timestamps

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

`format_iso_timestamp` converts the input to UTC before formatting; naive datetimes are treated as local time.

### Unique IDs

Three helpers for three needs:

```python
from nclutils.utils import new_uid, new_timestamp_uid, unique_id

# Random base-36, case-insensitive, no hyphens. Uses random.SystemRandom — safe for
# filenames, cache keys, anything where collision matters.
new_uid()              # 64 bits, ~13 chars: "kgk5mznp7q3xz"
new_uid(bits=128)      # ~25 chars

# Timestamp prefix + random suffix. Lexicographically sortable by creation time.
# This is the format nclutils.fs.backup_path uses.
new_timestamp_uid()    # "20260504T183201-kgk5mzn"
new_timestamp_uid(bits=64)

# Process-wide incrementing counter as a string. Module-level state — shared across
# every caller, NOT reset between calls. Useful for short-lived labels (test
# fixtures, in-memory IDs). NOT safe across processes or restarts.
unique_id()            # "1"
unique_id("id_")       # "id_2"
unique_id()            # "3"
```

### Python version check

```python
from nclutils.utils import check_python_version

if not check_python_version(3, 12):
    raise RuntimeError("Python 3.12+ required")
```

`nclutils.fs.copy_directory` uses this internally to refuse to run on interpreters lacking `Path.walk()`. Gate any new code that needs 3.11+/3.12+ features the same way rather than raising the package floor.

### Signatures

```python
check_python_version(major: int, minor: int) -> bool
format_iso_timestamp(datetime_obj: datetime, *, microseconds: bool = False) -> str
iso_timestamp(*, microseconds: bool = False) -> str
new_uid(bits: int = 64) -> str
new_timestamp_uid(bits: int = 32) -> str
unique_id(prefix: str = "") -> str
```
