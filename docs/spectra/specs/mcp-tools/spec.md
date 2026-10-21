# mcp-tools Specification

## Purpose

Let the agent call tools provided by MCP servers that the user lists in a configuration file, started over stdio with the official Python SDK, while every call is confirmed by the user and failures never stop the agent loop.

## Requirements

### Requirement: MCP servers come only from a file the user names

The command-line entry SHALL accept `--mcp-config PATH`, a JSON file whose top-level object has an `mcpServers` object mapping a server name to an object with `command` (string, required), `args` (list of strings, optional), `env` (object of strings, optional) and `cwd` (string, optional). fixlab SHALL NOT read an MCP configuration from any other place, such as the target project or the home directory, because the target project may be untrusted. A server name SHALL match `[A-Za-z0-9_-]+`. A file that is not valid JSON, has no `mcpServers` object, or has a server entry with a missing `command`, an unknown key such as `url`, or a value of the wrong type SHALL be refused with exit code 2 and a message naming the problem, before any server is started.

#### Scenario: Valid configuration

- **WHEN** the user runs `fixlab -i --mcp-config servers.json` and the file lists a server `echo` with `command` and `args`
- **THEN** fixlab starts that server over stdio before the first prompt

#### Scenario: Remote server entry

- **WHEN** a server entry has a `url` key instead of `command`
- **THEN** fixlab prints an error saying only stdio servers with `command` are supported, exits with code 2, and starts no server

#### Scenario: No configuration given

- **WHEN** `--mcp-config` is not given and the target project contains a `.mcp.json` file
- **THEN** no MCP server is started and the agent sees only the built-in tools


<!-- @trace
source: mcp-client
updated: 2026-10-21
code:
  - tests/mcp_echo_server.py
  - fixlab/cli.py
  - fixlab/display.py
  - pyproject.toml
  - fixlab/workspace.py
  - README.md
  - fixlab/mcp_tools.py
tests:
  - tests/test_display.py
  - tests/test_packaging.py
  - tests/test_mcp_tools.py
  - tests/test_interactive.py
-->

---
### Requirement: The MCP SDK is an optional dependency

The official `mcp` package SHALL be an optional dependency installed with the `mcp` extra, so installing fixlab without it adds no packages. When `--mcp-config` is given and the package cannot be imported, fixlab SHALL exit with code 2 and a message telling the user to install `fixlab[mcp]`. Nothing else in fixlab SHALL import the package.

#### Scenario: SDK not installed

- **WHEN** the user passes `--mcp-config` and the `mcp` package is not installed
- **THEN** fixlab prints a message naming the `mcp` extra, exits with code 2, and sends no model request


<!-- @trace
source: mcp-client
updated: 2026-10-21
code:
  - tests/mcp_echo_server.py
  - fixlab/cli.py
  - fixlab/display.py
  - pyproject.toml
  - fixlab/workspace.py
  - README.md
  - fixlab/mcp_tools.py
tests:
  - tests/test_display.py
  - tests/test_packaging.py
  - tests/test_mcp_tools.py
  - tests/test_interactive.py
-->

---
### Requirement: MCP tools are offered only in interactive mode and every call is confirmed

MCP tools SHALL be available only in interactive mode. Passing `--mcp-config` in one-shot mode SHALL exit with code 2, because nobody can confirm the calls. In interactive mode every call to an MCP tool SHALL ask the user every time, with a prompt that offers only yes or no. MCP tools SHALL NOT have the choice to always allow a tool for the session, because an MCP server runs outside the sandbox and allowing one call would let later calls with unseen arguments through; an answer of "a" or "always" SHALL be treated as no. Before asking, fixlab SHALL show the server name and the tool's own name as recorded at registration (never derived by splitting the combined name), and the call's complete arguments as JSON with every non-ASCII character escaped, so control or text-direction characters cannot make the screen differ from what is sent. A call whose arguments are longer than 4000 characters as shown SHALL be declined without asking, because the user could not read what they approve; a declined call SHALL return ok=false with the flag `denied` and SHALL NOT reach the server.

#### Scenario: One-shot mode with MCP

