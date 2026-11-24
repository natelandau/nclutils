[![PyPI version](https://badge.fury.io/py/nclutils.svg)](https://badge.fury.io/py/nclutils) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/nclutils) [![Tests](https://github.com/natelandau/nclutils/actions/workflows/automated-tests.yml/badge.svg)](https://github.com/natelandau/nclutils/actions/workflows/automated-tests.yml) [![codecov](https://codecov.io/gh/natelandau/nclutils/graph/badge.svg?token=Nl1V9jnI60)](https://codecov.io/gh/natelandau/nclutils)

# nclutils

nclutils is a collection of small helpers for Python scripts and packages: filesystem operations, shell commands, git automation, string transforms, console output, and interactive prompts.

> [!NOTE]
> nclutils is a personal package. The API can change between releases, and there is no guarantee that it is correct for your use case.

## Installation

nclutils requires Python 3.11 or later.

```bash
# With uv
uv add nclutils

# With pip
pip install nclutils
```

The package has two runtime dependencies: [questionary](https://github.com/tmbo/questionary) and [rich](https://github.com/Textualize/rich).

## Quick start

This script copies the Python files in `src/` to `backup/` and shows the progress in the terminal:

```python
from pathlib import Path

from nclutils import pp
from nclutils.fs import copy_file, find_files
from nclutils.strings import snake_case

pp.info("collecting Python sources")

with pp.step("copying files") as step:
    for source in find_files(Path("src"), globs=["*.py"]):
        copy_file(source, Path("backup") / source.name)
        step.sub(f"copied {source.name}")

pp.success(f"normalized name: {snake_case('Hello World')}")
```

If `src/` holds `a.py` and `b.py`, the script shows:

```text
collecting Python sources
✓ copying files
  ├─ copied a.py
  └─ copied b.py
✓ normalized name: hello_world
```

## Importing

Import each function from its module. The package root exports only `pp`, the console output module:

```python
from nclutils import pp

pp.info("hello")
pp.success("done")
```

The other modules use the same pattern:

```python
from nclutils.ask import choose_one_from_list
from nclutils.fs import copy_file, find_files
from nclutils.git import current_branch, is_dirty
from nclutils.net import network_available
from nclutils.sh import CompletedCommand, ShellCommandError, run_command, run_interactive, which
from nclutils.strings import camel_case, deburr
from nclutils.text import replace_in_file
from nclutils.utils import iso_timestamp, unique_id
```

You can also import a single `pp` function when that reads better at the call site:

```python
from nclutils.pp import info, success
```

## Modules

Each large module has its own guide. The two smallest modules are described in this file. For the full arguments of a function, read its docstring with `help(function)` or the hover text in your editor.

| Module             | Summary                                                                                                         | Docs                                             |
| ------------------ | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `nclutils.ask`     | Single-select and multi-select prompts, built on `questionary`.                                                 | [docs/ask.md](docs/ask.md)                       |
| `nclutils.fs`      | Copy, back up, search, and show a tree of files and directories.                                                | [docs/fs.md](docs/fs.md)                         |
| `nclutils.git`     | Git queries and multi-step workflows (sync a branch, prune branches, manage worktrees), built on `nclutils.sh`. | [docs/git.md](docs/git.md)                       |
| `nclutils.net`     | Network reachability check.                                                                                     | [nclutils.net](#nclutilsnet)                     |
| `nclutils.pp`      | Rich-based console output with verbosity levels, progress steps, and an optional log file.                      | [docs/pp.md](docs/pp.md)                         |
| `nclutils.sh`      | Run external commands. Returns a `CompletedCommand` and raises a `ShellCommandError` subclass on failure.       | [docs/shell_commands.md](docs/shell_commands.md) |
| `nclutils.strings` | Case conversion, padding, word splitting, normalization, and human-readable byte sizes.                         | [docs/strings.md](docs/strings.md)               |
| `nclutils.text`    | In-place edits of text files.                                                                                   | [nclutils.text](#nclutilstext)                   |
| `nclutils.utils`   | Timestamps, unique IDs, and a Python version check.                                                             | [docs/utils.md](docs/utils.md)                   |

### `nclutils.net`

- `network_available(address="8.8.4.4", port=53, timeout=5)` returns `True` if a TCP connection to the host and port succeeds within `timeout` seconds.

### `nclutils.text`

- `replace_in_file(path, replacements, *, use_regex=False)` applies a dict of replacements to a file in place. It returns `True` if the file changed.
- `ensure_lines_in_file(path, lines, *, at_top=False)` adds each line that is not already in the file. It returns `True` if the file changed.

```python
from nclutils.text import ensure_lines_in_file, replace_in_file

replace_in_file("config.toml", {"old": "new"})

# Regex mode: each key is a pattern, matched with re.MULTILINE
replace_in_file("config.toml", {r"^old": "new"}, use_regex=True)

ensure_lines_in_file(".gitignore", ["build", "dist"])
```

## Diagnostic logging

The `nclutils.fs`, `nclutils.sh`, and `nclutils.text` modules write diagnostic messages to the standard library `logging` module, under loggers named `nclutils.<module>`. These messages are silent by default. To see them, configure logging in your application:

```python
import logging

# Show warnings and errors from all libraries
logging.basicConfig(level=logging.WARNING)

# Also show debug messages from nclutils
logging.getLogger("nclutils").setLevel(logging.DEBUG)
```

This logging is separate from `nclutils.pp`, which writes to the terminal and, optionally, to a log file.

## For coding agents

The [`skill/`](skill/) directory holds a reference for AI coding agents that work in projects that depend on nclutils. [`skill/SKILL.md`](skill/SKILL.md) gives the import paths, a table that maps tasks to modules, and common mistakes. The files in [`skill/references/`](skill/references/) give the details of each module.

If you use a coding agent, for example Claude Code or Cursor, in a project that imports nclutils, tell it to read the skill before it edits code:

> Before writing any code that touches `nclutils`, read `https://raw.githubusercontent.com/natelandau/nclutils/main/skill/SKILL.md`. Follow the import patterns and gotchas described there. If a task involves the `pp`, `sh`, `fs`, `git`, `strings`, or smaller modules in detail, also read the matching file under `https://raw.githubusercontent.com/natelandau/nclutils/main/skill/references/`.

To match the guidance to the nclutils version that your project uses, replace `main` in the URLs with a release tag, for example `v4.0.0`.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) explains how to set up a development environment, run the checks, and submit changes.

## License

MIT. See [LICENSE](LICENSE).
