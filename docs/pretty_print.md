# Pretty Printing

The pretty printing module provides styled console output with configurable log levels and custom styles.

```python
from nclutils import pp, console

#Configure logging levels
pp.configure(debug=True, trace=True)

# Basic message types
pp.info("Hello, world!")
pp.debug("This is a debug message")
pp.trace("This is a trace message")
pp.success("This is a success message")
pp.warning("This is a warning message")
pp.error("This is an error message")
pp.critical("This is a critical message")
pp.dryrun("This is a dry run message")
pp.notice("This is a notice message")
pp.secondary("This is a secondary message")
pp.rule("This is a horizontal rule")
console.print("This is a console message")
console.log("This is a log message")
```

## Confirming verbosity state

The `pp` object has boolean attributes `is_debug` and `is_trace` that can be used to check the current verbosity state.

```python
if pp.is_debug:
    print("Debug is enabled")
if pp.is_trace:
    print("Trace is enabled")
```

## Customizing Styles

Create new styles or modify existing ones using the `PrintStyle` class:

```python
from nclutils import PrintStyle, pp

# Create custom styles
new_style = PrintStyle(name="new_style", prefix=":smile: ", suffix=" :rocket:")
new_error = PrintStyle(name="error", style="bold green")

# Apply custom styles
pp.configure(styles=[new_style, new_error])

# Use custom styles
pp.new_style("I am new style")
pp.error("This error message is now bold green")
```

## View All Styles

A debug method is available to view all available styles.

```python
pp.all_styles()
```
