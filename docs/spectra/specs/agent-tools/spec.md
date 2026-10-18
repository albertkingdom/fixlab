# agent-tools Specification

## Purpose

The agent gets six tools (read_file, list_files, grep, edit_file, write_file, run_tests) to explore a multi-file Python project, make local edits, and run its tests. Every tool returns a bounded, predictable output so the conversation stays small and the model knows when it has not seen everything.

## Requirements

### Requirement: read_file returns numbered lines

read_file SHALL split the file into lines with `str.splitlines` and return each line prefixed by its 1-based line number right-aligned in 6 characters followed by a tab, with no extra numbered line for a trailing newline. When start_line and end_line are given, it SHALL return only that inclusive range. An empty file SHALL return the text "(empty file)". When the output exceeds 20000 characters it SHALL be cut and end with a note giving the total character count. A missing file or a directory SHALL return ok=false. A file that is not valid UTF-8 text SHALL return ok=false instead of raising. A line range with start_line below 1, with end_line below start_line, or with start_line past the last line SHALL return ok=false. A read that has no line range and is not truncated SHALL record the file as fully read for write_file.

#### Scenario: Whole small file

- **WHEN** rules.py contains the two lines "def grace_days():" and "    return 3" followed by a trailing newline, and read_file is called with path rules.py
- **THEN** the output is "     1\tdef grace_days():\n     2\t    return 3"

#### Scenario: Line range

- **WHEN** read_file is called on a 100-line file with start_line 40 and end_line 42
- **THEN** the output has exactly 3 lines, numbered 40, 41, and 42

#### Scenario: Empty file

- **WHEN** read_file is called on a file with 0 bytes
- **THEN** the result is ok=true and the output is "(empty file)"

#### Scenario: Missing file

- **WHEN** read_file is called with path nope.py that does not exist
- **THEN** the result has ok=false, the message contains "file not found", and the `blocked` flag is not set

#### Scenario: Not a UTF-8 text file

- **WHEN** read_file is called on blob.bin, a file whose bytes are 0xFF 0xFE 0x00 0x80
- **THEN** the result has ok=false, the message contains "UTF-8", and no exception reaches the caller

#### Scenario: Invalid line range

- **WHEN** read_file is called on a 2-line file with start_line 9
- **THEN** the result has ok=false and the message contains "past the end"


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: list_files shows the project layout

list_files SHALL list files under the given directory (default the workspace root) recursively as relative paths sorted by plain string order of the full relative path, one per line. It SHALL skip the directories .git, .venv, __pycache__, and .pytest_cache, SHALL NOT follow or list symbolic links, and SHALL return at most 200 entries, ending with a note that states how many were omitted when more exist. When there is nothing to list it SHALL return ok=true with the text "no files listed", so the model can tell an empty result from a failed call.

#### Scenario: Small project

- **WHEN** the workspace has timelog/parser.py, timelog/report.py, and tests/test_report.py and list_files is called without arguments
- **THEN** the output lines are "tests/test_report.py", "timelog/parser.py", and "timelog/report.py" in that order

#### Scenario: Too many files

- **WHEN** the workspace has 250 files
- **THEN** the output has 200 file lines followed by a note that 50 entries were omitted

#### Scenario: Symbolic link inside the workspace

- **WHEN** the workspace contains a symbolic link link_secret pointing to ../secret
- **THEN** link_secret does not appear in the list_files output

#### Scenario: Nothing to list

- **WHEN** the workspace contains only a .git directory and list_files is called without arguments
- **THEN** the result has ok=true and the text "no files listed"


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: grep searches file contents

grep SHALL search text files under the given path (default the workspace root) with a regular expression and return matching lines as `relative/path:line_number:line_text`, in path then line order. It SHALL skip the same directories as list_files, SHALL NOT follow symbolic links, SHALL skip files that are not valid UTF-8 text, and SHALL match only the first 2000 characters of each line. Each line in the output SHALL be shortened to 200 characters with `...` appended when it is longer. It SHALL return at most 100 lines with a note stating how many matches were omitted, and `no matches` when nothing matches. An invalid regular expression SHALL return ok=false with a message containing "invalid regular expression". Matching a single line SHALL be limited to 1 second and the whole search to 5 seconds; when a limit is hit the result SHALL be ok=false with a message containing "pattern too slow" for the per-line limit, or ok=true with the matches found so far and a note "search stopped after 5s" for the overall limit.

