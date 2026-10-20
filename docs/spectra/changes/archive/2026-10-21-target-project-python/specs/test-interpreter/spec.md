## Purpose

Decide which Python interpreter run_tests uses for the project being fixed, so the tests can run with the project's own installed packages, and check that interpreter before any model request. The interpreter is only ever chosen by the user; files inside the project never choose it, because the project may be untrusted.

## ADDED Requirements

### Requirement: The command line chooses the test interpreter

The command-line entry SHALL use the interpreter given with `--python PATH` for run_tests, and otherwise the interpreter running fixlab (`sys.executable`). It SHALL NOT pick an interpreter from files inside the target directory (such as `.venv`), because the target project may be untrusted and those files would then decide what runs. A `--python` value containing a path separator SHALL be made absolute against the directory fixlab was started in, without resolving symbolic links (a virtual environment's python is a link, and resolving it loses the environment's packages); a bare name such as `python3` SHALL be looked up on PATH and the result made absolute. The same absolute path SHALL be used for the check, the Workspace, the sandbox and the event log. The source of the choice SHALL be `option` or `default`.

#### Scenario: Interpreter given on the command line

- **WHEN** the user runs `fixlab PATH --python /some/env/bin/python` and that interpreter passes the check
- **THEN** run_tests runs pytest with `/some/env/bin/python` and the source is `option`

#### Scenario: Relative interpreter path

- **WHEN** the user starts fixlab in directory D and passes `--python env/bin/python`
- **THEN** the interpreter used for the check, the Workspace and run_tests is `D/env/bin/python`

#### Scenario: A virtual environment in the project is not used by itself

- **WHEN** the target directory contains `.venv/bin/python` and `--python` is not given
- **THEN** run_tests runs pytest with the interpreter running fixlab, the source is `default`, and nothing inside `.venv` is executed

### Requirement: The test interpreter is checked before the run starts

After the other arguments are checked and before the event log or any model request is created, the command-line entry SHALL check the chosen interpreter and SHALL exit with code 2 and a message naming the interpreter when: the path does not exist or is not executable; following the interpreter path through every symbolic link to the real executable passes through any location inside the workspace other than a virtual environment directory that is itself inside the workspace, reached without links, and holds `pyvenv.cfg` (everything else in the workspace can be replaced by code under test, which would then run a fake interpreter); its environment directory is inside the workspace but is not such a virtual environment; its environment directory is the workspace or contains it; it is older than Python 3.11 (run_tests starts pytest with `-P`, which older versions do not have); or it cannot import pytest. The version and the pytest import SHALL be checked by one run of the interpreter inside exactly the sandbox that run_tests uses for that Workspace (the same read and write rules and the same test protection), with the same environment variables, a private temporary directory as the current directory, and a timeout of 10 seconds. The version SHALL be read from an output line that starts with a fixed marker, so other lines printed at startup do not matter. The message for a missing pytest SHALL tell the user to install pytest into that environment or to pass a different `--python`.

#### Scenario: Interpreter path does not exist

- **WHEN** the user runs `fixlab PATH --python /no/such/python`
- **THEN** fixlab prints an error naming `/no/such/python`, exits with code 2, sends no model request and creates no event log file

#### Scenario: Interpreter older than 3.11

- **WHEN** the chosen interpreter reports a version below 3.11
- **THEN** fixlab prints an error naming the interpreter and its version and saying 3.11 or newer is required, exits with code 2, and sends no model request

#### Scenario: Environment without pytest

- **WHEN** the chosen interpreter cannot import pytest
- **THEN** fixlab prints an error naming that interpreter and saying pytest is missing, exits with code 2, sends no model request, and creates no event log file

#### Scenario: Startup output before the version

- **WHEN** the chosen interpreter prints another line before the marked version line and can import pytest
- **THEN** the check passes

#### Scenario: Interpreter that goes through a link in the project

- **WHEN** `<workspace>/.venv/bin/python` links to `../../scripts/py`, which links to a real Python outside the workspace
- **THEN** fixlab prints an error naming `scripts/py`, exits with code 2, and sends no model request

#### Scenario: Environment in the project without pyvenv.cfg

- **WHEN** the user passes `--python <workspace>/tools/bin/python` and `tools` has no `pyvenv.cfg`
- **THEN** fixlab prints an error mentioning `pyvenv.cfg`, exits with code 2, and sends no model request

#### Scenario: Environment reached through a link in the project

- **WHEN** the project's `.venv` is a symbolic link to an environment elsewhere and the user passes `--python .venv/bin/python`
- **THEN** fixlab prints an error naming the link, exits with code 2, and sends no model request

#### Scenario: Environment that contains the workspace

- **WHEN** the environment directory of the chosen interpreter is the target directory or one of its parents
- **THEN** fixlab prints an error saying the environment contains the project, exits with code 2, and sends no model request

### Requirement: The benchmark uses fixlab's own interpreter

The benchmark runner SHALL pass the interpreter running fixlab to the command-line entry with `--python`, so the interpreter used in experiments is stated explicitly and stays comparable with earlier runs. The grader SHALL keep running tests with the interpreter running fixlab.

#### Scenario: Benchmark run records fixlab's interpreter

- **WHEN** the benchmark runner runs a problem
- **THEN** the run's `run_start` event records the interpreter running fixlab with the source `option`
