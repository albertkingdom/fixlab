---
name: project-review
description: "依 fixlab 的設計原則與守則審查變更、找出問題：跑測試與 benchmark 自我檢查、依變更區域套用檢查清單（agent 迴圈不退化成寫死流程、工具與安全邊界、沙箱與環境變數、隱藏測試隔離、telemetry、benchmark 與實驗紀錄的誠實度、原創性與來源註明、文件與規格同步）、問題分級（阻擋／重要／建議），通過後記錄審查結果讓 PR 與歸檔閘門放行。當使用者說「code review」「審查」「review 一下」「準備開 PR」「可以歸檔嗎」，或功能做完要開 PR／歸檔前使用。找到問題之後怎麼處理交給 review-findings。"
---

# Code review（fixlab，skill 名稱 `project-review`）

專案規則（AGENTS.md 第 5 節）：**歸檔與開 PR 之前都要完成 code review，阻擋與重要問題都處理完。** `.claude/hooks/guard-bash.sh` 會在 `gh pr create` 與 `spectra archive`（不含唯讀的 `--preview`）前檢查審查紀錄是否對應目前的 HEAD，沒有就擋下；只改文件與規格的分支免審。這個 skill 取名 `project-review`，以免與內建的 `/code-review` 同名。派 subagent 審查時，要把這份清單與步驟交給它，結果仍由你驗證後才記錄。

這個 skill 負責**找問題**；整理、驗證、修正由 `review-findings` 接手。`/spectra-review` 審的是某個 Spectra change 的程式品質，`/spectra-verify` 對照規格；這份清單補的是 fixlab 自己的設計原則，三者可以搭配，不互相取代。

## 邊界

- 只讀、只跑檢查，**不改程式**、不 push、不開 PR。
- 審查意見不是事實：每一筆都要有證據，推測的標明「推測」。
- 沒跑過的檢查就寫沒跑。**不要跑 `bench run --confirm`**：它會呼叫真實模型、花錢，不屬於 review。

## 步驟

### 1. 決定範圍

```bash
git fetch -q origin main
git diff --stat origin/main...HEAD
git log --oneline origin/main..HEAD
```

### 2. 自動檢查

```bash
.venv/bin/python -m pytest -q                          # fixlab 自己的測試，約 2 分鐘
.venv/bin/python -m fixlab.bench check                 # 動到 bench/ 或 fixlab/bench/ 時：題目自我檢查，不花錢
```

沙箱只在 macOS 啟用，CI 也在 macOS 跑；在別的系統上，沙箱相關測試會被略過，要在報告寫明。動到 `fixlab/sandbox.py`、`interpreter.py` 或 `run_tests` 時，必須在 macOS 實際跑過。

### 3. 依區域套用檢查清單

**Agent 迴圈**（`loop.py`、`toolparse.py`）
- 這是 agent，不是 workflow：下一步與何時完成由模型決定，程式只設保險（步數上限、連續失敗上限）。任何寫死「先讀檔再改檔」之類的流程都是阻擋。
- 連續失敗只算「整輪全失敗」；同一個回覆的多個呼叫都要執行；重試與例外（含 Ctrl-C）不能讓迴圈崩潰或遺失 trace。
- tool call 只認原生 `tool_calls`，參數要對照 schema 驗證；不要為了小模型加寬鬆的文字解析。
- system prompt 或 tool output 格式有改，`tests/golden/trace_golden.json` 會變：確認是刻意的，golden 是用 `UPDATE_GOLDEN=1` 重新產生並看過 diff，不是手改。

**工具與工作區**（`tools.py`、`workspace.py`）
- **不提供任意 shell。** 新增工具要先有白名單與確認機制，並走 Spectra 提案。
- 所有帶路徑的工具都要經過同一個解析：跟隨符號連結後必須落在工作目錄內；絕對路徑、`..`、`~` 都要擋（`workspace-isolation` 規格有表格）。
- 測試檔唯讀；`edit_file` 是唯一字串取代、`write_file` 覆寫前要先讀過。
- 工具錯誤回傳 `ok=false` 的結果，不丟例外。

**沙箱與環境**（`sandbox.py`、`interpreter.py`）
- 禁網路、限制讀寫；傳給子行程的環境變數要清理（金鑰不能洩漏給被測專案）。
- 非 macOS 要明確印出 `sandbox: OFF`，不能靜默降級。
- 隱藏測試與 agent 工作目錄隔離；agent 能讀到的路徑不能包含隱藏測試。

