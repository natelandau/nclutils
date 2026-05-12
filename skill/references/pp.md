# `nclutils.pp` reference

Rich-based user-facing console output. Imported as `from nclutils import pp` (the only symbol re-exported from the top-level `nclutils` namespace), or per-symbol via `from nclutils.pp import info, success, step`.

## Level functions

Every level (`info`, `success`, `warning`, `error`, `critical`, `debug`, `trace`, `dryrun`) shares the SAME signature:

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
    **kwargs: Any,
) -> None
```

`**kwargs` is accepted for forward compatibility but currently has no documented effect; all kwargs above are explicit.

| Function       | Stream | Marker (unicode / ASCII) | Gated by                                       |
| -------------- | ------ | ------------------------ | ---------------------------------------------- |
| `pp.info`      | stdout | (none)                   | `quiet=True` suppresses                        |
| `pp.success`   | stdout | `✓` / `+`                | `quiet=True` suppresses                        |
| `pp.warning`   | stderr | `!` / `!`                | always renders                                 |
| `pp.error`     | stderr | `✗` / `x`                | always renders                                 |
| `pp.critical`  | stderr | `‼` / `!!`               | always renders (severity-only; does NOT raise) |
| `pp.dryrun`    | stdout | `~ [dry-run]`            | always renders                                 |
| `pp.debug`     | stdout | `›` / `>`                | shown at `Verbosity.DEBUG` or higher           |
| `pp.trace`     | stdout | `·` / `.`                | shown at `Verbosity.TRACE`                     |

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

Strings in `details` are colored with the level's `detail_style` and Rich markup is escaped by default. Non-strings are auto-rendered: dicts/dataclasses via `Pretty`; `JSON` / `Syntax` / `Table` / other Rich renderables pass through unchanged.

Pass `markup=True` to opt into Rich-markup parsing for `message` AND any string `details` items in that call. Only do this when you control the string; arbitrary input (paths, exception messages) should keep the default escape so brackets don't render as styling or raise `MarkupError`.

Per-call `style`, `detail_style`, `marker` override the theme JUST for that call. Pass `marker=""` (empty string) to hide the marker for one emit; `marker=None` (default) keeps the level default.

### Per-call tags

```python
pp.info("saved", tag="api", right_tag="200ms")
# [api] saved                                                       200ms
```

- `tag` renders inline between marker and message; recorded in the logfile.
- `right_tag` is right-aligned to console width on the FIRST line only; presentation-only, NOT logged.
- When passed to `pp.debug` / `pp.trace`, `right_tag` REPLACES the auto-elapsed `[+s.fffs]` marker on console; the logfile still records the elapsed timing.
- `pp.dryrun` keeps its built-in `[dry-run]` AND a caller `tag` (caller tag first): `[deploy] [dry-run] would push`.

You are responsible for Rich-markup-escaping `[`, `]`, or other reserved characters in tags. Pass plain ASCII or pre-escaped strings.

### Exceptions and tracebacks

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

`exception=` is accepted on every level method. `header()` and `step()` do NOT accept it. They manage their own exception display.

## `pp.header()`: section rule

```python
header(
    message: str | Text = "",
    *,
    align: AlignMethod = "center",  # Literal["left", "center", "right"]
    markup: bool = False,
    **kwargs: Any,
) -> None
```

`**kwargs` is forwarded to `Console.rule()`. Common ones:

- `characters=`: glyph for the rule line (e.g. `"="`, `"-"`).
- `style=`: Rich style for the line. Defaults to `"header.rule"` if you don't override.

Unlike level methods, `message` is `str | Text` only (Console.rule has no meaning for a `Table` or `Panel` inline in a rule). Suppressed when `quiet=True`. NOT logged to the logfile. Header is console-only structural sugar.

## `pp.kv()`: aligned key/value block

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
pp.kv({"Branch": "main", "Commit": "abc1234", "Status": "clean"})
```

Renders aligned pairs. Keys are padded to the widest key's width; padded width = `widest_key_len + len(separator)`. Pass `list[tuple[str, Any]]` when you need duplicate keys or explicit ordering.

`pp.kv()` is suppressed on console by `quiet=True` (same as `pp.info`), but each pair is recorded as an `INFO` record in the logfile regardless. Multi-line values produce one log record per visual line, aligned with the key column. `markup=True` parses markup in string values; keys are always escaped.

## `pp.step()`: spinner context manager

