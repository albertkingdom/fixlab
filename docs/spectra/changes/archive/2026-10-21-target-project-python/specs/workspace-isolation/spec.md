## ADDED Requirements

### Requirement: The sandbox allows the test interpreter and its base Python

When the sandbox is available, it SHALL allow reads of the test interpreter's environment directory (two levels above the interpreter path, as given) only when that directory is a virtual environment (it holds `pyvenv.cfg`), and of the base Python installation, in addition to the workspace, even when they are inside the user's home directory; for an interpreter that is not in a virtual environment, only the base installation SHALL be allowed. The base installation SHALL be computed once per Workspace, the result (or the failure) kept and reused for every run, never re-read during the run. It SHALL be two levels above the interpreter's real path (symbolic links resolved, so a virtual environment whose python links to the base, or a folder of links such as `~/.local/bin`, leads to the real installation); only when the real path is still inside the environment (an environment made with copies) SHALL it be the parent of the real path of the `home` value in `pyvenv.cfg`. When `pyvenv.cfg` has a `home` value, it MUST be an absolute path. A virtual environment directory that is allowed for reading SHALL NOT be the user's home directory or one of its parents, SHALL NOT be, contain, or be inside an extra deny_read directory, and SHALL NOT be or contain fixlab's own project directory unless that directory is inside the environment's site-packages (as when fixlab is installed into that environment), because allowing it would reopen fixlab's own files, such as its `.env`, to code under test; an interpreter that is not in a virtual environment SHALL NOT be refused because of where its environment directory is, since that directory is not allowed. The base installation SHALL be refused, and fixlab SHALL exit with code 2 before any model request, when: the `home` value is not absolute; the base contains no Python standard library (no `lib/python3.N/os.py`, or `Frameworks/Python.framework/Versions/3.N/lib/python3.N/os.py` for a framework build); the base is the user's home directory or one of its parents; the base is, or is inside, the workspace, fixlab's own project directory, or an extra deny_read directory; or the base contains the workspace or an extra deny_read directory. A base that contains fixlab's own project directory SHALL be allowed only when that directory is inside the base's site-packages, because fixlab installed into a plain Python lives there; otherwise it SHALL be refused, because allowing it would reopen fixlab's own files, such as its `.env`. All of these containment and overlap checks SHALL compare file-system identity, not spelling, because the sandbox matches paths without regard to letter case. Without a sandbox the base SHALL NOT be computed or checked, because nothing needs to be allowed and the standard library layout differs between platforms. Reads of the rest of the home directory and of fixlab's own project directory SHALL stay denied.

#### Scenario: Base Python under the home directory

- **WHEN** the test interpreter belongs to a virtual environment whose `pyvenv.cfg` names a base Python under the user's home directory (as uv-managed and pyenv Pythons are)
- **THEN** run_tests starts pytest and reports the project's test results, with no `dyld` or permission error

#### Scenario: The rest of the home directory stays closed

- **WHEN** the base Python is under the user's home directory and code under test reads a fake key file elsewhere in the home directory during run_tests
- **THEN** the read fails with PermissionError

#### Scenario: An interpreter outside a virtual environment

- **WHEN** the test interpreter is a link such as `~/.local/bin/python3` that is not in a virtual environment
- **THEN** the sandbox allows reads of the real Python installation only, not of `~/.local`

#### Scenario: fixlab installed into a plain Python

- **WHEN** fixlab is installed into a Python that is not a virtual environment and runs with its default interpreter
- **THEN** the base installation contains fixlab's own directory and is allowed

#### Scenario: No sandbox available

- **WHEN** sandbox-exec is not available
- **THEN** the base installation is not computed or checked, and `run_start` records `test_python.base` as null

#### Scenario: A pyvenv.cfg that points at another folder

| `home` in the environment's pyvenv.cfg                         | Result                    |
| -------------------------------------------------------------- | ------------------------- |
| a relative path such as `../../.ssh/bin`                       | refused with exit code 2  |
| an absolute folder with no standard library under its parent   | refused with exit code 2  |
| the home directory's own bin folder                            | refused with exit code 2  |
| a bin folder inside the workspace                              | refused with exit code 2  |
| a bin folder inside fixlab's project directory                 | refused with exit code 2  |
| the bin folder of a real Python installation                   | allowed                   |

### Requirement: The test environment inside the workspace is read-only

When the test interpreter's environment directory is inside the workspace, the tool layer SHALL treat every path inside it as read-only, and the sandbox SHALL deny every write inside it during run_tests (whether or not it holds `pyvenv.cfg`). Whether a path is inside the environment or the workspace SHALL be decided by file-system identity, not by spelling, so a path that differs only in letter case on a case-insensitive file system is still protected and SHALL deny deleting, renaming or moving the environment directory and each of its parent directories inside the workspace, so neither the model nor code under test can change the pytest that judges the result. This SHALL hold whether or not `protect_tests` is on.

#### Scenario: Model edits pytest in the environment

- **WHEN** the test interpreter is `<workspace>/.venv/bin/python` and the model calls write_file or edit_file on a file under `.venv`
- **THEN** the tool returns ok=false with the flag `blocked` and the file is unchanged

#### Scenario: Code under test edits pytest in the environment

- **WHEN** the test interpreter is `<workspace>/.venv/bin/python` and code under test tries to write a file under `.venv`, or to create a hard link to one, during run_tests
- **THEN** the attempt fails with PermissionError and the file is unchanged

#### Scenario: Renaming a parent of the environment

- **WHEN** `protect_tests` is off, the test interpreter is `<workspace>/tools/env/bin/python`, and code under test tries to rename `tools` during run_tests
- **THEN** the rename fails with PermissionError
