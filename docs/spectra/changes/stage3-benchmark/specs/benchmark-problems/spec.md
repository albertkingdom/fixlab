## Purpose

The benchmark problems are a fixed set of small multi-file Python projects with a bug in each. They exist so that the agent, with and without a test-running tool, can be measured on the same tasks, with hidden tests the agent never sees.

## ADDED Requirements

### Requirement: Each problem is a self-contained folder

Every problem SHALL live in its own folder under the benchmark problems directory, named by the problem id. The folder SHALL contain `problem.json`, a `project` folder (the initial project the agent receives, with its README, source files and visible tests), a `solution` folder (only the files the reference fix changes, overlaid on `project`), and a `hidden` folder with the two subfolders `fix` and `keep`. `problem.json` SHALL contain the keys `id`, `domain`, `bug_type`, `bug_files` (list of paths inside `project`), `distractors` (list of paths inside `project`), `visible` (an object with `total` and `failing` test counts) and `hidden` (an object with the test counts of `fix` and `keep`). The benchmark SHALL contain exactly the eight problems with the ids `inventory`, `calendar`, `settings`, `billing`, `subscription`, `paging`, `scheduler` and `permissions`.

#### Scenario: Loading a problem

- **WHEN** the loader reads the folder of the problem `inventory`
- **THEN** it returns the id, domain, bug type, the listed bug and distractor paths, and the expected test counts, and every listed path exists inside `project`

#### Scenario: A malformed problem is rejected

- **WHEN** a problem folder has no `hidden/keep` folder, or `problem.json` lacks the key `bug_files`
- **THEN** the loader raises an error that names the problem and the missing item

### Requirement: Hidden tests and the solution never reach the agent

The agent's working directory SHALL be a temporary copy of the `project` folder only. The `hidden` folder, the `solution` folder and `problem.json` SHALL NOT be copied into it, and no tool call SHALL be able to read them: the file tools are limited to the working directory, and the sandboxed test process cannot read the fixlab project directory where the benchmark lives.

#### Scenario: The working directory holds only the project

- **WHEN** the working directory for a problem is created
- **THEN** it contains exactly the files of `project`, and contains no file from `hidden` or `solution` and no `problem.json`

### Requirement: Each project states its correct behavior and contains distractors

Every `project` folder SHALL state the correct behavior of the code in a README or in module docstrings, and the hidden tests SHALL only test behavior that this text states, and SHALL call the code only through the public entry points that the README names, never through internal functions, so that two equally valid fixes are not graded differently. Every visible test SHALL assert on the whole output of the code under test, not on a single number that points at the cause. Every project SHALL contain between one and three distractor files or blocks: code that looks suspicious but is correct, and each is listed in `distractors`.

#### Scenario: Listed paths exist

- **WHEN** the self-check reads a problem whose `distractors` lists `inventory/legacy_import.py`
- **THEN** that file exists in `project`, and the same holds for every path in `bug_files`

### Requirement: A problem does not depend on the execution environment

A problem SHALL give the same test results on any machine. It SHALL NOT depend on the time zone, the locale, the current time, random numbers, hash order or file listing order. When the behavior involves a local time, the project SHALL define the local offset explicitly in its code.

#### Scenario: A time zone problem has an explicit offset

- **WHEN** a problem is about the difference between UTC and local time
- **THEN** its code defines the local offset as a constant, and its tests give the same result with the environment variable TZ set to any value

### Requirement: A problem has a content digest

The benchmark SHALL compute a digest of every problem: a SHA-256 over the sorted relative paths and contents of all files in the problem folder. The digest SHALL change when any file of the problem changes, so that a result can be tied to the exact version of the problem that produced it.

#### Scenario: Editing a hidden test changes the digest

- **GIVEN** a problem with digest D
- **WHEN** one character of a hidden test is changed
- **THEN** the digest of the problem is different from D

### Requirement: The self-check verifies every problem without calling a model

The `check` command SHALL verify each problem using only pytest and SHALL NOT call any language model. For the original `project` it SHALL verify that the number of failing visible tests equals `visible.failing`, that at least one `fix` test fails, that all `keep` tests pass, and that the test counts match `problem.json`. For `project` with `solution` overlaid it SHALL verify that the visible, `fix` and `keep` groups all pass. It SHALL repeat each of these runs a configurable number of times (default 20) and SHALL fail a problem whose results differ between repetitions. It SHALL verify that the output of the failing visible tests does not contain the base name of any file in `bug_files`. It SHALL print one line per problem and exit with a non-zero code when any problem fails.

#### Scenario: A correct problem passes

- **WHEN** `check` runs on a problem whose original project fails one visible test and its `fix` group, passes its `keep` group, and whose solved project passes everything, in every repetition
- **THEN** the line for that problem says it passed and the exit code is zero

#### Scenario: A fix group that already passes is reported

- **WHEN** the `fix` group of a problem passes on the original project
- **THEN** `check` reports that problem as failed with the reason that the bug is not covered by the `fix` group, and exits with a non-zero code

#### Scenario: A flaky problem is reported

- **WHEN** a test of a problem passes in some repetitions and fails in others
- **THEN** `check` reports that problem as failed with the reason that its results differ between repetitions

#### Scenario: The failure output names the buggy file

- **WHEN** the failing visible test output of a problem contains the base name of a file listed in `bug_files`
- **THEN** `check` reports that problem as failed with the reason that the failure points at the bug location
