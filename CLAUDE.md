# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

This project uses [`duty`](https://pawamoy.github.io/duty/) as the task runner and [`uv`](https://docs.astral.sh/uv/) for package management. Use them exclusively — never `pip`, `poetry`, or `conda`.

```bash
uv sync                         # install/refresh dependencies
pre-commit install --install-hooks   # one-time hook setup

duty --list                     # discover all tasks
duty test                       # run pytest with coverage
duty lint                       # ruff + mypy + typos + pre-commit
duty ruff | duty format | duty mypy | duty typos   # individual linters
duty update                     # refresh uv.lock and pre-commit pins
```

To run a single test, invoke pytest directly through `uv`:

```bash
uv run pytest tests/test_strings.py::test_random_string
uv run pytest tests/filesystem/test_copy.py -k "backup"
```

`pytest` is configured (`pyproject.toml`) with `--xdoctest --exitfirst --failed-first --strict-config --strict-markers` and runs against both `tests/` and `src/`. Doctests in source docstrings are part of the suite.

## Architecture

`nclutils` is a flat collection of utility modules. Each public module under `src/nclutils/` follows the same shape:

- `src/nclutils/<module>/__init__.py` — re-exports the public surface and defines `__all__`.
- `src/nclutils/<module>/<implementation>.py` — actual code.

Every module must be imported from its submodule. The preferred form for the pretty-printer is `from nclutils import pp` and call sites use `pp.info(...)`, `pp.success(...)`, etc.; individual symbols may also be pulled with `from nclutils.pp import info`. Other modules follow the same pattern (`from nclutils.fs import copy_file`). Preserve this convention — it's the public API contract and is documented in the README.

`tests/` mirrors the source layout. Larger modules have their own subdirectory (`tests/filesystem/`, `tests/pp/`), each with its own `conftest.py`. Smaller modules use a single `tests/test_<module>.py` file.

`docs/` contains per-module guides (`fs.md`, `strings.md`, `utils.md`, `pp.md`, `ask.md`, `shell_commands.md`). The README is an index; the `docs/` pages are the deep dives.

**Always update documentation when code changes.** Any change that affects a public function's signature, behavior, defaults, exceptions, or examples must be reflected in the matching `docs/<module>.md` page (and the README's module summary table if the surface area shifts). New public exports must be added to the relevant `__init__.py`'s `__all__`, the module's API reference section in `docs/`, and the README. Removing or renaming a public symbol is a breaking change — update the docs in the same commit.

### Two logging systems

The project has two parallel output paths and they are intentionally separate:

1. **`nclutils.pp`** — Rich-based user-facing CLI output (`info`, `success`, `error`, `step()`, etc.). The `Emitter` class owns this, with module-level functions delegating to a shared default. Has its own theme, verbosity gates, and optional file logger.
2. **stdlib `logging`** — internal diagnostics inside `nclutils.fs` and `nclutils.text`. Each module logs under `nclutils.<module>` and is silent unless the host application attaches a handler.

Do not bridge these. `nclutils.fs` does not call `pp`; `pp` does not call stdlib `logging` for its own output. The project recently migrated off `loguru` (commit 6cafada) — any older guidance referencing `loguru` (including `.cursor/rules/python_preferred_tools.mdc`) is stale.

## Testing conventions

Tests follow a strict house style enforced by code review (not lint):

- Use `pytest` and `pytest-mock` only. Never `unittest`.
- Use the `mocker` fixture with `autospec=True` for mocks.
- Write single-sentence docstrings in imperative voice starting with **"Verify"** (e.g., `"""Verify backup creates file with .bak extension."""`).
- Structure test bodies with `# Given`, `# When`, `# Then` comments.
- Use `@pytest.mark.parametrize` for input/output variants.

## Commits and branches

Commits are enforced by `committed` and `commitizen` pre-commit hooks. The format is conventional commits with these types only: `build`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `style`, `test`. Header: `<type>(<scope>): <subject>` with imperative-mood, lowercase subject, no trailing period, ≤70 chars.

Always work on a feature branch (`feat/<name>`, `fix/<name>`, `refactor/<name>`). Never commit to `main` or push to `origin/main` without explicit permission.

If pre-commit modifies files during a commit, re-stage and create a new commit — never `--amend` or `--no-verify` to bypass a failing hook.

## Python compatibility

The package supports Python 3.10+. A few features (e.g., `nclutils.fs.copy_directory`) gate themselves on Python 3.12 via `nclutils.utils.check_python_version`. When adding code that depends on newer language or stdlib features, gate it the same way rather than raising the project minimum.
