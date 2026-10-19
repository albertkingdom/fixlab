# benchmark-problems Specification

## Purpose

The benchmark problems are a fixed set of small multi-file Python projects with a bug in each. They exist so that the agent, with and without a test-running tool, can be measured on the same tasks, with hidden tests the agent never sees.

## Requirements

### Requirement: Each problem is a self-contained folder

Every problem SHALL live in its own folder under the benchmark problems directory, named by the problem id. The folder SHALL contain `problem.json`, a `project` folder (the initial project the agent receives, with its README, source files and visible tests), a `solution` folder (only the files the reference fix changes, overlaid on `project`), and a `hidden` folder with the two subfolders `fix` and `keep`. `problem.json` SHALL contain the keys `id`, `domain`, `bug_type`, `bug_files` (list of paths inside `project`), `distractors` (list of paths inside `project`), `visible` (an object with `total` and `failing` test counts) and `hidden` (an object with the test counts of `fix` and `keep`). The benchmark SHALL contain exactly the eight problems with the ids `inventory`, `calendar`, `settings`, `billing`, `subscription`, `paging`, `scheduler` and `permissions`.

#### Scenario: Loading a problem

- **WHEN** the loader reads the folder of the problem `inventory`
- **THEN** it returns the id, domain, bug type, the listed bug and distractor paths, and the expected test counts, and every listed path exists inside `project`

#### Scenario: A malformed problem is rejected

- **WHEN** a problem folder has no `hidden/keep` folder, or `problem.json` lacks the key `bug_files`
- **THEN** the loader raises an error that names the problem and the missing item


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
### Requirement: Hidden tests and the solution never reach the agent

The agent's working directory SHALL be a temporary copy of the `project` folder only. The `hidden` folder, the `solution` folder and `problem.json` SHALL NOT be copied into it, and no tool call SHALL be able to read them: the file tools are limited to the working directory, and the sandboxed test process cannot read the fixlab project directory where the benchmark lives.

#### Scenario: The working directory holds only the project

- **WHEN** the working directory for a problem is created
- **THEN** it contains exactly the files of `project`, and contains no file from `hidden` or `solution` and no `problem.json`


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
### Requirement: Each project states its correct behavior and contains distractors

Every `project` folder SHALL state the correct behavior of the code in a README or in module docstrings, and the hidden tests SHALL only test behavior that this text states, and SHALL call the code only through the public entry points that the README names, never through internal functions, so that two equally valid fixes are not graded differently. Every visible test SHALL assert on the whole output of the code under test, not on a single number that points at the cause. Every project SHALL contain between one and three distractor files or blocks: code that looks suspicious but is correct, and each is listed in `distractors`.

#### Scenario: Listed paths exist

- **WHEN** the self-check reads a problem whose `distractors` lists `inventory/legacy_import.py`
- **THEN** that file exists in `project`, and the same holds for every path in `bug_files`


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
### Requirement: A problem does not depend on the execution environment

A problem SHALL give the same test results on any machine. It SHALL NOT depend on the time zone, the locale, the current time, random numbers, hash order or file listing order. When the behavior involves a local time, the project SHALL define the local offset explicitly in its code.

#### Scenario: A time zone problem has an explicit offset

- **WHEN** a problem is about the difference between UTC and local time
- **THEN** its code defines the local offset as a constant, and its tests give the same result with the environment variable TZ set to any value


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
### Requirement: A problem has a content digest

The benchmark SHALL compute a digest of every problem: a SHA-256 over the sorted relative paths and contents of all files in the problem folder. The digest SHALL change when any file of the problem changes, so that a result can be tied to the exact version of the problem that produced it.

#### Scenario: Editing a hidden test changes the digest

- **GIVEN** a problem with digest D
- **WHEN** one character of a hidden test is changed
- **THEN** the digest of the problem is different from D


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