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

## 指令

```bash
.venv/bin/python -m pytest -q                  # fixlab 自己的測試（約 30 秒）；CI 在 macOS 跑
.venv/bin/python -m fixlab.bench check         # benchmark 題目自我檢查，不花錢
UPDATE_GOLDEN=1 .venv/bin/python -m pytest tests/test_trace_golden.py   # 只在刻意改變行為時使用；要檢視 diff
```

`bench run --confirm` 會呼叫真實模型、花錢，只有使用者要求時才執行。目錄結構與設計原則見 AGENTS.md。

## 規格

- 規格放在 `docs/spectra/specs/`，一個 capability 一個資料夾，用 kebab-case 命名（`workspace-isolation`、`run-telemetry`）。新行為在實作前要有 Spectra change（`/spectra-propose`）。
- 需求用 `SHALL`／`SHALL NOT`；每條需求至少一個 `#### Scenario:`，以 WHEN／THEN 或「輸入與結果」表格撰寫。
- 測試用 `# 規格：<Requirement>` 註解標出它驗證的需求。
- 已歸檔的 change 是歷史紀錄，不要修改；需要時另開新的 change。
- 只動文件或工具設定的變更（README、`docs/`、`.claude/`、CI 設定）可以不走 Spectra 流程，並在 PR 說明寫明。

## Skills 與 Hooks

`.claude/skills/` 的專案專屬 skill（`spectra-*` 是通用 skill）：

| Skill | 使用時機 |
|---|---|
| `code-review` | 開 PR 或歸檔前找問題；套用 fixlab 的設計原則並記錄結果 |
| `review-findings` | 處理 review 發現的問題：驗證、分級、用新 commit 修正、重審 |
| `unit-test` | 撰寫或修改測試（劇本假模型、golden trace、fixtures） |
| `create-pr` | push 並開 PR |
| `add-bench-problem` | 新增或修改 benchmark 題目；說明題集變動對既有結果的影響 |

Hooks（`.claude/settings.json`，腳本在 `.claude/hooks/`）執行 AGENTS.md 第 5 節的規則：

| Hook | 作用 |
|---|---|
| `guard-bash.sh`（PreToolUse，Bash） | 擋下 `git add -A`／`.`／`-u`、在 `main`／`master`／`develop` 上 commit、帶 AI 署名的 commit 訊息，以及 HEAD 沒有審查紀錄時的 `gh pr create`／`spectra archive` |
| `remind-docs.sh`（PostToolUse，Edit/Write） | 修改套件程式碼後，提醒檢查規格、README 與文件；提醒不要手改 golden trace |
| `review-reminder.sh`（Stop） | 分支上有未審查的程式碼 commit 時，每個 HEAD 提醒一次要做 code review |
| `mark-reviewed.sh` | 把 HEAD 的審查結果記在 `.claude/state/`（不進版控）；由 skill 呼叫，不要手動執行 |
