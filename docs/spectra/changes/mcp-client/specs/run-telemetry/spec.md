## ADDED Requirements

### Requirement: run_start records the MCP configuration summary

The `run_start` event SHALL include the key `mcp`: null when `--mcp-config` is not given, otherwise an object with `sdk_version` and `servers`, a list of objects with `name`, `tools` (the registered names) and `skipped` (the names of skipped tools). It SHALL NOT include a server's command, arguments, environment or working directory, because they can contain secrets.

#### Scenario: Run with one MCP server

- **WHEN** fixlab runs with a configuration listing server `echo` that provides tool `shout`
- **THEN** the `run_start` line has `mcp.servers` equal to `[{"name": "echo", "tools": ["mcp__echo__shout"], "skipped": []}]` and contains no `command` or `args` value
