# run-telemetry Specification

## Purpose

Run telemetry writes every fixlab run to a JSON Lines event file: the conditions of the run, every step of the agent loop, and the result of each task. Later stages read these files to compute fix rates, step counts, token use and fake passes without re-running anything.

## Requirements

### Requirement: One event file per run

Each fixlab run SHALL create exactly one new directory `<log-dir>/<UTC start time as %Y%m%dT%H%M%SZ>-<model>/` containing `events.jsonl`. The model name SHALL have every character outside letters, digits, `.`, `_` and `-` replaced by `-`. The default `<log-dir>` SHALL be `~/.fixlab/runs`. The run SHALL NOT overwrite or append to an existing file; if the directory name is taken, the run SHALL append `-2`, `-3`, and so on.

#### Scenario: Default location and name

- **WHEN** `fixlab ./timelog --model qwen/qwen3.5-9b` starts at 2026-10-18 09:30:05 UTC
- **THEN** the run writes `~/.fixlab/runs/20261018T093005Z-qwen-qwen3.5-9b/events.jsonl` and prints `log: ` followed by that path on stderr

#### Scenario: Name already taken

- **WHEN** a second run with the same model starts in the same second as an earlier run
- **THEN** it writes to a directory with the suffix `-2` and the earlier file is unchanged

#### Scenario: Custom log directory

- **WHEN** the run is started with `--log-dir /tmp/exp1`
- **THEN** the event file is created under `/tmp/exp1/` instead of `~/.fixlab/runs`


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

---
### Requirement: Four event types

Every line of `events.jsonl` SHALL be one JSON object with the keys `event` and `ts` (UTC, ISO 8601 with milliseconds and a trailing `Z`). The `event` value SHALL be one of `run_start`, `task_start`, `trace`, `task_end`. The first line SHALL be `run_start`, written once per run, with the keys `schema` (the integer 1), `mode` (`once` or `interactive`), `model`, `base_url`, `path`, `max_steps`, `max_tokens`, `sandbox`, `fixlab_commit` (null when unknown), `python`, `openai` and `meta` (an object). Each task SHALL write `task_start` with `task` (1-based number) and `text`, then one `trace` line per record passed to the trace callback with `task` and `record` (the record unchanged), then `task_end` with `task`, `stop_reason`, `steps`, `counters`, `prompt_tokens`, `completion_tokens`, `seconds`, `final_tests` and `changed_files`. The file SHALL NOT contain cost figures.

#### Scenario: A one-task run

- **WHEN** `fixlab` fixes the timelog project in 8 steps with one `edit_file` call
- **THEN** the file starts with one `run_start` line with `"mode": "once"`, then one `task_start` with `"task": 1`, then one `trace` line per model reply, then one `task_end` with `"stop_reason": "done"` and `"steps": 8`

##### Example: a trace line

- **GIVEN** the loop calls the trace callback with `{"step": 1, "event": "tool_calls", "prompt_tokens": 412, ...}`
- **WHEN** the callback runs
- **THEN** the file gets the line `{"event": "trace", "ts": "2026-10-18T09:30:07.412Z", "task": 1, "record": {"step": 1, "event": "tool_calls", "prompt_tokens": 412, ...}}`

#### Scenario: Request failure is a trace line too

- **WHEN** the loop reports `{"step": 2, "event": "request_error", "error": "..."}` to the trace callback
- **THEN** the file gets a `trace` line with that record, followed by a `task_end` with `"stop_reason": "error"`


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

---
### Requirement: Each line is written immediately

The run SHALL flush every line when it writes it, so that a run that is killed or crashes leaves every earlier line complete and parseable. A killed run SHALL leave the file without a `task_end` line for the unfinished task.

#### Scenario: Reading while the run is still going

- **WHEN** a test writes a `run_start` line and a `task_start` line and then reads the file without closing the log
- **THEN** both lines are present and each parses as JSON


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

---
### Requirement: Experiment conditions come from --meta

`--meta KEY=VALUE` SHALL be accepted any number of times and SHALL be stored in the `meta` object of `run_start` as strings. A `--meta` value without `=` SHALL make fixlab print an error and exit with code 2 before the agent starts.

#### Scenario: Two meta values

- **WHEN** the run starts with `--meta quantization=Q4_K_M --meta context_length=32768`
- **THEN** `run_start` has `"meta": {"quantization": "Q4_K_M", "context_length": "32768"}`

#### Scenario: Missing equals sign

- **WHEN** the run starts with `--meta quantization`
- **THEN** fixlab prints an error naming `--meta`, exits with code 2, and creates no event file


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

---
### Requirement: The event log stays outside the target directory

fixlab SHALL refuse to start, with exit code 2 and a clear message, when the log directory (the default or the value of `--log-dir`) is the target PATH or inside it. The check SHALL compare resolved real paths, so a symbolic link cannot hide the overlap.

#### Scenario: PATH is the home directory

- **WHEN** the run is `fixlab ~` with the default log directory `~/.fixlab/runs`
- **THEN** fixlab exits with code 2 and explains that the log directory is inside the target

#### Scenario: Log directory inside the target

- **WHEN** the run is `fixlab ./timelog --log-dir ./timelog/logs`
- **THEN** fixlab exits with code 2 and writes nothing under `./timelog`

#### Scenario: Snapshot diff is not polluted

- **WHEN** a normal one-shot run finishes with the default log directory
- **THEN** the printed diff lists no file from the log directory


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

---
### Requirement: Logging failures never stop the run

When writing to the event file raises an OS error, fixlab SHALL print one warning on stderr, stop writing further events, and let the agent run finish normally. The run's exit code SHALL be the same as without the failure.

#### Scenario: Unwritable log directory

- **WHEN** `--log-dir` points to a directory the user cannot create files in
- **THEN** fixlab prints one warning that the event log is unavailable, the agent runs to completion, and the exit code is 0 when the final tests pass


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

---
### Requirement: One-shot results go in task_end

For a one-shot run, `task_end` SHALL carry `final_tests` as `{"tests_passed": <bool>, "timed_out": <bool>}` from the final test run, and `changed_files` as `{"added": [...], "modified": [...], "deleted": [...]}` with sorted paths relative to PATH, taken from the same snapshot comparison that produces the printed diff. For an interactive task both fields SHALL be null.

#### Scenario: The model fixed the bug

- **WHEN** a one-shot run edits only `timelog/parser.py` and the final tests pass
- **THEN** `task_end` has `"final_tests": {"tests_passed": true, "timed_out": false}` and `"changed_files": {"added": [], "modified": ["timelog/parser.py"], "deleted": []}`

#### Scenario: Interactive task

- **WHEN** a task finishes in interactive mode
- **THEN** its `task_end` has `"final_tests": null` and `"changed_files": null`

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