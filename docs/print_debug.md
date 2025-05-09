# Print Debug

Print debug information about the current environment. Takes these optional arguments:

-   `envar_prefix`: A prefix to filter environment variables. Only variables starting with this prefix will be included.
-   `custom`: A list of dictionaries containing custom debug data. Each dictionary represents a section with key-value pairs.
-   `packages`: A list of installed package names to check versions for.
-   `all_packages`: Whether to show all installed package names and versions.

```python
from nclutils import print_debug

config_as_dict = {
    "Configuration": {
        "key": "value",
        "key2": "value2",
        "key3": "value3",
    }
}

cli_args_as_dict = {
    "somevar": "somevalue",
    "anothervar": "anothervalue",
}

print_debug(custom=[config_as_dict, cli_args_as_dict], envar_prefix="NCLUTILS_", packages=["nclutils"])
```
