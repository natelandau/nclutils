# Utilities

Timestamps, unique identifiers, and a Python version check. Imported from `nclutils.utils`.

```python
from nclutils.utils import iso_timestamp, new_timestamp_uid

iso_timestamp()        # "2026-05-04T18:32:01Z"
new_timestamp_uid()    # "20260504T183201-kgk5mzn"
```

## Timestamps

### `iso_timestamp`

Return the current UTC time as an ISO 8601 string. The `+00:00` suffix is replaced with a trailing `Z` so the output is consistent across timezones.

```python
from nclutils.utils import iso_timestamp

iso_timestamp()                       # "2026-05-04T18:32:01Z"
iso_timestamp(microseconds=True)      # "2026-05-04T18:32:01.847239Z"
```

### `format_iso_timestamp`

The same format applied to an existing `datetime`. The input is converted to UTC before formatting, so naive datetimes are treated as local time.

```python
from datetime import datetime, timezone
from nclutils.utils import format_iso_timestamp

dt = datetime(2026, 5, 4, 18, 32, 1, tzinfo=timezone.utc)
format_iso_timestamp(dt)  # "2026-05-04T18:32:01Z"
```

## Unique identifiers

Three helpers cover different needs: random strings (`new_uid`), sortable timestamp-prefixed strings (`new_timestamp_uid`), and process-local incrementing counters (`unique_id`).

### `new_uid`

Generate a case-insensitive random base-36 string with at least the requested bits of entropy. Uses `random.SystemRandom`, so it's safe for filenames, cache keys, and other identifiers where collisions matter.

```python
from nclutils.utils import new_uid

new_uid()           # 64 bits, ~13 chars: "kgk5mznp7q3xz"
new_uid(bits=128)   # ~25 chars
```

### `new_timestamp_uid`

Combine a UTC timestamp prefix with a random suffix. The result is lexicographically sortable by creation time, which is useful for backup filenames or log records.

```python
from nclutils.utils import new_timestamp_uid

new_timestamp_uid()         # "20260504T183201-kgk5mzn"
new_timestamp_uid(bits=64)  # longer random suffix
```

This is the format `nclutils.fs.backup_path` uses for default backup suffixes.

### `unique_id`

Return a process-wide incrementing integer as a string, optionally prefixed. The counter is module-level state, so it's shared across every caller and isn't reset between calls.

```python
from nclutils.utils import unique_id

unique_id()        # "1"
unique_id("id_")   # "id_2"
unique_id()        # "3"
```

> **Note:** `unique_id` is sequential, not random. It's useful for short-lived labels (test fixtures, in-memory IDs) but isn't safe across processes or restarts.

## Python version checks

`check_python_version` compares `sys.version_info` against a `(major, minor)` minimum. Use it to gate code paths that depend on a specific interpreter version.

```python
from nclutils.utils import check_python_version

if not check_python_version(3, 12):
    raise RuntimeError("Python 3.12+ required")
```

`nclutils.fs.copy_directory` uses this internally to refuse to run on older interpreters that lack `Path.walk()`.

## API reference

- `check_python_version(major, minor)`. Return `True` if the running interpreter meets the minimum version.
- `format_iso_timestamp(datetime_obj, *, microseconds=False)`. Format a `datetime` as an ISO 8601 UTC string.
- `iso_timestamp(*, microseconds=False)`. Current UTC time as an ISO 8601 string.
- `new_uid(bits=64)`. Random base-36 string with at least the requested bits of entropy.
- `new_timestamp_uid(bits=32)`. Sortable timestamp-prefixed UID.
- `unique_id(prefix="")`. Process-wide incrementing counter as a string.