```python
@contextmanager
def step(
    message: str | RenderableType,
    *,
    ephemeral: bool = False,
    markup: bool = False,
    success_msg: str | RenderableType | None = None,
) -> Generator[Step]
```

```python
with pp.step("running migrations") as s:
    for m in pending:
        run(m)
        s.sub(f"applied {m.name}")
```

The `Step` object yielded has four public methods:

```python
Step.sub(text: str | Text, *, markup: bool = False) -> None
Step.set_success_msg(message: str | RenderableType, *, markup: bool = False) -> None
Step.fail(message: str | RenderableType, *, exception: BaseException | bool = False, markup: bool = False) -> NoReturn
Step.skip(message: str | RenderableType, *, markup: bool = False) -> NoReturn
```

`sub()` appends a sub-item beneath the spinner. Strings are escaped by default; `markup=True` parses Rich markup. A `Text` instance keeps its own styling. Each sub-item is also written to the logfile (indented continuation line at `INFO`).

Outcome resolution:

- Block exits normally → success outcome. Header uses `set_success_msg()` if called from inside the block, else the `success_msg=` kwarg, else the original `message`. Logfile records `succeeded: …`.
- `s.fail(msg)` → exits the block, replaces the spinner with an error marker, writes `failed: …` to the logfile. Pass `exception=e` to attach the exception's type/message as a logfile continuation line. Code after the call inside the block does not execute.
- `s.skip(msg)` → exits the block, replaces the spinner with an info-styled header (no checkmark), writes `skipped: …` to the logfile. Code after the call inside the block does not execute.
- Any other exception escapes → propagates cleanly. No marker, no log line. The spinner is replaced with a plain static line so it does not stay frozen on screen; sub-items remain visible.

`set_success_msg()` is the dynamic counterpart to `success_msg=`: use it when the success text depends on work done inside the block (a count, a duration, an output path). The setter wins over the kwarg, which wins over the original message. Each carries its own `markup=` flag.

`fail()` and `skip()` exit via an internal `BaseException` subclass, so a stray `except Exception:` inside the step body does not swallow them. Both require a message argument.

- `ephemeral=True` wipes the spinner AND sub-items on success/skip with no extra console output. `s.fail()` still surfaces a fresh `✗ message` error line on stderr after the wipe so failures are not silently hidden. An uncaught exception in ephemeral mode leaves no console trace, the caller owns error reporting.
- `success_msg=` overrides the success header at the call site; `set_success_msg()` overrides it dynamically from inside the block. The setter wins.
- The `step(markup=...)` flag applies to `message` and `success_msg=`. Each setter (`set_success_msg`, `fail`, `skip`) carries its own per-call `markup=` flag.
- **`pp.step()` CANNOT NEST.** Rich's `Live` cannot stack, `pp` raises `RuntimeError` on nested entry on the same emitter. Use `s.sub("...")` for nested progress lines instead.

## Configuration

```python
configure(
    *,
    verbosity: int | Verbosity | None = None,
    quiet: bool | None = None,
    console: Console | None = None,
    err_console: Console | None = None,
    theme: Theme | None = None,
    logfile: Path | str | None = None,
    loglevel: LogLevel | None = None,
    logfmt: str | None = None,
) -> None
```

Partial update of the shared default emitter. Fields you don't pass are left alone. Passing `logfile=None` is a NO-OP, not a way to disable the logfile. To stop logging, build a fresh emitter: `pp.set_default(pp.Emitter())`.

```python
pp.configure(
    verbosity=pp.Verbosity.DEBUG,
    quiet=False,
    logfile=Path("./run.log"),
    loglevel=pp.LogLevel.INFO,
)
```

`verbosity` and `quiet` are independent gates:

- `verbosity` only affects `debug` and `trace`.
- `quiet=True` suppresses `info`, `success`, `header`, `kv`. Warnings, errors, dryrun, and step lifecycle still render.
- `--verbose --quiet` together is sensible: debug output without info chatter.

Out-of-range verbosity ints are clamped via `_clamp_verbosity`, so `-vvvvv` is safe.

## Isolated emitters

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
        logfile: Path | str | None = None,
        loglevel: LogLevel = LogLevel.INFO,
        logfmt: str | None = None,
    ) -> None
