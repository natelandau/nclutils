# Pretty Printing

Themed console output and file logging for Python CLI scripts. A thin layer over [Rich](https://github.com/Textualize/rich) that gives you `info` / `success` / `warning` / `error` / `debug` / `trace` / `dryrun` calls, a spinner-driven `step()` context manager, and an optional parallel logfile.

```python
from nclutils import pp

pp.success("deployed to production")
pp.warning("API rate limit at 80%")
```

```
✓ deployed to production

! API rate limit at 80%
```

## What it owns

`pp` handles the four things that grow out of `print()` in any non-trivial CLI script: the verbosity gates (`--verbose` / `--quiet`), the stdout/stderr split, Rich-markup escaping for untrusted input, and a preset theme.

## Quick start

```python
import time
from nclutils import pp

pp.configure(verbosity=pp.Verbosity.DEBUG)

pp.info("starting build")

with pp.step("compiling sources") as s:
    time.sleep(0.5)
    s.sub("compiling src/api.py")
    s.sub("compiling src/cli.py")

pp.success("build complete", details=["artifact: dist/app-1.4.2.tar.gz"])
```

The `pp.step()` block shows a live spinner with sub-items beneath it. On success it turns into a green checkmark; on any exception (including `SystemExit` and `KeyboardInterrupt`) it turns into a red X and the exception re-raises.

## Output levels

Every level routes through the same shape: `pp.func(message, details=[...])`. `details` is optional. Items render as a tree beneath the message. Non-final items are prefixed with `├─` and the final item with `└─`, matching `pp.step()`'s sub-item layout. Multi-line renderables (Tables, JSON, multi-line `Pretty` outputs) get a `│ ` continuation pipe under non-final positions and a blank gutter under the final position. String items are colored with the level's `detail_style`; Rich markup is escaped by default so user-supplied strings can't inject styling. Non-strings are auto-rendered with Rich (dicts, dataclasses, and arbitrary objects via `Pretty`; `JSON` / `Syntax` / `Table` pass through unchanged).

For example, this call:

```python
from nclutils import pp

pp.success("deployed", details=["build #1742", "rollout 100%", "duration: 3.2s"])
```

renders as:

```text
✓ deployed
  ├─ build #1742
  ├─ rollout 100%
  └─ duration: 3.2s
```

The `├─` and `└─` glyphs are styled via the `sub.pipe` theme key (the same key `pp.step()` uses for its sub-item connectors), so retuning that one entry restyles every tree connector across the API.

> [!NOTE]
> Tree connectors appear in stdout/stderr only. In logfile records, each detail item becomes its own log record at the parent's severity with the detail text in the standard `%(message)s` field, prefixed by two spaces; the file does not contain `├─`, `└─`, or `│` characters.

Pass `markup=True` to opt into Rich markup parsing for `message` and any string `details` items in that call:

```python
from rich.text import Text
from nclutils import pp

pp.info("Found [bold]42[/] matches", markup=True)
pp.info(Text.from_markup("Found [bold]42[/] matches"))  # Text instances always keep their styling
```

Use `markup=True` when _you_ control the string. When the message comes from arbitrary input (file paths, exception messages, JSON snippets), keep the default escape so brackets in the input can't accidentally render as styling or raise `MarkupError`.

| Function      | Stream | Marker                   | Gated by                   |
| ------------- | ------ | ------------------------ | -------------------------- |
| `pp.info`     | stdout | (none)                   | `quiet` suppresses         |
| `pp.success`  | stdout | `✓`                      | `quiet` suppresses         |
| `pp.warning`  | stderr | `!`                      | always renders             |
| `pp.error`    | stderr | `✗`                      | always renders             |
| `pp.critical` | stderr | `‼`                      | always renders             |
| `pp.dryrun`   | stdout | `~ [dry-run]`            | always renders             |
| `pp.debug`    | stdout | `›`                      | shown at `DEBUG` or higher |
| `pp.trace`    | stdout | `·`                      | shown at `TRACE`           |
| `pp.header`   | stdout | (rule line)              | `quiet` suppresses         |
| `pp.step`     | stdout | spinner, then `✓` or `✗` | always renders             |

`pp.critical` is severity-only and does not raise. Use it for "the world is broken" notices that warrant a more emphatic visual than `pp.error`.

Every level method (`info`, `success`, `warning`, `error`, `critical`, `dryrun`, `debug`, `trace`) accepts the optional `tag=` and `right_tag=` kwargs documented in [Per-call tags](#per-call-tags) below.

### Per-call tags

Every level method accepts `tag=` and `right_tag=` for one-off metadata that doesn't warrant a theme change:

```python
pp.info("saved", tag="api", right_tag="200ms")
pp.error("upload failed", tag="uploader")
```

Renders:

```text
[api] saved                                                            200ms
[uploader] ✗ upload failed
```

`tag` is dim text rendered between the marker and the message. It is recorded inline in the logfile (`[api] saved`) so file consumers see the same metadata that appeared on the console.

`right_tag` is dim text right-aligned to the console width on the first line only. It is **presentation-only** and is never written to the logfile.

When `right_tag` is passed to `pp.debug` or `pp.trace`, the caller's value replaces the auto-elapsed `[+s.fffs]` marker on the console; the logfile still records the elapsed timing so the audit trail is preserved.

`pp.dryrun` combines a caller-supplied `tag` with its built-in `[dry-run]` marker on both the console and the logfile, with the caller's tag rendered first (`[deploy] [dry-run] would push`).

> [!NOTE]
> The caller is responsible for Rich-markup-escaping any `[`, `]`, or other reserved characters in `tag` and `right_tag`. Pass plain ASCII tags or pre-escaped strings.

### Exceptions and tracebacks

Every level method accepts an `exception=` kwarg. Pass an exception instance to render a styled Rich Traceback below the message:

```python
try:
    upload()
except UploadError as exc:
    pp.error("upload failed", exception=exc)
```

```text
✗ upload failed
  └─ ╭─ Traceback ─────────────────────────────────
       File "upload.py", line 42, in upload
         raise UploadError("403 Forbidden")
       UploadError: 403 Forbidden
     ╰─────────────────────────────────────────────
```

Inside an `except` block you can pass `exception=True` to grab the active exception via `sys.exc_info()`:

```python
try:
    upload()
except UploadError:
    pp.error("upload failed", exception=True)
```

Outside an `except` block, `exception=True` is a silent no-op (matches the behavior of `logging.exception()`).

Pass `show_locals=True` for verbose dumps that include each frame's local variables. Rich handles its own glyph fallbacks based on console encoding, so the traceback renders cleanly on terminals that can't display box-drawing characters.

The formatted traceback is also written to the logfile as continuation lines under the parent record at the same severity, so a level filter drops the traceback alongside its message.

> [!NOTE]
> `exception=` is accepted on every level method (`info`, `success`, `warning`, `error`, `critical`, `debug`, `trace`, `dryrun`). It is not supported on `header()` or `step()`, both of which already manage their own exception display.

You can pass Rich renderables in `details` to get syntax-aware output, which is especially useful at `debug` / `trace`:

```python
from rich.json import JSON
from nclutils import pp

pp.debug("got response", details=[response_dict])
pp.debug("raw payload", details=[JSON(resp.text)])
```

`pp.header()` draws a `Console.rule()` with an optional centered title to break long output into scannable sections:

```python
from nclutils import pp

pp.header("phase 1: download")
# ... work ...
pp.header("phase 2: process")
```

## Key/value blocks

`pp.kv()` renders aligned key/value pairs as a clean section block, which is handy for status summaries and final-state output:

```python
pp.header("Build Status")
pp.kv({
    "Branch":   "main",
    "Commit":   "abc1234",
    "Status":   "clean",
    "Duration": "3.2s",
})
```

```text
─── Build Status ───

  Branch:   main
  Commit:   abc1234
  Status:   clean
  Duration: 3.2s
```

Keys are padded automatically, so you don't need to pre-align them. Pass a `list[tuple[str, Any]]` when you need duplicate keys or want to control ordering explicitly:

```python
pp.kv([
    ("Step", "init"),
    ("Step", "build"),
    ("Step", "deploy"),
])
```

The default `indent=2` and `separator=": "` work for typical CLI output. Pass `markup=True` to parse Rich markup in string values; keys are always escaped (treated as identifiers).

> [!NOTE]
> `pp.kv()` is suppressed on the console by `quiet=True`, the same as `pp.info()` and `pp.success()`. Each pair is still recorded as one INFO record in the logfile (or one record per visual line for multi-line values), so the audit trail stays complete even under quiet.

Non-string, non-renderable values pass through `str()`. Rich renderables (Tables, JSON, etc.) render below the key, indented to the value column.

## Wiring up `--verbose` and `--quiet`

`pp.Verbosity` is an `IntEnum` with three levels (`INFO`, `DEBUG`, `TRACE`), so a `-v` count flag maps cleanly:

```python
import argparse
from nclutils import pp

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="count", default=0)
parser.add_argument("-q", "--quiet", action="store_true")
args = parser.parse_args()

pp.configure(verbosity=args.verbose, quiet=args.quiet)
```

Out-of-range integers are clamped, so `-vvvvv` is safe.

The two flags are independent gates:

- `verbosity` only gates `debug` and `trace`. The default is `INFO`.
- `quiet=True` suppresses `info`, `success`, and `header`. Warnings, errors, dry-run notices, and steps still render.
- `--verbose --quiet` is a sensible combination: you get debug output without the routine info chatter.

`pp.configure()` is a partial update. Fields you don't pass are left alone. Call it as many times as you like:

```python
pp.configure(verbosity=pp.Verbosity.DEBUG)
pp.configure(quiet=True)         # verbosity still DEBUG
```

## The `step()` context manager

`pp.step()` renders a Rich `Live` spinner that updates while your code runs, then resolves to a success or failure marker:

```python
from nclutils import pp

with pp.step("running migrations") as s:
    for migration in pending:
        run(migration)
        s.sub(f"applied {migration.name}")
```

On exit the spinner stops, the marker (`✓` or `✗`) is rendered, and any sub-items remain on screen so the final output is a static record of what happened.

For transient progress that shouldn't clutter the final transcript, pass `ephemeral=True`. The spinner and sub-items are wiped on success, leaving no trace on the console. If the block calls `s.fail()`, a fresh error line still surfaces on stderr after the wipe (see [Failing a step](#failing-a-step)):

```python
with pp.step("warming caches", ephemeral=True) as s:
    warm_cache()
    s.sub("cache populated")
# success leaves no trace
```

> [!WARNING]
> `pp.step()` cannot nest. Rich's `Live` doesn't stack, so nesting silently corrupts the parent's display. `pp` raises `RuntimeError` when you try.

### Customizing the success message

By default `step()` reuses the original message on success. To show different text, pass `success_msg`:

```python
with pp.step(
    "compiling sources",
    success_msg="compiled 42 files in 1.2s",
) as s:
    s.sub("api.py")
    s.sub("cli.py")
```

On success the spinner resolves to `✓ compiled 42 files in 1.2s`. The override message is also recorded in the `succeeded:` logfile line so the audit trail matches what the user saw.

When the success text depends on work done inside the block (a count, a duration, an output path), call `s.set_success_msg()` from inside the block:

```python
with pp.step("compiling sources") as s:
    processed = []
    for path in sources:
        compile_one(path)
        processed.append(path)
        s.sub(path.name)
    s.set_success_msg(f"compiled {len(processed)} files")
```

The setter wins over the `success_msg` kwarg, which wins over the original message. Each takes its own `markup=` flag.

### Failing a step

When the work didn't succeed, call `s.fail(message)` from inside the block. This exits the `with` block immediately, replaces the spinner with an error marker, and writes a `failed:` line to the logfile:

```python
with pp.step("compiling sources") as s:
    for path in sources:
        if not path.exists():
            s.fail(f"missing source: {path}")  # exits here
        compile_one(path)
    s.set_success_msg(f"compiled {len(sources)} files")
```

Code after `s.fail(...)` inside the block does not run. To attach an exception's type and message to the `failed:` log line, pass `exception=`:

```python
with pp.step("compiling sources") as s:
    try:
        compile_all(sources)
    except CompileError as e:
        s.fail("compilation aborted", exception=e)
```

> [!NOTE]
> `s.fail()` is the only way to render the failure marker. An uncaught exception inside `step()` propagates through cleanly with no marker and no log line, leaving the original message visible (no spinner) and any sub-items intact. The caller owns error reporting in that path.

When `ephemeral=True`, `s.fail()` still surfaces a fresh error line on stderr after wiping the spinner, so failures are never silently hidden:

```python
with pp.step("warming caches", ephemeral=True) as s:
    if not cache_target_reachable():
        s.fail("cache target unreachable")
# stderr shows: ✗ cache target unreachable
```

### Skipping a step

When the work the step describes did not run (nothing to do, preconditions unmet, intentional bypass), call `s.skip(message)`. This exits the `with` block immediately, replaces the spinner with an info-styled completion (no checkmark, no error glyph), and writes a `skipped:` line to the logfile:

```python
with pp.step("warming caches") as s:
    if cache.is_warm():
        s.skip("caches already warm")  # exits here
    warm_cache()
```

Code after `s.skip(...)` does not run. Skip is not an error; in ephemeral mode it wipes the spinner with no extra console output.

## File logging

Pass `logfile=` to write a parallel record of every emission to disk:

```python
from pathlib import Path
from nclutils import pp

e = pp.Emitter(
    logfile=Path("./run.log"),
    loglevel=pp.LogLevel.INFO,        # default; filter cutoff for the file
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

| Emission                      | Logged at                         | Notes                                                                                                  |
| ----------------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `info` / `success` / `dryrun` | `INFO` (20)                       | `success`/`dryrun` aren't real severities. `dryrun` keeps `[dry-run]` inline.                          |
| `debug`                       | `DEBUG` (10)                      | `[+s.fffs]` elapsed tag inlined into message.                                                          |
| `trace`                       | `TRACE` (5)                       | Custom level registered with stdlib `logging` at import.                                               |
| `warning`                     | `WARNING` (30)                    |                                                                                                        |
| `error`                       | `ERROR` (40)                      |                                                                                                        |
| `critical`                    | `CRITICAL` (50)                   | Severity-only and does not raise.                                                                      |
| `step()` lifecycle            | `INFO` start, `INFO`/`ERROR` exit | `ephemeral=True` does not suppress file output.                                                        |
| `Step.sub()`                  | `INFO`                            | Indented continuation, written immediately.                                                            |
| `kv()`                        | `INFO` (20)                       | One INFO record per pair; one per visual line for multi-line values. Recorded even under `quiet=True`. |
| `header()`                    | (not logged)                      | Console-only structural sugar.                                                                         |

Filtering with `loglevel=pp.LogLevel.WARNING` drops every `info` / `success` / `dryrun` / `debug` / `trace` emission and its detail continuations as a unit. `LogLevel` is severity-shaped, not emission-shaped, so there's no way to "log only successes."

### What's not included

The logfile is for CLI audit and diagnostic capture. It does not ship rotation, JSON output, syslog, or multi-process safety. If you need those, run `pp` on top of your own preconfigured `logging.Logger`, or use external rotation (`logrotate`, `savelog`).

## Customizing the theme

The seven output levels (`info`, `success`, `warning`, `error`, `debug`, `trace`, `dryrun`) each expose three things you can override: the main message style, the indented detail style, and the marker glyph. Override any combination in a `Theme`:

```python
from nclutils import pp

pp.configure(
    theme=pp.Theme(
        success=pp.Level(style="cyan", marker="🎉 "),
        warning=pp.Level(marker=""),  # hide the warning marker entirely
    ),
)

pp.success("deployed", details=["build #1742"])
```

Anything you don't set keeps its default. `pp.Level(style="cyan")` only changes the main color; `detail_style` and `marker` stay as the defaults. Pass `marker=""` (empty string) to suppress a marker; `marker=None` (the default) keeps the built-in glyph.

Successive `pp.configure(theme=...)` calls accumulate at the field level:

```python
from nclutils import pp

pp.configure(theme=pp.Theme(success=pp.Level(style="blue", marker="🎉 ")))
pp.configure(theme=pp.Theme(success=pp.Level(detail_style="navy")))
# success now has style="blue", detail_style="navy", marker="🎉 "
```

To fully reset, build a fresh emitter: `pp.set_default(pp.Emitter())`.

### What's not themed

The horizontal rule under `pp.header()` and the `[dry-run]` tag are not customizable. The `├─`/`└─` connector glyphs beneath `pp.step()` and `details` lists share the `sub.pipe` Rich theme entry on the underlying console (defaulting to `bright_black`); the glyph characters themselves are fixed, and the `pp.Theme` dataclass does not expose a field to retune their style. To override it, build a custom `Console(theme=...)` and pass it via `pp.Emitter(console=...)`.

### ASCII fallback

When the console's encoding can't produce the default unicode glyphs (e.g. `LANG=C`, `PYTHONIOENCODING=ascii`, or a Windows host whose code page rejects box-drawing characters), `pp` automatically falls back to an ASCII-only rendering. Detection is automatic, there is no flag to set:

- Detail tree connectors (`├─`, `└─`, `│`) collapse to a simple `- ` prefix on every line, with continuation lines aligned under the value column.
- `pp.step()` sub-items render with the same `- ` prefix instead of tree connectors.
- Default level markers fall back per the table below.

| Level    | Unicode | ASCII    |
| -------- | ------- | -------- |
| info     | (none)  | (none)   |
| success  | `✓`     | `+`      |
| warning  | `!`     | `!`      |
| error    | `✗`     | `x`      |
| critical | `‼`     | `!!`     |
| debug    | `›`     | `>`      |
| trace    | `·`     | `.`      |
| dryrun   | `~`     | `~`      |

User-supplied `pp.Theme(level=pp.Level(marker=...))` markers are always respected verbatim, even on ASCII consoles. The fallback only triggers when a level still has its built-in default marker.

> [!NOTE]
> Detection probes `console.encoding` at render time and chooses the rendering path per call. To force one path or the other, build your own `Console` with the desired encoding and pass it via `pp.configure(console=...)` or `pp.Emitter(console=...)`.

## Reaching the underlying consoles

When you need to render a Rich object (`Table`, `Syntax`, `Panel`, …) on the same stream the level functions write to, use the `pp.console()` and `pp.err_console()` accessors:

```python
from rich.table import Table
from nclutils import pp

table = Table("name", "status")
table.add_row("api", "ok")
pp.console().print(table)

pp.err_console().print("[bold red]fatal[/]")
```

## Library use: isolated emitters

The module-level functions delegate to a shared default `Emitter`. If you're writing a library that needs its own output configuration without trampling its host CLI's settings, instantiate an `Emitter` directly:

```python
from nclutils import pp

logger = pp.Emitter(verbosity=pp.Verbosity.DEBUG, quiet=False)
logger.info("library-internal message")
logger.debug("only this emitter's verbosity matters here")
```

Each `Emitter` owns its own `verbosity`, `quiet`, `console`, `err_console`, and logfile. Nothing leaks across instances.

For tests, swap in a recording console so you can assert on output:

```python
from rich.console import Console
from nclutils import pp

capture = Console(theme=pp.THEME, record=True, force_terminal=True, width=80)
e = pp.Emitter(console=capture, err_console=capture)
e.info("captured")
assert "captured" in capture.export_text()
```

> [!NOTE]
> Use the `theme=` argument to customize level styles, not a custom `Console(theme=...)`. Level styles are resolved inline at print time, so a theme dict on a user-supplied `Console` no longer overrides level rendering.
>
> The `Console(theme=pp.THEME)` pattern is still valid when you need to capture the default theme's structural styles (`header`, `header.rule`, `sub.pipe`) on your own console.

To route the module-level functions through a test emitter:

```python
from nclutils import pp

original = pp.get_default()
pp.set_default(e)
try:
    run_code_under_test()
finally:
    pp.set_default(original)
```

## API reference

Every name below is available on the `pp` namespace (`from nclutils import pp`) and from `nclutils.pp` directly (e.g. `from nclutils.pp import info`).

- `info`, `success`, `warning`, `error`, `critical`, `dryrun`, `debug`, `trace`, `header`. Output functions. Every level function accepts `tag=` / `right_tag=` (see [Per-call tags](#per-call-tags)) and `exception=` / `show_locals=` (see [Exceptions and tracebacks](#exceptions-and-tracebacks)).
- `kv(items, *, indent=2, separator=": ", markup=False)`. Render aligned key/value blocks (see [Key/value blocks](#keyvalue-blocks)).
- `step(message, *, ephemeral=False)`. Spinner context manager.
- `configure(*, verbosity=None, quiet=None, console=None, err_console=None, theme=None, logfile=None, loglevel=None, logfmt=None)`. Partial update of the default emitter.
- `Emitter`. Instantiate directly for isolated configuration.
- `Theme`, `Level`. Per-level style and marker overrides. Pass `Theme(success=Level(...))` to `configure()` or `Emitter()`.
- `Verbosity`. `IntEnum` with `INFO`, `DEBUG`, `TRACE`.
- `LogLevel`. `IntEnum` aligned with stdlib `logging` (`TRACE=5`, `DEBUG=10`, …, `CRITICAL=50`). Used as the `loglevel=` filter cutoff for the logfile.
- `THEME`. The Rich `Theme` used by default consoles, in case you build your own.
- `console()`, `err_console()`. Return the default emitter's stdout / stderr `Console` for direct Rich rendering. Re-resolves on each call.
- `get_default()`, `set_default(emitter)`. Read or replace the shared default emitter.
