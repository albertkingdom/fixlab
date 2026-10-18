## ADDED Requirements

### Requirement: The test run environment is deterministic

The environment of every test subprocess started by `run_tests` SHALL set `TZ` to `UTC`, `PYTHONHASHSEED` to `0` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD` to `1`, in addition to the variables it already sets. Pytest plugins are therefore not loaded automatically, and the result of a test does not depend on the machine's time zone or hash order.

#### Scenario: The variables are set

- **WHEN** a test run executes a test that reads `TZ`, `PYTHONHASHSEED` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD` from its environment
- **THEN** the values are `UTC`, `0` and `1`, whatever the parent process had

#### Scenario: Installed pytest plugins are not loaded

- **WHEN** `run_tests` runs a test that asserts the module `anyio` has not been imported, in an environment where the anyio pytest plugin is installed and registered by entry point
- **THEN** the test passes, because plugins registered by entry point are not loaded automatically

### Requirement: Tools can be hidden from the model

A Workspace SHALL be able to hide a registered tool by name. A hidden tool SHALL NOT appear in the tool list sent to the model and SHALL NOT appear in the schemas used to validate the model's reply, so a model call to it is treated as a call to an unknown tool. The program itself SHALL still be able to call a hidden tool through the Workspace. The fixlab command SHALL offer `--hide-tool NAME`, repeatable, and SHALL exit with code 2 and create no event file when a name is not a registered tool.

#### Scenario: A hidden tool is not offered

- **WHEN** `run_tests` is hidden and the tool list is built
- **THEN** the list contains `read_file`, `list_files`, `grep`, `edit_file` and `write_file`, and does not contain `run_tests`

#### Scenario: The model calls a hidden tool anyway

- **WHEN** `run_tests` is hidden and the model's reply calls `run_tests`
- **THEN** the call is rejected as an unknown tool and no tests run

#### Scenario: The program still runs the tests

- **WHEN** `run_tests` is hidden and a one-shot run finishes
- **THEN** the final test run that fixlab performs itself still executes and its result is printed

#### Scenario: An unknown tool name

- **WHEN** fixlab is started with `--hide-tool bash`
- **THEN** it exits with code 2 with a message that names `bash`, and no event file is created