- **WHEN** the user runs `fixlab PATH --mcp-config servers.json`
- **THEN** fixlab prints an error saying MCP tools need interactive mode, exits with code 2, and starts no server

#### Scenario: The confirmation shows the arguments

- **WHEN** the model calls `mcp__echo__shout` with `{"text": "hi"}` in interactive mode
- **THEN** the lines shown before the question contain `echo`, `shout` and `"text": "hi"`

#### Scenario: MCP calls are asked every time

- **WHEN** the model calls an MCP tool twice in one session and the user answers `y` both times
- **THEN** fixlab asks twice with a prompt that has no always choice, and both calls reach the server

#### Scenario: An always answer is declined

- **WHEN** the user answers `a` or `always` to the confirmation of an MCP call
- **THEN** the call is declined, does not reach the server, and the next MCP call is asked again

#### Scenario: Arguments too long to confirm

- **WHEN** the model calls an MCP tool with arguments longer than 4000 characters as shown
- **THEN** fixlab prints that the arguments are too long to confirm, does not ask, and the server receives no call

#### Scenario: Declined call

- **WHEN** the model calls an MCP tool and the user answers no
- **THEN** the result is ok=false with the flag `denied`, and the server receives no call


<!-- @trace
source: mcp-client
updated: 2026-10-21
code:
  - tests/mcp_echo_server.py
  - fixlab/cli.py
  - fixlab/display.py
  - pyproject.toml
  - fixlab/workspace.py
  - README.md
  - fixlab/mcp_tools.py
tests:
  - tests/test_display.py
  - tests/test_packaging.py
  - tests/test_mcp_tools.py
  - tests/test_interactive.py
-->

---
### Requirement: MCP tools join the tool list with a prefix

After starting, fixlab SHALL list each server's tools (following pagination) and register each one as `mcp__<server>__<tool>` with the tool's description, marked as provided by that external server, and its input schema. A tool whose combined name does not match `[A-Za-z0-9_-]{1,64}`, or whose input schema is not a JSON object schema, SHALL be skipped with a warning on stderr and listed as skipped in the event log. When two tools from the configured servers produce the same combined name (for example server `a__b` with tool `c` and server `a` with tool `b__c`), fixlab SHALL exit with code 2 before any model request and name both, because one would silently replace the other. For MCP tools, fixlab SHALL check only that the arguments are a JSON object and that every name in `required` is present; every other schema rule (types, extra arguments, boolean or nested subschemas, `patternProperties`) SHALL be left to the server, so a valid schema is never rejected or crashes the check. The built-in tools keep their current argument checks.

#### Scenario: Tool appears to the model

- **WHEN** server `echo` provides a tool `shout`
- **THEN** the tool list sent to the model contains `mcp__echo__shout` with the server's input schema

#### Scenario: Tool with a name that is too long

- **WHEN** the combined name of a tool is longer than 64 characters
- **THEN** that tool is not offered to the model, a warning naming it is printed, and the other tools are still offered

#### Scenario: Schemas the simple check does not understand

| Input schema of the MCP tool                                   | Arguments from the model | Result                    |
| -------------------------------------------------------------- | ------------------------ | ------------------------- |
| `{"properties": {"x": {"type": ["string", "null"]}}}`          | `{"x": "a"}`             | reaches the server        |
| `{"properties": {"x": true}}`                                  | `{"x": 1}`               | reaches the server        |
| `{"patternProperties": {"^y": {}}, "additionalProperties": false}` | `{"y1": 1}`          | reaches the server        |
| `{"required": ["x"]}`                                          | `{}`                     | ok=false, missing `x`     |


<!-- @trace
source: mcp-client
updated: 2026-10-21
code:
  - tests/mcp_echo_server.py
  - fixlab/cli.py
  - fixlab/display.py
  - pyproject.toml
  - fixlab/workspace.py
  - README.md
  - fixlab/mcp_tools.py
tests:
  - tests/test_display.py
  - tests/test_packaging.py
  - tests/test_mcp_tools.py
  - tests/test_interactive.py
-->

---
### Requirement: MCP results are text, bounded, and never crash the loop

