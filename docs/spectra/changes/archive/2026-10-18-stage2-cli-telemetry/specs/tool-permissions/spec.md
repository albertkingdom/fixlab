## Purpose

Tool permissions let the entry point decide whether a tool call needs the user's approval before it runs. One-shot runs have nobody to ask and keep running unattended; interactive sessions ask before changing files or running code.

## ADDED Requirements

### Requirement: A Workspace can require confirmation

`Workspace` SHALL accept an optional `confirm` function taking the tool name and the arguments and returning a bool. The default SHALL approve every call. A call SHALL be confirmed after the tool exists, its arguments pass validation and its pre-check passes, and before the tool runs. `edit_file`, `write_file` and `run_tests` SHALL have a pre-check that refuses the call, without changing anything, for every reason the tool itself would refuse it before acting (an empty path, a path outside the working directory, a read-only file, a missing file, an `old_string` that does not occur exactly once or equals `new_string`, an existing file that was not read first), with the same error the tool would give. When `confirm` returns False, the tool SHALL NOT run, and the result SHALL be `ok=false` with the flag `denied` and an output that tells the model the user declined and that it must not retry the same call.

#### Scenario: Default approves

- **WHEN** a Workspace is created without `confirm` and the model calls `edit_file` on `timelog/parser.py`
- **THEN** the edit is applied with no question asked

#### Scenario: Denied call does nothing

- **WHEN** `confirm` returns False for `edit_file` on `timelog/parser.py`
- **THEN** the file is unchanged, the result has `ok=false` and flags `{"denied": true}`, and the output starts with `error: the user declined this call`

#### Scenario: Invalid calls are not asked about

- **WHEN** the model calls `edit_file` without `new_string`, or calls an unknown tool `bash`
- **THEN** `confirm` is not called and the result is the usual validation error

#### Scenario: Calls the tool would refuse are not asked about

- **WHEN** the model calls `run_tests` with `target` set to an empty string, or `edit_file` with an `old_string` that does not occur in the file, or `edit_file` with identical `old_string` and `new_string`
- **THEN** `confirm` is not called, the file is unchanged, and the result is the same error the tool gives

#### Scenario: A read-only file is not asked about

- **WHEN** the model calls `edit_file` on a read-only file
- **THEN** `confirm` is not called and the result is blocked with the flag `protected_write`

### Requirement: Interactive mode asks before changing files or running tests

In interactive mode the confirm function SHALL ask only for `edit_file`, `write_file` and `run_tests`; `read_file`, `list_files` and `grep` SHALL run without a question. The question SHALL be `Allow? [y]es / [a]lways for this tool / [N]o: `, printed after the block that shows what the call will do (the header line and, for `edit_file`, the changed regions; see the requirement about tool call blocks in interactive-session).

#### Scenario: Reading is not asked

- **WHEN** the model calls `read_file` on `timelog/report.py` in interactive mode
- **THEN** no question is shown

##### Example: answers

| Answer typed | Result |
|--------------|--------|
| `y`, `yes` | this call runs |
| `a`, `always` | this call runs, and later calls to the same tool in this session run without a question |
| `n`, `no` | the call is denied |
| (empty line) | the call is denied |
| `yes please` | the call is denied |
| end of input | the call is denied |

#### Scenario: Always applies per tool

- **WHEN** the user answers `a` to an `edit_file` question and the model later calls `edit_file` again and then `write_file`
- **THEN** the second `edit_file` runs without a question and `write_file` still asks

#### Scenario: Long strings are cut

- **WHEN** the model calls `edit_file` with an `old_string` of 500 characters on one line
- **THEN** the removed line shows only the first 200 characters of it

### Requirement: One-shot mode never asks

`fixlab PATH` without `-i` SHALL NOT pass a confirm function, so no tool call is ever denied by a prompt and the command works unattended.

#### Scenario: Unattended run

- **WHEN** a one-shot run is started with standard input closed
- **THEN** every tool call runs as before and no call has the flag `denied`
