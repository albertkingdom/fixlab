# workspace-isolation Specification

## Purpose

Workspace isolation keeps the agent inside one project directory and makes the project's tests a trustworthy signal. It blocks paths outside the workspace, makes test files unwritable and tamper-evident, and runs the tests in a sandbox with no network, limited file access, and a minimal environment.

## Requirements

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


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
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


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: Tests run in a sandbox

run_tests SHALL run pytest under macOS sandbox-exec with no network access, with reads denied for the user's home directory, the whole project directory of fixlab, and every extra deny_read directory except the workspace itself and the Python virtual environment, and with writes allowed only inside the workspace, a private temporary directory created for that run, and /dev. Every path given to the sandbox SHALL be a real path with symbolic links resolved, because the sandbox compares real paths (on macOS `/var` is a link to `/private/var`). On a platform without sandbox-exec, run_tests SHALL run pytest without a sandbox, and the command-line entry SHALL print a status line saying whether the sandbox is on. A Workspace SHALL have a `protect_tests` option, off by default, because writing tests is a normal task for a general-purpose agent; the command-line entry `fixlab PATH` turns it on together with `looks_like_test_file`. When it is on, the sandbox SHALL deny, inside the workspace, every write (create, overwrite, delete, truncate, rename, move, change of permissions) to a path whose location relative to the workspace root follows the same naming rules as `looks_like_test_file`, compared case-insensitively, and to the directories named `tests` or `test` themselves, so those directories cannot be renamed or moved either. The denial SHALL hold when the write goes through a symbolic link to such a file, and creating a hard link to such a file SHALL fail; a hard link made before the run, outside the sandbox, is not covered. The sandbox SHALL also deny writes to every `__pycache__` directory (pytest loads cached bytecode, so a forged .pyc would replace a test), and SHALL deny deleting, renaming or moving any directory inside the workspace, because renaming a folder that holds tests and copying back a version without them would make the tests disappear from the collection. The price is that code under test cannot remove or rename directories in the workspace. Modification of pytest from inside the pytest process itself, by the code under test, is outside what the sandbox can prevent. The option is independent of the read-only rule: a custom read-only rule is enforced by the tool layer only. Folders above the workspace root that are named `tests` SHALL have no effect. The workspace path in the sandbox's regular-expression rule SHALL be quoted by the sandbox's own `regex-quote` on a parameter, so regular-expression special characters in the path have no effect. The sandbox profile text SHALL contain no literal workspace, project, home, or deny_read paths; they SHALL be passed as parameters.

#### Scenario: Network access

- **WHEN** code under test opens a TCP connection during run_tests to a server that is listening on 127.0.0.1 (so the connection would succeed without the sandbox)
- **THEN** the connection fails with PermissionError

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

- **WHEN** the workspace has `protect_tests` on and code under test tries to open tests/test_report.py for writing during run_tests
- **THEN** the write fails with PermissionError and the file is unchanged

#### Scenario: Creating a new file in a tests directory

- **WHEN** the workspace has `protect_tests` on and code under test tries to create tests/new_helper.py for writing during run_tests
- **THEN** the write fails with PermissionError and the file does not exist

#### Scenario: Renaming the tests directory

- **WHEN** the workspace has `protect_tests` on and code under test tries to rename the tests directory to t2 during run_tests
- **THEN** the rename fails with PermissionError, tests/helpers.py is still in place and t2 does not exist

#### Scenario: Other ways to change a test file

The workspace has `protect_tests` on and contains tests/test_report.py, tests/helpers.py and timelog/parser.py. Each row is tried in a fresh workspace.