#### Scenario: Find a definition

- **WHEN** parser.py line 7 is "def parse_duration(text):" and grep is called with pattern `def parse_duration`
- **THEN** the output is "timelog/parser.py:7:def parse_duration(text):"

#### Scenario: Invalid pattern

- **WHEN** grep is called with pattern `(`
- **THEN** the result has ok=false and the message contains "invalid regular expression"

#### Scenario: Output cap

- **WHEN** 120 lines match the pattern
- **THEN** the output has 100 match lines followed by a note that 20 matches were omitted

#### Scenario: Catastrophic backtracking

- **WHEN** a file has a line of 40 "a" characters followed by "!" and grep is called with pattern `(a|aa)+$` (the classic `(a+)+$` is not used because the `regex` package optimises it and finishes at once)
- **THEN** the call returns within 5 seconds with ok=false and a message containing "pattern too slow"

#### Scenario: Symbolic link to a file outside the workspace

- **WHEN** the workspace contains a symbolic link link_secret to ../secret and the target file contains the word "password"
- **THEN** grep with pattern `password` returns no match from link_secret

#### Scenario: Long lines are shortened

- **WHEN** a matching line is 500 characters long
- **THEN** the output line shows its first 200 characters followed by `...`


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: edit_file replaces one unique string

edit_file SHALL replace old_string with new_string in the given file only when old_string occurs exactly once in the file. When it occurs zero times or more than once, the file SHALL stay unchanged and the result SHALL be ok=false with a message stating the actual count. A successful edit SHALL remove the file from the set of files recorded as fully read.

#### Scenario: Unique match

- **WHEN** parser.py contains "re.match(r\"(\\d+)([hm])\", text)" once and edit_file replaces it with a corrected expression
- **THEN** the result is ok=true and parser.py contains the new expression

#### Scenario: Ambiguous match

- **WHEN** old_string "return 0" occurs 2 times in the file
- **THEN** the file is unchanged and the message contains "2 times"

#### Scenario: No match

- **WHEN** old_string does not occur in the file
- **THEN** the file is unchanged and the message contains "0 times"


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: write_file creates files and guards overwrites

write_file SHALL create the file, including missing parent directories, when it does not exist. When the file already exists, write_file SHALL succeed only if the file is recorded as fully read, meaning a read_file call without a line range and without truncation returned it earlier, no successful edit_file has changed it since, and its content on disk is still identical to what that read_file call returned (a fingerprint of the content is recorded at read time); otherwise it SHALL return ok=false with a message containing "read the file first" and leave the file unchanged. A successful write_file SHALL record the written file as fully read. A failed read_file call SHALL NOT record anything.

#### Scenario: Create a new file

- **WHEN** write_file is called with path notes/summary.txt that does not exist
- **THEN** the file is created with the given content and the result says how many characters were written

#### Scenario: Overwrite without reading

- **WHEN** write_file is called on the existing report.py and read_file was never called on it
- **THEN** the result is ok=false, the message contains "read the file first", and report.py is unchanged

#### Scenario: Overwrite after a full read

- **WHEN** read_file was called on report.py without a line range and then write_file is called on report.py
- **THEN** the file content is replaced

#### Scenario: Partial read does not count

- **WHEN** read_file was called on report.py with start_line 1 and end_line 3 and then write_file is called on report.py
- **THEN** the result is ok=false and the file is unchanged

#### Scenario: Truncated read does not count

- **WHEN** read_file returned report.py cut at 20000 characters and then write_file is called on report.py
- **THEN** the result is ok=false and the file is unchanged

#### Scenario: Edit makes the earlier read stale

- **WHEN** read_file was called on report.py, edit_file changed report.py, and then write_file is called on report.py
- **THEN** the result is ok=false and the message contains "read the file first"

