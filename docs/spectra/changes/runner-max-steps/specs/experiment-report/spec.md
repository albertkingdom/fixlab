## ADDED Requirements

### Requirement: The report states the settings of each model

The report SHALL have an experiment settings section that lists, for each model that appears in the results and in the models file, the model's API name, `temperature`, `extra_body`, `max_steps` and recorded `meta`. `max_steps` SHALL be shown as the number written in the models file, or as `預設` when the entry has no `max_steps` or has it as `null`. These settings SHALL be read from the models file given to the command, not from the result lines, so the section describes the current file and not necessarily the settings under which every old result line was produced.

#### Scenario: The report shows each model's step limit

- **WHEN** the models file has the entry `a` with `"max_steps": 40` and the entry `b` without `max_steps`, and the results contain lines for both
- **THEN** the settings line of `a` contains `max_steps 40` and the settings line of `b` contains `max_steps 預設`

#### Scenario: The settings come from the models file

- **WHEN** the models file is edited to change `max_steps` of `a` from 20 to 40 after some results were written
- **THEN** the report shows `max_steps 40` for `a` for all of its result lines, and the section does not claim to know the limit of each earlier run
