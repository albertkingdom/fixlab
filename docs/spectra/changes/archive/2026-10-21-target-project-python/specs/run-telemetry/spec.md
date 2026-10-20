## ADDED Requirements

### Requirement: run_start records the test interpreter

The `run_start` event SHALL include the key `test_python`, an object with `path` (the chosen interpreter path, made absolute, links not resolved), `source` (`option` or `default`) and `base` (the base Python installation directory allowed by the sandbox, as a real path, or null when no sandbox is available). The existing key `python` SHALL keep recording the version of the interpreter running fixlab.

#### Scenario: Interpreter given with --python is recorded

- **WHEN** fixlab runs with `--python <env>/bin/python` whose base Python is B
- **THEN** the `run_start` line has `test_python.path` equal to `<env>/bin/python`, `test_python.source` equal to `option`, and `test_python.base` equal to the real path of B
