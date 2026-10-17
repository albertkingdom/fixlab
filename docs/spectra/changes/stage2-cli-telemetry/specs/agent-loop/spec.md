## ADDED Requirements

### Requirement: A run can continue an existing conversation

`run_agent` SHALL accept an optional keyword argument `messages`. When it is None, the run SHALL build its own conversation exactly as before and keep nothing. When it is an empty list, the run SHALL fill that list with the system prompt and the task text as the first user message. When it is a non-empty list, the run SHALL append the task text to that list as a new user message. In the last two cases the run SHALL add every message to the caller's list itself, so the caller keeps the conversation. When the model finishes with a reply that has no tool call (stop reason `done`), the run SHALL also append that reply as an assistant message.

#### Scenario: Default is unchanged

- **WHEN** `run_agent` is called without `messages`
- **THEN** the first request is the system prompt followed by the task text, and the requests recorded in the golden trace are identical to before

#### Scenario: Empty list is filled

- **WHEN** `run_agent` is called with `messages=[]` and the model answers "Done." after reading `rules.py`
- **THEN** the list ends with the assistant message "Done." and starts with the system prompt followed by the task text

#### Scenario: Second task continues

- **WHEN** `run_agent` is called a second time with the same list and the task `add a comment`
- **THEN** the second run's first request contains all messages of the first run, including its final assistant reply, followed by the new user message `add a comment`

### Requirement: Step records show truncation and the original call count

Every trace record for a model reply SHALL contain `truncated` (true when the reply was cut off by the output limit, the same condition that counts `truncated_replies`) and `reply_tool_calls` (the number of native tool calls the reply carried, counting calls that were invalid or dropped).

#### Scenario: Cut-off reply

- **WHEN** the reply has finish reason `length` and one tool call
- **THEN** the record has `"truncated": true` and `"reply_tool_calls": 1`, and no tool is executed

#### Scenario: One valid and one invalid call

- **WHEN** the reply carries a valid `read_file` call and an `edit_file` call without `new_string`
- **THEN** the record has `"reply_tool_calls": 2`, `"truncated": false`, one entry in `tool_calls`, and one entry in `parse_errors`

#### Scenario: Reply without tools

- **WHEN** the model replies "Done." with no tool call
- **THEN** the record has `"reply_tool_calls": 0` and `"truncated": false`

### Requirement: Denied calls count as failures

A tool call with the flag `denied` SHALL be counted in `denied_calls` and SHALL count as a failed call for the consecutive-failure rule, the same as a blocked call. Three rounds in a row in which every executed call failed, including denied ones, SHALL end the run with stop reason `stuck`.

#### Scenario: Three refused edits

- **WHEN** the user denies the model's `edit_file` call in three consecutive rounds
- **THEN** the run ends with stop reason `stuck` after step 3, with `denied_calls` 3 and `stuck_failures` 3

#### Scenario: A refusal followed by a success

- **WHEN** the user denies one `edit_file` call and then the model calls `list_files`, which succeeds
- **THEN** the failure count goes back to zero and the run continues

### Requirement: Protected writes are counted

A tool result with the flag `protected_write` SHALL be counted in `protected_write_calls`, next to `blocked_calls`, so that the counters in `task_end` show how often the model tried to change a read-only file.

#### Scenario: A refused write to a test file

- **WHEN** the model calls `write_file` on `tests/test_report.py` and the Workspace treats test files as read-only
- **THEN** the run's counters contain `"blocked_calls": 1` and `"protected_write_calls": 1`