#### Scenario: File changed behind the model's back

- **WHEN** read_file was called on report.py without a line range, then the file was changed on disk by something other than the tools, and then write_file is called on report.py
- **THEN** the result is ok=false, the message contains "changed since you read it" and "read the file first", and the file keeps the other change


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: run_tests runs pytest in the workspace

run_tests SHALL start pytest with `python -P`, loading the real pytest and then adding the workspace to the end of the module search path, so a pytest.py or _pytest directory inside the workspace is never loaded; the pytest arguments SHALL be exactly `-q -p no:cacheprovider -c /dev/null --rootdir=. --confcutdir=. --` followed by the target (default `.`), with the workspace as the current directory. It SHALL return the combined stdout and stderr. When the output is longer than 4000 characters, the result SHALL keep the first 2000 and the last 2000 characters with a note between them that states the total length, because pytest puts its summary at the end. A target SHALL be a path inside the workspace; a target outside the workspace SHALL be rejected as blocked. A target other than `.` SHALL be passed to pytest with a leading `./`, so a target starting with `-` is treated as a path, never as a pytest option (pytest 9.1.1 treats `--version` as an option even after `--`). A run longer than 10 seconds SHALL be stopped and reported as timed out. The result SHALL be ok=true whether or not the tests pass, and the flags SHALL include `tests_passed` and `timed_out`. `tests_passed` SHALL be true only when the exit code is 0 and some output line is a pytest summary of the form "N passed ... in Ns", so a run that exits with 0 before pytest reports anything, or in which every test is skipped, is not a pass; output printed after the summary does not matter. These checks guard against accidents and simple fakery only: code that tampers with the pytest process from inside, or that exploits pytest's plugin loading or collection rules (for example a module named like an optional dependency in the workspace root, or a pyvenv.cfg inside a folder), is outside what run_tests guarantees. Trustworthy scoring needs a separate run in a clean environment (stage 3). The run SHALL NOT create a .pytest_cache directory in the workspace.

#### Scenario: Failing fixture project

- **WHEN** run_tests is called on the unfixed timelog fixture project
- **THEN** the flag `tests_passed` is false, the result is ok=true, and the output contains "1 failed"

#### Scenario: Simple fakery of the result is rejected

- **WHEN** the workspace contains a pytest.py that prints "1 passed", or a _pytest directory whose __init__.py calls os._exit(0), or source code that calls os._exit(0) when imported, and the tests would otherwise fail
- **THEN** the flag `tests_passed` is false and, for the first two, the output still contains "1 failed"

#### Scenario: Output after the summary

- **WHEN** the tests pass and the code under test prints another line when the interpreter exits
- **THEN** the flag `tests_passed` is true

#### Scenario: A line that only mentions passed

- **WHEN** the code under test prints "all tests passed" and exits with code 0 before pytest reports anything
- **THEN** the flag `tests_passed` is false

#### Scenario: All tests skipped

- **WHEN** run_tests runs a project whose only test is skipped
- **THEN** the flag `tests_passed` is false

#### Scenario: Workspace inside the project directory

- **WHEN** the workspace is tests/fixtures/timelog inside the fixlab project directory and run_tests is called under the sandbox
- **THEN** pytest starts and reports the test results instead of failing with PermissionError on the project's pyproject.toml

#### Scenario: Target a single test file

- **WHEN** run_tests is called with target tests/test_report.py
- **THEN** only that file's tests run

#### Scenario: Target that looks like an option

- **WHEN** run_tests is called with target `--version`
- **THEN** pytest does not print its version and the output reports that the path was not found

#### Scenario: Target outside the workspace

- **WHEN** run_tests is called with target ../other
- **THEN** the call is blocked with ok=false

#### Scenario: Infinite loop in the code under test

- **WHEN** the code under test loops forever and run_tests is called
- **THEN** the flag `timed_out` is true, `tests_passed` is false, and the output says the tests timed out after 10s

#### Scenario: No cache directory left behind

