## Purpose

Workspace isolation keeps the agent inside one project directory and makes the project's tests a trustworthy signal. It blocks paths outside the workspace, makes test files unwritable and tamper-evident, and runs the tests in a sandbox with no network, limited file access, and a minimal environment.

## ADDED Requirements

### Requirement: Paths stay inside the workspace

Every tool that takes a path SHALL resolve it (following symbolic links) and reject it unless the result is inside the workspace directory. Absolute paths and paths starting with `~` SHALL be rejected. A rejected call SHALL return ok=false and set the `blocked` flag, and the `blocked` flag SHALL be set for no other reason than a path rejection or a write to a read-only path.

#### Scenario: Path traversal attempts

| Path given                         | Result  |
| ---------------------------------- | ------- |
| ../secret.txt                      | blocked |
| sub/../../secret.txt               | blocked |
| /etc/hosts                         | blocked |
| ~/.zprofile                        | blocked |
| link_secret (symlink to ../secret) | blocked |
| timelog/parser.py                  | allowed |

#### Scenario: Other errors are not blocked

- **WHEN** read_file is called on timelog/missing.py inside the workspace
- **THEN** the result has ok=false and the `blocked` flag is not set

### Requirement: Test files cannot be written

A Workspace SHALL accept a read-only rule: a function that takes a path relative to the workspace root and returns whether that file may not be written. By default the rule SHALL mark no file as read-only. The rule `looks_like_test_file` SHALL mark a relative path when its file name, compared case-insensitively, starts with `test_`, ends with `_test.py`, or equals `conftest.py`, or when any directory component of the relative path is named `tests` or `test`, compared case-insensitively. write_file and edit_file SHALL reject any path that the Workspace's rule marks, judged on the path relative to the workspace root after symbolic links are resolved, so the location of the workspace itself has no effect. A rejected call SHALL set the `blocked` flag and leave the file unchanged.

#### Scenario: Relative paths marked by looks_like_test_file

The Workspace is created with `looks_like_test_file` as its rule.

| Relative path                 | write_file and edit_file |
| ----------------------------- | ------------------------ |
| tests/test_report.py          | blocked                  |
| tests/helpers.py              | blocked                  |
| conftest.py                   | blocked                  |
| TEST_REPORT.PY                | blocked                  |
| timelog/test_formatting.py    | blocked                  |
| notes/test_notes.txt          | blocked                  |
| Tests/data/cases.json         | blocked                  |
| timelog/parser.py             | allowed                  |
| timelog/contest.py            | allowed                  |
| timelog/tests.py              | allowed                  |

#### Scenario: Workspace located under a tests directory

- **WHEN** the workspace root is /project/tests/fixtures/timelog and edit_file is called on timelog/parser.py
- **THEN** the call is allowed, while tests/test_report.py in the same workspace is still blocked

#### Scenario: No rule by default

- **WHEN** a Workspace is created without a read-only rule and edit_file is called on tests/test_report.py
- **THEN** the edit is allowed and the `blocked` flag is not set

#### Scenario: Custom rule

- **WHEN** a Workspace is created with a rule that marks only tests/test_report.py
- **THEN** edit_file on tests/test_report.py is blocked, while edit_file on tests/helpers.py is allowed

### Requirement: Tampering with test files is detected

When a Workspace is created it SHALL compute one SHA-256 fingerprint over the sorted relative paths and contents of all files that the Workspace's read-only rule marks, skipping the directories .git, .venv, __pycache__, and .pytest_cache and not following symbolic links. After every run_tests call it SHALL compute the fingerprint again and SHALL set the flag `test_file_tampered` when it differs, including when a marked file was added, deleted, or changed. A Workspace with the default rule marks no files, so it SHALL never set the flag.

#### Scenario: Test changed behind the tools' back

- **WHEN** a read-only file tests/test_report.py is modified on disk by code run outside the sandbox between the two fingerprints
- **THEN** the run_tests result has the flag `test_file_tampered` set

#### Scenario: Nothing changed

- **WHEN** no read-only file changed and run_tests is called
- **THEN** the flag `test_file_tampered` is not set

#### Scenario: Read-only file deleted

