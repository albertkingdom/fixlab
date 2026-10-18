## ADDED Requirements

### Requirement: The report states the extra system prompt of each model

The experiment settings section of the report SHALL show, on the settings line of each model, the `system_prompt_extra` of that model's entry in the models file: the text itself, or `無` when the entry has none or has it as `null`. As with the other settings, it is read from the models file given to the command and not from the result lines.

#### Scenario: The report shows the extra prompt

- **WHEN** the models file has the entry `a` with `"system_prompt_extra": "Finish once the fix is made."` and the entry `b` without that key, and the results contain lines for both
- **THEN** the settings line of `a` contains `system_prompt_extra Finish once the fix is made.` and the settings line of `b` contains `system_prompt_extra 無`