- **WHEN** run_tests finishes on the timelog fixture project
- **THEN** the workspace contains no .pytest_cache directory


<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: Tool errors never crash the loop

Every tool call SHALL return a result object. Bad arguments, unknown tool names, blocked paths, and operating system errors SHALL become an error message for the model with ok=false, never an exception.

#### Scenario: Unknown tool

- **WHEN** the workspace is asked directly to run a tool named `bash`
- **THEN** the call returns ok=false with a message containing "unknown tool"

#### Scenario: Wrong argument type

- **WHEN** edit_file is called with `old_string` set to the number 5
- **THEN** the call returns ok=false with a message saying the argument must be a string

<!-- @trace
source: bootstrap-agent-core
updated: 2026-10-17
code:
  - README.md
  - fixlab/cli.py
  - tests/golden/trace_golden.json
  - fixlab/loop.py
  - docs/articles/04-edit-file.md
  - docs/articles/08-write-file.md
  - AGENTS.md
  - tests/fixtures/timelog/timelog/formatting.py
  - tests/fixtures/timelog/timelog/parser.py
  - fixlab/__init__.py
  - fixlab/workspace.py
  - tests/fixtures/timelog/timelog/report.py
  - docs/articles/06-first-full-repair.md
  - fixlab/toolparse.py
  - docs/articles/05-run-tests.md
  - fixlab/sandbox.py
  - docs/articles/11-loop-safeguards.md
  - docs/articles/07-grep.md
  - tests/fixtures/timelog/timelog/__init__.py
  - fixlab/tools.py
  - pyproject.toml
  - docs/articles/09-sandbox.md
  - docs/articles/02-seeing-the-project.md
  - docs/articles/03-the-agent-loop.md
  - docs/articles/10-protect-tests.md
  - docs/articles/01-tool-calls-and-workspace.md
tests:
  - tests/fixtures/timelog/tests/test_report.py
  - tests/test_tools.py
  - tests/test_cli.py
  - tests/test_isolation.py
  - tests/test_trace_golden.py
  - tests/test_fixture.py
  - tests/fixtures/timelog/timelog/test_formatting.py
  - tests/test_loop.py
  - tests/test_toolparse.py
-->

---
### Requirement: The test run environment is deterministic

The environment of every test subprocess started by `run_tests` SHALL set `TZ` to `UTC`, `PYTHONHASHSEED` to `0` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD` to `1`, in addition to the variables it already sets. Pytest plugins are therefore not loaded automatically, and the result of a test does not depend on the machine's time zone or hash order.

#### Scenario: The variables are set

- **WHEN** a test run executes a test that reads `TZ`, `PYTHONHASHSEED` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD` from its environment
- **THEN** the values are `UTC`, `0` and `1`, whatever the parent process had

#### Scenario: Installed pytest plugins are not loaded

- **WHEN** `run_tests` runs a test that asserts the module `anyio` has not been imported, in an environment where the anyio pytest plugin is installed and registered by entry point
- **THEN** the test passes, because plugins registered by entry point are not loaded automatically


