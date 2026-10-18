## ADDED Requirements

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
