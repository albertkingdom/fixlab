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

### Requirement: Interrupting a task discards its messages

When the user presses Ctrl-C while a task is running, the session SHALL restore the conversation to its length before the task started, print `interrupted; this task was discarded; files may already have been changed (use /reset to start over)`, write a `task_end` event with `stop_reason` `interrupted` for that task, and show the prompt again. The next task's request SHALL NOT contain an assistant tool call without its matching tool result.

#### Scenario: Interrupted between a tool call and its result

- **WHEN** the fake client raises `KeyboardInterrupt` on the second request of a task, after the first request's tool call was already added to the conversation
- **THEN** the session's messages have the same length as before the task, the message is printed, and the next task's request contains no assistant message with `tool_calls`

### Requirement: No automatic final test run in interactive mode

Interactive mode SHALL NOT run the project's tests after a task on its own. The user can ask the model to run them.

#### Scenario: A task ends

- **WHEN** a task finishes with stop reason `done`
- **THEN** fixlab prints the stop reason, steps and tokens for the task and returns to the prompt, and no `RESULT:` line is printed

### Requirement: The model's final reply is shown

When a task ends with stop reason `done`, interactive mode SHALL print the model's final message on standard output before the summary line, because that message is the answer the user asked for. For other stop reasons there is no final message to print.

#### Scenario: A task finishes

- **WHEN** the model ends a task with the reply "Fixed parse_duration."
- **THEN** standard output contains `Fixed parse_duration.` followed by the line starting with `stop reason: done`

