# Logging

The `logger` object is a wrapper around the [Loguru](https://github.com/Delgan/loguru) logger with configurable log levels and custom styles.

The logger is a singleton, so it can be imported and used anywhere in your code. Once it has been configured, it will continue to output logs to the console or a file.

```python
# main.py
from nclutils import logger
from other import some_function

logger.configure(log_level="info")

some_function()
```

```python
# other.py
from nclutils import logger


def some_function():
    logger.info("This is a test info message")
    ...
```

## Configuration

By default, the logger will not output any logs. To enable logging, you must first configure the logger.

**`logger.configure(log_level: str, log_file: str | None = None, rotation: str = "5 MB", retention: int = 3, stderr: bool = True, enqueue: bool = False)`**

Configure the logger with the given log level, log file, rotation, retention, and enqueue.

-   `enqueue (bool)`: Whether the messages to be logged should first pass through a multiprocessing-safe queue before reaching the sink. This is useful while logging to a file through multiple processes. This also has the advantage of making logging calls non-blocking
-   `log_level (str)`: The log level to use.
-   `log_file (str | None)`: The log file to use. If not provided, logs will not be written to a file.
-   `rotation (str, int, datetime.time, datetime.timedelta or callable, optional)`: A condition indicating whenever the current logged file should be closed and a new one started. Defaults to "5 MB". See [Loguru's documentation](https://loguru.readthedocs.io/en/stable/api/logger.html#loguru.logger.add) for more information.
-   `retention (str, int, datetime.timedelta or callable, optional)`: A directive filtering old files that should be removed during rotation or end of program. Defaults to 3. See [Loguru's documentation](https://loguru.readthedocs.io/en/stable/api/logger.html#loguru.logger.add) for more information.
-   `stderr (bool)`: Whether to log to stderr. Defaults to True.

> [!IMPORTANT]\
> If `log_level` is not set, no logs will be output.

### Log Levels

The following log levels are available. Each will output all messages at that level and above.

-   `trace`
-   `debug`
-   `info`
-   `success`
-   `warning`
-   `error`
-   `critical`

## Logging Methods

The logger has the following methods:

-   `logger.trace(message: str, *args, **kwargs)`
-   `logger.debug(message: str, *args, **kwargs)`
-   `logger.info(message: str, *args, **kwargs)`
-   `logger.success(message: str, *args, **kwargs)`
-   `logger.warning(message: str, *args, **kwargs)`
-   `logger.error(message: str, *args, **kwargs)`
-   `logger.critical(message: str, *args, **kwargs)`

Extras can be added to the log message by passing `**kwargs` to the logging method.

```python
logger.warning("Hello, world!", somevar="somevalue")
>> 2025-05-11 11:30:43 | WARNING  | Hello, world! | {'somevar': 'somevale'} | __main__:<module>:19
```

## Catching Exceptions

The logger can log exceptions to the console or a file using the `@logger.catch` decorator.

```python
@logger.catch
def divide(a: int, b: int) -> float:
    return a / b

divide(1, 0)
```

This will log the following:

```shell
2025-05-11 11:34:17 | ERROR    | An error has been caught in function '<module>', process 'MainProcess' (99162), thread 'MainThread' (8372784256): (__main__:<module>:28)
Traceback (most recent call last):

> File "/Users/natelandau/repos/nclutils/tmp/test.py", line 28, in <module>
    answer = divide(1, 0)
             └ <function divide at 0x103d23e20>

  File "/Users/natelandau/repos/nclutils/tmp/test.py", line 25, in divide
    return a / b
           │   └ 0
           └ 1

ZeroDivisionError: division by zero
```
