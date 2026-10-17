## Purpose

Tool-call parsing turns a model reply into validated tool calls. It reads only the native `tool_calls` field of the reply. A reply without native tool calls is plain text, so models that write tool calls as JSON inside the reply text are not supported.

## ADDED Requirements

### Requirement: Only native tool calls are parsed

When a reply has native `tool_calls`, the parser SHALL decode each call's JSON-string arguments and return those calls in order. The parser SHALL NOT look for tool calls in the reply text, so a reply without native tool calls yields no calls and no errors. A native call whose arguments are not a valid JSON object SHALL be reported as an error and SHALL NOT be returned as a call.

#### Scenario: Native call plus JSON in text

- **WHEN** the reply has a native read_file call and its text contains a run_tests JSON object
- **THEN** the parsed calls are [read_file] and there are no errors

#### Scenario: JSON only in the reply text

- **WHEN** the reply has no native tool calls and its text is {"name": "run_tests", "arguments": {}}
- **THEN** there are no calls and no errors

#### Scenario: Two native calls in one reply

- **WHEN** the reply has a native read_file call followed by a native run_tests call
- **THEN** the parsed calls are [read_file, run_tests] in that order

#### Scenario: Native call with broken arguments

- **WHEN** a native read_file call has the arguments string `{"path": ` which is not valid JSON
- **THEN** no call is returned and the error contains "bad arguments"

#### Scenario: Ordinary text

- **WHEN** the reply text is "Done. Example: {'a': 1}" and there are no native tool calls
- **THEN** there are no calls and no errors

### Requirement: Calls are validated against tool schemas

A parsed call SHALL be rejected with an error when its tool name is not in the offered tool list or a required argument is missing. A shell-like tool name such as `bash` SHALL be rejected as an unknown tool.

#### Scenario: Missing required argument

- **WHEN** a native edit_file call has `path` and `old_string` but no `new_string`
- **THEN** no call is returned and the error mentions "missing"

#### Scenario: Shell tool is not offered

- **WHEN** the reply calls a tool named `bash`
- **THEN** no call is returned and the error contains "unknown tool: 'bash'"
