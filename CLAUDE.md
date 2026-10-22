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
.venv/bin/python -m pytest -q                  # fixlab 自己的測試（約 2 分鐘）；CI 在 macOS 跑
.venv/bin/python -m fixlab.bench check         # benchmark 題目自我檢查，不花錢
UPDATE_GOLDEN=1 .venv/bin/python -m pytest tests/test_trace_golden.py   # 只在刻意改變行為時使用；要檢視 diff
```

`bench run --confirm` 會呼叫真實模型、花錢，只有使用者要求時才執行。目錄結構與設計原則見 AGENTS.md。

## 規格

- 規格放在 `docs/spectra/specs/`，一個 capability 一個資料夾，用 kebab-case 命名（`workspace-isolation`、`run-telemetry`）。新行為在實作前要有 Spectra change（`/spectra-propose`）。
- 需求用 `SHALL`／`SHALL NOT`；每條需求至少一個 `#### Scenario:`，以 WHEN／THEN 或「輸入與結果」表格撰寫。
- 測試檔開頭用註解寫它對應哪份規格；需要時在個別測試上方用 `# 規格：<Requirement>` 標出需求。
- 已歸檔的 change 是歷史紀錄，不要修改；需要時另開新的 change。
- 只動文件或工具設定的變更（README、`docs/`、`.claude/`、CI 設定）可以不走 Spectra 流程，並在 PR 說明寫明。

## Skills 與 Hooks

專案專屬的 skill 放在 `.agents/skills/`（不含 Claude Code 專屬機制，其他支援該目錄的工具也能讀）和 `.claude/skills/`（用到 Claude Code 專屬機制的）；`.claude/skills/` 裡有 symlink 指向 `.agents/skills/`，Claude Code 靠它載入。`spectra-*` 是通用 skill：

| Skill | 使用時機 |
|---|---|
| `project-review` | 開 PR 或歸檔前找問題；套用 fixlab 的設計原則並記錄結果（取名避開內建的 `/code-review`） |
| `review-findings` | 處理 review 發現的問題：驗證、分級、用新 commit 修正、重審 |
| `unit-test` | 撰寫或修改測試（劇本假模型、golden trace、fixtures） |
| `create-pr` | push 並開 PR |
| `add-bench-problem` | 新增或修改 benchmark 題目；說明題集變動對既有結果的影響 |

Hooks（`.claude/settings.json`，腳本在 `.claude/hooks/`）執行 AGENTS.md 第 5 節的規則。它們讀指令文字做判斷，是防止疏忽的護欄，不是安全邊界；需要 `jq`（沒有時 `guard-bash.sh` 會顯示警告並停用，不會擋住所有指令）。改 hook 後執行 `.claude/hooks/test-hooks.sh` 做回歸測試。

| Hook | 作用 |
|---|---|
| `guard-bash.sh`（PreToolUse，Bash） | 擋下 `git add -A`／`.`／`-u` 與 `git commit -a`、在 `main`／`master`／`develop` 上 commit、帶 AI 署名行（`Co-Authored-By`、`Generated with`）的 commit 訊息，以及 HEAD 沒有審查紀錄時的 `gh pr create`／`spectra archive`（`--preview` 放行；只改文件與規格的分支免審；歸檔產生的 `docs/spectra/` commit 不會讓審查紀錄失效）。`git commit` 與 `gh pr create` 不能串在同一個指令 |
| `remind-docs.sh`（PostToolUse，Edit/Write） | 修改套件程式碼（含 `fixlab/bench/`）後，每個檔案每個 HEAD 提醒一次檢查規格、README 與文件；提醒不要手改 golden trace |
| `review-reminder.sh`（Stop） | 分支上有未審查的程式碼 commit 時，每個 HEAD 提醒一次要做 code review（程式碼範圍同 `guard-bash.sh`） |
| `mark-reviewed.sh` | 把 HEAD 的審查結果記在 `.claude/state/`（不進版控），可在任何子目錄執行；由 skill 呼叫，不要手動執行 |
