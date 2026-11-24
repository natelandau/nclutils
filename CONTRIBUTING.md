# Contributing to nclutils

This guide explains how to set up a development environment, run the checks, and submit a change. Bug fixes, features, documentation, and tests are all welcome.

## Prerequisites

Install these tools before you start:

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which manages Python, the dependencies, and the virtual environment.
- Git.

The package supports Python 3.11 and later. If no supported Python is on your system, `uv sync` downloads one.

## Set up the environment

Every command in this guide starts with `uv run`, which runs the tool from the project's `.venv`. You do not need to activate the virtual environment.

1. Clone the repository:

    ```bash
    git clone https://github.com/natelandau/nclutils
    ```

2. Go to the repository directory:

    ```bash
    cd nclutils
    ```

3. Install the dependencies:

    ```bash
    uv sync
    ```

4. Install the git hooks with [prek](https://prek.j178.dev/):

    ```bash
    uv run prek install --prepare-hooks
    ```

## Make sure that the setup works

Run the linters and the test suite:

```bash
uv run duty lint
uv run duty test
```

If the setup is correct, both commands finish without errors.

## Run tasks

The project uses [duty](https://pawamoy.github.io/duty/) as its task runner. To list all tasks, run `uv run duty --list`. The tasks are:

| Command                   | What it does                                                                     |
| ------------------------- | -------------------------------------------------------------------------------- |
| `uv run duty lint`        | Runs all the linters: `ruff`, `format`, `ty`, `typos`, `actionlint`, and `prek`. |
| `uv run duty test`        | Runs the test suite in parallel, with coverage.                                  |
| `uv run duty ruff`        | Checks the code with ruff.                                                       |
| `uv run duty format`      | Checks the code formatting with ruff. It does not change files.                  |
| `uv run duty ty`          | Checks the types with ty.                                                        |
| `uv run duty typos`       | Checks the spelling with typos.                                                  |
| `uv run duty actionlint`  | Checks the GitHub Actions workflows.                                             |
| `uv run duty prek`        | Runs the other git hooks on all files.                                           |
| `uv run duty update`      | Upgrades the dependencies in `uv.lock` and the git hook versions.                |
| `uv run duty clean`       | Deletes build output, caches, and `__pycache__` directories.                     |

To format the code, run `uv run ruff format src tests`.

To run one test file or one test, run pytest directly:

```bash
uv run pytest tests/test_strings.py::test_random_string
uv run pytest tests/filesystem/test_copy.py -k "backup"
```

The test suite also runs the examples in the source docstrings. `uv run duty test` runs the tests in a random order, so every test must pass alone and in any order.

### Skipped checks

The `typos`, `prek`, and `test` tasks run their tool through [gate-cache](https://github.com/natelandau/gate-cache). If the tool already passed on the same files and the same Python version, gate-cache skips it and the task passes. The `ruff`, `format`, and `ty` tasks always run.

The `test` gate looks only at `src/`, `tests/`, `pyproject.toml`, `uv.lock`, and `duties.py`. A change to other files, for example the docs, does not run the tests again. If you give `uv run duty test` extra pytest arguments, the tests always run.

The git hooks run the same tasks. A check that passed in your terminal skips at commit time and at push time. Caching is off when the `CI` environment variable is set.

To run a check that gate-cache skipped, set `GATE_CACHE_DISABLE=1` for that command:

```bash
GATE_CACHE_DISABLE=1 uv run duty test
```

To see which gates passed, run `uv run gate-cache status`.

## Write the code

Your change must meet these rules:

- Give every function type hints and a full docstring.
- Add a unit test for every new function and an integration test for every new feature.
- Write tests with `pytest` and `pytest-mock`. Do not use `unittest`. Create mocks with the `mocker` fixture and `autospec=True`.
- Start each test docstring with "Verify", and divide the test body with `# Given`, `# When`, and `# Then` comments.
- Keep the code compatible with Python 3.11. If code needs a newer Python feature, put it behind `nclutils.utils.check_python_version()`.
- Import each function from its module, for example `from nclutils.fs import copy_file`.

If you change a public function, update its documentation in the same pull request: `docs/<module>.md`, `skill/references/<module>.md`, and, if the list of modules or functions changes, `README.md` and `skill/SKILL.md`. Removing or renaming a public function is a breaking change.

## Submit a change

The git hooks check each commit message, and CI checks each pull request title. A message or title that does not obey these rules fails:

- The format is `<type>(<scope>): <subject>`. The scope is optional.
- The type is one of `build`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `style`, or `test`.
- The subject is in the imperative mood, starts with a lowercase letter, and has no period at the end.
- The subject line and each body line are at most 60 characters.

For example: `fix(fs): keep file permissions when copying`.

To submit a change, do these steps:

1. Create a branch named `<type>/<name>`, for example `fix/copy-permissions`. Use a type from the list above.
2. Make your changes.
3. Run `uv run duty lint` and correct each error.
4. Run `uv run duty test` and correct each failure.
5. Commit your changes. To write the commit message with prompts, run `uv run cz commit`.
6. Push your branch and open a pull request. Give it a title that obeys the commit message rules.

If a git hook changes files during a commit, stage the changed files and commit again. Do not use `--no-verify` to skip a hook that fails.

The maintainer squashes each pull request into one commit, with the pull request title as the commit subject. Releases follow [Semantic Versioning](https://semver.org/).
