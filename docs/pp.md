# Pretty Printing

Themed console output and a parallel logfile for Python CLI scripts. A thin layer over [Rich](https://github.com/Textualize/rich) that gives you `info` / `success` / `warning` / `error` / `debug` / `trace` / `dryrun` calls, a spinner-driven `step()` context manager, automatic stdout/stderr routing, and per-level markers.

```python
from nclutils import pp

pp.success("deployed to production")
pp.warning("API rate limit at 80%")
```

```
✓ deployed to production

! API rate limit at 80%
```

`pp` handles the four things that grow out of `print()` in any non-trivial CLI script: `--verbose` / `--quiet` gating, stdout/stderr routing, Rich-markup escaping for untrusted input, and a consistent theme.

## Quick start

```python
import time
from nclutils import pp

pp.info("starting build")

with pp.step("compiling sources") as s:
    time.sleep(0.5)
    s.sub("src/api.py")
    s.sub("src/cli.py")

pp.success("build complete", details=["artifact: dist/app-1.4.2.tar.gz"])
```

`pp.step()` shows a live spinner while the body runs. On natural completion it resolves to a green checkmark, and the sub-items remain on screen. `pp.success(..., details=[...])` renders the details as a small tree beneath the message.

## Output levels

Every level method routes through the same shape:

```python
pp.func(message, *, details=None, markup=False, tag=None, right_tag=None, exception=False)
```

| Function      | Stream | Marker                       | Gated by                   |
| ------------- | ------ | ---------------------------- | -------------------------- |
| `pp.info`     | stdout | (none)                       | `quiet` suppresses         |
| `pp.success`  | stdout | `✓`                          | `quiet` suppresses         |
| `pp.warning`  | stderr | `!`                          | always renders             |
| `pp.error`    | stderr | `✗`                          | always renders             |
| `pp.critical` | stderr | `‼`                          | always renders             |
| `pp.dryrun`   | stdout | `~ [dry-run]`                | always renders             |
| `pp.debug`    | stdout | `›`                          | shown at `DEBUG` or higher |
| `pp.trace`    | stdout | `·`                          | shown at `TRACE`           |
| `pp.header`   | stdout | (rule line)                  | `quiet` suppresses         |
| `pp.step`     | stdout | spinner, then outcome marker | always renders             |

`pp.critical` is severity-only and does not raise. Use it for "the world is broken" notices that warrant more visual weight than `pp.error`.

`pp.header()` draws a `Console.rule()` with an optional centered title to break long output into scannable sections:

```python
pp.header("phase 1: download")
# ... work ...
pp.header("phase 2: process")
```

### Wiring up `--verbose` and `--quiet`

`pp.Verbosity` is an `IntEnum` with `INFO`, `DEBUG`, `TRACE`, so a `-v` count flag maps cleanly:

```python
import argparse
from nclutils import pp

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="count", default=0)
parser.add_argument("-q", "--quiet", action="store_true")
args = parser.parse_args()

pp.configure(verbosity=args.verbose, quiet=args.quiet)
```

The two flags are independent:

- `verbosity` only gates `debug` and `trace`. The default is `INFO`. Out-of-range integers are clamped, so `-vvvvv` is safe.
- `quiet=True` suppresses `info`, `success`, `header`, and `kv`. Warnings, errors, dry-run notices, and step lifecycle still render.

Combining `--verbose --quiet` is reasonable: debug output without the routine info chatter.

`pp.configure()` is a partial update. Fields you don't pass are left alone, so you can call it as many times as you like:

```python
pp.configure(verbosity=pp.Verbosity.DEBUG)
pp.configure(quiet=True)   # verbosity still DEBUG
```

## Detail trees

Pass `details=[...]` to render items as a tree beneath the message. Non-final items are prefixed with `├─`, the final item with `└─`:

```python
pp.success("deployed", details=["build #1742", "rollout 100%", "duration: 3.2s"])
```

```text
✓ deployed
  ├─ build #1742
  ├─ rollout 100%
  └─ duration: 3.2s
```

String items are escaped by default and colored with the level's `detail_style`. Multi-line renderables (Tables, JSON, multi-line `Pretty` outputs) get a `│ ` continuation pipe under non-final positions and a blank gutter under the final position. Non-strings auto-render with Rich: dicts, dataclasses, and arbitrary objects go through `Pretty`; `JSON` / `Syntax` / `Table` pass through unchanged.

```python
from rich.json import JSON

pp.debug("got response", details=[response_dict])
pp.debug("raw payload", details=[JSON(resp.text)])
```

The connector glyphs share the `sub.pipe` Rich theme key (the same one `pp.step()` uses for its sub-items), so retuning that one entry restyles every tree connector across the API.

> [!NOTE]
> Tree connectors appear in stdout/stderr only. In logfile records, each detail item becomes its own log record at the parent's severity with the detail text in the standard `%(message)s` field, prefixed by two spaces. The file does not contain `├─`, `└─`, or `│` characters.

## Markup and escaping

Strings passed to any level method are Rich-markup-escaped by default. `[red]` in a message renders literally, not as styling. Pass `markup=True` to opt into parsing:

```python
from rich.text import Text
from nclutils import pp

pp.info("Found [bold]42[/] matches", markup=True)
pp.info(Text.from_markup("Found [bold]42[/] matches"))   # Text instances always keep their styling
```

Use `markup=True` only when you control the string. For arbitrary input (file paths, exception messages, JSON snippets), keep the default escape so brackets can't accidentally render as styling or raise `MarkupError`.

## Per-call tags

Every level method accepts `tag=` and `right_tag=` for one-off metadata:

```python
pp.info("saved", tag="api", right_tag="200ms")
pp.error("upload failed", tag="uploader")
```

```text
[api] saved                                                            200ms
[uploader] ✗ upload failed
```

`tag` is dim text rendered between the marker and the message. It is recorded inline in the logfile (`[api] saved`) so file consumers see the same metadata that appeared on the console.

`right_tag` is dim text right-aligned to the console width on the first line only. It is presentation-only and is never written to the logfile.

When `right_tag` is passed to `pp.debug` or `pp.trace`, the caller's value replaces the auto-elapsed `[+s.fffs]` marker on the console. The logfile still records the elapsed timing so the audit trail is preserved.

`pp.dryrun` combines a caller-supplied `tag` with its built-in `[dry-run]` marker on both the console and the logfile, with the caller's tag rendered first (`[deploy] [dry-run] would push`).

> [!NOTE]
> The caller is responsible for Rich-markup-escaping any `[`, `]`, or other reserved characters in `tag` and `right_tag`. Pass plain ASCII tags or pre-escaped strings.

## Tracebacks

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

Pass `show_locals=True` for verbose dumps that include each frame's local variables. The formatted traceback is also written to the logfile as continuation lines under the parent record at the same severity, so a level filter drops the traceback alongside its message.

> [!NOTE]
> `exception=` is accepted on every level method (`info`, `success`, `warning`, `error`, `critical`, `debug`, `trace`, `dryrun`). It is not supported on `header()` or `step()`, both of which manage their own outcome display. For `step()`, use `s.fail(message, exception=...)` instead.

## Key/value blocks

`pp.kv()` renders aligned key/value pairs as a clean section block, useful for status summaries and final-state output:

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

Keys are padded automatically. Pass a `list[tuple[str, Any]]` when you need duplicate keys or want explicit ordering:

```python
pp.kv([
    ("Step", "init"),
    ("Step", "build"),
    ("Step", "deploy"),
])
```

`indent=2` and `separator=": "` are the defaults. Pass `markup=True` to parse Rich markup in string values. Keys are always escaped (treated as identifiers). Non-string, non-renderable values pass through `str()`. Rich renderables (Tables, JSON, etc.) render below the key, indented to the value column.

> [!NOTE]
> `pp.kv()` is suppressed on the console by `quiet=True`, the same as `pp.info()` and `pp.success()`. Each pair is still recorded as one INFO record in the logfile (or one record per visual line for multi-line values), so the audit trail stays complete even under quiet.

## The `step()` context manager

`pp.step()` renders a Rich `Live` spinner while the body runs, then resolves to one of four outcomes:

```python
from nclutils import pp

with pp.step("running migrations") as s:
    for migration in pending:
        run(migration)
        s.sub(f"applied {migration.name}")
```

| Trigger                                  | Outcome                                                                                                                          |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Block exits naturally                    | Green `✓` marker. The success line keeps the original `message` (or whatever `success_msg=` / `s.set_success_msg()` set).        |
| `s.fail(msg)` called inside the block    | Red `✗` marker, `failed:` logfile entry. The block exits early; code after `s.fail()` does not run.                              |
| `s.skip(msg)` called inside the block    | Info-styled completion (no checkmark, no error glyph), `skipped:` logfile entry. The block exits early.                          |
| Any other exception escapes the block    | Exception propagates to the caller. No marker, no log line. The spinner is replaced with a static line so it doesn't stay frozen on screen; sub-items remain. The caller owns error reporting. |

Sub-items added via `s.sub()` render beneath the spinner during the step and remain on screen beneath the final completion line.

For transient progress that shouldn't clutter the final transcript, pass `ephemeral=True`. The spinner and sub-items are wiped on natural completion or `s.skip()`, leaving no console trace. `s.fail()` still surfaces a fresh `✗ message` line on stderr after wiping, so failures aren't silently hidden.

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

The success line resolves to `✓ compiled 42 files in 1.2s`. The override is also recorded in the `succeeded:` logfile entry.

When the success text depends on work done inside the block (a count, a duration, an output path), call `s.set_success_msg()`:

```python
with pp.step("compiling sources") as s:
    processed = []
    for path in sources:
        compile_one(path)
        processed.append(path)
        s.sub(path.name)
    s.set_success_msg(f"compiled {len(processed)} files")
```

The setter wins over the `success_msg` kwarg, which wins over the original message. Each takes its own `markup=` flag. `s.set_success_msg()` does not exit the block; it just records the message for natural completion.

### Failing a step

Call `s.fail(message)` inside the block to render the failure marker and exit early. Code after the call doesn't run:

```python
with pp.step("compiling sources") as s:
    for path in sources:
        if not path.exists():
            s.fail(f"missing source: {path}")   # exits here
        compile_one(path)
    s.set_success_msg(f"compiled {len(sources)} files")
```

To attach an exception's type and message to the `failed:` log line, pass `exception=`:

```python
with pp.step("compiling sources") as s:
    try:
        compile_all(sources)
    except CompileError as e:
        s.fail("compilation aborted", exception=e)
```

> [!NOTE]
> `s.fail()` is the only way to render the failure marker. An uncaught exception inside `step()` propagates through cleanly with no marker and no log line, leaving the original message visible (no spinner) and any sub-items intact. The caller owns error reporting in that path.

### Skipping a step

Call `s.skip(message)` when the work didn't run (nothing to do, preconditions unmet, intentional bypass). Skip is not an error: the completion renders with info-level styling (no checkmark, no error glyph) and the logfile records a `skipped:` line:

```python
with pp.step("warming caches") as s:
    if cache.is_warm():
        s.skip("caches already warm")   # exits here
    warm_cache()
```

In ephemeral mode, skip wipes the spinner with no extra output:

```python
with pp.step("warming caches", ephemeral=True) as s:
    if cache.is_warm():
        s.skip("caches already warm")
# wipes with no console output
```

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

Console and file rendering are independent. The console ignores `loglevel`; the file ignores `quiet` and `verbosity`. Every level method writes to the file before checking its console gate, so the logfile is a complete audit trail.

### What gets logged

| Emission                      | Logged at                     | Notes                                                                                                  |
| ----------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| `info` / `success` / `dryrun` | `INFO` (20)                   | `success`/`dryrun` aren't real severities. `dryrun` keeps `[dry-run]` inline.                          |
| `debug`                       | `DEBUG` (10)                  | `[+s.fffs]` elapsed tag inlined into message.                                                          |
| `trace`                       | `TRACE` (5)                   | Custom level registered with stdlib `logging` at import.                                               |
| `warning`                     | `WARNING` (30)                |                                                                                                        |
| `error`                       | `ERROR` (40)                  |                                                                                                        |
| `critical`                    | `CRITICAL` (50)               | Severity-only and does not raise.                                                                      |
| `step()` lifecycle            | `INFO` start, outcome at exit | `succeeded:` / `failed:` / `skipped:` line at exit. Uncaught exceptions write only the `starting:` line. |
| `Step.sub()`                  | `INFO`                        | Indented continuation, written immediately.                                                            |
| `kv()`                        | `INFO` (20)                   | One INFO record per pair; one per visual line for multi-line values. Recorded even under `quiet=True`. |
| `header()`                    | (not logged)                  | Console-only structural sugar.                                                                         |

Filtering with `loglevel=pp.LogLevel.WARNING` drops every `info` / `success` / `dryrun` / `debug` / `trace` emission and its detail continuations together. `LogLevel` filters by severity, not by emission type, so there's no way to "log only successes."

### What's not included

The logfile is for CLI audit and diagnostic capture. It doesn't ship rotation, JSON output, syslog, or multi-process safety. If you need those, run `pp` on top of your own preconfigured `logging.Logger`, or use external rotation (`logrotate`, `savelog`).

## Theming

The seven output levels (`info`, `success`, `warning`, `error`, `debug`, `trace`, `dryrun`) each expose three things you can override: the main message style, the indented detail style, and the marker glyph. Override any combination in a `Theme`:

```python
from nclutils import pp

pp.configure(
    theme=pp.Theme(
        success=pp.Level(style="cyan", marker="🎉 "),
        warning=pp.Level(marker=""),   # hide the warning marker entirely
    ),
)

pp.success("deployed", details=["build #1742"])
```

Anything you don't set keeps its default. `pp.Level(style="cyan")` only changes the main color; `detail_style` and `marker` stay as the defaults. Pass `marker=""` (empty string) to suppress a marker; `marker=None` (the default) keeps the built-in glyph.

Successive `pp.configure(theme=...)` calls accumulate at the field level:

```python
pp.configure(theme=pp.Theme(success=pp.Level(style="blue", marker="🎉 ")))
pp.configure(theme=pp.Theme(success=pp.Level(detail_style="navy")))
# success now has style="blue", detail_style="navy", marker="🎉 "
```

To fully reset, build a fresh emitter: `pp.set_default(pp.Emitter())`.

### What's not themed

The horizontal rule under `pp.header()` and the `[dry-run]` tag are not customizable. The `├─`/`└─` connector glyphs beneath `pp.step()` and `details` lists share the `sub.pipe` Rich theme entry on the underlying console (defaulting to `bright_black`); the glyph characters themselves are fixed, and the `pp.Theme` dataclass does not expose a field to retune their style. To override it, build a custom `Console(theme=...)` and pass it via `pp.Emitter(console=...)`.

### ASCII fallback

When the console's encoding can't produce the default unicode glyphs (`LANG=C`, `PYTHONIOENCODING=ascii`, or a Windows host whose code page rejects box-drawing characters), `pp` falls back to ASCII automatically. Detection is automatic; there is no flag to set.

- Detail tree connectors (`├─`, `└─`, `│`) collapse to a simple `- ` prefix on every line, with continuation lines aligned under the value column.
- `pp.step()` sub-items render with the same `- ` prefix instead of tree connectors.
- Default level markers fall back per the table below.

| Level    | Unicode | ASCII |
| -------- | ------- | ----- |
| info     | (none)  | (none)|
| success  | `✓`     | `+`   |
| warning  | `!`     | `!`   |
| error    | `✗`     | `x`   |
| critical | `‼`     | `!!`  |
| debug    | `›`     | `>`   |
| trace    | `·`     | `.`   |
| dryrun   | `~`     | `~`   |

User-supplied `pp.Theme(level=pp.Level(marker=...))` markers are always respected verbatim, even on ASCII consoles. The fallback only triggers when a level still has its built-in default marker.

> [!NOTE]
> Detection probes `console.encoding` at render time and chooses the rendering path per call. To force one path or the other, build your own `Console` with the desired encoding and pass it via `pp.configure(console=...)` or `pp.Emitter(console=...)`.

## Capturing output

Rich folds a line that exceeds the console width. When output goes to a real terminal that is what you want. When output is captured, it corrupts the data: a folded path or URL arrives at the caller as two tokens.

```bash
# Without soft wrapping, a path longer than the console width arrives split in two
INBOX=$(myapp path --inbox)
```

`pp` handles this for you. `soft_wrap` defaults to `None`, which auto-detects **per console**: fold at the terminal width when writing to a tty, emit unfolded lines otherwise. Because it resolves per console, a piped stdout soft-wraps while an interactive stderr keeps folding.

Force it either way when the default is wrong:

```python
from nclutils import pp

pp.configure(soft_wrap=True)   # never fold, whatever the stream is
pp.configure(soft_wrap=False)  # always fold at the console width

pp.info(long_path, soft_wrap=False)  # per-call override, wins over the emitter
```

This covers the level functions, `pp.kv()`, and `pp.step()` sub-items. `pp.header()` is unaffected, since a rule is defined by the console width.

> [!NOTE]
> `configure(soft_wrap=None)` is a no-op, matching the partial-update contract shared by every `configure()` kwarg. To return an emitter to auto-detection, assign `emitter.soft_wrap = None` directly.

A soft-wrapping `pp.step()` forgoes the spinner and draws its final state once when the block exits. Rich's live display renders through the console width and crops to it, so a spinner and unfolded output cannot coexist. This costs nothing in practice: a captured stream has no one watching an animation.

> [!TIP]
> If you build your own `Console` rather than letting `pp` construct one, pass `theme=pp.THEME`. Without it, the `sub.pipe` and `header` style keys resolve to nothing and detail connectors and section rules render unstyled. There is no error, just silently plain output.

## Library use and testing

The module-level functions delegate to a shared default `Emitter`. If you're writing a library that needs its own output configuration without trampling its host CLI's settings, instantiate an `Emitter` directly:

```python
from nclutils import pp

logger = pp.Emitter(verbosity=pp.Verbosity.DEBUG, quiet=False)
logger.info("library-internal message")
logger.debug("only this emitter's verbosity matters here")
```

Each `Emitter` owns its own `verbosity`, `quiet`, `console`, `err_console`, and logfile. Nothing leaks across instances.

When you need to render a Rich object (`Table`, `Syntax`, `Panel`, etc.) on the same stream the level functions write to, use `pp.console()` and `pp.err_console()`:

```python
from rich.table import Table
from nclutils import pp

table = Table("name", "status")
table.add_row("api", "ok")
pp.console().print(table)

pp.err_console().print("[bold red]fatal[/]")
```

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

### Output functions

`info`, `success`, `warning`, `error`, `critical`, `dryrun`, `debug`, `trace`. Every level method accepts:

- `message`: the body text. Strings are escaped unless `markup=True`. Rich renderables pass through unchanged.
- `details=None`: optional iterable rendered as a tree beneath the message.
- `markup=False`: parse Rich markup in `message` and string `details` items.
- `tag=None` / `right_tag=None`: see [Per-call tags](#per-call-tags).
- `exception=False` / `show_locals=False`: see [Tracebacks](#tracebacks).
- `style=None` / `detail_style=None` / `marker=None`: per-call overrides of the level's theme.
- `soft_wrap=None`: per-call override of the emitter's [line folding](#capturing-output) behavior.

### Structural output

```python
header(message="", *, align="center", markup=False, **kwargs) -> None    # **kwargs forwarded to Console.rule()
kv(items, *, indent=2, separator=": ", markup=False) -> None
```

### `step()` context manager

```python
step(message, *, ephemeral=False, markup=False, success_msg=None) -> Generator[Step]
```

The yielded `Step` object has four public methods:

```python
Step.sub(text, *, markup=False) -> None
Step.set_success_msg(message, *, markup=False) -> None
Step.fail(message, *, exception=False, markup=False) -> NoReturn
Step.skip(message, *, markup=False) -> NoReturn
```

- `s.sub()`: append a sub-item beneath the spinner. Persists beneath the completion line in non-ephemeral mode.
- `s.set_success_msg()`: override the success header. Does NOT exit the block; applied at natural completion. Ignored if the block exits via `fail()`, `skip()`, or an uncaught exception.
- `s.fail()`: exit the block with a failure outcome (renders `✗`, writes `failed:` to the logfile). Pass `exception=` to attach exception details. Code after the call doesn't run.
- `s.skip()`: exit the block with a skip outcome (info-styled completion, `skipped:` log line). Code after the call doesn't run.

### Configuration

```python
configure(*, verbosity=None, quiet=None, console=None, err_console=None,
          theme=None, soft_wrap=None, logfile=None, loglevel=None, logfmt=None) -> None
```

Partial update of the shared default emitter. Fields you don't pass are left alone.

### Emitter and supporting types

- `Emitter(*, verbosity=Verbosity.INFO, quiet=False, console=None, err_console=None, theme=None, soft_wrap=None, logfile=None, loglevel=LogLevel.INFO, logfmt=None)`: instantiate directly for isolated configuration. Same kwargs as `configure()`, but with positive defaults instead of `None`.
- `Theme`, `Level`: per-level style and marker overrides. Pass `Theme(success=Level(...))` to `configure()` or `Emitter()`.
- `Verbosity`: `IntEnum` with `INFO`, `DEBUG`, `TRACE`.
- `LogLevel`: `IntEnum` aligned with stdlib `logging` (`TRACE=5`, `DEBUG=10`, …, `CRITICAL=50`). Used as the `loglevel=` filter cutoff for the logfile.
- `THEME`: the Rich `Theme` used by default consoles, in case you build your own.
- `console()`, `err_console()`: return the default emitter's stdout / stderr `Console` for direct Rich rendering. Re-resolves on each call.
- `get_default()`, `set_default(emitter)`: read or replace the shared default emitter.
