# `nclutils.pp` reference

Rich-based user-facing console output. Imported as `from nclutils import pp` (or, for individual symbols, `from nclutils.pp import info, success, step`).

## Level functions

Every level routes through the same shape: `pp.func(message, details=[...], tag=..., right_tag=..., exception=..., show_locals=...)`. `details` items render as a tree under the message.

| Function       | Stream | Marker (unicode / ASCII) | Gated by                   |
| -------------- | ------ | ------------------------ | -------------------------- |
| `pp.info`      | stdout | (none)                   | `quiet=True` suppresses    |
| `pp.success`   | stdout | `✓` / `+`                | `quiet=True` suppresses    |
| `pp.warning`   | stderr | `!` / `!`                | always renders             |
| `pp.error`     | stderr | `✗` / `x`                | always renders             |
| `pp.critical`  | stderr | `‼` / `!!`               | always renders (severity-only; does NOT raise) |
| `pp.dryrun`    | stdout | `~ [dry-run]`            | always renders             |
| `pp.debug`     | stdout | `›` / `>`                | shown at `Verbosity.DEBUG` or higher |
| `pp.trace`     | stdout | `·` / `.`                | shown at `Verbosity.TRACE` |
| `pp.header`    | stdout | rule line                | `quiet=True` suppresses    |

```python
pp.success("deployed", details=["build #1742", "rollout 100%", "duration: 3.2s"])
```

renders as:

```
✓ deployed
  ├─ build #1742
  ├─ rollout 100%
  └─ duration: 3.2s
```

Strings in `details` are colored with the level's `detail_style` and Rich markup is escaped by default. Non-strings are auto-rendered: dicts/dataclasses via `Pretty`; `JSON` / `Syntax` / `Table` instances pass through unchanged.

Pass `markup=True` to opt into Rich-markup parsing for `message` and any string `details` items in that call. Only do this when you control the string; arbitrary input (paths, exception messages) should keep the default escape so brackets don't render as styling or raise `MarkupError`.

## Per-call tags

Every level method accepts `tag=` and `right_tag=` for one-off metadata:

```python
pp.info("saved", tag="api", right_tag="200ms")
# [api] saved                                                       200ms
```

- `tag` renders inline between marker and message; recorded in the logfile.
- `right_tag` is right-aligned to console width on the first line only; presentation-only, NOT logged.
- When passed to `pp.debug` / `pp.trace`, `right_tag` replaces the auto-elapsed `[+s.fffs]` marker on console; the logfile still records the elapsed timing.
- `pp.dryrun` keeps its built-in `[dry-run]` AND a caller `tag` (caller tag first): `[deploy] [dry-run] would push`.

You are responsible for Rich-markup-escaping `[`, `]`, or other reserved characters in tags. Pass plain ASCII or pre-escaped strings.

## Exceptions and tracebacks

Every level method accepts `exception=`:

```python
try:
    upload()
except UploadError as exc:
    pp.error("upload failed", exception=exc)

# Inside an except block, exception=True grabs the active exception via sys.exc_info()
try:
    upload()
except UploadError:
    pp.error("upload failed", exception=True)
```

Outside an `except` block, `exception=True` is a silent no-op (matches `logging.exception()`). Pass `show_locals=True` for verbose dumps that include each frame's locals.

`exception=` is accepted on every level method EXCEPT `header()` and `step()`, which manage their own exception display.

## `pp.step()` — spinner context manager

```python
with pp.step("running migrations") as s:
    for m in pending:
        run(m)
        s.sub(f"applied {m.name}")
```

On exit, the spinner resolves to `✓` (success) or `✗` (failure) and any sub-items remain on screen. Exceptions inside the block (including `SystemExit` and `KeyboardInterrupt`) re-raise after marking failure.

- `ephemeral=True` wipes the spinner and sub-items on success; on failure the red X surfaces (and `failure_msg` if set).
- `success_msg=` and `failure_msg=` override the resolved text; either can be omitted independently.
- `pp.step()` CANNOT NEST. Rich's `Live` can't stack — `pp` raises `RuntimeError` on nested entry. Use `s.sub("...")` for nested progress lines.

## `pp.kv()` — aligned key/value block

```python
pp.kv({"Branch": "main", "Commit": "abc1234", "Status": "clean"})
```

Renders aligned pairs with auto-padded keys. Pass `list[tuple[str, Any]]` when you need duplicate keys or explicit ordering. `pp.kv()` is suppressed on console by `quiet=True` (same as `pp.info`), but each pair is recorded as an `INFO` record in the logfile regardless. Pass `markup=True` to parse markup in string values; keys are always escaped.

## Configuration

`pp.configure(...)` is a partial update of the shared default emitter. Fields you don't pass are left alone.

```python
pp.configure(
    verbosity=pp.Verbosity.DEBUG,   # IntEnum: INFO=0, DEBUG=1, TRACE=2
    quiet=False,
    console=None,                    # rich.Console for stdout
    err_console=None,                # rich.Console for stderr
    theme=pp.Theme(...),             # see "Customizing the theme" below
    logfile=Path("./run.log"),
    loglevel=pp.LogLevel.INFO,       # IntEnum aligned with stdlib logging
    logfmt="%(asctime)s [%(levelname)s] %(message)s",
)
```

`verbosity` and `quiet` are independent gates:

- `verbosity` only affects `debug` and `trace`.
- `quiet=True` suppresses `info`, `success`, `header`, `kv`. Warnings, errors, dryrun, and steps still render.
- `--verbose --quiet` together is sensible: debug output without info chatter.

Out-of-range verbosity ints are clamped, so `-vvvvv` is safe.

## File logging

Pass `logfile=` to write a parallel record to disk:

```python
e = pp.Emitter(logfile=Path("./run.log"), loglevel=pp.LogLevel.INFO)
e.info("starting build")
```

Console and file rendering are independent. The console ignores `loglevel`; the file ignores `quiet` and `verbosity`. Every level method writes to the file BEFORE checking its console gate, so the logfile is a complete audit trail.

What gets logged:

| Emission                      | Logged at                         | Notes                                                                                                  |
| ----------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `info` / `success` / `dryrun` | `INFO` (20)                       | `success`/`dryrun` aren't real severities. `dryrun` keeps `[dry-run]` inline.                          |
| `debug`                       | `DEBUG` (10)                      | `[+s.fffs]` elapsed tag inlined into message.                                                          |
| `trace`                       | `TRACE` (5)                       | Custom level registered with stdlib `logging` at import.                                               |
| `warning`                     | `WARNING` (30)                    |                                                                                                        |
| `error`                       | `ERROR` (40)                      |                                                                                                        |
| `critical`                    | `CRITICAL` (50)                   | Severity-only.                                                                                         |
| `step()` lifecycle            | `INFO` start, `INFO`/`ERROR` exit | `ephemeral=True` does NOT suppress file output.                                                        |
| `Step.sub()`                  | `INFO`                            | Indented continuation.                                                                                 |
| `kv()`                        | `INFO`                            | One record per pair. Recorded even under `quiet=True`.                                                 |
| `header()`                    | (not logged)                      | Console-only structural sugar.                                                                         |

`LogLevel` is severity-shaped, not emission-shaped: there's no way to "log only successes." The logfile does not ship rotation, JSON output, syslog, or multi-process safety; layer your own `logging.Logger` underneath if you need those.

## Themes

Override per-level style, detail style, or marker:

```python
pp.configure(
    theme=pp.Theme(
        success=pp.Level(style="cyan", marker="🎉 "),
        warning=pp.Level(marker=""),   # hide the warning marker
    ),
)
```

Anything you don't set keeps its default. `marker=""` (empty string) suppresses the marker; `marker=None` (default) keeps the built-in glyph. Successive `pp.configure(theme=...)` calls accumulate at the field level. To fully reset, build a fresh emitter: `pp.set_default(pp.Emitter())`.

Not themable: the `pp.header()` rule, the `[dry-run]` tag, the tree connector glyphs (`├─` / `└─` / `│` share the `sub.pipe` Rich theme entry — style only, not glyph). Build a custom `Console(theme=...)` if you need to override the connector style.

## ASCII fallback

`pp` detects `console.encoding` and falls back to ASCII when unicode glyphs can't render (e.g. `LANG=C`, `PYTHONIOENCODING=ascii`, Windows code-page rejection). Tree connectors collapse to `- `; default markers map to `+`, `x`, `!!`, etc. (see table above). User-supplied `Theme(level=Level(marker=...))` markers are always respected verbatim, ASCII or not.

## Isolated emitters

The module-level functions delegate to a shared default `Emitter`. For library code that needs its own configuration without trampling the host CLI's settings, instantiate an `Emitter` directly:

```python
logger = pp.Emitter(verbosity=pp.Verbosity.DEBUG)
logger.info("library-internal message")
```

Each `Emitter` owns its own `verbosity`, `quiet`, consoles, and logfile. Nothing leaks across instances. For tests, swap in a recording console:

```python
from rich.console import Console
capture = Console(theme=pp.THEME, record=True, force_terminal=True, width=80)
e = pp.Emitter(console=capture, err_console=capture)
e.info("captured")
assert "captured" in capture.export_text()
```

To temporarily route module-level functions through a test emitter:

```python
original = pp.get_default()
pp.set_default(e)
try:
    run_code_under_test()
finally:
    pp.set_default(original)
```

## Reaching the underlying consoles

When you need to render a Rich object (`Table`, `Syntax`, `Panel`) on the same stream `pp` writes to:

```python
from rich.table import Table

table = Table("name", "status")
table.add_row("api", "ok")
pp.console().print(table)
pp.err_console().print("[bold red]fatal[/]")
```

`pp.console()` and `pp.err_console()` re-resolve on each call.

## Public symbols

- Level functions: `info`, `success`, `warning`, `error`, `critical`, `dryrun`, `debug`, `trace`, `header`
- `kv(items, *, indent=2, separator=": ", markup=False)`
- `step(message, *, ephemeral=False, success_msg=None, failure_msg=None, markup=False)`
- `configure(*, verbosity=None, quiet=None, console=None, err_console=None, theme=None, logfile=None, loglevel=None, logfmt=None)`
- `Emitter` — instantiate for isolated configuration
- `Theme`, `Level` — per-level style and marker overrides
- `Verbosity` — `IntEnum(INFO, DEBUG, TRACE)`
- `LogLevel` — `IntEnum` aligned with stdlib logging (`TRACE=5` … `CRITICAL=50`)
- `THEME` — Rich `Theme` used by default consoles
- `console()`, `err_console()` — default emitter's stdout/stderr `Console`
- `get_default()`, `set_default(emitter)` — read/replace the shared default