```

Note the difference vs `configure()`: `Emitter.__init__` has POSITIVE defaults (every field becomes its sensible value if not passed), while `configure()` defaults to `None` everywhere (None means "leave existing alone"). When `console=None`, a fresh `Console(theme=THEME)` is built. When `err_console=None`, a fresh stderr console (also with the default theme).

Each `Emitter` owns its own `verbosity`, `quiet`, consoles, and logfile. Nothing leaks across instances. Module-level functions delegate to a shared default emitter accessible via `pp.get_default()`.

```python
# Library-internal emitter (won't trample the host CLI's settings)
logger = pp.Emitter(verbosity=pp.Verbosity.DEBUG)
logger.info("library-internal message")

# Recording console for tests
from rich.console import Console
capture = Console(theme=pp.THEME, record=True, force_terminal=True, width=80)
e = pp.Emitter(console=capture, err_console=capture)
e.info("captured")
assert "captured" in capture.export_text()

# Temporarily route module-level functions through a test emitter
original = pp.get_default()
pp.set_default(e)
try:
    run_code_under_test()
finally:
    pp.set_default(original)
```

`Emitter` exposes the same level methods (`emitter.info(...)`, `emitter.success(...)`, …) with the same signatures as the module-level functions, plus `emitter.configure(...)` for partial post-construction updates.

## Themes

```python
@dataclass(frozen=True, slots=True)
class Level:
    style: str | None = None         # main message style (Rich style string)
    detail_style: str | None = None  # detail-line style
    marker: str | None = None        # marker glyph; "" hides; None inherits default

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
pp.configure(
    theme=pp.Theme(
        success=pp.Level(style="cyan", marker="🎉 "),
        warning=pp.Level(marker=""),   # hide the warning marker
    ),
)
```

Field semantics:

- `Level.style`/`detail_style`/`marker = None` keeps the built-in default for that field.
- `Level.marker=""` (empty string) is a REAL value meaning "no marker". Only `None` falls back to the default. Same for empty-string `style`/`detail_style`.
- `Theme.<level> = None` keeps that level's defaults entirely.

Successive `pp.configure(theme=...)` calls ACCUMULATE at the field level. Overrides are not reset between calls. To fully reset, build a fresh emitter: `pp.set_default(pp.Emitter())`.

**Not themable.** The `pp.header()` rule, the `[dry-run]` tag, and the tree connector glyphs (`├─` / `└─` / `│`). Connectors share the `sub.pipe` Rich theme key for STYLE only. To change the connector glyph itself, build a custom `Console(theme=...)`.

Default styles (read-only, from source):

| Level    | Default style          | Default detail style | Default marker (unicode) | Default marker (ASCII) |
| -------- | ---------------------- | -------------------- | ------------------------ | ---------------------- |
| info     | `bold default`         | `default`            | `""`                     | `""`                   |
| success  | `bold green`           | `green`              | `"✓ "`                   | `"+ "`                 |
| warning  | `bold yellow`          | `yellow`             | `"! "`                   | `"! "`                 |
| error    | `bold red`             | `red`                | `"✗ "`                   | `"x "`                 |
| critical | `bold white on red`    | `red`                | `"‼ "`                   | `"!! "`                |
| debug    | `bold cyan`            | `cyan`               | `"› "`                   | `"> "`                 |
| trace    | `bold bright_black`    | `bright_black`       | `"· "`                   | `". "`                 |
| dryrun   | `bold magenta`         | `magenta`            | `"~ "`                   | `"~ "`                 |

## ASCII fallback

`pp` probes `console.encoding` once per encoding (memoized in `_ASCII_REQUIRED_CACHE`) and falls back to ASCII when unicode glyphs can't render (e.g. `LANG=C`, `PYTHONIOENCODING=ascii`, Windows code-page rejection). Tree connectors collapse to `- `; default markers map per the table above. User-supplied `Theme(level=Level(marker=...))` markers are ALWAYS respected verbatim, ASCII or not. Only built-in defaults get substituted.

## File logging

Pass `logfile=` to write a parallel record to disk:

```python
e = pp.Emitter(logfile=Path("./run.log"), loglevel=pp.LogLevel.INFO)
e.info("starting build")
```

Console and file rendering are independent. The console ignores `loglevel`; the file ignores `quiet` and `verbosity`. Every level method writes to the file BEFORE checking its console gate, so the logfile is a complete audit trail.

What gets logged:

| Emission                      | Logged at                         | Notes                                                                                |
| ----------------------------- | --------------------------------- | ------------------------------------------------------------------------------------ |
| `info` / `success` / `dryrun` | `INFO` (20)                       | `success`/`dryrun` aren't real severities. `dryrun` keeps `[dry-run]` inline.        |
| `debug`                       | `DEBUG` (10)                      | `[+s.fffs]` elapsed tag inlined into message.                                        |
| `trace`                       | `TRACE` (5)                       | Custom level registered with stdlib `logging` at import of `_logsink`.               |
| `warning`                     | `WARNING` (30)                    |                                                                                      |
| `error`                       | `ERROR` (40)                      |                                                                                      |
| `critical`                    | `CRITICAL` (50)                   | Severity-only.                                                                       |
| `step()` lifecycle            | `INFO` start, `INFO`/`ERROR` exit | `ephemeral=True` does NOT suppress file output.                                      |
| `Step.sub()`                  | `INFO`                            | Indented continuation.                                                               |
| `kv()`                        | `INFO`                            | One record per visual line (multi-line values produce multiple records).             |
| `header()`                    | (not logged)                      | Console-only structural sugar.                                                       |

`LogLevel` is severity-shaped, not emission-shaped: there's no way to "log only successes." The logfile does NOT ship rotation, JSON output, syslog, or multi-process safety; layer your own `logging.Logger` underneath if you need those.

### `Verbosity` and `LogLevel` enums

```python
class Verbosity(IntEnum):
    INFO = 0
    DEBUG = 1
    TRACE = 2

