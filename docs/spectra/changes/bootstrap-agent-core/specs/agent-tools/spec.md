## Purpose

The agent gets six tools (read_file, list_files, grep, edit_file, write_file, run_tests) to explore a multi-file Python project, make local edits, and run its tests. Every tool returns a bounded, predictable output so the conversation stays small and the model knows when it has not seen everything.

## ADDED Requirements

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

### Requirement: grep searches file contents

grep SHALL search text files under the given path (default the workspace root) with a regular expression and return matching lines as `relative/path:line_number:line_text`, in path then line order. It SHALL skip the same directories as list_files, SHALL NOT follow symbolic links, SHALL skip files that are not valid UTF-8 text, and SHALL match only the first 2000 characters of each line. It SHALL return at most 100 lines with a note stating how many matches were omitted. An invalid regular expression SHALL return ok=false with a message containing "invalid regular expression". Matching a single line SHALL be limited to 1 second and the whole search to 5 seconds; when a limit is hit the result SHALL be ok=false with a message containing "pattern too slow" for the per-line limit, or ok=true with the matches found so far and a note "search stopped after 5s" for the overall limit.

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

- **WHEN** a file has a line of 40 "a" characters followed by "!" and grep is called with pattern `(a+)+$`
- **THEN** the call returns within 5 seconds with ok=false and a message containing "pattern too slow"

#### Scenario: Symbolic link to a file outside the workspace

- **WHEN** the workspace contains a symbolic link link_secret to ../secret and the target file contains the word "password"
- **THEN** grep with pattern `password` returns no match from link_secret

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

### Requirement: write_file creates files and guards overwrites

write_file SHALL create the file, including missing parent directories, when it does not exist. When the file already exists, write_file SHALL succeed only if the file is recorded as fully read, meaning a read_file call without a line range and without truncation returned it earlier and no successful edit_file has changed it since; otherwise it SHALL return ok=false with a message containing "read the file first" and leave the file unchanged. A successful write_file SHALL record the written file as fully read. A failed read_file call SHALL NOT record anything.

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

### Requirement: run_tests runs pytest in the workspace

run_tests SHALL run exactly `python -m pytest -q -p no:cacheprovider -c /dev/null --rootdir=. --confcutdir=. --` followed by the target (default `.`) with the workspace as the current directory, and return the combined stdout and stderr. When the output is longer than 4000 characters, the result SHALL keep the first 2000 and the last 2000 characters with a note between them that states the total length, because pytest puts its summary at the end. A target SHALL be a path inside the workspace; a target outside the workspace SHALL be rejected as blocked. A target other than `.` SHALL be passed to pytest with a leading `./`, so a target starting with `-` is treated as a path, never as a pytest option (pytest 9.1.1 treats `--version` as an option even after `--`). A run longer than 10 seconds SHALL be stopped and reported as timed out. The result SHALL be ok=true whether or not the tests pass, and the flags SHALL include `tests_passed` and `timed_out`. The run SHALL NOT create a .pytest_cache directory in the workspace.

#### Scenario: Failing fixture project

- **WHEN** run_tests is called on the unfixed timelog fixture project
- **THEN** the flag `tests_passed` is false, the result is ok=true, and the output contains "1 failed"

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

### Requirement: Tool errors never crash the loop

Every tool call SHALL return a result object. Bad arguments, unknown tool names, blocked paths, and operating system errors SHALL become an error message for the model with ok=false, never an exception.

#### Scenario: Unknown tool

- **WHEN** the workspace is asked directly to run a tool named `bash`
- **THEN** the call returns ok=false with a message containing "unknown tool"

#### Scenario: Wrong argument type

- **WHEN** edit_file is called with `old_string` set to the number 5
- **THEN** the call returns ok=false with a message saying the argument must be a string
