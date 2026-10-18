## ADDED Requirements

### Requirement: The system prompt can carry extra text

`run_agent` SHALL accept an optional keyword argument `system_prompt_extra` whose default is None. When the run puts the system prompt into the conversation (the run builds its own conversation, or the list passed as `messages` is empty), the content of the system message SHALL be the default system prompt when the argument is None, and otherwise the default system prompt, then one blank line, then the argument. When the caller passes a `messages` list that already has content, the argument SHALL have no effect, because the system prompt is already in that conversation. The text of the default system prompt SHALL NOT change.

#### Scenario: Extra text is appended after a blank line

- **WHEN** `run_agent` is called without `messages` and with `system_prompt_extra` set to `Finish with a short message once the fix is made.`
- **THEN** the first request starts with a system message whose content is the default system prompt, a blank line, and `Finish with a short message once the fix is made.`, followed by the user message with the task text

#### Scenario: No extra text leaves the requests unchanged

- **WHEN** `run_agent` is called without `system_prompt_extra`
- **THEN** the requests are identical to the requests recorded in the golden trace

#### Scenario: A conversation that already has content is not changed

- **WHEN** `run_agent` is called with a non-empty `messages` list and a `system_prompt_extra`
- **THEN** the system message already in the list is left as it is and no second system message is added
