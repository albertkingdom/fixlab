## ADDED Requirements

### Requirement: A model entry can set the step limit of its runs

An entry in the models file SHALL accept an optional key `max_steps`. When the key is present, its value SHALL be an integer of at least 1, and the runner SHALL pass it to fixlab as `--max-steps` with that value for every run of that model, in both conditions. When the key is absent or its value is `null`, the runner SHALL NOT pass `--max-steps`, so fixlab uses its own default step limit and the arguments are the same as before this key existed; this matches how `temperature` and `extra_body` treat `null`. Loading a models file in which `max_steps` is present with a value other than `null` but is not an integer of at least 1 (zero, a negative number, a decimal, a string or a boolean) SHALL fail with a configuration error that names the model's label and the value, and no run SHALL start.

#### Scenario: A model sets a larger step limit

- **WHEN** the entry labelled `qwen3.5-9b` has `"max_steps": 40` and the runner builds the fixlab arguments for the problem `cart`, condition `no_tests`, repeat 1
- **THEN** the arguments contain `--max-steps` followed by `40`, and the `run_start` event of that run records `max_steps` as 40

#### Scenario: The limit is the same in both conditions

- **WHEN** the runner builds the fixlab arguments for the same model, problem and repeat under `with_tests` and under `no_tests`, and the entry has `"max_steps": 40`
- **THEN** both argument lists contain `--max-steps` followed by `40`

#### Scenario: A model without the key keeps the default

- **WHEN** an entry has no `max_steps` key
- **THEN** the arguments contain no `--max-steps`, and the `run_start` event records the fixlab default of 20

#### Scenario: An explicit null means no step limit

- **WHEN** an entry has `"max_steps": null`
- **THEN** the entry loads without error, the arguments contain no `--max-steps`, and the run uses the fixlab default

#### Scenario: An invalid value is rejected before any run

- **WHEN** a models file contains an entry labelled `qwen3.5-9b` whose `max_steps` is one of the values below
- **THEN** loading fails with a configuration error that names `qwen3.5-9b` and the value, and no model request is made

##### Example: values that are not integers of at least 1

| `max_steps` | Result | Notes |
|-------------|--------|-------|
| 0 | rejected | below the minimum of 1 |
| -5 | rejected | negative |
| 2.5 | rejected | decimal |
| "40" | rejected | string, not a number |
| true | rejected | boolean, even though it counts as 1 in Python |
| 1 | accepted | the minimum |
| 40 | accepted | typical larger limit |
