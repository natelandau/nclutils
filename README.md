[![PyPI version](https://badge.fury.io/py/nclutils.svg)](https://badge.fury.io/py/nclutils) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nclutils) [![Tests](https://github.com/natelandau/nclutils/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/nclutils/actions/workflows/automated-tests.yml) [![codecov](https://codecov.io/gh/natelandau/nclutils/graph/badge.svg?token=Nl1V9jnI60)](https://codecov.io/gh/natelandau/nclutils)

# nclutils

A grab-bag of small convenience helpers I reach for again and again across my Python scripts and packages: filesystem operations, shell execution, string transformations, console output, interactive prompts, and a few odds and ends.

Comprehensive tests are included, but this package is written and maintained for my own use. No guarantees are made about API stability or correctness for your use case.

## Quick example

```python
from pathlib import Path
from nclutils import pp
from nclutils.fs import copy_file, find_files
from nclutils.strings import snake_case

pp.info("collecting Python sources")

with pp.step("copying files") as s:
    for src in find_files(Path("src"), globs=["*.py"]):
        dst = Path("backup") / src.name
        copy_file(src, dst)
        s.sub(f"copied {src.name}")

pp.success(f"normalized name: {snake_case('Hello World')}")
```

## Installation

Requires Python 3.10 or newer.

```bash
# With uv
uv add nclutils

# With pip
pip install nclutils
```

The package brings in two runtime dependencies: [questionary](https://github.com/tmbo/questionary) and [rich](https://github.com/Textualize/rich).

## Importing

Each module is imported from its submodule. The pretty-printing helpers are namespaced under `pp`:

```python
from nclutils import pp

pp.info("hello")
pp.success("done")
```

Other modules follow the same pattern:

```python
from nclutils.ask import choose_one_from_list
from nclutils.fs import copy_file, find_files
from nclutils.net import network_available
from nclutils.sh import run_command, run_interactive, which, CompletedCommand, ShellCommandError
from nclutils.strings import camel_case, deburr
from nclutils.text import replace_in_file
from nclutils.utils import iso_timestamp, unique_id
```

Individual `pp` symbols can also be imported directly when that reads better at the call site:

```python
from nclutils.pp import info, success
```

## Modules

The larger modules have their own documentation pages. Smaller modules are listed inline below. Function signatures live with the source; consult docstrings (`help(func)` or your editor's hover) for authoritative argument details.

| Module             | Summary                                                                                                                                                           | Docs                                             |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `nclutils.ask`     | Single- and multi-select prompts via `questionary`.                                                                                                               | [docs/ask.md](docs/ask.md)                       |
| `nclutils.fs`      | Copy, back up, search, and visualize the filesystem.                                                                                                              | [docs/fs.md](docs/fs.md)                         |
| `nclutils.net`     | Lightweight network reachability check.                                                                                                                           | _(inline below)_                                 |
| `nclutils.pp`      | Rich-based console output, verbosity gates, file logger.                                                                                                          | [docs/pp.md](docs/pp.md)                         |
| `nclutils.sh`      | Run commands via subprocess; returns `CompletedCommand`, raises typed errors (`ShellCommandError` hierarchy). Includes `run_command`, `run_interactive`, `which`. | [docs/shell_commands.md](docs/shell_commands.md) |
| `nclutils.strings` | Case conversions, padding, tokenizing, normalization.                                                                                                             | [docs/strings.md](docs/strings.md)               |
| `nclutils.text`    | In-place file edits.                                                                                                                                              | _(inline below)_                                 |
| `nclutils.utils`   | Timestamps, unique IDs, Python version check.                                                                                                                     | [docs/utils.md](docs/utils.md)                   |

### `nclutils.net`

- `network_available(address="8.8.4.4", port=53, timeout=5)`. Return `True` if a TCP connection to the given host and port succeeds within `timeout` seconds.

### `nclutils.text`

- `replace_in_file(path, replacements, *, use_regex=False)`. Apply a dict of replacements to a file in place. Returns `True` if the file changed.
- `ensure_lines_in_file(path, lines, *, at_top=False)`. Add lines to a file if they aren't already present. Returns `True` if the file changed.

```python
from nclutils.text import ensure_lines_in_file, replace_in_file

replace_in_file("config.toml", {"old": "new"})

# Regex mode (each key is a pattern; matches use re.MULTILINE)
replace_in_file("config.toml", {r"^old": "new"}, use_regex=True)

ensure_lines_in_file(".gitignore", [".env", "*.pyc"])
```

## Diagnostic logging

Internal modules (`nclutils.fs`, `nclutils.text`) emit diagnostic messages through the stdlib `logging` module under their own logger names. By default these are silent. Attach a handler in your application to see them:

```python
import logging

logging.basicConfig(level=logging.WARNING)
# or, narrower:
logging.getLogger("nclutils").setLevel(logging.DEBUG)
```

This is separate from `nclutils.pp`, which writes to the console (and optionally a logfile) using its own machinery.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, task runner commands, and the commit workflow.

## License

MIT. See [LICENSE](LICENSE).
