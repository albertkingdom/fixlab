## Purpose

Tool-call parsing turns a model reply into validated tool calls. It reads native `tool_calls` first and falls back to JSON written in the reply text, because small local models often put tool calls in plain text.

## ADDED Requirements

### Requirement: Native tool calls take precedence

When a reply has native `tool_calls`, the parser SHALL use only those, decoding JSON-string arguments, and SHALL ignore JSON in the reply text.

#### Scenario: Native call plus JSON in text

- **WHEN** the reply has a native read_file call and its text contains a run_tests JSON object
- **THEN** the parsed calls are [read_file] with source `native`

### Requirement: Fallback parsing from reply text

When there are no native tool calls, the parser SHALL scan the reply text for JSON objects and treat every object that has a `name` field as a call candidate, taking its arguments from `arguments`, else `parameters`, else an empty object.

#### Scenario: Object with only a name

- **WHEN** the reply text is {"name": "run_tests"}
- **THEN** the parsed calls are [run_tests] with empty arguments

#### Scenario: Ordinary JSON with a name field

- **WHEN** the reply text is Done. Example: {"name": "Alice", "age": 3}
- **THEN** there are no calls and the errors contain "unknown tool: 'Alice'"

#### Scenario: Two calls written as JSON lines

- **WHEN** the reply text is an edit_file JSON object on one line and a run_tests JSON object on the next
- **THEN** the parsed calls are [edit_file, run_tests], both with source `fallback`

### Requirement: Calls are validated against tool schemas

A parsed call SHALL be rejected with an error when its tool name is not in the offered tool list or a required argument is missing. A shell-like tool name such as `bash` SHALL be rejected as an unknown tool.

#### Scenario: Missing required argument

- **WHEN** a native edit_file call has `path` and `old_string` but no `new_string`
- **THEN** no call is returned and the error mentions "missing"

#### Scenario: Shell tool is not offered

- **WHEN** the reply calls a tool named `bash`
- **THEN** no call is returned and the error contains "unknown tool: 'bash'"

### Requirement: Broken call attempts are errors, not silence

When no valid call and no other error is found but the text looks like a call attempt (contains `<tool_call>`, a known tool name in `"name": "..."`, or any `{"name": ..., "arguments"|"parameters": ...}` shape), the parser SHALL report an error so the loop does not mistake the reply for a completion.

#### Scenario: Python triple quotes inside JSON

- **WHEN** the reply text is an edit_file object whose new_string uses Python triple quotes
- **THEN** no call is returned and an error says the tool call is not valid JSON

#### Scenario: Ordinary text

- **WHEN** the reply text is "Done. Example: {'a': 1}"
- **THEN** there are no calls and no errors
