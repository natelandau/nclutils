## Development commands

Use [`uv`](https://docs.astral.sh/uv/) for packages and [`duty`](https://pawamoy.github.io/duty/) for tasks, never `pip`, `poetry`, or `conda`. Run every duty through `uv run`, so it uses this checkout's `.venv`.

```bash
uv sync                                 # install or refresh dependencies
uv run prek install --prepare-hooks     # one-time git hook setup

uv run duty --list                      # list all tasks
uv run duty test                        # pytest with coverage
uv run duty lint                        # ruff, ty, typos, actionlint, prek hooks
uv run duty ruff                        # one linter: ruff, format, ty, typos, actionlint
uv run duty update                      # refresh uv.lock and prek hook pins
```

The `typos`, `prek`, and `test` duties wrap their tool in [`gate-cache`](https://github.com/natelandau/gate-cache): a duty that already passed on the same files and Python version prints a skip line and exits 0. Treat a skip as a pass. The git hooks call the same duties and share the cache. `ruff`, `format`, and `ty` are fast and stay uncached on purpose.

- Run lint and the full test suite only through the duties, not the tools directly, so runs read and write the shared cache.
- The `test` gate is scoped with `--path` to `TEST_GATE_PATHS` in `duties.py`. When the suite starts reading a new tracked file or directory, add it there.
- `uv run duty test <args>` passes the arguments to pytest and bypasses the cache, because a filtered run must not mark the full suite as passed.
- Force a full run (`GATE_CACHE_DISABLE=1 uv run duty test`) only when asked, or when an input git does not track changed: an installed tool, an environment variable, an ignored file. `uv run gate-cache status` lists the gates that passed.
- Before adding or changing a gate, run `uv run gate-cache --skill` and follow it. Wrap a new gate with the `gated()` helper in `duties.py`.

Run a single test with pytest directly:

```bash
uv run pytest tests/test_strings.py::test_random_string
uv run pytest tests/filesystem/test_copy.py -k "backup"
```

pytest config lives in `[tool.pytest]` in `pyproject.toml`:

- Runs `tests/` and `src/` with `--xdoctest --exitfirst --failed-first`. Doctests in source docstrings are part of the suite.
- Strict: unknown markers or config keys, duplicate parametrize IDs, a passing `xfail`, and any warning fail the run.
- Every test must pass alone and in any order: `duty test` runs in parallel (pytest-xdist) and shuffled (pytest-randomly). A direct `uv run pytest` runs serially; add `-n auto` for parallel. To repeat an order, pass the `--randomly-seed` value from the pytest header; `-p no:randomly` turns shuffling off.

## Architecture

`nclutils` is a flat collection of utility modules. Each public module under `src/nclutils/` has the same shape:

- `src/nclutils/<module>/__init__.py`: re-exports the public surface and defines `__all__`.
- `src/nclutils/<module>/<implementation>.py`: the code.

Import from the module, not the package root: `from nclutils import pp`, then `pp.info(...)`; or `from nclutils.pp import info`; or `from nclutils.fs import copy_file`. This is the public API contract documented in the README, so keep it.

`tests/` mirrors the source layout. Larger modules have a subdirectory with its own `conftest.py`; smaller modules use one `tests/test_<module>.py`. Match the existing pattern when adding tests.

`docs/<module>.md`: one guide per public module. The README is the index.

`skill/` is the agent-facing reference shipped with the source: `skill/SKILL.md` is the quick-reference card (import patterns, task-to-module table, gotchas, public-symbols list), and `skill/references/<module>.md` holds per-module detail. Downstream agents read it from this repo, often pinned to a tag, so it must stay accurate for the version it ships in.

Keep docs in step with code:

| Change | Update |
| --- | --- |
| Public function signature, behavior, defaults, exceptions, or examples | `docs/<module>.md`, `skill/references/<module>.md`; the README module table if the surface shifts; `skill/SKILL.md` if it mentions the change |
| New public export | The module's `__init__.py` `__all__`, `docs/<module>.md`, `skill/references/<module>.md`, the public-symbols list in `skill/SKILL.md`, the README |
| New top-level module | All of the above, plus a new `skill/references/<module>.md` linked from `skill/SKILL.md` |

Removing or renaming a public symbol is a breaking change.

### Two logging systems

The project has two output paths, kept separate on purpose:

1. **`nclutils.pp`**: Rich-based user-facing CLI output (`info`, `success`, `error`, `step()`, and others). The `Emitter` class owns it; module-level functions delegate to a shared default. Has its own theme, verbosity gates, and optional file logger.
2. **stdlib `logging`**: internal diagnostics inside library modules. Each module logs under its own `nclutils.<module>` logger and is silent unless the host application attaches a handler.

Do not bridge them. Library modules do not call `pp`; `pp` does not call stdlib `logging` for its own output.

## Test style

- Use `pytest` and `pytest-mock` only, never `unittest`.
- Use the `mocker` fixture with `autospec=True` for mocks.
- Write single-sentence docstrings in imperative voice starting with "Verify", for example `"""Verify backup creates file with .bak extension."""`.
- Structure test bodies with `# Given`, `# When`, `# Then` comments.
- Use `@pytest.mark.parametrize` for input and output variants.

## Commits and branches

- Conventional commits: `<type>(<scope>): <subject>`, scope optional. Types: `build`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `style`, `test`. `bump` is for release commits only.
- Subject in imperative mood, lowercase first letter, no trailing period. Subject and body lines at most 60 characters. The `committed` hook checks every commit message. CI rejects a pull request title with any other type, and the title becomes the squash commit.
- Work on a branch named `<type>/<name>`, using a type from the list above. Never commit to `main` or push to `origin/main` without explicit permission.
- If a git hook modifies files during a commit, re-stage and create a new commit. Never `--amend` or `--no-verify` to get past a failing hook.

## Python compatibility

The package supports Python 3.11+. When code needs a newer language or stdlib feature, gate it on `nclutils.utils.check_python_version(major, minor)` instead of raising the project minimum.
