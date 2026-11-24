# Pretty Printing

`nclutils.pp` prints themed console output for Python CLI scripts and can write a parallel logfile. It is a layer over [Rich](https://github.com/Textualize/rich) with one function per output level (`info`, `success`, `warning`, `error`, `critical`, `debug`, `trace`, `dryrun`), a spinner context manager (`step()`), stdout and stderr routing, and a marker glyph for each level.

```python
from nclutils import pp

pp.success("deployed to production")
pp.warning("API rate limit at 80%")
```

```text
✓ deployed to production
! API rate limit at 80%
```

Use `pp` in place of `print()` when a script needs `--verbose` and `--quiet` flags, separate stdout and stderr output, safe output of untrusted text, and a consistent theme.

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

`pp.step()` shows a spinner while the block runs. When the block ends, the spinner changes to a green checkmark and the sub-items stay on screen. The `details` list shows as a small tree under the message.

## Output levels

All eight level functions take the same arguments:

```python
pp.info(message, *, details=None, markup=False, style=None, detail_style=None,
        marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs)
```

| Function      | Stream | Marker                       | Console gate                  |
| ------------- | ------ | ---------------------------- | ----------------------------- |
| `pp.info`     | stdout | (none)                       | hidden by `quiet`             |
| `pp.success`  | stdout | `✓`                          | hidden by `quiet`             |
| `pp.warning`  | stderr | `!`                          | always shown                  |
| `pp.error`    | stderr | `✗`                          | always shown                  |
| `pp.critical` | stderr | `‼`                          | always shown                  |
| `pp.dryrun`   | stdout | `~ [dry-run]`                | always shown                  |
| `pp.debug`    | stdout | `›`                          | shown at `Verbosity.DEBUG` or higher |
| `pp.trace`    | stdout | `·`                          | shown at `Verbosity.TRACE`    |
| `pp.header`   | stdout | (rule line)                  | hidden by `quiet`             |
| `pp.kv`       | stdout | (none)                       | hidden by `quiet`             |
| `pp.step`     | stdout | spinner, then outcome marker | always shown                  |

`pp.critical` sets a severity only. It does not raise an exception. Use it when a failure needs more visual weight than `pp.error`.

`pp.debug` and `pp.trace` add a dim elapsed-time tag such as `[+0.512s]` at the right edge of the line. The clock starts at the first `debug` or `trace` call.

`pp.header()` draws a horizontal rule with an optional title, with a blank line above and below. Use it to divide long output into sections:

```python
pp.header("phase 1: download")
download_all()
pp.header("phase 2: process")
```

### Connect `--verbose` and `--quiet`

`pp.Verbosity` is an `IntEnum` with `INFO=0`, `DEBUG=1`, and `TRACE=2`, so the count from a `-v` flag maps directly to a level:

```python
import argparse
from nclutils import pp

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="count", default=0)
parser.add_argument("-q", "--quiet", action="store_true")
args = parser.parse_args()

pp.configure(verbosity=args.verbose, quiet=args.quiet)
```

The two settings are independent:

- `verbosity` controls only `debug` and `trace`. The default is `Verbosity.INFO`. Values out of range are clamped, so `-vvvvv` gives `TRACE`.
- `quiet=True` hides `info`, `success`, `header`, and `kv`. Warnings, errors, critical messages, dry-run notices, and steps are always shown.

With `--verbose --quiet` together, the script shows debug output without the routine info messages.

`pp.configure()` changes only the settings you pass. You can call it many times:

```python
pp.configure(verbosity=pp.Verbosity.DEBUG)
pp.configure(quiet=True)  # verbosity stays DEBUG
```

## Detail trees

Pass `details=[...]` to show items as a tree under the message:

```python
pp.success("deployed", details=["build #1742", "rollout 100%", "duration: 3.2s"])
```

```text
✓ deployed
  ├─ build #1742
  ├─ rollout 100%
  └─ duration: 3.2s
```

The level's `detail_style` colors string items, and Rich markup in them is escaped by default. Other items are shown with Rich: Rich renderables (`JSON`, `Syntax`, `Table`) render unchanged, and dicts, dataclasses, and other objects render through `rich.pretty.Pretty`. Multi-line items keep the tree connectors aligned.

```python
from rich.json import JSON

pp.debug("got response", details=[response_dict])
pp.debug("raw payload", details=[JSON(response_text)])
```

> [!NOTE]
> The logfile contains no tree connectors. Each line of each detail item is its own log record at the parent's severity, indented by two spaces.

## Markup and escaping

Every level function escapes Rich markup in strings by default, so `[red]` in a message shows as literal text. Pass `markup=True` to parse markup. A `rich.text.Text` message always keeps its own styling:

```python
from rich.text import Text
from nclutils import pp

pp.info("Found [bold]42[/] matches", markup=True)
pp.info(Text.from_markup("Found [bold]42[/] matches"))
```

Use `markup=True` only for strings you control. Keep the default for file paths, exception messages, and other external text, so that brackets do not change the style or raise `MarkupError`.

## Per-call tags

Every level function accepts `tag=` and `right_tag=` to add metadata to one message:

```python
pp.info("saved", tag="api", right_tag="200ms")
pp.error("upload failed", tag="uploader")
pp.dryrun("would push", tag="deploy")
```

```text
api saved                                                              200ms
✗ uploader upload failed
~ deploy [dry-run] would push
```

`tag` is dim text between the marker and the message. The logfile records it in brackets before the message, for example `[api] saved` and `[deploy] [dry-run] would push`.

`right_tag` is dim text aligned to the right edge of the first line. It is not written to the logfile. On `pp.debug` and `pp.trace`, `right_tag` replaces the elapsed-time tag on the console, and the logfile keeps the elapsed time.

If `message` is a Rich renderable other than `str` or `Text`, the marker, tags, and level style are not shown on the console.

> [!NOTE]
> `pp` does not escape `tag` or `right_tag`. Use plain text, or escape the `[` and `]` characters yourself.

## Tracebacks

Every level function accepts `exception=`. Pass an exception instance to show a Rich traceback under the message:

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

In an `except` block, you can pass `exception=True` to use the active exception from `sys.exc_info()`. Outside an `except` block, `exception=True` does nothing, the same as `logging.exception()`.

```python
try:
    upload()
except UploadError:
    pp.error("upload failed", exception=True)
```

Pass `show_locals=True` to include the local variables of each frame. The logfile receives the plain traceback as continuation lines at the same severity as the message.

`header()`, `kv()`, and `step()` do not accept `exception=`. In a step, use `s.fail(message, exception=...)`.

## Key/value blocks

`pp.kv()` shows aligned key/value pairs. Use it for status summaries and final-state output:

```python
pp.header("Build Status")
pp.kv(
    {
        "Branch": "main",
        "Commit": "abc1234",
        "Status": "clean",
        "Duration": "3.2s",
    }
)
```

```text
─────────────────── Build Status ───────────────────

  Branch:   main
  Commit:   abc1234
  Status:   clean
  Duration: 3.2s
```

`items` is a dict or a list of `(key, value)` tuples. Use the list form for duplicate keys:

```python
pp.kv([("Step", "init"), ("Step", "build"), ("Step", "deploy")])
```

Keys are padded to the widest key and are always escaped. `indent` (default `2`) sets the leading spaces, and `separator` (default `": "`) goes between key and value. Pass `markup=True` to parse Rich markup in string values. Other values go through `str()`, except Rich renderables such as `Table`, which show on the lines under their key, indented to the value column.

`quiet=True` hides `pp.kv()` on the console. The logfile still receives one INFO record for each pair, or one for each line of a multi-line value.

## The `step()` context manager

`pp.step()` shows a spinner while the block runs, then shows one of four outcomes:

```python
from nclutils import pp

with pp.step("running migrations") as s:
    for migration in pending:
        apply_migration(migration)
        s.sub(f"applied {migration.name}")
```

| Trigger                       | Console                                                        | Logfile                       |
| ----------------------------- | -------------------------------------------------------------- | ----------------------------- |
| The block ends normally       | `✓` and the success message                                    | `succeeded:` at INFO          |
| `s.fail(message)`             | `✗` and the message. The block stops at the call.              | `failed:` at ERROR            |
| `s.skip(message)`             | The message in info style, with no marker. The block stops at the call. | `skipped:` at INFO   |
| Another exception leaves the block | The original message with no marker. The exception propagates to the caller. | (no outcome line) |

The logfile also receives a `starting:` line when the step begins and one indented INFO line for each `s.sub()` call. When an exception propagates, the caller reports it.

Items from `s.sub()` show under the spinner and stay under the final line.

Pass `ephemeral=True` for progress that must not stay in the output. When the block ends normally or calls `s.skip()`, the spinner and sub-items are cleared and nothing stays on screen. After `s.fail()`, the step is cleared and a `✗ message` line is printed on stderr, so failures stay visible.

```python
with pp.step("warming caches", ephemeral=True) as s:
    warm_cache()
    s.sub("cache populated")
```

> [!WARNING]
> `pp.step()` cannot nest. A second `step()` on the same emitter while one is active raises `RuntimeError`, because Rich's `Live` display cannot stack.

### Change the success message

By default, the success line repeats the original message. To show different text, pass `success_msg`:

```python
with pp.step("compiling sources", success_msg="compiled 42 files in 1.2s") as s:
    s.sub("api.py")
    s.sub("cli.py")
```

The success line shows `✓ compiled 42 files in 1.2s`, and the logfile records the same text after `succeeded:`. The step's `markup=` argument applies to both `message` and `success_msg`.

If the text depends on work done in the block, call `s.set_success_msg()`:

```python
with pp.step("compiling sources") as s:
    for path in sources:
        compile_one(path)
        s.sub(path.name)
    s.set_success_msg(f"compiled {len(sources)} files")
```

`s.set_success_msg()` takes priority over `success_msg`, and has its own `markup=` argument. It does not end the block. It has no effect if the block ends with `s.fail()`, `s.skip()`, or an exception.

### Fail a step

Call `s.fail(message)` to show the failure marker and stop the block. Code after the call does not run:

```python
with pp.step("compiling sources") as s:
    for path in sources:
        if not path.exists():
            s.fail(f"missing source: {path}")
        compile_one(path)
```

Pass `exception=` to write the exception's traceback to the logfile under the `failed:` line. The console shows only the message. Pass an exception instance, or `True` in an `except` block:

```python
with pp.step("compiling sources") as s:
    try:
        compile_all(sources)
    except CompileError as exc:
        s.fail("compilation aborted", exception=exc)
```

`s.fail()` is the only way to show the failure marker. To report an expected error as a step failure, catch it in the block and call `s.fail()`.

### Skip a step

Call `s.skip(message)` when the work does not need to run, for example when there is nothing to do. A skip is not an error. The message shows in info style with no marker, and the block stops at the call:

```python
with pp.step("warming caches") as s:
    if cache.is_warm():
        s.skip("caches already warm")
    warm_cache()
```

## File logging

Pass `logfile=` to write a record of every message to a file:

```python
from pathlib import Path
from nclutils import pp

pp.configure(
    logfile=Path("./run.log"),
    loglevel=pp.LogLevel.INFO,  # the default cutoff
)

pp.info("starting build")
with pp.step("compile assets") as s:
    s.sub("app.css")
    s.sub("app.js")
```

`run.log` then contains:

```text
2026-05-04 14:32:01.234 | INFO     | starting build
2026-05-04 14:32:01.234 | INFO     | starting: compile assets
2026-05-04 14:32:01.235 | INFO     |   app.css
2026-05-04 14:32:01.235 | INFO     |   app.js
2026-05-04 14:32:01.236 | INFO     | succeeded: compile assets
```

The file is opened in append mode when the first record is written. If the parent directory does not exist or the file cannot be opened, that call raises the `OSError` from the file handler, for example `FileNotFoundError`. Pass `logfmt=` to replace the default format string, `"%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s"`, with any stdlib `logging` format.

The console and the file are independent. The console ignores `loglevel`, and the file ignores `quiet` and `verbosity`. Every level function writes to the file before it applies its console gate, so the logfile has a full record of the run.

### What goes to the logfile

| Call                          | Severity                     | Content                                                       |
| ----------------------------- | ---------------------------- | ------------------------------------------------------------- |
| `info`, `success`, `dryrun`   | `INFO` (20)                  | `dryrun` adds `[dry-run]` before the message.                 |
| `debug`                       | `DEBUG` (10)                 | The elapsed time follows the message.                         |
| `trace`                       | `TRACE` (5)                  | The elapsed time follows the message. `TRACE` is registered with stdlib `logging`. |
| `warning`                     | `WARNING` (30)               |                                                               |
| `error`                       | `ERROR` (40)                 |                                                               |
| `critical`                    | `CRITICAL` (50)              |                                                               |
| `step()`                      | `INFO`, or `ERROR` for `failed:` | `starting:`, one line per `sub()`, then the outcome line. |
| `kv()`                        | `INFO` (20)                  | One record for each pair, or for each line of a multi-line value. |
| `header()`                    | (not logged)                 |                                                               |

`loglevel` filters by severity. For example, `loglevel=pp.LogLevel.WARNING` drops `info`, `success`, `dryrun`, `debug`, and `trace` records together with their detail lines. You cannot filter by function, for example to log only `success`.

The logfile does not rotate files, write JSON, send to syslog, or coordinate between processes. For rotation, use an external tool such as `logrotate`.

`configure(logfile=None)` leaves the logfile unchanged. To stop file logging, replace the default emitter: `pp.set_default(pp.Emitter())`.

## Theming

Each of the eight output levels (`info`, `success`, `warning`, `error`, `critical`, `debug`, `trace`, `dryrun`) has three settings: the message style, the detail style, and the marker glyph. Set any of them with a `pp.Theme` of `pp.Level` values:

```python
from nclutils import pp

pp.configure(
    theme=pp.Theme(
        success=pp.Level(style="cyan", marker="🎉 "),
        warning=pp.Level(marker=""),  # no marker
    ),
)

pp.success("deployed", details=["build #1742"])
```

A field you do not set keeps its default. `pp.Level(style="cyan")` changes only the message style. `marker=""` hides the marker, and `marker=None` (the default) keeps the default glyph.

Successive `pp.configure(theme=...)` calls combine field by field:

```python
pp.configure(theme=pp.Theme(success=pp.Level(style="blue", marker="🎉 ")))
pp.configure(theme=pp.Theme(success=pp.Level(detail_style="navy")))
# success has style="blue", detail_style="navy", marker="🎉 "
```

To go back to the default theme, replace the emitter: `pp.set_default(pp.Emitter())`.

To change the style for one message only, pass `style=`, `detail_style=`, or `marker=` to the level function. These arguments do not change the logfile.

### Styles outside the theme

`pp.Theme` does not control these parts of the output:

- The `[dry-run]` text on `pp.dryrun` is fixed.
- `pp.header()` passes extra keyword arguments to Rich's `Console.rule()`. Use `characters=` for the line glyph and `style=` for the line style, for example `pp.header("phase", characters="=")`.
- The tree connectors under `details` and `pp.step()` use the `sub.pipe` style of the console (default `bright_black`). The header title uses `header` and the rule uses `header.rule`. To change these styles, pass a `Console` with your own Rich theme to `pp.Emitter(console=...)` or `pp.configure(console=...)`.

> [!TIP]
> If you make your own `Console`, pass `theme=pp.THEME` or a theme that defines `sub.pipe`, `header`, and `header.rule`. Without those keys, connectors and rules show without style and no error occurs.

### ASCII fallback

If the console encoding cannot show the default Unicode glyphs (for example with `LANG=C` or `PYTHONIOENCODING=ascii`), `pp` uses ASCII. There is no flag to set.

- Detail trees and step sub-items use a `- ` prefix in place of `├─`, `└─`, and `│`.
- Default markers change as the table shows.

| Level    | Unicode | ASCII  |
| -------- | ------- | ------ |
| info     | (none)  | (none) |
| success  | `✓`     | `+`    |
| warning  | `!`     | `!`    |
| error    | `✗`     | `x`    |
| critical | `‼`     | `!!`   |
| debug    | `›`     | `>`    |
| trace    | `·`     | `.`    |
| dryrun   | `~`     | `~`    |

A marker you set in `pp.Theme` or with `marker=` is always shown as you wrote it. To force one mode, pass a `Console` with the encoding you want to `pp.configure(console=...)` or `pp.Emitter(console=...)`.

## Capturing output

Rich folds a line that is longer than the console width. In a terminal, this is correct. When another program captures the output, a folded path or URL arrives as two tokens:

```bash
# If the output folds, a long path arrives split in two
INBOX=$(myapp path --inbox)
```

The `soft_wrap` setting controls folding. The default, `None`, decides for each console: output to a terminal folds at the terminal width, and other output is not folded. Thus a piped stdout does not fold while stderr in a terminal still folds.

To force one behavior:

```python
from nclutils import pp

pp.configure(soft_wrap=True)  # never fold
pp.configure(soft_wrap=False)  # always fold at the console width

pp.info(long_path, soft_wrap=False)  # one call, takes priority over the emitter
```

The setting applies to the level functions, `pp.kv()`, and `pp.step()`. It does not apply to `pp.header()`, because a rule always fills the console width.

`configure(soft_wrap=None)` leaves the setting unchanged. To go back to automatic detection, set the attribute: `pp.get_default().soft_wrap = None`.

A `pp.step()` that does not fold shows no spinner. It prints its final state once when the block ends, because Rich's live display crops to the console width.

## Library use and testing

The module-level functions use a shared default `Emitter`. A library that needs its own output settings, separate from the host CLI, can make its own `Emitter`:

```python
from nclutils import pp

output = pp.Emitter(verbosity=pp.Verbosity.DEBUG)
output.info("library message")
output.debug("only this emitter's verbosity applies")
```

Each `Emitter` has its own `verbosity`, `quiet`, `soft_wrap`, theme, consoles, and logfile. An `Emitter` has the same methods as the module: the eight level functions, `header()`, `kv()`, `step()`, and `configure()`.

To show a Rich object (`Table`, `Syntax`, `Panel`) on the same stream as the level functions, use `pp.console()` and `pp.err_console()`:

```python
from rich.table import Table
from nclutils import pp

table = Table("name", "status")
table.add_row("api", "ok")
pp.console().print(table)

pp.err_console().print("[bold red]fatal[/]")
```

In tests, give the emitter a recording console and examine its output:

```python
from rich.console import Console
from nclutils import pp

capture = Console(theme=pp.THEME, record=True, force_terminal=True, width=80)
test_emitter = pp.Emitter(console=capture, err_console=capture)
test_emitter.info("captured")
assert "captured" in capture.export_text()
```

> [!NOTE]
> A Rich theme on your own `Console` does not change level styles, because `pp` resolves level styles itself. Use `pp.Theme` for level styles. `Console(theme=pp.THEME)` supplies the `header`, `header.rule`, and `sub.pipe` styles.

To send the module-level functions to a test emitter, swap the default and restore it after the test:

```python
from nclutils import pp

original = pp.get_default()
pp.set_default(test_emitter)
try:
    run_code_under_test()
finally:
    pp.set_default(original)
```

## API reference

Every name below is available as `pp.<name>` after `from nclutils import pp`, and as `from nclutils.pp import <name>`.

### Output functions

`info`, `success`, `warning`, `error`, `critical`, `dryrun`, `debug`, and `trace` take the same arguments and return `None`:

- `message`: a `str`, a `rich.text.Text`, or another Rich renderable. Strings are escaped unless `markup=True`.
- `details=None`: a list of items to show as a tree under the message. See [Detail trees](#detail-trees).
- `markup=False`: parse Rich markup in `message` and in string `details` items.
- `style=None`, `detail_style=None`, `marker=None`: change the level's theme for this call only.
- `tag=None`, `right_tag=None`: see [Per-call tags](#per-call-tags).
- `exception=False`, `show_locals=False`: an exception instance, or `True` for the active exception. See [Tracebacks](#tracebacks).
- `**kwargs`: passed to Rich's `Console.print()`. This includes `soft_wrap=`, which takes priority over the emitter's [line folding](#capturing-output) setting.

### Structural output

```python
header(message="", *, align="center", markup=False, **kwargs) -> None
kv(items, *, indent=2, separator=": ", markup=False) -> None
```

- `header`: `message` is a `str` or `Text`. `align` is `"left"`, `"center"`, or `"right"`. Other keyword arguments go to `Console.rule()`.
- `kv`: `items` is a `dict[str, Any]` or a `list[tuple[str, Any]]`.

### `step()` context manager

```python
step(message, *, ephemeral=False, markup=False, success_msg=None)
```

Use `step()` in a `with` statement. It gives a `Step` object with these methods:

```python
Step.sub(text, *, markup=False) -> None
Step.set_success_msg(message, *, markup=False) -> None
Step.fail(message, *, exception=False, markup=False) -> NoReturn
Step.skip(message, *, markup=False) -> NoReturn
```

- `s.sub()`: add a line under the spinner. It stays under the final line unless the step is ephemeral.
- `s.set_success_msg()`: set the success message. It does not end the block.
- `s.fail()`: end the block with a failure. Pass `exception=` to write a traceback to the logfile.
- `s.skip()`: end the block with a skip.

Raises `RuntimeError` if a step is already active on the same emitter.

### Configuration

```python
configure(*, verbosity=None, quiet=None, console=None, err_console=None,
          theme=None, soft_wrap=None, logfile=None, loglevel=None, logfmt=None) -> None
```

Changes the settings you pass on the shared default emitter and leaves the others unchanged. `None` means "no change" for every argument. `theme` combines with the existing theme field by field.

### Emitter and supporting types

- `Emitter(*, verbosity=Verbosity.INFO, quiet=False, console=None, err_console=None, theme=None, soft_wrap=None, logfile=None, loglevel=LogLevel.INFO, logfmt=None)`: an independent output stream. It takes the same arguments as `configure()`. `console` and `err_console` default to new Rich consoles with `THEME`. `logfile` is a `Path` or `str`, and `None` writes no file. `verbosity`, `quiet`, `soft_wrap`, `console`, and `err_console` are also attributes that you can set.
- `Theme`, `Level`: per-level style and marker settings. `Theme` has one optional `Level` field for each of the eight levels, and `Level` has `style`, `detail_style`, and `marker`.
- `Verbosity`: `IntEnum` with `INFO=0`, `DEBUG=1`, `TRACE=2`.
- `LogLevel`: `IntEnum` with the stdlib `logging` values `TRACE=5`, `DEBUG=10`, `INFO=20`, `WARNING=30`, `ERROR=40`, `CRITICAL=50`. Use it for `loglevel=`.
- `THEME`: the Rich `Theme` of the default consoles. Pass it to a `Console` that you make yourself.
- `console()`, `err_console()`: return the stdout and stderr `Console` of the current default emitter.
- `get_default()`, `set_default(emitter)`: return or replace the shared default emitter. The module-level functions use the new emitter at once.
