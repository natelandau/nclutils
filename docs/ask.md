# Ask

Two wrappers around [questionary](https://github.com/tmbo/questionary) for the most common interactive prompts: pick one item or pick many. Import them from `nclutils.ask`.

> [!NOTE]
> `nclutils.questions` is a deprecated alias of `nclutils.ask`. It raises a `DeprecationWarning` on import and will be removed in a future major release. Import from `nclutils.ask` instead.

```python
from nclutils.ask import choose_one_from_list

color = choose_one_from_list(["red", "green", "blue"], "Pick a color")
```

## Single selection

`choose_one_from_list(choices, message)` shows a select widget and returns the chosen value. It returns `None` if the choices list is empty or the user presses Ctrl-C. A falsy value such as `0`, `False`, or `""` is returned like any other value.

```python
from nclutils.ask import choose_one_from_list

color = choose_one_from_list(["red", "green", "blue"], "Pick a color")
if color is None:
    print("cancelled")
```

## Multiple selection

`choose_multiple_from_list(choices, message)` shows a checkbox widget and returns a list of the selected values. It returns `None` if the choices list is empty, the user selects nothing, or the user presses Ctrl-C.

```python
from nclutils.ask import choose_multiple_from_list

picks = choose_multiple_from_list(
    ["api", "cli", "docs", "tests"],
    "Which areas changed?",
)
for area in picks or []:
    print(area)
```

## Choice formats

Both functions accept the same three input shapes. Use the shape that fits your data.

### Plain values

A list of `Path`, `str`, `int`, `float`, or `bool`. The widget shows the `str()` of each value. For a `Path`, the widget shows `path.name`.

```python
from pathlib import Path
from nclutils.ask import choose_one_from_list

# The widget shows only the filename, but the returned value is the full Path
config = choose_one_from_list(
    [Path("./conf/dev.toml"), Path("./conf/prod.toml")],
    "Choose a config",
)
```

### `(label, value)` tuples

To show a label that is different from the value, pass a list of two-tuples. The widget shows the first element and the function returns the second.

```python
from dataclasses import dataclass
from nclutils.ask import choose_one_from_list


@dataclass
class Profile:
    name: str
    region: str


profile = choose_one_from_list(
    [
        ("US production", Profile(name="prod", region="us-east-1")),
        ("EU production", Profile(name="prod", region="eu-west-1")),
        ("Staging", Profile(name="staging", region="us-east-1")),
    ],
    "Pick a deployment target",
)
```

### Single-key dicts

A list of single-key `{label: value}` dicts works the same as the tuple form. Use it when your data already has that shape.

```python
from nclutils.ask import choose_multiple_from_list

selected = choose_multiple_from_list(
    [{"Frontend": "fe"}, {"Backend": "be"}, {"Infra": "infra"}],
    "Which teams to notify?",
)
# ["fe", "be"] if the user checks Frontend and Backend
```

> [!NOTE]
> Each item is converted on its own, so one call can mix shapes. One shape per prompt is easier to read.

## API reference

- `choose_one_from_list(choices, message) -> T | None`. Single-select prompt. Returns the chosen value or `None`.
- `choose_multiple_from_list(choices, message) -> list[T] | None`. Multi-select prompt. Returns the chosen values or `None`.

`choices` accepts `list[Path | str | int | float | bool]`, `list[tuple[str, T]]`, or `list[dict[str, T]]`. `message` is the prompt text that shows above the widget.