<!-- @trace
source: stage3-benchmark
updated: 2026-10-18
code:
  - bench/problems/calendar/project/cal/legacy.py
  - docs/articles/19-first-results.md
  - bench/problems/subscription/project/subs/tz.py
  - fixlab/bench/report.py
  - bench/problems/subscription/problem.json
  - fixlab/bench/__main__.py
  - docs/articles/images/18-two-conditions.drawio.png
  - bench/problems/scheduler/project/taskplan/names.py
  - bench/problems/calendar/project/cal/__init__.py
  - bench/problems/scheduler/project/taskplan/legacy_order.py
  - bench/problems/permissions/project/perm/guard.py
  - docs/articles/images/16-grader-flow.drawio.png
  - bench/problems/calendar/project/cal/holidays.py
  - fixlab/workspace.py
  - bench/problems/subscription/project/subs/__init__.py
  - bench/problems/subscription/project/subs/check.py
  - bench/problems/permissions/solution/perm/errors.py
  - AGENTS.md
  - README.md
  - bench/problems/inventory/project/README.md
  - docs/articles/16-grader.md
  - fixlab/bench/selfcheck.py
  - bench/problems/permissions/project/perm/__init__.py
  - bench/problems/billing/problem.json
  - tests/fixtures/bench_toy/cart/project/shop/cart.py
  - bench/problems/settings/problem.json
  - bench/problems/paging/solution/pager/display.py
  - bench/problems/paging/project/pager/clamp.py
  - bench/problems/inventory/project/stock/ledger.py
  - bench/problems/subscription/solution/subs/check.py
  - docs/articles/10-protect-tests.md
  - pyproject.toml
  - bench/problems/calendar/problem.json
  - docs/articles/images/18-one-run.drawio.png
  - bench/problems/permissions/project/perm/handler.py
  - docs/benchmark-results.md
  - docs/articles/images/19-qwen-outcomes.drawio.png
  - tests/fixtures/bench_toy/cart/project/shop/legacy.py
  - fixlab/bench/grader.py
  - docs/articles/images/15-symptom-and-cause.drawio.png
  - tests/fixtures/bench_toy/cart/project/README.md
  - tests/fixtures/bench_toy/cart/project/shop/__init__.py
  - docs/articles/images/16-outcome-order.drawio.png
  - fixlab/tools.py
  - bench/problems/inventory/project/stock/report.py
  - bench/problems/scheduler/project/taskplan/queue.py
  - docs/articles/17-self-check.md
  - bench/problems/paging/project/pager/__init__.py
  - tests/fixtures/bench_toy/cart/solution/shop/cart.py
  - bench/problems/permissions/problem.json
  - bench/problems/calendar/project/cal/conflicts.py
  - bench/problems/calendar/project/cal/events.py
  - bench/problems/billing/project/bill/discounts.py
  - fixlab/cli.py
  - docs/articles/images/19-qwen-per-problem.drawio.png
  - bench/problems/settings/project/conf/overrides.py
  - bench/problems/billing/project/bill/rounding.py
  - bench/problems/scheduler/project/README.md
  - tests/fixtures/bench_toy/cart/problem.json
  - docs/articles/15-problems.md
  - bench/problems/scheduler/project/taskplan/ordering.py
  - bench/problems/inventory/project/stock/__init__.py
  - bench/problems/billing/project/README.md
  - bench/problems/inventory/project/stock/importer.py
  - bench/problems/scheduler/solution/taskplan/ordering.py
  - bench/problems/billing/project/bill/__init__.py
  - bench/problems/paging/project/pager/display.py
  - bench/problems/permissions/project/perm/roles.py
  - bench/problems/billing/project/bill/prices.py
  - bench/problems/settings/project/README.md
  - bench/problems/calendar/project/README.md
  - bench/problems/calendar/project/cal/duration.py
  - bench/problems/scheduler/problem.json
  - bench/problems/inventory/project/stock/legacy_import.py
  - bench/problems/settings/project/conf/plugins.py
  - docs/articles/images/15-problem-folder.drawio.png
  - bench/problems/subscription/project/subs/parse.py
  - bench/problems/billing/project/bill/receipt.py
  - bench/problems/billing/solution/bill/discounts.py
  - bench/problems/permissions/project/perm/errors.py
  - bench/problems/settings/project/conf/loader.py
  - fixlab/bench/problems.py
  - docs/articles/images/17-check-matrix.drawio.png
  - bench/problems/scheduler/project/taskplan/report.py
  - bench/models.json
  - bench/problems/inventory/solution/stock/importer.py
  - bench/problems/settings/project/conf/defaults.py
  - fixlab/bench/__init__.py
  - bench/problems/inventory/problem.json
  - bench/problems/paging/project/pager/legacy_pages.py
  - bench/problems/subscription/project/subs/report.py
  - bench/problems/settings/project/conf/__init__.py
  - tests/fixtures/bench_toy/cart/project/shop/report.py
  - bench/problems/calendar/solution/cal/conflicts.py
  - bench/problems/paging/problem.json
  - tests/fixtures/bench_toy/cart/project/shop/prices.py
  - docs/articles/18-experiment-runner.md
  - bench/problems/paging/project/pager/pages.py
  - bench/problems/scheduler/project/taskplan/__init__.py
  - bench/problems/permissions/project/perm/legacy_roles.py
  - bench/problems/subscription/project/subs/clock.py
  - bench/problems/permissions/project/README.md
  - bench/problems/inventory/project/stock/catalog.py
  - bench/problems/scheduler/project/taskplan/tasks.py
  - bench/problems/settings/solution/conf/loader.py
  - bench/problems/subscription/project/README.md
  - fixlab/bench/runner.py
  - bench/problems/calendar/project/cal/report.py
  - bench/problems/paging/project/README.md
  - bench/problems/settings/project/conf/render.py
