# Utilities

Timestamps, unique identifiers, and a Python version check. Import them from `nclutils.utils`.

```python
from nclutils.utils import iso_timestamp, new_timestamp_uid

iso_timestamp()  # "2026-05-04T18:32:01Z"
new_timestamp_uid()  # "20260504T183201-kgk5mzn"
```

## Timestamps

Both timestamp functions return an ISO 8601 string in UTC with a trailing `Z` in place of `+00:00`.

### `iso_timestamp`

Return the current UTC time. Pass `microseconds=True` to add microseconds.

```python
from nclutils.utils import iso_timestamp

iso_timestamp()  # "2026-05-04T18:32:01Z"
iso_timestamp(microseconds=True)  # "2026-05-04T18:32:01.847239Z"
```

### `format_iso_timestamp`

Format an existing `datetime` in the same format. The function converts the input to UTC first. A naive `datetime` is treated as local time.

```python
from datetime import datetime, timezone
from nclutils.utils import format_iso_timestamp

dt = datetime(2026, 5, 4, 18, 32, 1, tzinfo=timezone.utc)
format_iso_timestamp(dt)  # "2026-05-04T18:32:01Z"
```

## Unique identifiers

Three functions make identifiers for different needs: random strings (`new_uid`), sortable strings with a timestamp prefix (`new_timestamp_uid`), and a counter for the current process (`unique_id`).

### `new_uid`

Make a random string of lowercase letters and digits (base 36) with at least `bits` bits of entropy. It uses `random.SystemRandom`, so it is safe for filenames, cache keys, and other identifiers that must not collide.

```python
from nclutils.utils import new_uid

new_uid()  # 64 bits, 13 characters: "kgk5mznp7q3xz"
new_uid(bits=128)  # 25 characters
```

### `new_timestamp_uid`

Join a UTC timestamp (`YYYYMMDDTHHMMSS`) and a random suffix from `new_uid`. A sort by string puts the results in creation order, to the second. Use it for backup filenames or log records. `nclutils.fs.backup_path` uses this value in its default backup suffix.

```python
from nclutils.utils import new_timestamp_uid

new_timestamp_uid()  # 32 bits: "20260504T183201-kgk5mzn"
new_timestamp_uid(bits=64)  # 13-character random suffix
```

### `unique_id`

Return the next value of a counter as a string, with an optional prefix. The counter starts at 1, is shared by all callers in the process, and does not reset.

```python
from nclutils.utils import unique_id

unique_id()  # "1"
unique_id("id_")  # "id_2"
unique_id()  # "3"
```

> [!NOTE]
> `unique_id` is sequential, not random. Use it for short-lived labels, such as test fixtures and in-memory IDs. It is not unique across processes or restarts.

## Python version checks

`check_python_version(major, minor)` returns `True` if the running interpreter is at the `(major, minor)` version or later. Use it to gate code that needs a newer interpreter than the package minimum of Python 3.11.

```python
from nclutils.utils import check_python_version

if check_python_version(3, 13):
    ...  # code that needs Python 3.13
```

## API reference

- `check_python_version(major, minor) -> bool`. Return `True` if the running interpreter meets the minimum version.
- `format_iso_timestamp(datetime_obj, *, microseconds=False) -> str`. Format a `datetime` as an ISO 8601 UTC string.
- `iso_timestamp(*, microseconds=False) -> str`. Current UTC time as an ISO 8601 string.
- `new_uid(bits=64) -> str`. Random base-36 string with at least `bits` bits of entropy.
- `new_timestamp_uid(bits=32) -> str`. Sortable UID with a timestamp prefix.
- `unique_id(prefix="") -> str`. Next value of the process-wide counter, as a string.
