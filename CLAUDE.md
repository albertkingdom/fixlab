@AGENTS.md

<!-- SPECTRA:START v1.3.0 -->

# Spectra Instructions

This project uses Spectra for Spec-Driven Development(SDD). Specs live in `docs/spectra/specs/`, change proposals in `docs/spectra/changes/`.

## Skills

Each `/spectra-*` skill carries its own trigger description; these are the groups:

- Shape and plan → `/spectra-discuss`, `/spectra-propose`
- Continue tasks for an identified change → `/spectra-apply`
- Update requirements or plans for an identified change → `/spectra-ingest`
- Quality gate → `/spectra-verify`, `/spectra-review`, `/spectra-analyze`, `/spectra-audit`, `/spectra-drift`, `/spectra-debug`
- Finish → `/spectra-archive`, `/spectra-commit`

Explicit skill invocation takes precedence. Apply existing authorization within its unchanged scope.

## Workflow

discuss? → propose → apply ⇄ ingest → verify / review → archive

- `discuss` is optional — skip if requirements are clear
- Requirements change mid-work? Plan mode → `ingest` → resume `apply`

## Parked Changes

Changes can be parked（暫存）— temporarily moved out of `docs/spectra/changes/`. Parked changes won't appear in `spectra list` but can be found with `spectra list --parked`. To restore: `spectra unpark <name>`. The `/spectra-apply` and `/spectra-ingest` skills disclose parking and restore when the named operation is already explicitly requested; respect a known refusal, otherwise ask for missing authorization.

<!-- SPECTRA:END -->

## Commands

```bash
.venv/bin/python -m pytest -q                  # fixlab's own tests (about 30 s); CI runs them on macOS
.venv/bin/python -m fixlab.bench check         # benchmark problem self-check, free
UPDATE_GOLDEN=1 .venv/bin/python -m pytest tests/test_trace_golden.py   # only for an intentional behavior change; review the diff
```

`bench run --confirm` calls real models and costs money; run it only when the user asks. Directory layout and design rules are in AGENTS.md.

## Specs

- Specs live in `docs/spectra/specs/`, one capability per directory in kebab-case (`workspace-isolation`, `run-telemetry`). New behavior needs a Spectra change (`/spectra-propose`) before implementation.
- Requirements use `SHALL`/`SHALL NOT`; each has at least one `#### Scenario:`, as WHEN/THEN lines or a table of inputs and results.
- Tests cite the requirement they verify in a `# 規格：<Requirement>` comment.
- Archived changes are history. Do not edit them; open a new change instead.
- Docs-only or tooling-only changes (README, `docs/`, `.claude/`, CI wiring) may skip the Spectra flow; say so in the PR description.

## Skills and Hooks

Project skills in `.claude/skills/` (the `spectra-*` skills are general-purpose):

| Skill | Use when |
|---|---|
| `code-review` | Finding problems before a PR or archive; applies fixlab's design rules and records the result |
| `review-findings` | Handling the findings: verify, grade, fix with new commits, re-review |
| `unit-test` | Writing or changing tests (scripted fake model, golden trace, fixtures) |
| `create-pr` | Pushing and opening a PR |

Hooks (`.claude/settings.json`, scripts in `.claude/hooks/`) enforce the rules in AGENTS.md section 5:

| Hook | Effect |
|---|---|
| `guard-bash.sh` (PreToolUse, Bash) | Blocks `git add -A`/`.`/`-u`, commits on `main`/`master`/`develop`, commit messages with AI attribution, and `gh pr create` / `spectra archive` when HEAD has no recorded code review |
| `remind-docs.sh` (PostToolUse, Edit/Write) | After editing package code, reminds to check specs, README and docs; warns against hand-editing the golden trace |
| `review-reminder.sh` (Stop) | Once per HEAD, asks for a code review when the branch has unreviewed code commits |
| `mark-reviewed.sh` | Records the review for HEAD in `.claude/state/` (git-ignored); run by the skills, not by hand |
