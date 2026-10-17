# agent-loop Specification

## Purpose

The agent loop lets the language model decide which tool to call next and when the task is finished. The program only enforces safety nets (a step budget and a consecutive-failure limit) and turns every failure into recorded feedback instead of a crash.

## Requirements

### Requirement: Task text is the first user message

The loop SHALL start the conversation with a system prompt and one user message whose content is exactly the task text passed by the caller. The loop SHALL NOT inject any file content or problem statement of its own.

#### Scenario: Caller passes a task

- **WHEN** run_agent is called with the task text "The tests under tests/ fail. Find the cause and fix it."
- **THEN** the first request sends two messages, a system message and a user message whose content equals that task text


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
### Requirement: Model decides the next step and when to stop

The loop SHALL send the conversation and the tool list to the model, execute the tool calls the model returns, append the results to the conversation, and repeat. The loop SHALL end with stop reason `done` when a model reply contains no tool call and no parse error. The program SHALL NOT decide the order of tool calls.

#### Scenario: Read, edit, test, then finish

- **WHEN** the model replies with read_file for rules.py, then edit_file on rules.py, then run_tests, then a text reply "Fixed." with no tool call
- **THEN** the loop stops after 4 steps with stop reason `done`, and the fourth request's conversation contains the run_tests result


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
### Requirement: Step budget is a safety net

The loop SHALL count one step per model call and SHALL stop with stop reason `max_steps` after the configured maximum even if the model keeps calling tools. The default maximum SHALL be 20.

#### Scenario: Model never stops

- **WHEN** the model calls run_tests on every reply and max_steps is 3
- **THEN** the loop stops after exactly 3 model calls with stop reason `max_steps`

#### Scenario: Default budget

- **WHEN** run_agent is called without max_steps and the model calls list_files on every reply
- **THEN** the loop stops after exactly 20 model calls with stop reason `max_steps`


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
### Requirement: Consecutive failing rounds stop the loop

The loop SHALL count a round as failing only when at least one tool call was executed in that round and every executed tool call returned ok=false (a call rejected as blocked counts as ok=false). A round in which at least one executed tool call returned ok=true SHALL reset the counter to 0. A round in which no tool call was executed (invalid reply, empty reply, truncated reply) SHALL neither increment nor reset the counter. When the counter reaches 3 the loop SHALL stop with stop reason `stuck` and SHALL record `stuck_failures` equal to 3 in the counters. A run_tests call whose tests fail SHALL still count as ok=true.

#### Scenario: Three failing rounds in a row

- **WHEN** the model calls read_file on a missing file "nope.py" in three consecutive replies
- **THEN** the loop stops after 3 steps with stop reason `stuck`

#### Scenario: A success resets the counter

- **WHEN** the replies are a failing read_file, a successful list_files, a failing read_file, a failing read_file, and then a text reply "Done."
- **THEN** the loop does not stop with `stuck` and ends with stop reason `done`

#### Scenario: Mixed round counts as success

- **WHEN** a single reply contains one failing read_file call and one successful list_files call
- **THEN** the failure counter stays at 0

#### Scenario: Invalid reply between failures

- **WHEN** the replies are a failing read_file, an invalid reply with a parse error, a failing read_file, and a failing read_file
- **THEN** the invalid reply neither resets nor increments the counter, and the loop stops with `stuck` after the fourth reply

#### Scenario: Blocked calls count as failures

- **WHEN** the model calls write_file on "tests/test_report.py" in three consecutive replies
- **THEN** every call is blocked with ok=false and the loop stops with `stuck` after 3 steps

#### Scenario: Failing tests are not tool failures

- **WHEN** the model calls run_tests in three consecutive replies and the tests fail every time
- **THEN** `stuck_failures` is absent and the loop continues until another stop condition


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
### Requirement: Invalid replies become feedback, not completion

When a reply contains no valid tool call but has parse errors, the loop SHALL append the assistant text and a user message describing the errors, record event `invalid_tool_call`, and continue within the step budget. When a reply has no tool call, no text, and no error, the loop SHALL treat it as an empty response error instead of completion. When a reply is cut off by the output limit, the loop SHALL discard any tool call in it and tell the model that the reply was cut off.

#### Scenario: Missing required argument

- **WHEN** the model calls edit_file with only `path`
- **THEN** no file is changed, the next request contains a user message with the word "invalid", and `parse_errors` is 1

#### Scenario: Empty reply

- **WHEN** the model returns empty content and no tool calls
- **THEN** the loop does not stop, `empty_responses` is 1, `parse_errors` is 1, and the model is asked again
- **AND** the next request contains a user message saying the reply was empty and that the model may either give a short final message or call a tool, because an empty reply often comes from a model that has finished and only lacks a closing message

#### Scenario: Truncated reply

- **WHEN** the reply's finish reason is `length`
- **THEN** the tool call in that reply is not executed, the next request tells the model its reply was "cut off", and `truncated_replies` is 1


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
### Requirement: All native calls in one reply are executed

When a reply contains more than one valid native tool call, the loop SHALL execute all of them in the order given and append one tool result per call before asking the model again. The whole reply counts as one step.

#### Scenario: Two reads in one reply

- **WHEN** the reply has a native read_file call on "timelog/parser.py" and a native read_file call on "timelog/report.py"
- **THEN** both files are read in that order, the next request contains two tool results, and the reply counts as one step (`steps` is 2 once the model has answered with "Done.")


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
### Requirement: Transient provider errors are retried, timeouts are not

The loop SHALL retry a model request after HTTP 429, HTTP 5xx, or connection errors, waiting the delays in the module-level constant RETRY_DELAYS_S between attempts. The loop SHALL NOT retry request timeouts. A request that still fails SHALL end the run with stop reason `error` and count `request_errors`, never raise.

#### Scenario: Timeout is not retried

- **WHEN** the request raises openai.APITimeoutError
- **THEN** there is no retry, the run ends with stop reason `error`, and `request_errors` is 1

#### Scenario: One rate limit then success

- **WHEN** the first request raises a 429 error and the second succeeds with "Done."
- **THEN** the run ends with stop reason `done`, `rate_limit_retries` is 1, and `request_errors` is absent


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
### Requirement: Every step is traced

The loop SHALL call the trace callback once per answered model call with event `tool_calls`, `invalid_tool_call`, or `done`, containing the step number, latency, finish reason, token counts, reply text, parse errors, and for each executed tool call its name, arguments, ok flag, flags, and output. Arguments and outputs longer than 2000 characters SHALL be truncated in the record.

#### Scenario: Trace for a tool step

- **WHEN** the model calls read_file on rules.py
- **THEN** the trace record has event `tool_calls` and one tool call entry with name `read_file` and the numbered file content as output

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