tests:
  - tests/test_cli.py
  - bench/problems/inventory/hidden/fix/test_cases.py
  - tests/test_bench_selfcheck.py
  - bench/problems/settings/hidden/keep/test_basics.py
  - bench/problems/calendar/hidden/keep/test_basics.py
  - tests/fixtures/bench_toy/cart/project/tests/test_report.py
  - bench/problems/paging/hidden/keep/test_basics.py
  - bench/problems/billing/project/tests/test_checkout.py
  - bench/problems/permissions/hidden/fix/test_banned.py
  - tests/fixtures/bench_toy/cart/hidden/fix/test_discount.py
  - bench/problems/subscription/hidden/fix/test_boundaries.py
  - tests/test_bench_grader.py
  - tests/test_loop.py
  - bench/problems/calendar/hidden/fix/test_sharing.py
  - tests/fixtures/bench_toy/cart/hidden/keep/test_basics.py
  - tests/test_tools.py
  - bench/problems/settings/hidden/fix/test_independent.py
  - bench/problems/subscription/hidden/keep/test_basics.py
  - bench/problems/paging/project/tests/test_render.py
  - bench/problems/billing/hidden/fix/test_unknown_codes.py
  - tests/test_bench_report.py
  - bench/problems/scheduler/hidden/fix/test_order.py
  - tests/test_bench_problems.py
  - bench/problems/settings/project/tests/test_describe.py
  - bench/problems/calendar/project/tests/test_calendar_report.py
  - bench/problems/scheduler/project/tests/test_summary.py
  - bench/problems/permissions/hidden/keep/test_basics.py
  - bench/problems/paging/hidden/fix/test_partial_pages.py
  - bench/problems/billing/hidden/keep/test_checkout.py
  - tests/test_bench_runner.py
  - bench/problems/permissions/project/tests/test_access.py
  - bench/problems/inventory/project/tests/test_stock_report.py
  - bench/problems/subscription/project/tests/test_status.py
  - bench/problems/scheduler/hidden/keep/test_summary.py
  - bench/problems/inventory/hidden/keep/test_basics.py
-->

---
### Requirement: Tools can be hidden from the model

A Workspace SHALL be able to hide a registered tool by name. A hidden tool SHALL NOT appear in the tool list sent to the model and SHALL NOT appear in the schemas used to validate the model's reply, so a model call to it is treated as a call to an unknown tool. The program itself SHALL still be able to call a hidden tool through the Workspace. The fixlab command SHALL offer `--hide-tool NAME`, repeatable, and SHALL exit with code 2 and create no event file when a name is not a registered tool.

#### Scenario: A hidden tool is not offered

- **WHEN** `run_tests` is hidden and the tool list is built
- **THEN** the list contains `read_file`, `list_files`, `grep`, `edit_file` and `write_file`, and does not contain `run_tests`

#### Scenario: The model calls a hidden tool anyway

- **WHEN** `run_tests` is hidden and the model's reply calls `run_tests`
- **THEN** the call is rejected as an unknown tool and no tests run

#### Scenario: The program still runs the tests

- **WHEN** `run_tests` is hidden and a one-shot run finishes
- **THEN** the final test run that fixlab performs itself still executes and its result is printed

#### Scenario: An unknown tool name

