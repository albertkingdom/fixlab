## Purpose

The experiment runner executes the benchmark for a set of models and conditions and records one result line per run. It exists so that the comparison between "with run_tests" and "without run_tests" is repeatable, and so that no run that costs money starts by accident.

## ADDED Requirements

### Requirement: The plan is shown and nothing runs without confirmation

The `run` command SHALL expand its options into a list of runs, one for each combination of problem, model, condition and repeat number, and SHALL print the plan: the number of runs, the models, the conditions, the repeats and the results file path. Without the confirmation option it SHALL print the plan and exit with code 0 without calling any model. With the confirmation option it SHALL execute the runs one after another.

#### Scenario: Plan only

- **WHEN** `run` is started with 8 problems, 2 models, 2 conditions and 5 repeats and without the confirmation option
- **THEN** it prints `160 runs`, makes no model request, and writes nothing to the results file

### Requirement: Formal runs need the sandbox

With the confirmation option, the `run` command SHALL exit with code 2 before starting any run when the sandbox is not available, because without it the agent's test runs can read the hidden tests. Printing the plan without the confirmation option SHALL work without the sandbox.

#### Scenario: No sandbox

- **WHEN** `run` is started with the confirmation option and the sandbox is not available
- **THEN** it exits with code 2, names the sandbox in its message, and starts no run

### Requirement: The two conditions differ only in the visible tools

The condition `with_tests` SHALL run fixlab without hiding any tool. The condition `no_tests` SHALL run fixlab with `--hide-tool run_tests`. The system prompt, the task text, the model settings and every other option SHALL be identical in the two conditions.

#### Scenario: Arguments of the two conditions

- **WHEN** the runner builds the fixlab arguments for the same problem, model and repeat under both conditions
- **THEN** the two argument lists are identical except that the `no_tests` list contains `--hide-tool run_tests`

### Requirement: Each run uses a fresh copy of the problem

For every run the runner SHALL copy the `project` folder of the problem into a new temporary directory outside the repository, run fixlab on that copy as a one-shot run, grade the copy with the grader, and then delete the temporary directory. The event log of the run SHALL be kept in the log directory given by the options.

#### Scenario: Runs do not affect each other

- **WHEN** the first run of a problem edits a source file
- **THEN** the second run of the same problem starts from the original `project` content

### Requirement: Results are appended one line per run and runs can resume

The runner SHALL append one JSON object per finished run to the results file, with the keys `problem`, `problem_digest`, `model`, `condition`, `repeat`, `grade` (the grader's JSON), `stop_reason`, `steps`, `prompt_tokens`, `completion_tokens`, `seconds`, `claimed_done_but_failed`, `hidden_tool_calls`, `log_path`, `started_at` and `error`. Each run SHALL write its event log into a folder of its own, and the runner SHALL take `stop_reason`, `steps`, the token counts and `seconds` from the `task_end` event of that log and the description in `error` from a `request_error` trace record. `hidden_tool_calls` SHALL be the number of parse errors in the log's `trace` records that name a tool hidden in that run. `claimed_done_but_failed` SHALL be true when `stop_reason` is `done` and the grade's `fixed` is false. When started again with the same results file, the runner SHALL skip every combination of problem, model, condition and repeat that already has a line with a null `error`, and SHALL run again every combination whose latest line has a non-null `error`.

#### Scenario: Resuming an interrupted experiment

- **GIVEN** a results file with lines for 37 of 160 planned runs
- **WHEN** the experiment is started again with confirmation
- **THEN** exactly 123 runs are executed and the file then has 160 lines

#### Scenario: Retrying errors on resume

- **GIVEN** a results file whose line for one combination has a non-null `error`
- **WHEN** the experiment is started again with confirmation
- **THEN** that combination is run again and gets a new line

#### Scenario: Counting calls to a hidden tool

- **WHEN** a `no_tests` run's log has three `trace` records whose parse errors name `run_tests`
- **THEN** its line has `hidden_tool_calls` equal to 3

#### Scenario: Claiming done without fixing

- **WHEN** a run ends with stop reason `done` and the grade has `fixed` false
- **THEN** its line has `claimed_done_but_failed` true

### Requirement: A failed request is recorded as an error, not as unfixed

When a run ends because the model request failed (stop reason `error`), the runner SHALL still grade the working directory, SHALL write the line with `error` set to a short description, and SHALL continue with the next run. The report counts such runs separately from unfixed runs.

#### Scenario: The provider rejects the request

- **WHEN** the model request of a run fails with an error
- **THEN** the results file gets a line for that run with a non-null `error`, and the following runs still execute

### Requirement: The conditions of each run are recorded

The runner SHALL pass these `--meta` values to fixlab for every run so that they appear in the `run_start` event: `problem`, `condition`, `repeat`, `problem_digest`, and every key of the model's `meta` object (for example `quantization`, `runtime`, `context_length`). It SHALL also pass the model's `temperature` and `extra_body` through the matching options.

#### Scenario: Meta of a run

- **WHEN** a run of the problem `billing` in condition `no_tests`, repeat 3, is started for a model whose meta has `quantization` set to `Q4_K_M`
- **THEN** its `run_start` event has `meta` with `problem` `billing`, `condition` `no_tests`, `repeat` `3` and `quantization` `Q4_K_M`

### Requirement: Model settings come from a file and secrets from the environment

The models SHALL be described in a JSON file whose entries have `name`, `label`, `base_url`, `api_key_env` (the name of an environment variable), `temperature`, `extra_body`, `price` (with `input_per_million`, `output_per_million`, `source` and `date`) and `meta`. The file SHALL NOT contain an API key; the runner SHALL read the key from the environment variable named by `api_key_env` and SHALL exit with code 2 before running anything when that variable is not set. For each run the runner SHALL set `OPENAI_BASE_URL` to the model's `base_url` and `OPENAI_API_KEY` to that key for the duration of the run only, and restore the previous values afterwards, so that the `run_start` event records the model's own endpoint.

#### Scenario: Missing key

- **WHEN** a model entry names the variable `OPENROUTER_API_KEY` and that variable is not set
- **THEN** the runner exits with code 2 and no run is started