| Action by code under test during run_tests                        | Result          |
| ----------------------------------------------------------------- | --------------- |
| delete tests/helpers.py                                           | PermissionError |
| create a folder tests/sub                                         | PermissionError |
| truncate tests/test_report.py                                     | PermissionError |
| change the permissions of tests/test_report.py                    | PermissionError |
| create test_x.py, TEST_Y.PY, foo_test.py or conftest.py           | PermissionError |
| create timelog/test_inner.py                                      | PermissionError |
| rename tests/test_report.py to plain.txt                          | PermissionError |
| rename timelog/parser.py to test_p.py                             | PermissionError |
| create a symbolic link to the test file, then write through it    | PermissionError |
| create a hard link to the test file, then write through it        | PermissionError |
| append to timelog/parser.py                                       | succeeds        |
| create tests.py or contest.py                                     | succeeds        |
| rename the folder timelog to timelog2                             | PermissionError |
| create and then remove an empty folder                            | PermissionError |
| write a file inside a `__pycache__` folder                        | PermissionError |

#### Scenario: Sandbox and tool layer agree

- **WHEN** a path relative to the workspace is tried for writing in a workspace with `protect_tests` on, for each of tests/a.py, test/a.py, Tests/a.py, pkg/tests/data.json, a/b/test_c.py, x_test.py, X_TEST.PY, conftest.py, pkg/conftest.py, tests.py, contest.py, testing/a.py, pkg/attests/a.py, latest.py, timelog/parser.py, notes/test.txt and notes/test_notes.txt
- **THEN** the sandbox denies the write exactly when `looks_like_test_file` marks the path; the paths foo_testxpy and conftestxpy (no real dot) are not denied. The sandbox is deliberately a little stricter in three places: a file or folder named test or tests (a regular expression cannot tell a file from a folder), the creation of a folder whose name starts with test_ (an existing one stays writable), and anything under `__pycache__`

#### Scenario: Test protection is off by default

- **WHEN** a Workspace is created without `protect_tests` and code under test creates tests/new_test.py during run_tests
- **THEN** the file is created

#### Scenario: A folder named tests above the workspace

- **WHEN** the workspace is .../tests/fixtures/x with `protect_tests` on, and code under test appends to timelog/parser.py
- **THEN** the write succeeds, while appending to tests/test_report.py still fails with PermissionError

#### Scenario: A source edit that rewrites the tests cannot fake a pass

- **WHEN** `fixlab PATH` runs and the model inserts into timelog/parser.py code that rewrites tests/test_report.py to `assert True`, then the tests run
- **THEN** tests/test_report.py is unchanged and the result line says tests FAILED

#### Scenario: Hiding tests by renaming a parent folder

- **WHEN** the workspace has `protect_tests` on, a failing tests lives in timelog/test_inner.py, and code under test renames timelog to .old and copies it back without the test_ files
- **THEN** the rename fails with PermissionError and the next run_tests still reports the failure

#### Scenario: Forged bytecode

- **WHEN** the workspace has `protect_tests` on, timelog/formatting_test.py has a failing test, and code under test writes a bytecode file for it into timelog/__pycache__ that holds a passing version
- **THEN** the write fails with PermissionError and the next run_tests still reports `1 failed`

#### Scenario: Workspace path with regular-expression characters

- **WHEN** the workspace has `protect_tests` on, its directory is named "a+b(c)", and code under test tries to open tests/test_report.py for writing during run_tests
- **THEN** the write fails with PermissionError, while appending to timelog/parser.py succeeds

#### Scenario: Workspace inside the project directory

- **WHEN** the workspace is a folder inside the fixlab project directory (the tests use a temporary one, so the real fixture is never written)
- **THEN** reads of AGENTS.md at the project root fail with PermissionError, reads of timelog/parser.py succeed, and writing timelog/parser.py succeeds
- **WHEN** run_tests runs in place on tests/fixtures/timelog, which only reads
- **THEN** the output contains no PermissionError and ends with `1 failed, 4 passed`

#### Scenario: Workspace given as a symbolic link

- **WHEN** the Workspace is created from a path that is a symbolic link to the real directory
- **THEN** code under test can still write a file inside the workspace

#### Scenario: Workspace inside the home directory