- **WHEN** fixlab is started with `--hide-tool bash`
- **THEN** it exits with code 2 with a message that names `bash`, and no event file is created

<!-- @trace
source: stage3-benchmark
updated: 2026-10-18
code:
  - bench/problems/calendar/project/cal/legacy.py
  - docs/articles/19-first-results.md
  - bench/problems/subscription/project/subs/tz.py
  - fixlab/bench/report.py
  - bench/problems/subscription/problem.json
  - fixlab/bench/__main__.py
  - docs/articles/images/18-two-conditions.drawio.png
  - bench/problems/scheduler/project/taskplan/names.py
  - bench/problems/calendar/project/cal/__init__.py
  - bench/problems/scheduler/project/taskplan/legacy_order.py
  - bench/problems/permissions/project/perm/guard.py
  - docs/articles/images/16-grader-flow.drawio.png
  - bench/problems/calendar/project/cal/holidays.py
  - fixlab/workspace.py
  - bench/problems/subscription/project/subs/__init__.py
  - bench/problems/subscription/project/subs/check.py
  - bench/problems/permissions/solution/perm/errors.py
  - AGENTS.md
  - README.md
  - bench/problems/inventory/project/README.md
  - docs/articles/16-grader.md
  - fixlab/bench/selfcheck.py
  - bench/problems/permissions/project/perm/__init__.py
  - bench/problems/billing/problem.json
  - tests/fixtures/bench_toy/cart/project/shop/cart.py
  - bench/problems/settings/problem.json
  - bench/problems/paging/solution/pager/display.py
  - bench/problems/paging/project/pager/clamp.py
  - bench/problems/inventory/project/stock/ledger.py
  - bench/problems/subscription/solution/subs/check.py
  - docs/articles/10-protect-tests.md
  - pyproject.toml
  - bench/problems/calendar/problem.json
  - docs/articles/images/18-one-run.drawio.png
  - bench/problems/permissions/project/perm/handler.py
  - docs/benchmark-results.md
  - docs/articles/images/19-qwen-outcomes.drawio.png
  - tests/fixtures/bench_toy/cart/project/shop/legacy.py
  - fixlab/bench/grader.py
  - docs/articles/images/15-symptom-and-cause.drawio.png
  - tests/fixtures/bench_toy/cart/project/README.md
  - tests/fixtures/bench_toy/cart/project/shop/__init__.py
  - docs/articles/images/16-outcome-order.drawio.png
  - fixlab/tools.py
  - bench/problems/inventory/project/stock/report.py
  - bench/problems/scheduler/project/taskplan/queue.py
  - docs/articles/17-self-check.md
  - bench/problems/paging/project/pager/__init__.py
  - tests/fixtures/bench_toy/cart/solution/shop/cart.py
  - bench/problems/permissions/problem.json
  - bench/problems/calendar/project/cal/conflicts.py
  - bench/problems/calendar/project/cal/events.py
  - bench/problems/billing/project/bill/discounts.py
  - fixlab/cli.py
  - docs/articles/images/19-qwen-per-problem.drawio.png
  - bench/problems/settings/project/conf/overrides.py
  - bench/problems/billing/project/bill/rounding.py
  - bench/problems/scheduler/project/README.md
  - tests/fixtures/bench_toy/cart/problem.json
  - docs/articles/15-problems.md
  - bench/problems/scheduler/project/taskplan/ordering.py
  - bench/problems/inventory/project/stock/__init__.py
  - bench/problems/billing/project/README.md
  - bench/problems/inventory/project/stock/importer.py
  - bench/problems/scheduler/solution/taskplan/ordering.py
  - bench/problems/billing/project/bill/__init__.py
  - bench/problems/paging/project/pager/display.py
  - bench/problems/permissions/project/perm/roles.py
  - bench/problems/billing/project/bill/prices.py
  - bench/problems/settings/project/README.md
  - bench/problems/calendar/project/README.md
  - bench/problems/calendar/project/cal/duration.py
  - bench/problems/scheduler/problem.json
  - bench/problems/inventory/project/stock/legacy_import.py
  - bench/problems/settings/project/conf/plugins.py
  - docs/articles/images/15-problem-folder.drawio.png
  - bench/problems/subscription/project/subs/parse.py
  - bench/problems/billing/project/bill/receipt.py
  - bench/problems/billing/solution/bill/discounts.py
  - bench/problems/permissions/project/perm/errors.py
  - bench/problems/settings/project/conf/loader.py
  - fixlab/bench/problems.py
  - docs/articles/images/17-check-matrix.drawio.png
  - bench/problems/scheduler/project/taskplan/report.py
  - bench/models.json
  - bench/problems/inventory/solution/stock/importer.py
  - bench/problems/settings/project/conf/defaults.py
  - fixlab/bench/__init__.py
  - bench/problems/inventory/problem.json
  - bench/problems/paging/project/pager/legacy_pages.py
  - bench/problems/subscription/project/subs/report.py
  - bench/problems/settings/project/conf/__init__.py
  - tests/fixtures/bench_toy/cart/project/shop/report.py
  - bench/problems/calendar/solution/cal/conflicts.py
  - bench/problems/paging/problem.json
  - tests/fixtures/bench_toy/cart/project/shop/prices.py
  - docs/articles/18-experiment-runner.md
  - bench/problems/paging/project/pager/pages.py
  - bench/problems/scheduler/project/taskplan/__init__.py
  - bench/problems/permissions/project/perm/legacy_roles.py
  - bench/problems/subscription/project/subs/clock.py
  - bench/problems/permissions/project/README.md
  - bench/problems/inventory/project/stock/catalog.py
  - bench/problems/scheduler/project/taskplan/tasks.py
  - bench/problems/settings/solution/conf/loader.py
  - bench/problems/subscription/project/README.md
  - fixlab/bench/runner.py
  - bench/problems/calendar/project/cal/report.py
  - bench/problems/paging/project/README.md
  - bench/problems/settings/project/conf/render.py
