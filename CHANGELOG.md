## v2.3.6 (2025-04-01)

### Fix

- correct missing import

## v2.3.5 (2025-04-01)

### Fix

- **filesystem**: add `find_user_home_dir()`

## v2.3.4 (2025-04-01)

### Fix

- **print_debug**: include specific variables and packages

## v2.3.3 (2025-03-31)

### Refactor

- **prettyprint**: correct type error

## v2.3.2 (2025-03-31)

### Fix

- **prettyprint**: add support for dicts in messages

## v2.3.1 (2025-03-30)

### Fix

- **questions**: fix bug in select_multiple

## v2.3.0 (2025-03-29)

### Feat

- **sh**: run commands with sudo
- **sh**: exclude lines from command output with regex
- **fs**: add `copy_directory()` (#19)
- **strings**: add `random_string()`
- **fs**: add `continue_sequence` option to `unique_filename()`
- **fs**: add `copy_file()` (#18)

## v2.2.1 (2025-03-12)

### Fix

- **pretty-print**: remove duplicate packages from print_debug

## v2.2.0 (2025-03-12)

### Feat

- **pretty-print**: add `print_debug()` (#16)

### Refactor

- **errors**: simplify ShellCommandFailedError implementation

## v2.1.0 (2025-03-11)

### Feat

- **filesystem**: add `backup_path()`

## v2.0.1 (2025-03-11)

### Fix

- **questions**: fix typing for choose_multiple_from_list

## v2.0.0 (2025-03-11)

### BREAKING CHANGE

- removed `choose_from_list()` in favor of two distinct functions `choose_multiple_from_list()` and `choose_one_from_list()`

### Feat

- **questions**: refactor selecting from lists (#15)

## v1.7.0 (2025-03-10)

### Feat

- **strings**: add many string utilities (#14)
- add `network_available()` and `unique_id()` (#13)
- **filesystem**: add `unique_filename()` (#12)
- **filesystem**: add `directory_tree()` (#11)
- **pretty-print**: support inline code highlighting using markdown tags (#10)
- **pretty-print**: manage verbosity with `is_debug` and `is_trace` (#9)

## v1.6.0 (2025-02-27)

### Feat

- **run-command**: specify passing exit codes with `ok_codes`

## v1.5.0 (2025-02-25)

### Feat

- **questions**: pass objects to choose_from_list

## v1.4.0 (2025-02-25)

### Feat

- **shell-command**: allow changing directories before running a command
- **shell-command**: add `which` to check if command exists in PATH
- **shell-commands**: use exceptions for failed commands

## v1.3.1 (2025-02-24)

### Fix

- **sh**: iterate over shell output to speed responses

## v1.3.0 (2025-02-23)

### Feat

- **questions**: add `choose_from_list()` (#7)

## v1.2.1 (2025-02-23)

### Fix

- **filesystem**: `find_files` now importable

## v1.2.0 (2025-02-23)

### Feat

- **pretty-print**: view all available print styles with `pp.all_styles()`

## v1.1.0 (2025-02-23)

### Feat

- **shell**: add `run_command()` (#6)

### Fix

- **pretty-print**: dryrun is no longer bold
- **filesystem**: find_subdirectories defaults to include dotfiles
- **pretty-print**: use `cadet_blue` for trace and debug logging

## v1.0.0 (2025-02-22)

### Feat

- **filesystem**: add `find_files` (#5)
- **filesystem**: add `fetch_subdirectories` module

## v0.2.0 (2025-02-21)

### Feat

- **prettypint**: initial commit (#1)
