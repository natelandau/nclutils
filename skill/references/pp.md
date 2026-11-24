# `nclutils.pp` reference

Rich-based console output with an optional parallel logfile. Import `from nclutils import pp` (the only name the top-level `nclutils` package exports), or per symbol: `from nclutils.pp import info, step`.

## Public names

| Name | Kind | Section |
| --- | --- | --- |
| `info`, `success`, `warning`, `error`, `critical`, `debug`, `trace`, `dryrun` | Level functions | [Level functions](#level-functions) |
| `header` | Section rule | [`header()`](#header) |
| `kv` | Aligned key/value block | [`kv()`](#kv) |
| `step` | Spinner context manager | [`step()`](#step) |
| `configure` | Partial update of default | [Configuration](#configuration) |
| `Emitter`, `get_default`, `set_default` | Isolated emitters | [Emitters](#emitters) |
| `console`, `err_console` | Default emitter's consoles | [Emitters](#emitters) |
| `Theme`, `Level`, `THEME` | Styling | [Themes](#themes) |
| `Verbosity`, `LogLevel` | `IntEnum`s | [Enums](#enums) |

`Step` (yielded by `step()`) is not exported; reach it only through `with pp.step(...) as s`.

## Level functions

All eight share one signature (module function and `Emitter` method alike):

```python
info(
    message: str | RenderableType,
    *,
    details: list[Any] | None = None,
    markup: bool = False,
    style: str | None = None,
    detail_style: str | None = None,
    marker: str | None = None,
    tag: str | None = None,
    right_tag: str | None = None,
    exception: BaseException | bool = False,
    show_locals: bool = False,
    **kwargs: Any,  # forwarded to Console.print(), e.g. soft_wrap=, end=, highlight=
) -> None
```

| Function | Stream | Default marker (unicode / ASCII) | Console shown when | Logfile level |
| --- | --- | --- | --- | --- |
| `pp.info` | stdout | none | `quiet=False` | `INFO` |
| `pp.success` | stdout | `✓` / `+` | `quiet=False` | `INFO` |
| `pp.warning` | stderr | `!` / `!` | always | `WARNING` |
| `pp.error` | stderr | `✗` / `x` | always | `ERROR` |
| `pp.critical` | stderr | `‼` / `!!` | always; does not raise | `CRITICAL` |
| `pp.dryrun` | stdout | `~` / `~`, plus `[dry-run]` tag | always, including `quiet=True` | `INFO` |
| `pp.debug` | stdout | `›` / `>` | `verbosity >= Verbosity.DEBUG` | `DEBUG` |
| `pp.trace` | stdout | `·` / `.` | `verbosity >= Verbosity.TRACE` | `TRACE` (5) |

```python
pp.success("deployed", details=["build #1742", "rollout 100%"])
# ✓ deployed
#   ├─ build #1742
#   └─ rollout 100%
```

`message`:

- `str`: escaped unless `markup=True`; level style, marker, and tag applied.
- `rich.text.Text`: keeps its own spans over the level style; marker and tag prefixed.
- Any other Rich renderable (`Table`, `Panel`, ...): printed as-is. Marker, tag, `right_tag`, and level style are dropped on the console.

`details` items render as a tree under the message:

- `str`: escaped unless `markup=True`, colored with `detail_style`.
- Rich renderable (`JSON`, `Syntax`, `Table`): passed through with its own colors.
- Anything else (dict, list, dataclass): wrapped in `Pretty()`. `detail_style` does not apply.

`markup=True` parses Rich markup in `message` and every string in `details` for that call. Use it only for strings you control; paths, exception messages, and user input keep the default so brackets do not turn into styles or raise `MarkupError`.

`style`, `detail_style`, `marker`: override the theme for this call only. `marker=""` hides the marker; `marker=None` keeps the level default. Console-only; the logfile is unaffected.

### Tags

```python
pp.info("saved", tag="api", right_tag="200ms")
# console: api saved                                              200ms
# logfile: [api] saved
```

- `tag`: dim text between marker and message, no brackets on the console. The logfile prepends it as `[tag] `.
- `right_tag`: dim text right-aligned to the console width, first line only. Console-only, never logged.
- `debug` / `trace` auto-fill `right_tag` with elapsed time `[+s.fffs]`, measured from the emitter's first `debug` or `trace` call. A caller `right_tag` replaces it on the console; the logfile still appends the elapsed time to the message as `\[+s.fffs]`, with a literal backslash.
- `dryrun` with a tag: console `deploy [dry-run] would push`, logfile `[deploy] [dry-run] would push`.
- Tags are parsed as Rich markup. Escape `[` and `]` yourself (`rich.markup.escape`) or pass plain text.

### Exceptions

```python
try:
    upload()
except UploadError as exc:
    pp.error("upload failed", exception=exc)  # or exception=True inside the except block
```

- `exception=<instance>` or `exception=True` appends a Rich traceback as the last detail item on the console, and the plain traceback as continuation lines in the logfile at the record's level.
- `exception=True` reads `sys.exc_info()`. Outside an `except` block it attaches nothing and raises nothing (same as `logging.exception()`).
- `show_locals=True`: include each frame's locals in the console traceback.
- `header()` and `kv()` take no `exception=`. For `step()`, use `s.fail(..., exception=...)`.

## `header()`

```python
header(
    message: str | Text = "",
    *,
    align: AlignMethod = "center",  # "left" | "center" | "right"
    markup: bool = False,
    **kwargs: Any,  # forwarded to Console.rule(), e.g. characters="=", style="red"
) -> None
```

- Prints a blank line, a `Console.rule()` with the title, a blank line.
- Title uses the `header` theme key; rule line defaults to `style="header.rule"`.
- `message` accepts `str` or `Text` only, not other renderables.
- Hidden when `quiet=True`. Never logged.

## `kv()`

```python
kv(
    items: dict[str, Any] | list[tuple[str, Any]],
    *,
    indent: int = 2,
    separator: str = ": ",
    markup: bool = False,
) -> None
```

```python
pp.kv({"Branch": "main", "Commit": "abc1234"})
#   Branch: main
#   Commit: abc1234
```

- Keys render dim, padded to the widest key. Use the list form for duplicate keys.
- Keys are always escaped. `markup=True` parses markup in string values only.
- Multi-line string values align under the value column. Rich renderable values render on the lines below the key, indented to the value column. Other values use `str(value)`.
- Empty `items`: prints and logs nothing.
- Hidden when `quiet=True`, but every visual line is still logged as its own `INFO` record.
- No `**kwargs`; wrapping follows the emitter's `soft_wrap`.

## `step()`

```python
@contextmanager
step(
    message: str | RenderableType,
    *,
    ephemeral: bool = False,
    markup: bool = False,
    success_msg: str | RenderableType | None = None,
) -> Generator[Step]
```

Yielded `Step` methods:

```python
s.sub(text: str | Text, *, markup: bool = False) -> None
s.set_success_msg(message: str | RenderableType, *, markup: bool = False) -> None
s.fail(message: str | RenderableType, *, exception: BaseException | bool = False, markup: bool = False) -> NoReturn
s.skip(message: str | RenderableType, *, markup: bool = False) -> NoReturn
```

```python
with pp.step("running migrations") as s:
    for m in pending:
        run(m)
        s.sub(f"applied {m.name}")
    s.set_success_msg(f"applied {len(pending)} migrations")
```

- While running: spinner plus `message` in the info style. `s.sub()` lines render beneath it with tree connectors and stay after the step ends. Each sub is logged at `INFO`, indented two spaces.
- Renders even when `quiet=True`.
- Logfile: `starting: <message>` at `INFO` on entry.

Outcomes:

| Exit | Console (non-ephemeral) | Logfile |
| --- | --- | --- |
| Block ends normally | success marker + success message | `succeeded: <msg>` `INFO` |
| `s.fail(msg)` | error marker + `msg`; console shows only `msg`, no traceback | `failed: <msg>` `ERROR`, plus full traceback lines when `exception=` is set |
| `s.skip(msg)` | `msg` in info style, no marker | `skipped: <msg>` `INFO` |
| Any other exception | original message as a plain static line; exception propagates | nothing |

- Success message precedence: `s.set_success_msg()` -> `success_msg=` -> `message`.
- `step(markup=...)` applies to `message` and `success_msg=`. `set_success_msg()`, `fail()`, `skip()` each take their own `markup=`.
- `set_success_msg()` does not exit; it is ignored if the block ends by `fail()`, `skip()`, or an exception.
- `fail()` and `skip()` require a message and raise an internal `BaseException` subclass, so `except Exception:` inside the block does not catch them. Code after the call does not run. Both are valid only inside the `with` block.
- `exception=True` in `s.fail()` reads `sys.exc_info()`; call it from inside an `except` block.
- To get a failure marker for an error, catch it and call `s.fail(..., exception=exc)`. An uncaught exception gets no marker and no log line; the caller reports it.

`ephemeral=True`:

- Success or skip: spinner and subs are cleared, nothing remains on screen.
- `s.fail(msg)`: cleared, then `pp.error(msg)` is printed on stderr. The logfile gets `failed: <msg>` and also a plain `<msg>` `ERROR` record from that `error()` call.
- Uncaught exception: cleared, nothing on screen.
- Logfile records are written as for a non-ephemeral step.

Nesting: entering `step()` while another `step()` is active on the same emitter raises `RuntimeError`. Use `s.sub()` for nested progress, or sequential steps. Steps on two different emitters are not checked against each other.

## Configuration

```python
configure(
    *,
    verbosity: int | Verbosity | None = None,
    quiet: bool | None = None,
    console: Console | None = None,
    err_console: Console | None = None,
    theme: Theme | None = None,
    soft_wrap: bool | None = None,
    logfile: Path | str | None = None,
    loglevel: LogLevel | None = None,
    logfmt: str | None = None,
) -> None
```

Partial update of the default emitter (`Emitter.configure()` has the same signature for an instance). A `None` argument leaves that field unchanged, so:

- `configure(logfile=None)` does not stop logging. To stop, `pp.set_default(pp.Emitter())`.
- `configure(soft_wrap=None)` does not restore auto-detection. Assign `pp.get_default().soft_wrap = None`.
- `configure(theme=...)` merges into the existing theme (see [Themes](#themes)).
- `logfile=` with a different path closes the old file; the replacement opens on the next record. Same resolved path: no change.

```python
pp.configure(verbosity=args.verbose, quiet=args.quiet, logfile="run.log", loglevel=pp.LogLevel.DEBUG)
```

Gates:

- `verbosity` gates only `debug` and `trace`. Ints are clamped to 0..2, so a raw `-v` count is safe.
- `quiet=True` hides `info`, `success`, `header`, `kv`. Never hides `warning`, `error`, `critical`, `dryrun`, `step()`, or `debug`/`trace` when verbosity allows them.
- `verbosity` and `quiet` are independent: `-v --quiet` shows debug output without info output.
- Neither gate affects the logfile.

### `soft_wrap`

Rich folds lines longer than the console width (80 when not a tty). A folded path or URL breaks `$(...)` capture.

| Value | Behavior |
| --- | --- |
| `None` (default) | Per console: fold when that console is a terminal, otherwise never fold |
| `True` | Never fold |
| `False` | Always fold at the console width |

- Per console: piped stdout stays unfolded while a tty stderr folds.
- Per call: `pp.info(path, soft_wrap=False)` wins over the emitter setting (passed through `**kwargs` to `Console.print()`).
- Applies to level functions, `kv()`, and `step()` subs. `header()` always spans the console width.
- A soft-wrapping `step()` shows no spinner; it prints once when the block exits (nothing if ephemeral).
- To fix folding, set `soft_wrap`. A hand-built Console is not needed; one without `theme=pp.THEME` renders `header` and connectors unstyled.

## Emitters

```python
class Emitter:
    def __init__(
        self,
        *,
        verbosity: int | Verbosity = Verbosity.INFO,
        quiet: bool = False,
        console: Console | None = None,
        err_console: Console | None = None,
        theme: Theme | None = None,
        soft_wrap: bool | None = None,
        logfile: Path | str | None = None,
        loglevel: LogLevel = LogLevel.INFO,
        logfmt: str | None = None,
    ) -> None

get_default() -> Emitter
set_default(emitter: Emitter) -> None
console() -> Console      # default emitter's stdout console
err_console() -> Console  # default emitter's stderr console
```

- Constructor defaults are real values; `configure()` defaults mean "leave unchanged".
- `console=None` -> `Console(theme=THEME)`; `err_console=None` -> `Console(theme=THEME, stderr=True)`. A custom console needs `theme=pp.THEME` for `header` and connector styles.
- Methods: the eight level methods, `header`, `kv`, `step`, `configure`, same signatures as the module functions.
- Settable attributes: `verbosity`, `quiet`, `soft_wrap`, `console`, `err_console`.
- Each instance owns its gates, theme, consoles, logfile, and nested-step check. Module functions call `get_default()` on every call, so `set_default()`, `console()`, and `err_console()` follow a swap immediately.

```python
# Library code: own emitter, host CLI settings untouched
out = pp.Emitter(verbosity=pp.Verbosity.DEBUG)
out.info("library message")

# Tests: capture output
from rich.console import Console
capture = Console(theme=pp.THEME, record=True, width=80)
original = pp.get_default()
pp.set_default(pp.Emitter(console=capture, err_console=capture))
try:
    run_code_under_test()
finally:
    pp.set_default(original)
assert "expected" in capture.export_text()
```

Render other Rich objects on the same stream: `pp.console().print(table)`, `pp.err_console().print(...)`.

## Themes

```python
@dataclass(frozen=True, slots=True)
class Level:
    style: str | None = None         # message style (Rich style string)
    detail_style: str | None = None  # details style
    marker: str | None = None        # "" hides; None keeps default

@dataclass(frozen=True, slots=True)
class Theme:
    info: Level | None = None
    success: Level | None = None
    warning: Level | None = None
    error: Level | None = None
    critical: Level | None = None
    debug: Level | None = None
    trace: Level | None = None
    dryrun: Level | None = None
```

```python
pp.configure(theme=pp.Theme(success=pp.Level(style="cyan", marker="* "), warning=pp.Level(marker="")))
```

- `None` field: keeps the built-in default. `""` is a real value (`marker=""` hides the marker).
- `Theme.<level> = None`: level keeps all defaults.
- Successive `configure(theme=...)` calls merge per field; earlier overrides persist. Full reset: `pp.set_default(pp.Emitter())`.
- Include the trailing space in a custom marker; defaults include one.
- `step()` uses the `info` level for the running and skip headers, `success` for the success header, `error` for the failure header.

Built-in defaults:

| Level | `style` | `detail_style` | `marker` unicode | `marker` ASCII |
| --- | --- | --- | --- | --- |
| info | `bold default` | `default` | `""` | `""` |
| success | `bold green` | `green` | `"✓ "` | `"+ "` |
| warning | `bold yellow` | `yellow` | `"! "` | `"! "` |
| error | `bold red` | `red` | `"✗ "` | `"x "` |
| critical | `bold white on red` | `red` | `"‼ "` | `"!! "` |
| debug | `bold cyan` | `cyan` | `"› "` | `"> "` |
| trace | `bold bright_black` | `bright_black` | `"· "` | `". "` |
| dryrun | `bold magenta` | `magenta` | `"~ "` | `"~ "` |

`THEME` is a `rich.theme.Theme` installed on the default consoles. Keys read at render time:

| Key | Default | Used for |
| --- | --- | --- |
| `header` | `cyan` | `header()` title |
| `header.rule` | `cyan dim` | `header()` rule line |
| `sub.pipe` | `bright_black` | Tree connectors in `details` and `s.sub()` |

`THEME` also holds `<level>` and `<level>.detail` keys matching the table above; level rendering ignores them. Use `Theme`/`Level` for level styling. To restyle `header`, `header.rule`, or `sub.pipe`, pass consoles built with a `rich.theme.Theme` that overrides those keys. The connector glyphs (`├─`, `└─`, `│`) and the `[dry-run]` tag text are fixed.

### ASCII fallback

If a console's encoding cannot encode the default glyphs (`LANG=C`, `PYTHONIOENCODING=ascii`, some Windows code pages), `pp` switches that console to ASCII: default markers map per the table above, and tree connectors become `- `. Custom markers print as given, unless they equal a built-in unicode default.

## File logging

```python
pp.configure(logfile=Path("run.log"), loglevel=pp.LogLevel.INFO)
```

- Every emission is logged before the console gate, so the logfile ignores `quiet` and `verbosity`. The console ignores `loglevel`.
- `loglevel`: minimum severity written. Severity only; no filter by emission type (no "successes only").
- File opens lazily on the first record, append mode, UTF-8, line-buffered. A missing parent directory or unwritable path raises the `OSError` (e.g. `FileNotFoundError`) from that emitting call.
- Default format: `"%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s"`, date format `"%Y-%m-%d %H:%M:%S"`. `logfmt=` replaces the format string; the date format is fixed.
- Records are plain text: markup stripped, renderables rendered without color at width 120. `details` and tracebacks become continuation records indented two spaces at the parent's level.
- Each emitter writes through its own private stdlib logger with `propagate=False`. `pp` cannot write into a caller's `logging.Logger` or handlers, and records never reach the root logger. No rotation, JSON, syslog, or multi-process safety.

| Emission | Level | Logfile text |
| --- | --- | --- |
| `info`, `success` | `INFO` | `[tag] msg` |
| `dryrun` | `INFO` | `[tag] [dry-run] msg` |
| `debug`, `trace` | `DEBUG`, `TRACE` | `[tag] msg  \[+s.fffs]` (literal backslash) |
| `warning`, `error`, `critical` | `WARNING`, `ERROR`, `CRITICAL` | `[tag] msg` |
| `step()` | `INFO`, `failed:` at `ERROR` | `starting:`, `succeeded:`, `skipped:`, `failed:` |
| `s.sub()` | `INFO` | `  text` |
| `kv()` | `INFO` | one record per visual line |
| `header()` | not logged |  |

## Enums

```python
class Verbosity(IntEnum):
    INFO = 0
    DEBUG = 1
    TRACE = 2

class LogLevel(IntEnum):  # numerics match stdlib logging
    TRACE = 5  # registered with logging.addLevelName on import
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
```
