## v1.0.1 (2025-06-25)

### Fix

- **ci**: fix broken workflow

## v1.0.0 (2025-06-25)

### BREAKING CHANGE

- Inverts the previous default behavior when configuring
the logger.

### Feat

- **logger**: change default to print timestamps to stderr (#11)
- add `err_console` to print to stderr (#10)

## v0.6.0 (2025-06-21)

### Feat

- **logger**: add an optional prefix to logs (#9)

## v0.5.0 (2025-06-18)

### Feat

- **fixtures**: add clean_stderrout fixture (#8)
- **filesystem**: add clean_directory()

## v0.4.0 (2025-06-06)

### Feat

- **logger**: add option to suppress source references (#6)
- **strings**: add int_to_emoji
- **fixtures**: strip `tmp_path` from test output (#5)

## v0.3.0 (2025-05-15)

### Feat

- add logging module (#4)

## v0.2.2 (2025-05-10)

### Fix

- support python 3.10 (#3)

## v0.2.1 (2025-05-09)

### Fix

- **copy_path**: fix error overwriting directories
- make split_camel_case importable

## v0.2.0 (2025-05-09)

### Feat

- **strings**: add `split_camel_case()`

## v0.1.0 (2025-05-09)

### Feat

- **fixtures**: add pytest fixtures (#1)
- initial commit
