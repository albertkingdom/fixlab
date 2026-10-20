## Purpose

Define how fixlab is packaged so that people other than the author can install it as a regular Python tool and run the `fixlab` command from any directory without creating a virtual environment by hand.

## ADDED Requirements

### Requirement: Regular installs include every fixlab subpackage

The package configuration SHALL discover every Python package under `fixlab` (every directory under `fixlab` that contains an `__init__.py`), so that a regular, non-editable install contains `fixlab` and all of its subpackages, including `fixlab.bench`. The package configuration SHALL NOT include the `tests` or `bench/problems` directories as packages.

#### Scenario: Every subpackage is covered by the package configuration

- **WHEN** the packaging test reads the setuptools package discovery settings from pyproject.toml, lists every directory under `fixlab` that contains an `__init__.py`, and walks the project the way setuptools discovery does with namespaces disabled (a directory without `__init__.py` stops the walk)
- **THEN** discovery searches from the project root with namespaces disabled, every listed package name, including `fixlab.bench`, is both reached by the walk and matched by the include patterns, and every discovered package that is included is `fixlab` or starts with `fixlab.`

#### Scenario: Non-editable tool install exposes the command and the subpackage

- **WHEN** fixlab is installed from the project directory with a non-editable `uv tool install` into a temporary tool directory and a temporary bin directory
- **THEN** the installed `fixlab --help` exits with code 0, and the tool's own Python interpreter can import `fixlab.bench`

#### Scenario: The installed tool runs tests inside the sandbox

- **WHEN** the tool was installed with a base Python located outside the home directory, and the tool's own Python runs the `run_tests` tool on a fresh copy of the timelog example project on macOS
- **THEN** the sandbox status is `on`, pytest starts and reports the example project's failing test, and the output contains no `dyld` or `ModuleNotFoundError` error

### Requirement: The README documents installation for users

README.md SHALL contain a user installation section, separate from the developer setup, that states at its start that fixlab supports only Python projects whose tests run with pytest, gives an install command for `uv tool install` and for `pipx install` from a git URL, names the three environment variables `OPENAI_BASE_URL`, `OPENAI_API_KEY` and `FIXLAB_MODEL`, states that fixlab does not load a `.env` file by itself, states that the test sandbox is enabled only on macOS, tells macOS users that the base Python of the environment running fixlab MUST be located outside the home directory (because the sandbox blocks a base Python under the home directory) while the tool environment itself MAY be under the home directory, gives a command for checking which base Python uv and pipx will use, gives the `uv tool install` command with `--no-managed-python` so uv does not pick its own Python stored under the home directory, and names `--python` as the way to choose another interpreter, explains how to add the target project's third-party dependencies to the isolated tool environment with `uv tool install --with` and `pipx inject`, and states that running the benchmark requires a clone of the project because the problem sets are not part of the installed package.

#### Scenario: A new user follows the README

- **WHEN** a reader opens the user installation section of README.md
- **THEN** it shows the Python-and-pytest-only scope note, both install commands, the three environment variable names, the `.env` note, the macOS-only sandbox note, the macOS base Python advice with `--no-managed-python` and the check commands, the `--with` and `pipx inject` dependency instructions and the benchmark clone note
