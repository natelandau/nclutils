### Questions

Convenience functions for working with the [questionary](https://github.com/tmbo/questionary) library.

## choose_one_from_list

Choose one item from a list of items:

```python
from nclutils import choose_one_from_list

choices = ["test", "test2", "test3"]
result = choose_one_from_list(choices, "Choose a string")
```

To use objects, send a list of tuples as choices. The first element of the tuple is the display title, the second element is the object to return.

```python
from nclutils import choose_from_list

@dataclass
class Something:
    name: str
    number: int

choices = [
    ("test1", Something(name="test1", number=1)),
    ("test2", Something(name="test2", number=2)),
]
result = choose_from_list(choices, msg="Choose one")
```

## choose_multiple_from_list

Choose multiple items from a list of items.

```python
from nclutils import choose_multiple_from_list

choices = ["test", "test2", "test3"]
results = choose_multiple_from_list(choices, msg="Choose multiple")
for result in results:
    print(result)
```
