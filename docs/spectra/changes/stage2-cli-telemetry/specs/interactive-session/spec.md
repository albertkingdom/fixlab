## Purpose

Interactive mode lets a user give fixlab several instructions in a row on the same project. The conversation is kept for the whole session, so a later instruction can refer to what an earlier one did.

## ADDED Requirements

### Requirement: Interactive mode is entered with -i

`fixlab PATH -i` SHALL start interactive mode: it SHALL print the prompt `fixlab> ` and read one line at a time. Without `-i`, fixlab SHALL behave exactly as the one-shot command. Interactive mode SHALL use the same checks as one-shot mode (PATH must be a directory, an API key and a model must be set) and exit with code 2 when they fail.

#### Scenario: Without -i nothing changes

- **WHEN** the user runs `fixlab ./timelog` with a fake client that answers "Done."
- **THEN** fixlab does not print `fixlab> `, runs one task with the default task text, and ends with a `RESULT:` line

#### Scenario: Missing model

- **WHEN** the user runs `fixlab ./timelog -i` with no `--model` and no `FIXLAB_MODEL`
- **THEN** fixlab prints an error about the missing model and exits with code 2 without showing the prompt

### Requirement: The conversation is kept for the session

Within one interactive session, each line the user types SHALL run as a new task whose request to the model contains the system prompt and every message of the earlier tasks in the session, followed by the new line as a user message. The first request of a session SHALL still be the system prompt followed by the first line as the user message. Nothing SHALL be saved after the session ends.

#### Scenario: A follow-up refers to earlier work

- **WHEN** the user types `fix the failing test` and, after the model answers "Fixed parse_duration.", types `add a docstring to that function`
- **THEN** the second task's first request contains the first task's messages, including the model's answer "Fixed parse_duration.", and ends with the user message `add a docstring to that function`

##### Example: message order in the second task's first request

| Position | Role | Content |
|----------|------|---------|
| 1 | system | the system prompt |
| 2 | user | fix the failing test |
| 3 | assistant | Fixed parse_duration. |
| 4 | user | add a docstring to that function |

#### Scenario: A new session starts empty

- **WHEN** the user leaves with `/exit` and starts `fixlab ./timelog -i` again
- **THEN** the first request contains only the system prompt and the first line the user types

### Requirement: Slash commands and empty lines

In interactive mode a line that is empty or only spaces SHALL be ignored. `/exit`, end of input (Ctrl-D) and Ctrl-C at the prompt SHALL end the session with exit code 0. `/reset` SHALL discard the conversation, print `conversation cleared`, and make the next line start a conversation like the first one of a session; task numbers in the event file SHALL keep counting up. Any other line SHALL be a task, including lines that start with `/` but are not a known command.

#### Scenario: Reset

- **WHEN** the user types a task, then `/reset`, then a second task
- **THEN** the second task's first request contains only the system prompt and the second line, and its `task_start` event has `"task": 2`

#### Scenario: Empty line

- **WHEN** the user presses Enter on an empty prompt
- **THEN** no request is sent to the model and the prompt is shown again

### Requirement: Interrupting a task keeps what was completed

When the user presses Ctrl-C while a task is running, the session SHALL keep every message the task already added to the conversation, then append the assistant message `[The user interrupted this task.]`, print `interrupted; what was done so far is kept (files may already have been changed; use /reset to start over)`, write a `task_end` event with `stop_reason` `interrupted` for that task (`steps`, `counters`, `prompt_tokens` and `completion_tokens` are null because the run did not return them; `seconds` is measured), and show the prompt again. After an interrupt every assistant tool call in the conversation SHALL have a matching tool result, so the next request is valid and the model knows what happened.

#### Scenario: Interrupted at a permission question

- **WHEN** the model calls `read_file` and `edit_file` in one reply, and the user presses Ctrl-C at the question about `edit_file`
- **THEN** the conversation keeps the reply and the result of `read_file`, gets an error result for `edit_file` saying the user interrupted and its state is unknown, and ends with `[The user interrupted this task.]`; the file is unchanged

