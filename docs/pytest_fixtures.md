# Pytest Fixtures

The `nclutils.pytest_fixtures` module contains convenience functions and fixtures that are useful for testing.

For use in your tests, import these into your `conftest.py` file:

```python
# tests/conftest.py

# import specific fixtures
from nclutils.pytest_fixtures import clean_stdout, debug

# or import all fixtures
from nclutils.pytest_fixtures import *
```

## clean_stdout

Clean the stdout of the console output by creating a wrapper around `capsys` to capture console stdout output. Mutually exclusive with `clean_stderr`.

By default, the `tmp_path` is stripped from the output to keep the output clean. To keep the `tmp_path` in the output, set `strip_tmp_path=False`.

```python
def test_something(clean_stdout):
    print("Hello, world!")
    output = clean_stdout()
    assert output == "Hello, world!"
```

## clean_stderr

Clean the stderr of the console output by creating a wrapper around `capsys` to capture console stderr output. Mutually exclusive with `clean_stdout`.

By default, the `tmp_path` is stripped from the output to keep the output clean. To keep the `tmp_path` in the output, set `strip_tmp_path=False`.

```python
def test_something(clean_stderr):
    print("Hello, world!", file=sys.stderr)
    output = clean_stderr(strip_tmp_path=False)
    assert output == "Hello, world!"
```

## clean_stderrout

Clean the stdout and stderr of the console output by creating a wrapper around `capsys` to capture console stdout and stderr output. Mutually exclusive with `clean_stdout` and `clean_stderr`.

By default, the `tmp_path` is stripped from the output to keep the output clean. To keep the `tmp_path` in the output, set `strip_tmp_path=False`.

```python
def test_something(clean_stderrout):
    print("this is stdout")
    print("this is stderr", file=sys.stderr)
    output = clean_stderrout()
    assert "this is stdout" in output
    assert "this is stderr" in output
```

## debug

Prints debug information to the console. Useful for writing and debugging tests. By default, the `tmp_path` is stripped from the output to keep the output clean.

Possible arguments:

-   `value`: (required) The value to debug.
-   `label`: The label to display above the debug output.
-   `width`: The width of the debug output.
-   `pause`: If True, pause test execution after printing the debug output.
-   `strip_tmp_path`: If False, do not strip the `tmp_path` from the output.

```python
def test_something(debug):
    something = some_complicated_function()

    debug(something)

    assert something == expected
```

## pytest_assertrepr_compare

Patches the default pytest behavior of hiding whitespace differences in assertion failure messages. Replaces spaces and tabs with `[space]` and `[tab]` markers.
