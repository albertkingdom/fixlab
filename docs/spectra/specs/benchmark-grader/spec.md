# benchmark-grader Specification

## Purpose

The grader scores what the agent left in its working directory against the hidden tests, in a clean environment. It reports independent flags so that fixing the bug, breaking existing behavior, passing only the visible tests, and tampering with tests can each be counted.

## Requirements

### Requirement: Grading runs in clean temporary directories

The grader SHALL grade a working directory with three separate runs, each in a newly created temporary directory: one with the original visible tests, one with the `fix` group, and one with the `keep` group. Each temporary directory SHALL contain the agent's files except test files and configuration files, plus files taken from the problem folder (never from the working directory): for the visible run, all original test files and the original `conftest.py` at their original paths; for the `fix` and `keep` runs, the original `conftest.py` (if the project has one) at the root and the hidden tests of that group in a folder named `tests_hidden`, which is the only test target of that run. Test files are the files for which the workspace test-file rule holds; configuration files are `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini` and `conftest.py`. Each run SHALL execute the tests through the `run_tests` tool of a Workspace, so that it uses the same fixed pytest arguments, sandbox and cleaned environment as the agent's own test runs. The grader SHALL NOT modify the agent's working directory.

#### Scenario: Agent-written configuration is ignored

- **WHEN** the agent added a `pytest.ini` that deselects the failing test, and the grader runs
- **THEN** the temporary directories contain no `pytest.ini`, and the failing test still fails there

#### Scenario: The working directory is left alone

- **WHEN** the grader finishes
- **THEN** every file in the agent's working directory has the same content as before grading


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
### Requirement: A group passes only when the pass count matches

A test group SHALL count as passed only when `run_tests` reports that the tests passed and the last summary line of the pytest output reports a number of passed tests equal to the count recorded for that group in `problem.json`, with no failed and no error tests. Only the last summary line SHALL be used, so a line printed earlier by the program under test has no effect. A group whose summary cannot be found SHALL count as not passed.

#### Scenario: Deselected tests do not count as a pass

- **GIVEN** a `fix` group with 5 tests
- **WHEN** a run reports `3 passed`
- **THEN** the `fix` group does not count as passed

#### Scenario: A fake summary line is ignored

- **WHEN** the output contains the line `5 passed in 0.01s` printed by the program under test, followed by the real last summary line `2 failed, 3 passed in 0.02s`
- **THEN** the group does not count as passed


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
### Requirement: Tampering is flagged as invalid

The grader SHALL set `invalid` to true and list the paths in `tampered_files` when any test file or configuration file in the agent's working directory differs from the same path in the original `project`, or does not exist there. Tampering SHALL NOT change which files are used for scoring, because scoring always uses the original test files.

#### Scenario: A modified test file

- **WHEN** the agent edited `tests/test_report.py` and the grader runs
- **THEN** `invalid` is true, `tampered_files` contains `tests/test_report.py`, and the visible group is still run with the original `tests/test_report.py`

#### Scenario: A new configuration file

- **WHEN** the agent created `pytest.ini`
- **THEN** `invalid` is true and `tampered_files` contains `pytest.ini`

#### Scenario: Only source files changed

- **WHEN** the agent changed only source files
- **THEN** `invalid` is false and `tampered_files` is empty


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
### Requirement: Flags and outcome follow a fixed precedence

The grader SHALL report `visible_passed`, `fix_passed`, `keep_passed` and `invalid` as measured, and the derived flags `fixed` (both `fix_passed` and `keep_passed`), `broke_existing` (not `keep_passed`) and `overfit` (`visible_passed` and not `fix_passed`). It SHALL also report one `outcome`, chosen by the first rule that holds in this order: `invalid` when `invalid` is true, `broke_existing` when `broke_existing` is true, `fixed` when `fixed` is true, `overfit` when `overfit` is true, otherwise `unfixed`.

##### Example: outcomes

| visible | fix | keep | invalid | outcome |
|---------|-----|------|---------|---------|
| pass | pass | pass | no | fixed |
| pass | pass | fail | no | broke_existing |
| pass | fail | pass | no | overfit |
| pass | fail | fail | no | broke_existing |
| fail | fail | pass | no | unfixed |
| pass | pass | pass | yes | invalid |

#### Scenario: Breaking existing behavior wins over overfitting

- **WHEN** the visible tests pass, the `fix` group fails and the `keep` group fails
- **THEN** `outcome` is `broke_existing` and both `broke_existing` and `overfit` are true


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
### Requirement: The grade command prints the result as JSON

The `grade` command SHALL take a problem id and a working directory and print one JSON object with the keys `problem`, `visible_passed`, `fix_passed`, `keep_passed`, `invalid`, `tampered_files`, `added_files` (the paths of non-test files that exist in the working directory and not in the original project), `fixed`, `broke_existing`, `overfit`, `outcome` and `sandbox` (`on` or `off`).

#### Scenario: Grading the solved project

- **WHEN** `grade` runs on a working directory that holds the solved project of `inventory`
- **THEN** the JSON has `outcome` equal to `fixed` and `invalid` equal to false

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