## MODIFIED Requirements

### Requirement: Interactive mode is entered with -i

`fixlab PATH -i` SHALL start interactive mode: it SHALL print the prompt `fixlab> ` and read one line at a time. When PATH is omitted, fixlab SHALL use the current working directory. Without PATH and without an explicit `--task`, fixlab SHALL default to interactive mode. An explicit `-i` SHALL select interactive mode regardless of PATH or `--task`. Without `-i`, providing PATH SHALL select the one-shot command. Because one-shot mode does not ask before editing, `--task` without PATH and without `-i` SHALL be refused with exit code 2 before any model request or event log is created. When PATH is omitted and the current directory contains the default log directory, fixlab SHALL exit with code 2 and tell the user to run from a project directory or pass PATH. Interactive mode SHALL use the same checks as one-shot mode (PATH must be a directory, an API key and a model must be set) and exit with code 2 when they fail. Telemetry SHALL record the resolved path and selected mode.

#### Scenario: Without -i nothing changes

- **WHEN** the user runs `fixlab ./timelog` with a fake client that answers "Done."
- **THEN** fixlab does not print `fixlab> `, runs one task with the default task text, and ends with a `RESULT:` line

#### Scenario: Missing model

- **WHEN** the user runs `fixlab ./timelog -i` with no `--model` and no `FIXLAB_MODEL`
- **THEN** fixlab prints an error about the missing model and exits with code 2 without showing the prompt

#### Scenario: Start in the current directory

- **WHEN** the user runs `fixlab` from a project directory with valid model settings and then sends EOF
- **THEN** fixlab shows `fixlab> `, records that directory and interactive mode, makes no model request, runs no tests, and exits with code 0

#### Scenario: Explicit interactive flag without a path

- **WHEN** the user runs `fixlab -i` from a project directory with valid model settings
- **THEN** fixlab starts interactive mode in that directory

#### Scenario: Explicit task without a path

- **WHEN** the user runs `fixlab --task 'explain parser'` without PATH and without `-i`
- **THEN** fixlab prints an error saying `--task` needs PATH, exits with code 2, sends no model request and leaves the directory unchanged

#### Scenario: Started from the home directory

- **WHEN** the user runs `fixlab` without PATH from a directory that contains the default log directory
- **THEN** fixlab exits with code 2 and tells the user to run it from a project directory or pass PATH, instead of suggesting `--log-dir`
