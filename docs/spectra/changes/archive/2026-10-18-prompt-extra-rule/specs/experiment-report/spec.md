## ADDED Requirements

### Requirement: The report states the extra system prompt of each model

The experiment settings section of the report SHALL show, on the settings line of each model, the `system_prompt_extra` of that model's entry in the models file: the text as a JSON string on that same line (so a text with line breaks stays on one line and leading or trailing spaces stay visible), or `無` when the entry has none or has it as `null`. As with the other settings, it is read from the models file given to the command and not from the result lines.

#### Scenario: The report shows the extra prompt

- **WHEN** the models file has the entry `a` with `"system_prompt_extra": "Finish once the fix is made."` and the entry `b` without that key, and the results contain lines for both
- **THEN** the settings line of `a` contains `system_prompt_extra "Finish once the fix is made."` and the settings line of `b` contains `system_prompt_extra 無`

#### Scenario: A multi-line extra prompt stays on one line

- **WHEN** the entry `a` has a `system_prompt_extra` made of three lines
- **THEN** the settings line of `a` shows the text with `\n` for each line break, and the fields after it on that line are still on the same line
