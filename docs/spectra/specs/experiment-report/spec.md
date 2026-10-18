# experiment-report Specification

## Purpose

The experiment report turns the results file into the numbers and examples that answer the project's questions: does having a test-running tool help, how often does the agent claim success without it, and what does it cost. It exists so that every number in the written results can be reproduced from the raw files.

## Requirements

### Requirement: The summary table covers every model and condition

The `report` command SHALL print a markdown table with one row for each pair of model and condition, with these columns: the number of runs, the counts and percentages of `fixed`, `broke_existing`, `overfit`, `invalid` and `unfixed` outcomes, the number of runs whose `claimed_done_but_failed` is true, the number of runs whose `stop_reason` is `max_steps`, the total `hidden_tool_calls`, the median number of steps, the mean prompt tokens and the mean completion tokens. Runs with a non-null `error` SHALL NOT be counted in any outcome and SHALL be shown in a separate column. When the results file has several lines for one combination of problem, model, condition and repeat, only the latest line SHALL be used.

#### Scenario: Counting outcomes

- **GIVEN** results for one model and one condition with 40 runs: 22 fixed, 6 broke_existing, 5 overfit, 0 invalid, 5 unfixed, and 2 further runs with an error
- **WHEN** the report is printed
- **THEN** that row shows 38 counted runs, 22 fixed (58%), and 2 errors


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
### Requirement: Cost uses a stated price

When a model has a price in the models file, the report SHALL print the cost per run (prompt tokens times the input price plus completion tokens times the output price) and the cost per fixed run (the total cost of the counted runs divided by their number of fixed runs), and SHALL print the price's source and date next to the model. When a model has no price, the report SHALL print token counts only and SHALL NOT print a cost.

#### Scenario: Cost per fixed run

- **GIVEN** a model with input price 0.10 and output price 0.40 per million tokens, and 10 counted runs that used 1,000,000 prompt tokens and 250,000 completion tokens in total, of which 5 are fixed
- **WHEN** the report is printed
- **THEN** the total cost shown is 0.20, the cost per run is 0.02 and the cost per fixed run is 0.04

#### Scenario: Every run of a priced model ended in an error

- **WHEN** a model has a price and every one of its runs has a non-null `error`
- **THEN** the report is still printed, its cost row shows that there are no counted runs, and no cost is computed from zero runs

#### Scenario: No price

- **WHEN** a model has no price entry
- **THEN** its rows show tokens and no cost


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
### Requirement: Failed runs are shown with their event logs

For each outcome other than `fixed`, the report SHALL list up to a configurable number of runs (default 3) with their problem, model, condition, repeat, stop reason, number of steps, the sequence of tool names the agent called, and the path of the event log.

#### Scenario: Example of an overfit run

- **WHEN** a run has outcome `overfit`
- **THEN** the examples section lists it with its event log path and the ordered tool names such as `run_tests, read_file, edit_file, run_tests`


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
### Requirement: The limits are always printed

Every report SHALL end with a limits section stating at least: the number of problems and repeats used and that the results describe only this set of problems, that the program under test runs in the same process as pytest and can therefore fake test results so the numbers reduce but do not remove that risk, and that the number of problems was reduced from the originally planned 15 to 20 to 8 before any problem was written.

#### Scenario: Limits section

- **WHEN** any report is printed
- **THEN** its last section contains the three statements above


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
### Requirement: Mismatched inputs produce warnings

The report SHALL print a warning and still print the report when: the results contain a problem digest that differs from the current digest of that problem, the results contain two different digests for one problem, a combination of model and condition does not have the same number of runs for every problem, or a result line names a problem that does not exist.

#### Scenario: A problem was edited after it was run

- **WHEN** a results line has a `problem_digest` that differs from the current digest of its problem
- **THEN** the report prints a warning naming the problem and still prints the tables

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