class LogLevel(IntEnum):
    TRACE = 5      # nclutils.pp-specific; registered via logging.addLevelName at import
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
```

`LogLevel` numerics match stdlib `logging` so the file substrate composes cleanly with stdlib tooling.

## Reaching the underlying consoles

When you need to render a Rich object on the same stream `pp` writes to:

```python
from rich.table import Table

table = Table("name", "status")
table.add_row("api", "ok")
pp.console().print(table)
pp.err_console().print("[bold red]fatal[/]")
```

`pp.console()` and `pp.err_console()` re-resolve on each call, reading from the current default emitter, so `set_default()` swaps take effect immediately.

## API reference (signatures only)

```python
# Module-level level functions (all share the SAME signature)
info(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None
success(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None
warning(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None
error(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None
critical(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None
debug(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None
trace(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None
dryrun(message, *, details=None, markup=False, style=None, detail_style=None, marker=None, tag=None, right_tag=None, exception=False, show_locals=False, **kwargs) -> None

# Structural output
header(message="", *, align="center", markup=False, **kwargs) -> None  # **kwargs forwarded to Console.rule()
kv(items, *, indent=2, separator=": ", markup=False) -> None
step(message, *, ephemeral=False, markup=False, success_msg=None) -> Generator[Step]

# Step API
Step.sub(text, *, markup=False) -> None
Step.set_success_msg(message, *, markup=False) -> None
Step.fail(message, *, exception=False, markup=False) -> NoReturn
Step.skip(message, *, markup=False) -> NoReturn

# Configuration
configure(*, verbosity=None, quiet=None, console=None, err_console=None, theme=None, logfile=None, loglevel=None, logfmt=None) -> None

# Emitter (positive defaults, unlike configure())
class Emitter:
    def __init__(self, *, verbosity=Verbosity.INFO, quiet=False, console=None, err_console=None,
                 theme=None, logfile=None, loglevel=LogLevel.INFO, logfmt=None) -> None
    # Plus same-shape level methods: emitter.info, emitter.success, ..., emitter.header, emitter.kv, emitter.step
    def configure(self, *, verbosity=None, quiet=None, console=None, err_console=None,
                  theme=None, logfile=None, loglevel=None, logfmt=None) -> None

# Defaults
get_default() -> Emitter
set_default(emitter: Emitter) -> None
console() -> Console       # stdout console of current default emitter
err_console() -> Console   # stderr console of current default emitter

# Dataclasses
@dataclass(frozen=True, slots=True)
class Level:
    style: str | None = None
    detail_style: str | None = None
    marker: str | None = None  # "" hides; None inherits default

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

# Enums
class Verbosity(IntEnum):
    INFO = 0; DEBUG = 1; TRACE = 2

class LogLevel(IntEnum):
    TRACE = 5; DEBUG = 10; INFO = 20; WARNING = 30; ERROR = 40; CRITICAL = 50

# Module constants
THEME: rich.theme.Theme  # default Rich theme used by Emitter's consoles
```
