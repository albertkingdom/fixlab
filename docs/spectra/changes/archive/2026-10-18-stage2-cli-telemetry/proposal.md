## Why

階段 1 已經能跑完「找、改、驗證」，但每次執行只在畫面上印幾行，什麼都沒留下；階段 3 要統計修好率、步數、token、費用與假通過，沒有執行記錄就沒有資料來源。同時 `fixlab` 只有一次性的 `fixlab PATH`，沒有人在旁邊授權，也不能接續上一句話繼續改。階段 2 補上這兩塊：把每次執行寫成事件檔，並加上互動模式與寫入前的權限提示。

## What Changes

- 新增事件記錄：每次執行（一次性或互動 session）寫一個 `events.jsonl`，有 `run_start`、`task_start`、`trace`、`task_end` 四種事件；一次性執行與互動模式都寫。
- 每步紀錄補三個欄位：回覆是否被截斷、回覆原本帶了幾個工具呼叫（含不合法的）、寫入唯讀檔案的嘗試（`protected_write` 旗標）。
- 新增互動模式 `fixlab PATH -i`：讀取使用者輸入，同一個 session 內保留對話，不跨 session 保存；`/reset` 清空對話、`/exit` 離開；Ctrl-C 中斷時丟棄這一個任務的訊息，讓對話保持可用。
- `run_agent` 可以接續既有的 `messages`；沒傳時行為與階段 1 完全相同。結束時把模型最後的回覆也加進對話，下一個任務才接得上。
- 新增權限提示：Workspace 多一個 `confirm(工具名稱, 參數)` 參數，預設全部放行；互動模式在 `edit_file`、`write_file`、`run_tests` 前問 y／a／N。使用者拒絕的呼叫回傳 `ok=false` 與 `denied` 旗標，計入連續失敗。
- 新增 `--log-dir`（預設 `~/.fixlab/runs`）與 `--meta KEY=VALUE`（把量化方式、context 長度這類無法自動取得的實驗條件記進 `run_start`）。
- 最後一項任務更新 README：狀態表加 tag 欄、新指令與選項、事件檔欄位說明、已知限制；完成後打 tag `stage-2`。

## Non-Goals

- 不做跨 session 的記憶，也不限制單一 session 內歷史的長度；等有事件記錄看到實際長度再決定。
- 不放進沙箱放行家目錄下的 Python、逾時後清理孤兒行程、重複呼叫偵測；這些是階段 1 code review 與實跑後延後的項目，重複呼叫偵測要先用事件檔看資料再決定。
- 不做測試檔指紋偵測（階段 3）；階段 2 只記錄「寫入唯讀檔案的嘗試」。
- 不做費用計算：事件檔只記 token，單價會變，由階段 3 的彙整腳本換算。
- 不做串流輸出、斜線指令以外的選單，也不做 Web UI。
- 不做彙整報告；事件檔的消費者是階段 3。

## Capabilities

### New Capabilities

- `run-telemetry`: 每次執行寫一個 JSONL 事件檔，記錄執行條件、每步紀錄與每個任務的結果。
- `interactive-session`: 互動模式，同一個 session 內連續下指令並保留對話，支援 `/reset`、`/exit` 與中斷。
- `tool-permissions`: 寫入前的權限提示與拒絕的處理，由入口決定要不要提示。

### Modified Capabilities

- `agent-loop`: `run_agent` 可接續既有對話；每步紀錄多截斷與原始呼叫數；被拒絕的呼叫計入連續失敗與計數器。
- `workspace-isolation`: 寫入唯讀檔案被擋時多一個 `protected_write` 旗標，讓事件檔分得出「碰了測試檔」與「路徑逃逸」。

## Impact

- Affected specs:
  - New: docs/spectra/specs/run-telemetry/spec.md
  - New: docs/spectra/specs/interactive-session/spec.md
  - New: docs/spectra/specs/tool-permissions/spec.md
  - Modified (增加需求): docs/spectra/specs/agent-loop/spec.md
  - Modified (增加需求): docs/spectra/specs/workspace-isolation/spec.md
- Affected code:
  - New: fixlab/telemetry.py
  - New: tests/test_telemetry.py
  - New: tests/test_interactive.py
  - Modified: fixlab/cli.py
  - Modified: fixlab/loop.py
  - Modified: fixlab/workspace.py
  - Modified: tests/test_loop.py
  - Modified: tests/test_cli.py
  - Modified: tests/test_isolation.py
  - Modified: tests/test_trace_golden.py
  - Modified: README.md
  - Modified: AGENTS.md
  - Removed: （無）
- 對應 JD：評估、Telemetry、實驗框架（工作 5、加分 1）靠事件記錄；CLI AI Assistant（工作 8、加分 3）靠互動模式與權限提示。
