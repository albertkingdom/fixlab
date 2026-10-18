## ADDED Requirements

### Requirement: run_start records the request options and hidden tools

The `run_start` event SHALL contain the keys `hidden_tools` (the list of tool names given with `--hide-tool`, empty when none), `temperature` (the number given with `--temperature`, or null) and `extra_body` (the JSON object given with `--extra-body`, or null). The value of `--extra-body` SHALL be a JSON object that is passed unchanged to the model request as extra body parameters; a value that is not valid JSON or not an object SHALL make fixlab exit with code 2 before creating any file. These keys are added to the existing ones, so the schema version stays 1 and readers SHALL ignore keys they do not know.

#### Scenario: Options are recorded

- **WHEN** fixlab is started with `--hide-tool run_tests --temperature 0.2 --extra-body '{"provider": {"order": ["Venice"]}}'`
- **THEN** `run_start` has `hidden_tools` equal to `["run_tests"]`, `temperature` equal to 0.2 and `extra_body` equal to the given object

#### Scenario: Defaults

- **WHEN** fixlab is started without these options
- **THEN** `run_start` has `hidden_tools` equal to `[]`, `temperature` null and `extra_body` null

#### Scenario: Invalid extra body

- **WHEN** fixlab is started with `--extra-body '[1, 2]'`
- **THEN** it exits with code 2 and no event file is created

#### Scenario: Temperature reaches the request

- **WHEN** fixlab is started with `--temperature 0.2`
- **THEN** every model request of the run carries the temperature 0.2