**Telemetry**（`telemetry.py`）
- 一行一個 JSON、每行立刻寫入；寫不進去只警告，實驗繼續。
- 事件欄位改動要看 `docs/spectra/specs/run-telemetry`、報告端（`fixlab/bench/report.py`）與 golden 是否同步；欄位不得含金鑰。`run_start` 的 `path` 與 `test_python.path` 是規格內的欄位（會含本機絕對路徑），所以事件檔不能提交進版控。

**CLI**（`cli.py`、`display.py`）
- 結束碼語意：0 最後測試通過、1 沒通過、2 輸入或設定有誤。
- 互動模式在改檔與跑測試前要詢問；一次性模式結束時自己重跑測試並印出差異。
- 未指定 PATH 時，在家目錄或更上層執行要被拒絕（明確給 PATH 不拒）；`display.py` 只回傳字串，不直接印。
- 只有 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`FIXLAB_MODEL` 這類環境變數；**不讀 `.env`**（README 有寫，不能偷偷改變）。

**Benchmark 與實驗**（`bench/`、`fixlab/bench/`、`docs/benchmark*.md`）
- 隱藏測試分「要修好」（`hidden/fix`）與「不能壞掉」（`hidden/keep`）；失敗輸出不能點名 bug 檔，`check` 要通過。
- **不為了讓數字好看調整題目或切分**；任何調整必須寫進結果報告（AGENTS.md 守則 4）。不編造結果。
- 每次實驗要記錄模型名稱與版本、量化、runtime 與版本、context 長度、題目子集、隨機種子、日期。
- 結果文字不能說得比資料多：本專案的結論只適用這 8 題，README 與文章不得寫成「一般成功率」。
- `bench/models.json` 不得含金鑰；`runs/` 不進版控。

**原創性與來源**（AGENTS.md 守則 7）
- 不複製他人專案的程式、題目結構、範例專案、bug 類型。沿用 KeSi 的沙箱寫法必須註明來源並保留版權聲明。
- 引用外部數字要註明來源與日期。

**文件與規格**
- 行為變更要有對應的 Spectra change，**不手改已 archive 的產物**；使用者看得到的差異同步 `README.md` 與 `docs/*.md`。
- 文件用繁體中文，程式碼與識別字用英文；commit 與 PR 說明用英文。
- 教學文章對應 `article-NN` tag：文章描述的程式有改動時，要提醒使用者 tag 是否需要更新（tag 只建在本機，不自動推送）。
- README 是給外部讀者的：不寫作者本機的設定、路徑或個人資訊；`docs/` 與範例輸出不得含本機路徑或使用者名稱。

**每次都看**
- 機密或個人資料（金鑰、`.env`、`~/` 絕對路徑、使用者名稱）進了 diff 嗎。
- commit 訊息有沒有帶 AI 署名行（hook 會擋，但既有歷史要自己看）。
- 新行為有測試嗎，測試是先失敗過才通過的嗎。

### 4. 分級與報告

分級標準與 `review-findings` 相同（阻擋／重要／建議，有爭議從嚴）。每一筆：

```
[阻擋|重要|建議] <file>:<line> <問題一句話>
證據：<讀到的程式／重現／輸出>
建議：<怎麼修>
狀態：已驗證｜推測
```

最後列出：範圍、實際執行過的檢查與結果、沒跑的檢查與原因（例如「非 macOS，沙箱測試略過」）。

### 5. 通過時記錄

**沒有未處理的阻擋與重要問題，而且步驟 2 的檢查都通過**，才執行：

```bash
"$(git rev-parse --show-toplevel)/.claude/hooks/mark-reviewed.sh"
```

它把目前 HEAD 寫進本機的 `.claude/state/review-passed`（不進版控）。有未 commit 的追蹤檔案時會拒絕，先 commit。之後任何新 commit 都會讓紀錄失效（只動 `docs/spectra/` 的歸檔 commit 除外），修正完要重審並重新記錄。順序是：實作 → review → 歸檔 → 開 PR；程式碼的範圍定義在 `.claude/hooks/lib.sh` 的 `CODE_RE`。有阻擋或重要問題時**不要記錄**，交給 `review-findings`。
