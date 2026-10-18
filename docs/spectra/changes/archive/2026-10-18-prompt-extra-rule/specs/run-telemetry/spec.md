## ADDED Requirements

### Requirement: The system prompt can be extended from the command line

`fixlab` SHALL accept the option `--system-prompt-extra TEXT` and SHALL pass TEXT as `system_prompt_extra` to every task of the run, in both one-shot and interactive mode. A TEXT that is empty or contains only whitespace SHALL make fixlab exit with code 2 and a message that names the option, before creating any file. The `run_start` event SHALL contain the key `system_prompt_extra` with exactly the given TEXT, or null when the option is not given. This key is added to the existing ones, so the schema version stays 1 and readers SHALL ignore keys they do not know.

#### Scenario: The option is recorded

- **WHEN** fixlab is started with `--system-prompt-extra "Finish once the fix is made."`
- **THEN** the `run_start` event has `"system_prompt_extra": "Finish once the fix is made."` and the first request's system message ends with that text

#### Scenario: The option is not given

- **WHEN** fixlab is started without `--system-prompt-extra`
- **THEN** the `run_start` event has `"system_prompt_extra": null` and the first request's system message is the default system prompt

#### Scenario: An empty value is refused

- **WHEN** fixlab is started with `--system-prompt-extra` set to one of the values below
- **THEN** it exits with code 2, prints a message that names `--system-prompt-extra`, and creates no event file

##### Example: values that are refused

| TEXT | Result | Notes |
|------|--------|-------|
| "" | refused | empty |
| "   " | refused | spaces only |
| " a " | accepted | has a non-whitespace character |