#### Scenario: The next task sees the interrupted one

- **WHEN** a task is interrupted and the user then types `try again`
- **THEN** the next request contains the interrupted task's messages, including the interrupt note, followed by the user message `try again`

#### Scenario: Interrupted while waiting for the model

- **WHEN** the user presses Ctrl-C during the first request of a task, before any reply arrived
- **THEN** the conversation holds the user's task text followed by `[The user interrupted this task.]`, and the next task's request is well formed

### Requirement: No automatic final test run in interactive mode

Interactive mode SHALL NOT run the project's tests after a task on its own. The user can ask the model to run them.

#### Scenario: A task ends

- **WHEN** a task finishes with stop reason `done`
- **THEN** fixlab prints the footer line for the task and returns to the prompt, and no `RESULT:` line is printed

### Requirement: The model's final reply is shown

When a task ends with stop reason `done`, interactive mode SHALL print the model's final message on standard output, with a blank line before and after it and the footer line below, because that message is the answer the user asked for. Blank lines at the start and the end of the message itself SHALL NOT be printed, so exactly one blank line separates it from what is above. For other stop reasons there is no final message to print.

#### Scenario: A task finishes

- **WHEN** the model ends a task with the reply "Fixed parse_duration."
- **THEN** standard output contains `Fixed parse_duration.` followed by the footer line

#### Scenario: A reply that starts with blank lines

- **WHEN** the model ends a task with the reply "\n\nFixed parse_duration."
- **THEN** the answer is printed as `Fixed parse_duration.` with a single blank line before it

### Requirement: A task that fails with a request error keeps what it already did

When a task ends with stop reason `error` before the model gave any reply, the session SHALL restore the conversation to its length before the task started and print `this task was discarded because the request failed`, so that the next task does not follow a user message that never got a reply. When the task had already completed at least one step, the session SHALL keep its messages, append the assistant message `[The task stopped because the request failed.]`, and print `the request failed; what was done so far is kept (files may already have been changed; use /reset to start over)`, because the files the task changed stay on disk and the next task's model has to know about them. Tasks that end with `max_steps` or `stuck` SHALL keep their messages, because the conversation is still well formed and the user can ask the model to continue.

#### Scenario: A request fails after an earlier task succeeded

- **WHEN** the user types `fix it` and gets the reply "Done.", then types `add a comment` and the request fails, then types `add a docstring`
- **THEN** the third task's first request contains the messages of the first task and the line `add a docstring`, and nothing from the failed task

#### Scenario: A request fails after the task already changed something

- **WHEN** the model edits a file, the next request fails, and the user then types `add a docstring`
- **THEN** the next task's first request contains the user message, the edit and its result, the message `[The task stopped because the request failed.]`, and `add a docstring`; the screen shows `the request failed; what was done so far is kept`

#### Scenario: A task runs out of steps

- **WHEN** a task ends with stop reason `max_steps` after one tool call and the user types a second line
- **THEN** the second task's first request contains the first task's messages, including the tool call and its result

### Requirement: Tool calls are shown as readable blocks

In interactive mode every tool call SHALL be shown on standard output as a block, in the order the calls run. The block starts with a header line `  ▸ <tool> <what it touches>`: for `read_file` the path (and the line range when one is given), for `list_files` the path (`.` when none), for `grep` the pattern and the path, for `edit_file` the path, for `write_file` the path and the number of characters, for `run_tests` the target (`.` when none). For `edit_file` the header is followed by the difference between the whole file before and after the edit, shown as changed regions: each region starts with a line `    @@ line N` (N is the first line shown, counted in the file before the edit) and shows 3 unchanged lines before and after each change. Unchanged lines and removed lines start with their line number in the file before the edit; removed lines have `-` after the number, added lines have `+` and no number, and unchanged lines have neither. Within one region, each run of removed lines and each run of added lines shows at most 10 lines, each cut to 200 characters, followed by a line `… N more lines` when lines were left out. At most 8 regions are shown, followed by `    … N more changes` when there are more. Changes that are close enough to share their context are one region. When the edit cannot be applied (the pre-check refuses it), no difference is shown and the block ends with the `✗` line. When the user is asked, the question follows. The block ends with a result line starting with `    ✓` or `    ✗`: `✓` when the call succeeded (for `run_tests` with the test summary, for example `✓ 5 passed in 0.01s`), `✗ 1 failed, 4 passed in 0.01s` when tests ran and failed, `✗ declined` when the user refused, `✗ blocked: <reason>` when a rule blocked it, and `✗ <reason>` for any other error. A blank line SHALL separate the typed task from the first block. The per-call lines SHALL NOT go to standard error in interactive mode.

