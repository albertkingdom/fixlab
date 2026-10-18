## ADDED Requirements

### Requirement: A model entry can add text to the system prompt

An entry in the models file SHALL accept an optional key `system_prompt_extra`. When the key is absent or its value is `null`, the runner SHALL NOT pass `--system-prompt-extra`. When the value is a string with at least one non-whitespace character, the runner SHALL pass it to fixlab as `--system-prompt-extra` with exactly that string for every run of that model, in both conditions, so the two conditions still differ only in the visible tools. Loading a models file in which `system_prompt_extra` is present with any other value (a number, a boolean, a list, an empty string or a string of whitespace only) SHALL fail with a configuration error that names the model's label and the value, and no run SHALL start.

#### Scenario: The text is passed in both conditions

- **WHEN** the entry labelled `qwen3.5-9b-rule` has `"system_prompt_extra": "Finish once the fix is made."` and the runner builds the fixlab arguments for the problem `cart` under `with_tests` and under `no_tests`
- **THEN** both argument lists contain `--system-prompt-extra` followed by `Finish once the fix is made.`, and the lists are otherwise identical except for the condition meta and the hidden tool

#### Scenario: A model without the key adds nothing

- **WHEN** an entry has no `system_prompt_extra`, or has it as `null`
- **THEN** the arguments contain no `--system-prompt-extra`

#### Scenario: An invalid value is rejected before any run

- **WHEN** a models file contains an entry labelled `qwen3.5-9b-rule` whose `system_prompt_extra` is one of the values below
- **THEN** loading fails with a configuration error that names `qwen3.5-9b-rule` and the value, and no model request is made

##### Example: values that are not accepted

| `system_prompt_extra` | Result | Notes |
|-----------------------|--------|-------|
| 5 | rejected | number |
| true | rejected | boolean |
| ["a"] | rejected | list |
| "" | rejected | empty string |
| "   " | rejected | whitespace only |
| null | accepted | means no extra text |
| "Finish once the fix is made." | accepted | normal case |
