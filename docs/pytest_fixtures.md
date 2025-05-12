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

Clean the stdout of the console output by creating a wrapper around `capsys` to capture console stdout output.

```python
def test_something(clean_stdout):
    print("Hello, world!")
    output = clean_stdout()
    assert output == "Hello, world!"
```

## clean_stderr

Clean the stderr of the console output by creating a wrapper around `capsys` to capture console stderr output.

````python
def test_something(clean_stderr):
    print("Hello, world!")
    output = clean_stderr()
    assert output == "Hello, world!"

## debug

Prints debug information to the console. Useful for writing and debugging tests.

```python
def test_something(debug):
    something = some_complicated_function()

    debug(something)

    assert something == expected
````

## pytest_assertrepr_compare

Patches the default pytest behavior of hiding whitespace differences in assertion failure messages. Replaces spaces and tabs with `[space]` and `[tab]` markers.
