# Questions

Two thin wrappers around [questionary](https://github.com/tmbo/questionary) for the most common interactive prompts: pick one item or pick many. Imported from `nclutils.questions`.

```python
from nclutils.questions import choose_one_from_list

color = choose_one_from_list(["red", "green", "blue"], "Pick a color")
```

## Single selection

`choose_one_from_list(choices, message)` displays a select widget and returns the chosen value, or `None` if the user cancels (Esc / Ctrl-C) or the choices list is empty.

```python
from nclutils.questions import choose_one_from_list

color = choose_one_from_list(["red", "green", "blue"], "Pick a color")
if color is None:
    print("cancelled")
```

## Multiple selection

`choose_multiple_from_list(choices, message)` shows a checkbox widget and returns a list of selected values. Like the single-select version, it returns `None` if nothing was selected or the user cancelled.

```python
from nclutils.questions import choose_multiple_from_list

picks = choose_multiple_from_list(
    ["api", "cli", "docs", "tests"],
    "Which areas changed?",
)
for area in picks or []:
    print(area)
```

## Choice formats

Both functions accept the same three input shapes. Use whichever fits your data:

### Plain values

A list of `Path`, `str`, `int`, `float`, or `bool`. The display string is the value's `str()` representation, except for `Path` where the display string is `path.name`:

```python
from pathlib import Path
from nclutils.questions import choose_one_from_list

# Display will show just the filename, but the returned value is the full Path
config = choose_one_from_list(
    [Path("./conf/dev.toml"), Path("./conf/prod.toml")],
    "Choose a config",
)
```

### `(label, value)` tuples

When you need a different display string than the value, pass a list of two-tuples. The first element is shown to the user; the second is what gets returned.

```python
from dataclasses import dataclass
from nclutils.questions import choose_one_from_list

@dataclass
class Profile:
    name: str
    region: str

profile = choose_one_from_list(
    [
        ("US production", Profile(name="prod", region="us-east-1")),
        ("EU production", Profile(name="prod", region="eu-west-1")),
        ("Staging",       Profile(name="staging", region="us-east-1")),
    ],
    "Pick a deployment target",
)
```

### Single-key dicts

A list of single-key `{label: value}` dicts works the same as the tuple form. Use it when your data is already shaped that way.

```python
from nclutils.questions import choose_multiple_from_list

selected = choose_multiple_from_list(
    [{"Frontend": "fe"}, {"Backend": "be"}, {"Infra": "infra"}],
    "Which teams to notify?",
)
# -> ["fe", "be"] (or whichever boxes the user checked)
```

> **Note:** Mixing shapes in the same call works (each item is inspected independently), but it's a smell. Pick one shape per prompt.

## API reference

- `choose_one_from_list(choices, message) -> T | None`. Single-select prompt. Returns the chosen value or `None`.
- `choose_multiple_from_list(choices, message) -> list[T] | None`. Multi-select prompt. Returns the chosen values or `None`.

`choices` accepts `list[Path | str | int | float | bool]`, `list[tuple[str, T]]`, or `list[dict[str, T]]`. `message` is the prompt text shown above the widget.