- **WHEN** tests/helpers.py is deleted before run_tests is called
- **THEN** the flag `test_file_tampered` is set

#### Scenario: Compiled cache files are ignored

- **WHEN** a file __pycache__/test_report.cpython-314-pytest-9.1.1.pyc appears after a test run
- **THEN** the flag `test_file_tampered` is not set

### Requirement: Tests run in a sandbox

run_tests SHALL run pytest under macOS sandbox-exec with no network access, with reads denied for the user's home directory, the whole project directory of fixlab, and every extra deny_read directory except the workspace itself and the Python virtual environment, and with writes allowed only inside the workspace and /dev. When the Workspace uses `looks_like_test_file`, the sandbox SHALL deny, inside the workspace, writes to every path that rule marks and renaming or moving a directory named `tests` or `test`, using the same case-insensitive rules as the tool layer. The sandbox derives its rules from `looks_like_test_file` only; a custom read-only rule is enforced by the tool layer and the fingerprint but not by the sandbox. The workspace path used in the sandbox's regular-expression rules SHALL have every regular-expression special character escaped. The sandbox profile text SHALL contain no literal workspace, project, home, or deny_read paths; they SHALL be passed as parameters.

#### Scenario: Network access

- **WHEN** code under test opens a TCP connection to 93.184.216.34 port 80 during run_tests
- **THEN** the connection fails and the test output shows an error

#### Scenario: Reading outside the workspace

| Path opened by code under test during run_tests | Result          |
| ----------------------------------------------- | --------------- |
| a file in an extra deny_read directory          | PermissionError |
| AGENTS.md at the fixlab project root            | PermissionError |
| a fake key file in the user's home directory    | PermissionError |
| a listing of ~/.ssh                             | PermissionError |
| .git/HEAD at the fixlab project root            | PermissionError |
| timelog/parser.py inside the workspace          | readable        |
| a package installed in the virtual environment  | importable      |

#### Scenario: Writing outside the workspace

- **WHEN** code under test tries to create a file in the user's home directory during run_tests
- **THEN** the write fails with PermissionError

#### Scenario: Overwriting a test file from code under test

- **WHEN** code under test tries to open tests/test_report.py for writing during run_tests
- **THEN** the write fails with PermissionError and `test_file_tampered` is not set

#### Scenario: Creating a new file in a tests directory

- **WHEN** code under test tries to create tests/new_helper.py for writing during run_tests
- **THEN** the write fails with PermissionError

#### Scenario: Renaming the tests directory

- **WHEN** code under test tries to rename the tests directory to t2 during run_tests
- **THEN** the rename fails with PermissionError and tests/helpers.py is still in place

#### Scenario: Workspace path with regular-expression characters

- **WHEN** the workspace directory is named "a+b(c)" and code under test tries to open tests/test_report.py for writing during run_tests
- **THEN** the write fails with PermissionError

#### Scenario: Workspace inside the project directory

- **WHEN** the workspace is tests/fixtures/timelog inside the fixlab project directory
- **THEN** reads of AGENTS.md at the project root fail with PermissionError, reads of timelog/parser.py succeed, and writing timelog/parser.py succeeds

#### Scenario: Profile has no literal paths

- **WHEN** the sandbox profile text is generated for a workspace
- **THEN** it contains no occurrence of the workspace path, the project path, or the home directory path

### Requirement: Child processes get a minimal environment

run_tests SHALL start pytest with an environment containing only PATH, LANG, LC_ALL, and TMPDIR copied from the parent process when present, plus PYTHONDONTWRITEBYTECODE set to 1. All other variables, including any whose names contain KEY, TOKEN, or SECRET, SHALL NOT be passed. The Python interpreter path SHALL be used as given, without resolving symbolic links, so the virtual environment is found.

#### Scenario: API key in the parent environment

- **WHEN** the parent process has OPENROUTER_API_KEY set to "sk-test-123" and code under test prints os.environ during run_tests
- **THEN** the test output does not contain "sk-test-123" or the name OPENROUTER_API_KEY

#### Scenario: Allowed variables pass through

- **WHEN** the parent process has LANG set to "en_US.UTF-8" and code under test prints os.environ["LANG"]
- **THEN** the test output contains "en_US.UTF-8"