#### Scenario: A read followed by a confirmed edit

- **WHEN** the model reads `timelog/parser.py`, then edits it, and the user answers `y`
- **THEN** standard output shows, in this order, `▸ read_file timelog/parser.py`, `✓`, `▸ edit_file timelog/parser.py`, one `-` line, one `+` line, the question, and `✓`

#### Scenario: A refused call

- **WHEN** the user answers `n` to a `run_tests` question
- **THEN** the block for that call ends with `✗ declined`

#### Scenario: Failing tests

- **WHEN** `run_tests` runs and one test fails
- **THEN** the block ends with a `✗` line showing the pytest summary, such as `1 failed, 4 passed in 0.01s`, although the tool call itself succeeded

#### Scenario: A long edit

- **WHEN** the model replaces a 25-line text with a 12-line text
- **THEN** the block shows 10 `-` lines followed by `… 15 more lines`, and 10 `+` lines followed by `… 2 more lines`

#### Scenario: Context around a change

- **WHEN** the model changes line 8 of a 20-line file
- **THEN** the block shows `@@ line 5`, lines 5 to 7 as unchanged lines, line 8 as a `-` line, the new text as a `+` line, and lines 9 to 11 as unchanged lines

#### Scenario: A change that a long edit would hide

- **WHEN** one `edit_file` replaces a one-line docstring with a 15-line docstring and also changes a line four lines further down
- **THEN** the block shows the first 10 added lines of the docstring, `… 5 more lines`, and then the second change as its own `-` and `+` lines

#### Scenario: An edit that cannot be applied

- **WHEN** the model calls `edit_file` with an `old_string` that does not occur in the file
- **THEN** no `-` or `+` line is shown, no question is asked, and the block ends with a `✗` line

### Requirement: Each task ends with a footer line

After a task, interactive mode SHALL print one footer line in parentheses: `(<N> steps · <P> + <C> tokens · <S> s)` with thousands separators in the token counts, `1 step` in the singular, and `S` the elapsed seconds rounded to a whole number. When the task did not end with stop reason `done`, the line SHALL start with `(stopped: <reason> · `. The old line `stop reason: ...` SHALL NOT be printed in interactive mode.

#### Scenario: Three steps

- **WHEN** a task ends with stop reason `done` after 3 steps, 11766 prompt tokens, 677 completion tokens and 18.4 seconds
- **THEN** the footer is `(3 steps · 11,766 + 677 tokens · 18 s)`

#### Scenario: Stuck

- **WHEN** a task ends with stop reason `stuck` after 3 steps
- **THEN** the footer starts with `(stopped: stuck · 3 steps`

### Requirement: Colors only on a terminal

Interactive mode SHALL color the output (green for `✓` and `+` lines, red for `✗` and `-` lines, dim for the footer) only when standard output is a terminal and the environment variable `NO_COLOR` is not set. Otherwise the output SHALL contain no escape codes.

#### Scenario: Output is captured

- **WHEN** standard output is not a terminal
- **THEN** the output contains no escape sequences

#### Scenario: NO_COLOR on a terminal

- **WHEN** standard output is a terminal and `NO_COLOR` is set
- **THEN** the output contains no escape sequences

