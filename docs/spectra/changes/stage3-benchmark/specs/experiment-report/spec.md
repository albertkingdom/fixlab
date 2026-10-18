## Purpose

The experiment report turns the results file into the numbers and examples that answer the project's questions: does having a test-running tool help, how often does the agent claim success without it, and what does it cost. It exists so that every number in the written results can be reproduced from the raw files.

## ADDED Requirements

### Requirement: The summary table covers every model and condition

The `report` command SHALL print a markdown table with one row for each pair of model and condition, with these columns: the number of runs, the counts and percentages of `fixed`, `broke_existing`, `overfit`, `invalid` and `unfixed` outcomes, the number of runs whose `claimed_done_but_failed` is true, the total `hidden_tool_calls`, the median number of steps, the mean prompt tokens and the mean completion tokens. Runs with a non-null `error` SHALL NOT be counted in any outcome and SHALL be shown in a separate column. When the results file has several lines for one combination of problem, model, condition and repeat, only the latest line SHALL be used.

#### Scenario: Counting outcomes

- **GIVEN** results for one model and one condition with 40 runs: 22 fixed, 6 broke_existing, 5 overfit, 0 invalid, 5 unfixed, and 2 further runs with an error
- **WHEN** the report is printed
- **THEN** that row shows 38 counted runs, 22 fixed (58%), and 2 errors

### Requirement: The two conditions are compared per problem with an interval

For each model that has both conditions, the report SHALL compute for every problem the fixed rate under `with_tests` minus the fixed rate under `no_tests`, then the mean of these differences over problems, and a 95% interval for that mean obtained by resampling the problems with replacement 2000 times using a fixed random seed. Running the report twice on the same file SHALL print identical numbers.

##### Example: paired difference

| Problem | with_tests fixed rate | no_tests fixed rate | Difference |
|---------|----------------------|---------------------|------------|
| inventory | 4/5 | 2/5 | +0.4 |
| calendar | 3/5 | 3/5 | 0.0 |

#### Scenario: Mean difference of two problems

- **WHEN** only the two problems of the example table have results
- **THEN** the mean difference printed is +0.2

#### Scenario: Reproducible interval

- **WHEN** the report runs twice on the same results file
- **THEN** the two interval bounds are identical in both outputs

### Requirement: Cost uses a stated price

When a model has a price in the models file, the report SHALL print the cost per run (prompt tokens times the input price plus completion tokens times the output price) and the cost per fixed run (the total cost of the counted runs divided by their number of fixed runs), and SHALL print the price's source and date next to the model. When a model has no price, the report SHALL print token counts only and SHALL NOT print a cost.

#### Scenario: Cost per fixed run

- **GIVEN** a model with input price 0.10 and output price 0.40 per million tokens, and 10 counted runs that used 1,000,000 prompt tokens and 250,000 completion tokens in total, of which 5 are fixed
- **WHEN** the report is printed
- **THEN** the total cost shown is 0.20, the cost per run is 0.02 and the cost per fixed run is 0.04

#### Scenario: No price

- **WHEN** a model has no price entry
- **THEN** its rows show tokens and no cost

### Requirement: Failed runs are shown with their event logs

For each outcome other than `fixed`, the report SHALL list up to a configurable number of runs (default 3) with their problem, model, condition, repeat, stop reason, number of steps, the sequence of tool names the agent called, and the path of the event log.

#### Scenario: Example of an overfit run

- **WHEN** a run has outcome `overfit`
- **THEN** the examples section lists it with its event log path and the ordered tool names such as `run_tests, read_file, edit_file, run_tests`

### Requirement: The limits are always printed

Every report SHALL end with a limits section stating at least: the number of problems and repeats used and that the results describe only this set of problems, that the program under test runs in the same process as pytest and can therefore fake test results so the numbers reduce but do not remove that risk, and that the number of problems was reduced from the originally planned 15 to 20 to 8 before any problem was written.

#### Scenario: Limits section

- **WHEN** any report is printed
- **THEN** its last section contains the three statements above

### Requirement: Mismatched inputs produce warnings

The report SHALL print a warning and still print the report when: the results contain a problem digest that differs from the current digest of that problem, the results contain two different digests for one problem, a combination of model and condition does not have the same number of runs for every problem, or a result line names a problem that does not exist.

#### Scenario: A problem was edited after it was run

- **WHEN** a results line has a `problem_digest` that differs from the current digest of its problem
- **THEN** the report prints a warning naming the problem and still prints the tables
