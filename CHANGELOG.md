## v3.4.4 (2026-08-15)

### Fix

- **pp**: add soft_wrap control for captured output
- **pp**: stop padding detail and kv lines to the console width

## v3.4.3 (2026-08-13)

### Fix

- **pp**: stop printing a blank line before warning, error, critical

## v3.4.2 (2026-07-09)

### Fix

- **git**: detect gone branches checked out in a worktree

## v3.4.1 (2026-05-12)

### Fix

- **pp**: rework step() outcome control for manual fail/skip (#46)

## v3.4.0 (2026-05-12)

### Feat

- **pp**: add set_skipped/skip_msg to step()
- **pp**: add set_success/set_failure to step() (#45)
- **strings**: add human_size byte formatter (#44)

## v3.3.1 (2026-05-11)

### Fix

- **sh**: strip trailing newlines and add properties

## v3.3.0 (2026-05-11)

### Feat

- add structured returns and new primitives (#43)

## v3.2.0 (2026-05-10)

### Feat

- **skill**: add agent-facing reference skill
- **sh**: log every run_command invocation at DEBUG (#42)
- **git**: add nclutils.git module (#41)

## v3.1.0 (2026-05-08)

### Feat

- **pp**: auto ASCII fallback for non-utf-8 consoles (#39)
- **pp**: add kv() for aligned key/value blocks (#38)
- **pp**: add exception kwarg to level methods (#37)
- **pp**: add success_msg and failure_msg to step() (#36)
- **pp**: add tag and right_tag kwargs to level methods (#35)

### Fix

- **pp**: render level details with tree connectors (#33)

### Refactor

- **pp**: dedupe log-prep and ASCII paths
- rename namespaces to ask/text/net (#34)

## v3.0.1 (2026-05-06)

### Fix

- **build**: update commitizen config

## v3.0.0 (2026-05-06)

### BREAKING CHANGE

- `from nclutils import info, success, ...` and similar
root-level imports no longer work. Migrate to `from nclutils import pp`
with `pp.info(...)` call sites, or `from nclutils.pp import info` for
direct symbol imports.
- `from nclutils import logger` is removed. Replace
with stdlib `logging`: `logger = logging.getLogger("your.module")`.
The `nclutils.logging` submodule is deleted entirely. Internal
diagnostic output from `nclutils.fs` / `nclutils.text_processing`
is now silent unless the consuming app attaches a handler to the
`nclutils` logger or its descendants.
- print_debug, pp, and PrintStyle are removed. console
and err_console are now functions returning the default emitter's
Console (call them: console().print(...)), not module-level Console
instances. imports like `from nclutils import copy_file` no
longer work. Use `from nclutils.fs import copy_file` (and equivalents
for sh, strings, utils, questions, text_processing, network).

### Feat

- **sh**: redesign shell module on subprocess (#28)
- **pretty_print**: rework around Emitter API (#24)
- remove pytest fixtures (#23)

### Fix

- **sh**: repair sudo, mutable default, and test gaps (#27)

### Refactor

- **pp**: rename pretty_print module to pp (#31)
- **fs**: _Copier class, strict kwarg, unified progress (#30)
- **fs**: correctness, consistency, and ergonomics cleanup (#29)
- drop nclutils.logging, use stdlib logging (#25)

## v2.1.0 (2025-08-02)

### Feat

- **sh**: add foreground support to run_command (#18)

## v2.0.0 (2025-07-14)

### Feat

- **sh**: add option to redirect stderr to stdout (#17)
- add text processing utilities

### Fix

- **utils**: remove microseconds from new_timestamp_uid (#16)
- **fs**: ensure file copy completeness and integrity (#14)

### Refactor

- **linting**: enable more ruff rules (#15)

## v1.0.1 (2025-06-25)

### Fix

-   **ci**: fix broken workflow

## v1.0.0 (2025-06-25)

### BREAKING CHANGE

-   Inverts the previous default behavior when configuring the logger.

### Feat

-   **logger**: change default to print timestamps to stderr (#11)
-   add `err_console` to print to stderr (#10)

## v0.6.0 (2025-06-21)

### Feat

-   **logger**: add an optional prefix to logs (#9)

## v0.5.0 (2025-06-18)

### Feat

-   **fixtures**: add clean_stderrout fixture (#8)
-   **filesystem**: add clean_directory()

## v0.4.0 (2025-06-06)

### Feat

-   **logger**: add option to suppress source references (#6)
-   **strings**: add int_to_emoji
-   **fixtures**: strip `tmp_path` from test output (#5)

## v0.3.0 (2025-05-15)

### Feat

-   add logging module (#4)

## v0.2.2 (2025-05-10)

### Fix

-   support python 3.10 (#3)

## v0.2.1 (2025-05-09)

### Fix

-   **copy_path**: fix error overwriting directories
-   make split_camel_case importable

## v0.2.0 (2025-05-09)

### Feat

-   **strings**: add `split_camel_case()`

## v0.1.0 (2025-05-09)

### Feat

-   **fixtures**: add pytest fixtures (#1)
-   initial commit