A call SHALL return the text of the result's text content blocks joined by newlines; any other content block SHALL be replaced by one line naming its type. When the result has no text block but has structured content, the structured content SHALL be returned as JSON. A result longer than 8000 characters SHALL keep its first and last 4000 characters with a note between them. A result the server marks as an error SHALL return ok=false with that text. A call that takes longer than 60 seconds SHALL be cancelled inside the client and return ok=false; a call that was cancelled or timed out SHALL NOT be sent to the server later. A server that has exited, or any other client error, SHALL return ok=false with a message saying what happened. A server SHALL be treated as exited only when the connection is really closed (an error with the SDK's connection-closed code followed by a failed ping), not because an error message from a running server mentions a closed connection. None of these SHALL stop the agent loop, and a later call to another tool of the same server SHALL still be answered or fail on its own.

#### Scenario: Text result

- **WHEN** `mcp__echo__shout` is called with `{"text": "hi"}` and the user allows it
- **THEN** the result is ok=true with the text `HI`

#### Scenario: Structured result only

- **WHEN** the server returns no content blocks and structured content `{"answer": 42}`
- **THEN** the tool result is ok=true with the text `{"answer": 42}`

#### Scenario: Server error

- **WHEN** the server returns a result marked as an error
- **THEN** the tool result is ok=false and contains the server's error text

#### Scenario: Call that times out

- **WHEN** a tool call does not finish within the time limit and the model then calls another tool of the same server
- **THEN** the first result is ok=false saying it timed out, the second call is answered, and the first call's request is never run afterwards

#### Scenario: Server exits during the session

- **WHEN** the server process exits and the model then calls one of its tools
- **THEN** the tool result is ok=false saying the server is not available, and the next model step still runs


<!-- @trace
source: mcp-client
updated: 2026-10-21
code:
  - tests/mcp_echo_server.py
  - fixlab/cli.py
  - fixlab/display.py
  - pyproject.toml
  - fixlab/workspace.py
  - README.md
  - fixlab/mcp_tools.py
tests:
  - tests/test_display.py
  - tests/test_packaging.py
  - tests/test_mcp_tools.py
  - tests/test_interactive.py
-->

---
### Requirement: Startup failures stop before any model request and servers are closed at exit

fixlab SHALL start every configured server, complete initialization and list its tools, each step within 30 seconds, after the other arguments are checked and before the event log or any model request is created. Any failure SHALL exit with code 2 with a message naming the server, and SHALL close the servers that were already started. Each server's stderr SHALL be written to a private temporary file, not to the terminal, so it does not mix with the interactive prompt; a startup failure SHALL include the last lines of that server's stderr in its message. The temporary files SHALL be removed when fixlab exits. When the session ends (EOF, `/exit`, or Ctrl-C), fixlab SHALL close every server within 10 seconds in total, including a server that is still starting: it SHALL cancel calls still in progress, drop queued calls, ask each server to exit and let the SDK's own stop sequence end the process, and, on POSIX systems, send SIGKILL to the process group of a server that has not exited within the last 2 seconds of that time, without changing the exit code. A server that has already exited SHALL NOT be signalled, because its process ID may belong to another process by then. Pressing Ctrl-C while closing SHALL go straight to that last step for every server and SHALL be raised again after all servers are cleaned up. A command that cannot be run SHALL be reported in one line naming the command.

#### Scenario: Server command not found

- **WHEN** a server's `command` does not exist
- **THEN** fixlab prints an error naming that server, exits with code 2, creates no event log, and sends no model request

#### Scenario: Clean exit

- **WHEN** the user ends the interactive session with EOF
- **THEN** every started server process has exited when fixlab exits

#### Scenario: Exit while a call is stuck

- **WHEN** a tool call is still running and the user presses Ctrl-C and then ends the session
- **THEN** fixlab exits within 10 seconds and no server process is left running

<!-- @trace
source: mcp-client
updated: 2026-10-21
code:
  - tests/mcp_echo_server.py
  - fixlab/cli.py
  - fixlab/display.py
  - pyproject.toml
  - fixlab/workspace.py
  - README.md
  - fixlab/mcp_tools.py
tests:
  - tests/test_display.py
  - tests/test_packaging.py
  - tests/test_mcp_tools.py
  - tests/test_interactive.py
-->