- **WHEN** the workspace is a directory under the user's home directory
- **THEN** reads and writes inside the workspace succeed, while writing elsewhere in the home directory fails with PermissionError

#### Scenario: Temporary files stay out of the workspace

- **WHEN** a test uses pytest's tmp_path during run_tests
- **THEN** the temporary directory is outside the workspace, no new file or directory appears in the workspace, and the temporary directory is gone after the run

#### Scenario: No sandbox available

- **WHEN** sandbox-exec is not available
- **THEN** run_tests still runs the tests, and the status line reports that the sandbox is off

#### Scenario: Interpreter that fails to start

- **WHEN** the Python interpreter exits with an error before running any test
- **THEN** `tests_passed` is false

#### Scenario: Profile has no literal paths

- **WHEN** the sandbox profile text is generated for a workspace
- **THEN** it contains no occurrence of the workspace path, the project path, or the home directory path


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: Child processes get a minimal environment

run_tests SHALL start pytest with an environment containing only PATH, LANG, and LC_ALL copied from the parent process when present, TMPDIR set to a private temporary directory created for that run and deleted afterwards, and PYTHONDONTWRITEBYTECODE set to 1. All other variables, including any whose names contain KEY, TOKEN, or SECRET, SHALL NOT be passed. The Python interpreter path SHALL be used as given, without resolving symbolic links, so the virtual environment is found.

#### Scenario: API key in the parent environment

- **WHEN** the parent process has OPENROUTER_API_KEY set to "sk-test-123" and code under test prints os.environ during run_tests
- **THEN** the test output does not contain "sk-test-123" or the name OPENROUTER_API_KEY

#### Scenario: Allowed variables pass through

- **WHEN** the parent process has LANG set to "en_US.UTF-8" and code under test prints os.environ["LANG"]
- **THEN** the test output contains "en_US.UTF-8"

<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: Writes to read-only files are flagged

When a write is refused because the file is read-only, the result SHALL carry the flag `protected_write` in addition to `blocked`. Refusals for other reasons (a path outside the working directory, an absolute path, a symbolic link pointing outside) SHALL carry `blocked` only.

#### Scenario: Editing a test file

- **WHEN** a Workspace created with `read_only=looks_like_test_file` is asked to run `edit_file` on `tests/test_report.py`
- **THEN** the result has `ok=false` and flags `{"blocked": true, "protected_write": true}`

#### Scenario: Writing a new test file

- **WHEN** the model calls `write_file` with the path `tests/new_helper.py` in the same Workspace
- **THEN** the result has flags `{"blocked": true, "protected_write": true}` and the file is not created

#### Scenario: Path escape

- **WHEN** the model calls `edit_file` with the path `../outside.py`
- **THEN** the result has flags `{"blocked": true}` and no `protected_write` flag

<!-- @trace
source: stage2-cli-telemetry
updated: 2026-10-18
code:
  - docs/articles/images/12-event-log-where-trace.drawio.png
  - fixlab/loop.py
  - README.md
  - docs/articles/images/14-workspace-call.drawio.png
  - docs/articles/14-permissions.md
  - AGENTS.md
  - fixlab/tools.py
  - tests/golden/trace_golden.json
  - fixlab/telemetry.py
  - fixlab/cli.py
  - docs/articles/images/12-event-log-lines.drawio.png
  - docs/articles/12-event-log.md
  - docs/articles/images/14-who-decides.drawio.png
  - docs/articles/images/12-event-log-where-task_end.drawio.png
  - docs/articles/13-interactive-session.md
  - docs/articles/11-loop-safeguards.md
  - fixlab/display.py
  - docs/articles/images/12-event-log-where-run_start.drawio.png
  - docs/articles/images/12-event-log-trace-line.drawio.png
  - fixlab/workspace.py
tests:
  - tests/test_display.py
  - tests/test_interactive.py
  - tests/test_loop.py
  - tests/test_telemetry.py
  - tests/test_isolation.py
  - tests/test_cli.py
  - tests/test_trace_golden.py
-->