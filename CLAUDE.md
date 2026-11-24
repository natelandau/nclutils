# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

This project uses [`duty`](https://pawamoy.github.io/duty/) as the task runner and [`uv`](https://docs.astral.sh/uv/) for package management. Use them exclusively — never `pip`, `poetry`, or `conda`.

```bash
uv sync                         # install/refresh dependencies
uv run prek install --prepare-hooks   # one-time git hook setup

duty --list                     # discover all tasks
duty test                       # run pytest with coverage
duty lint                       # ruff + ty + typos + actionlint + prek hooks
duty ruff | duty format | duty ty | duty typos | duty actionlint   # individual linters
duty update                     # refresh uv.lock and prek hook pins
```

The `typos`, `prek`, and `test` duties wrap their tool in [`gate-cache`](https://github.com/natelandau/gate-cache), so a duty that already passed on the same files and Python version prints a skip line and exits 0. Treat a skip as a pass. The pre-commit hooks call these duties, so they share the same cache. `ruff`, `format`, and `ty` are fast and stay ungated on purpose.

- Run lint and the full test suite only through the duties, never by calling the tool directly, so runs read and write the shared cache.
- The `test` gate is scoped with `--path` to `TEST_GATE_PATHS` in `duties.py`. When the suite starts reading a new tracked file or directory, add it there.
- `duty test <args>` passes the arguments to pytest and bypasses the cache, because a filtered run must not mark the full suite as passed.
- Use `GATE_CACHE_DISABLE=1 duty test` to force a real run, and `uv run gate-cache status` to see which gates passed.
- Before adding or changing a gate, run `uv run gate-cache --skill` and follow it. Wrap a new gate with the `gated()` helper in `duties.py`.

To run a single test, invoke pytest directly through `uv`:

```bash
uv run pytest tests/test_strings.py::test_random_string
uv run pytest tests/filesystem/test_copy.py -k "backup"
```

`pytest` is configured in the `[tool.pytest]` table of `pyproject.toml`. It runs against both `tests/` and `src/` with `--xdoctest --exitfirst --failed-first`, so doctests in source docstrings are part of the suite. Strict mode is on: unknown markers, config keys, and duplicate parametrize IDs are errors, and an `xfail` test that passes fails. Every warning is an error.

`duty test` runs the suite in parallel with `pytest-xdist`, and `pytest-randomly` shuffles the test order on every run, so every test must pass alone and in any order, with no state shared across tests. A direct `uv run pytest` runs serially unless you add `-n auto`. To repeat a failing order, pass the `--randomly-seed` value that pytest prints in its header; `-p no:randomly` turns shuffling off.

## Architecture

`nclutils` is a flat collection of utility modules. Each public module under `src/nclutils/` follows the same shape:

- `src/nclutils/<module>/__init__.py` — re-exports the public surface and defines `__all__`.
- `src/nclutils/<module>/<implementation>.py` — actual code.

Every module must be imported from its submodule. The preferred form for the pretty-printer is `from nclutils import pp` and call sites use `pp.info(...)`, `pp.success(...)`, etc.; individual symbols may also be pulled with `from nclutils.pp import info`. Other modules follow the same pattern (`from nclutils.fs import copy_file`). Preserve this convention — it's the public API contract and is documented in the README.

`tests/` mirrors the source layout. Larger modules have their own subdirectory with its own `conftest.py`; smaller modules use a single `tests/test_<module>.py` file. Match the existing pattern when adding tests.

`docs/` contains one per-module guide per public module. The README is an index; the `docs/` pages are the deep dives.

`skill/` is the AI-agent-facing reference shipped alongside the source. `skill/SKILL.md` is the quick-reference card (import patterns, task-to-module lookup, top gotchas); `skill/references/<module>.md` holds per-module deep dives written for agents. Downstream agents read it directly from this repo, often pinned to a tag, so the content must stay accurate for the version it lives in.

**Always update documentation when code changes.** Any change to a public function's signature, behavior, defaults, exceptions, or examples must be reflected in the matching `docs/<module>.md`, the matching `skill/references/<module>.md`, and the README's module summary table if the surface area shifts. Update `skill/SKILL.md` too when the change touches anything it calls out (import patterns, the task-to-module table, the gotchas, the public-symbols list).

New public exports must be added to the relevant `__init__.py`'s `__all__`, the module's API reference in `docs/`, the matching `skill/references/<module>.md`, the public-symbols list in `skill/SKILL.md`, and the README. Removing or renaming a public symbol is a breaking change. If a new top-level module is added, also add a new `skill/references/<module>.md` and link it from `skill/SKILL.md`.

### Two logging systems

The project has two parallel output paths and they are intentionally separate:

1. **`nclutils.pp`** — Rich-based user-facing CLI output (`info`, `success`, `error`, `step()`, etc.). The `Emitter` class owns this, with module-level functions delegating to a shared default. Has its own theme, verbosity gates, and optional file logger.
2. **stdlib `logging`** — internal diagnostics inside library modules. Each module logs under its own `nclutils.<module>` logger and is silent unless the host application attaches a handler.

Do not bridge these. Library modules do not call `pp`; `pp` does not call stdlib `logging` for its own output.

## Testing conventions

Tests follow a strict house style enforced by code review (not lint):

- Use `pytest` and `pytest-mock` only. Never `unittest`.
- Use the `mocker` fixture with `autospec=True` for mocks.
- Write single-sentence docstrings in imperative voice starting with **"Verify"** (e.g., `"""Verify backup creates file with .bak extension."""`).
- Structure test bodies with `# Given`, `# When`, `# Then` comments.
- Use `@pytest.mark.parametrize` for input/output variants.

## Commits and branches

Commits are enforced by the `committed` pre-commit hook. The format is conventional commits with these allowed types: `build`, `bump`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`. Header: `<type>(<scope>): <subject>` with imperative-mood, lowercase subject, no trailing period, at most 60 characters. Body lines are at most 60 characters too.

Always work on a feature branch (`feat/<name>`, `fix/<name>`, `refactor/<name>`). Never commit to `main` or push to `origin/main` without explicit permission.

If a git hook modifies files during a commit, re-stage and create a new commit — never `--amend` or `--no-verify` to bypass a failing hook.

## Python compatibility

The package supports Python 3.11+. When adding code that depends on newer language or stdlib features, gate it on `nclutils.utils.check_python_version(major, minor)` rather than raising the project minimum.

## Context Navigation (Graphify)

### 3-Layer Query Rule

1. **First:** query `graphify-out/graph.json` or `graphify-out/wiki/index.md`
   to understand code structure and connections
2. **Second:** query the Obsidian vault for decisions, progress, and project context
3. **Third:** only read raw code files when editing
   or when the first two layers don't have the answer

### When to rebuild the graph

- After structural changes (new modules, major refactors)
- Headless: `graphify update .` (only processes modified files)
- Skill: `/graphify . --update` (same behavior, runs through the skill — also accepts `--obsidian` to refresh the vault)
- The graph is persistent — NO need to rebuild every session

### Do NOT

- Don't manually modify files inside `graphify-out/`
- Don't re-read the entire codebase if the graph already has the information
