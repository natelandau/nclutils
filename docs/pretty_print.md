# Pretty Printing

Themed console output and file logging for Python CLI scripts. A thin layer over [Rich](https://github.com/Textualize/rich) that gives you `info` / `success` / `warning` / `error` / `debug` / `trace` / `dryrun` calls, a spinner-driven `step()` context manager, and an optional parallel logfile.

```python
from nclutils import success, warning

success("deployed to production")
warning("API rate limit at 80%")
```

```
✓ deployed to production

! API rate limit at 80%
```

## Why nllog

If you've written a CLI script in Python, you've probably written this:

```python
print(f"[OK] {message}")
print(f"[!] {warning}", file=sys.stderr)
```

A few iterations in, you've added `--verbose` and `--quiet` flags, swapped brackets for ANSI codes, and finally pulled in Rich. nllog collapses that progression into one import. It owns the verbosity gates, the stdout/stderr split, the markup escaping, and a Rich theme that's already been tuned to look reasonable.

## Quick start

```python
import time
from nclutils import configure, info, success, step, Verbosity

configure(verbosity=Verbosity.DEBUG)

info("starting build")

with step("compiling sources") as s:
    time.sleep(0.5)
    s.sub("compiling src/api.py")
    s.sub("compiling src/cli.py")

success("build complete", details=["artifact: dist/app-1.4.2.tar.gz"])
```

The `step()` block shows a live spinner with sub-items beneath it. On success it turns into a green checkmark; on any exception (including `SystemExit` and `KeyboardInterrupt`) it turns into a red X and the exception re-raises.

## Output levels

Every level routes through the same shape: `func(message, details=[...])`. `details` is optional. String items render as indented continuation lines in a dimmer shade; Rich markup is escaped by default so user-supplied strings can't inject styling. Non-strings are auto-rendered with Rich (dicts, dataclasses, and arbitrary objects via `Pretty`; `JSON` / `Syntax` / `Table` pass through unchanged).

Pass `markup=True` to opt into Rich markup parsing for `message` and any string `details` items in that call:

```python
from rich.text import Text
from nllog import info

info("Found [bold]42[/] matches", markup=True)
info(Text.from_markup("Found [bold]42[/] matches"))  # Text instances always keep their styling
```

Use `markup=True` when _you_ control the string. When the message comes from arbitrary input (file paths, exception messages, JSON snippets), keep the default escape so brackets in the input can't accidentally render as styling or raise `MarkupError`.

| Function   | Stream | Marker                   | Gated by                   |
| ---------- | ------ | ------------------------ | -------------------------- |
| `info`     | stdout | (none)                   | `quiet` suppresses         |
| `success`  | stdout | `✓`                      | `quiet` suppresses         |
| `warning`  | stderr | `!`                      | always renders             |
| `error`    | stderr | `✗`                      | always renders             |
| `critical` | stderr | `‼`                      | always renders             |
| `dryrun`   | stdout | `~ [dry-run]`            | always renders             |
| `debug`    | stdout | `›`                      | shown at `DEBUG` or higher |
| `trace`    | stdout | `·`                      | shown at `TRACE`           |
| `header`   | stdout | (rule line)              | `quiet` suppresses         |
| `step`     | stdout | spinner, then `✓` or `✗` | always renders             |

`critical` is severity-only - it does not raise. Use it for "the world is broken" notices that warrant a more emphatic visual than `error`.

You can pass Rich renderables in `details` to get syntax-aware output, which is especially useful at `debug` / `trace`:

```python
from rich.json import JSON
from nllog import debug

debug("got response", details=[response_dict])
debug("raw payload", details=[JSON(resp.text)])
```

`header()` draws a `Console.rule()` with an optional centered title to break long output into scannable sections:

```python
from nllog import header

header("phase 1: download")
# ... work ...
header("phase 2: process")
```

## Wiring up `--verbose` and `--quiet`

`Verbosity` is an `IntEnum` with three levels (`INFO`, `DEBUG`, `TRACE`), so a `-v` count flag maps cleanly:

```python
import argparse
from nllog import configure, Verbosity

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="count", default=0)
parser.add_argument("-q", "--quiet", action="store_true")
args = parser.parse_args()

configure(verbosity=args.verbose, quiet=args.quiet)
```

Out-of-range integers are clamped, so `-vvvvv` is safe.

The two flags are independent gates:

- `verbosity` only gates `debug` and `trace`. The default is `INFO`.
- `quiet=True` suppresses `info`, `success`, and `header`. Warnings, errors, dry-run notices, and steps still render.
- `--verbose --quiet` is a sensible combination: you get debug output without the routine info chatter.

`configure()` is a partial update - fields you don't pass are left alone. Call it as many times as you like:

```python
configure(verbosity=Verbosity.DEBUG)
configure(quiet=True)         # verbosity still DEBUG
```

## The `step()` context manager

`step()` renders a Rich `Live` spinner that updates while your code runs, then resolves to a success or failure marker:

```python
from nclutils import step

with step("running migrations") as s:
    for migration in pending:
        run(migration)
        s.sub(f"applied {migration.name}")
```

On exit the spinner stops, the marker (`✓` or `✗`) is rendered, and any sub-items remain on screen so the final output is a static record of what happened.

For transient progress that shouldn't clutter the final transcript, pass `ephemeral=True`. The spinner and sub-items are wiped on success; on failure only the red X surfaces:

```python
with step("warming caches", ephemeral=True) as s:
    warm_cache()
    s.sub("cache populated")
# success leaves no trace; failure still prints "✗ warming caches"
```

> **Warning:** `step()` cannot nest. Rich's `Live` doesn't stack, so nesting silently corrupts the parent's display. nllog raises `RuntimeError` when you try.

## File logging

Pass `logfile=` to write a parallel record of every emission to disk:

```python
from pathlib import Path
from nllog import Emitter, LogLevel

e = Emitter(
    logfile=Path("./run.log"),
    loglevel=LogLevel.INFO,        # default; filter cutoff for the file
    # logfmt="%(asctime)s [%(levelname)s] %(message)s",  # optional override
)

e.info("starting build")
with e.step("compile assets") as s:
    s.sub("foo.css")
    s.sub("bar.js")
```

Produces `run.log`:

```
2026-05-04 14:32:01.234 | INFO     | starting build
2026-05-04 14:32:01.234 | INFO     | starting: compile assets
2026-05-04 14:32:01.235 | INFO     |   foo.css
2026-05-04 14:32:01.235 | INFO     |   bar.js
2026-05-04 14:32:01.236 | INFO     | succeeded: compile assets
```

Console rendering and file rendering are independent. The console ignores `loglevel`; the file ignores `quiet` and `verbosity`. Every level method writes to the file before checking its console gate, so the logfile remains a complete audit trail.

### What gets logged

| nllog emission                | Logged at                         | Notes                                                                         |
| ----------------------------- | --------------------------------- | ----------------------------------------------------------------------------- |
| `info` / `success` / `dryrun` | `INFO` (20)                       | `success`/`dryrun` aren't real severities. `dryrun` keeps `[dry-run]` inline. |
| `debug`                       | `DEBUG` (10)                      | `[+s.fffs]` elapsed tag inlined into message.                                 |
| `trace`                       | `TRACE` (5)                       | Custom level registered with stdlib `logging` at import.                      |
| `warning`                     | `WARNING` (30)                    |                                                                               |
| `error`                       | `ERROR` (40)                      |                                                                               |
| `critical`                    | `CRITICAL` (50)                   | Severity-only - does NOT raise.                                               |
| `step()` lifecycle            | `INFO` start, `INFO`/`ERROR` exit | `ephemeral=True` does not suppress file output.                               |
| `Step.sub()`                  | `INFO`                            | Indented continuation, written immediately.                                   |
| `header()`                    | (not logged)                      | Console-only structural sugar.                                                |

Filtering with `loglevel=LogLevel.WARNING` drops every `info` / `success` / `dryrun` / `debug` / `trace` emission and its detail continuations as a unit. `LogLevel` is severity-shaped, not emission-shaped, so there's no way to "log only successes."

### What's not included

nclutils pretty_print's logfile is for sane CLI audit and diagnostic capture. It does not ship rotation, JSON output, syslog, or multi-process safety. If you need those, run nllog on top of your own preconfigured `logging.Logger`, or use external rotation (`logrotate`, `savelog`).

## Customizing the theme

The seven output levels (`info`, `success`, `warning`, `error`, `debug`, `trace`, `dryrun`) each expose three things you can override: the main message style, the indented detail style, and the marker glyph. Override any combination in a `Theme`:

```python
from nclutils import configure, Theme, Level, success

configure(
    theme=Theme(
        success=Level(style="cyan", marker="🎉 "),
        warning=Level(marker=""),  # hide the warning marker entirely
    ),
)

success("deployed", details=["build #1742"])
```

Anything you don't set keeps its default. `Level(style="cyan")` only changes the main color; `detail_style` and `marker` stay as the defaults. Pass `marker=""` (empty string) to suppress a marker; `marker=None` (the default) keeps the built-in glyph.

Successive `configure(theme=...)` calls accumulate at the field level:

```python
from nclutils import configure, Theme, Level, success

configure(theme=Theme(success=Level(style="blue", marker="🎉 ")))
configure(theme=Theme(success=Level(detail_style="navy")))
# success now has style="blue", detail_style="navy", marker="🎉 "
```

To fully reset, build a fresh emitter: `set_default(Emitter())`.

The horizontal rule (`header`), the connector glyphs under `step()` (`├─`, `└─`), and the `[dry-run]` tag are not customizable.

## Reaching the underlying consoles

When you need to render a Rich object (`Table`, `Syntax`, `Panel`, …) directly to the same stream nclutils.pretty_print's level functions write to, use the `console()` and `err_console()` accessors:

```python
from rich.table import Table
from nclutils import console, err_console

table = Table("name", "status")
table.add_row("api", "ok")
console().print(table)

err_console().print("[bold red]fatal[/]")
```

## Library use: isolated emitters

The module-level functions delegate to a shared default `Emitter`. If you're writing a library that needs its own output configuration without trampling its host CLI's settings, instantiate an `Emitter` directly:

```python
from nclutils import Emitter, Verbosity

logger = Emitter(verbosity=Verbosity.DEBUG, quiet=False)
logger.info("library-internal message")
logger.debug("only this emitter's verbosity matters here")
```

Each `Emitter` owns its own `verbosity`, `quiet`, `console`, `err_console`, and logfile. Nothing leaks across instances.

For tests, swap in a recording console so you can assert on output:

```python
from rich.console import Console
from nclutils import Emitter, THEME

capture = Console(theme=THEME, record=True, force_terminal=True, width=80)
e = Emitter(console=capture, err_console=capture)
e.info("captured")
assert "captured" in capture.export_text()
```

For customizing nclutils.pretty_print's level styles, prefer the `theme=` argument over a custom `Console(theme=...)`. Level styles are resolved inline at print time, so a custom theme dict on a user-supplied `Console` no longer overrides level rendering. The `Console(theme=THEME)` pattern remains valid for capturing the default theme's `header` / `header.rule` / `sub.pipe` styles.

To route the module-level functions through a test emitter:

```python
from nclutils import set_default, get_default

original = get_default()
set_default(e)
try:
    run_code_under_test()
finally:
    set_default(original)
```

## API reference

The full public surface lives in `nclutils.pretty_print`:

- `info`, `success`, `warning`, `error`, `critical`, `dryrun`, `debug`, `trace`, `header` - output functions.
- `step(message, *, ephemeral=False)` - spinner context manager.
- `configure(*, verbosity=None, quiet=None, console=None, err_console=None, theme=None, logfile=None, loglevel=None, logfmt=None)` - partial update of the default emitter.
- `Emitter` - instantiate directly for isolated configuration.
- `Theme`, `Level` - per-level style and marker overrides; pass `Theme(success=Level(...))` to `configure()` or `Emitter()`.
- `Verbosity` - `IntEnum` with `INFO`, `DEBUG`, `TRACE`.
- `LogLevel` - `IntEnum` aligned with stdlib `logging` (`TRACE=5`, `DEBUG=10`, …, `CRITICAL=50`); used as the `loglevel=` filter cutoff for the logfile.
- `THEME` - the Rich `Theme` used by default consoles, in case you build your own.
- `console()`, `err_console()` - return the default emitter's stdout / stderr `Console` for direct Rich rendering. Re-resolves on each call.
- `get_default()`, `set_default(emitter)` - read or replace the shared default emitter.

## License

MIT. See [LICENSE](LICENSE).