tests:
  - tests/test_cli.py
  - bench/problems/inventory/hidden/fix/test_cases.py
  - tests/test_bench_selfcheck.py
  - bench/problems/settings/hidden/keep/test_basics.py
  - bench/problems/calendar/hidden/keep/test_basics.py
  - tests/fixtures/bench_toy/cart/project/tests/test_report.py
  - bench/problems/paging/hidden/keep/test_basics.py
  - bench/problems/billing/project/tests/test_checkout.py
  - bench/problems/permissions/hidden/fix/test_banned.py
  - tests/fixtures/bench_toy/cart/hidden/fix/test_discount.py
  - bench/problems/subscription/hidden/fix/test_boundaries.py
  - tests/test_bench_grader.py
  - tests/test_loop.py
  - bench/problems/calendar/hidden/fix/test_sharing.py
  - tests/fixtures/bench_toy/cart/hidden/keep/test_basics.py
  - tests/test_tools.py
  - bench/problems/settings/hidden/fix/test_independent.py
  - bench/problems/subscription/hidden/keep/test_basics.py
  - bench/problems/paging/project/tests/test_render.py
  - bench/problems/billing/hidden/fix/test_unknown_codes.py
  - tests/test_bench_report.py
  - bench/problems/scheduler/hidden/fix/test_order.py
  - tests/test_bench_problems.py
  - bench/problems/settings/project/tests/test_describe.py
  - bench/problems/calendar/project/tests/test_calendar_report.py
  - bench/problems/scheduler/project/tests/test_summary.py
  - bench/problems/permissions/hidden/keep/test_basics.py
  - bench/problems/paging/hidden/fix/test_partial_pages.py
  - bench/problems/billing/hidden/keep/test_checkout.py
  - tests/test_bench_runner.py
  - bench/problems/permissions/project/tests/test_access.py
  - bench/problems/inventory/project/tests/test_stock_report.py
  - bench/problems/subscription/project/tests/test_status.py
  - bench/problems/scheduler/hidden/keep/test_summary.py
  - bench/problems/inventory/hidden/keep/test_basics.py
-->