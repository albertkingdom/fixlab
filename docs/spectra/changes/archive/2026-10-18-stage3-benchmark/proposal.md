## Why

階段 1、2 做出了能修 bug 的 agent 與事件記錄，但目前只有一個範例專案（timelog）、一個模型、少數幾次實跑，說不出任何有根據的結論。這個專案想回答的問題是：agent 能不能用測試自己驗證？它會不會假裝修好（假通過）、會不會弄壞原本正常的功能？要回答，需要一組固定的題目、一個可信的評分方式，以及可重複的實驗與彙整報告。

## What Changes

- 新增 8 題多檔 Python bug 題目，每題一個不同的小領域（庫存、行事曆、設定載入、金額、訂閱到期、分頁、排程、權限）。每題是一個小專案（3 到 5 個模組），有 1 到 2 個失敗的可見測試、1 到 3 個干擾檔，並附規格（寫明正確行為）。可見測試只斷言整個輸出，不指出 bug 所在的檔案。
- 每題的隱藏測試放在題目目錄，不複製進 agent 的工作目錄，分兩組：fix（bug 真的修好）與 keep（既有行為沒壞）。
- 新增評分器：在乾淨的暫存目錄裡，用 agent 改完的原始碼加原版測試跑隱藏測試。結果是四個獨立旗標：fixed、broke_existing、overfit（可見測試過但 fix 組沒過）、invalid（動了測試或設定檔，優先於其他判定）。沒有 run_tests 的條件另外記「宣稱完成但隱藏測試沒過」。
- 新增題目自我檢查（不花任何 LLM 費用）：原始 bug 時 fix 組一定失敗且 keep 組一定通過、標準解全部通過、重跑 20 次結果不變、可見測試的失敗輸出不含 bug 所在檔案名。
- 新增實驗執行器：有或沒有 run_tests 兩個條件，system prompt 一致、只差工具；每個（題目、模型、條件）跑 5 次；執行前先顯示計畫與次數，需要明確確認才會真的呼叫模型。
- fixlab 命令列新增三個選項：隱藏工具（讓模型看不到某個工具）、temperature、額外的請求參數（用來固定 OpenRouter 的供應商與思考模式）。事件檔的 run_start 記下這三者。
- 新增彙整報告：修好率、假通過、弄壞既有行為、步數、token 與成本、每修好一題的成本、同題成對比較的差異與信賴區間、失敗 trace 實例。結論只寫「在這組題目上觀察到」。
- 文件：每個里程碑一篇教學文章（接在第 14 篇之後），用白話與圖說明，附真實輸出。AGENTS.md 與 README 的題數已由 15 到 20 題改為 8 題左右，結果報告要註明這項調整。

## Non-Goals

- 測試檔指紋偵測、system prompt 規則消融、tool output 截斷實驗、步數與連續失敗上限的校準：有餘力再做，不在這個變更內。
- 多 agent 對照與 Connector：屬於階段 4。
- 防止被測程式偽造結果：被測程式與 pytest 在同一個行程，可以印假的摘要再以 0 離開。這個變更只用固定參數、乾淨環境重跑與案例數比對降低風險，不宣稱根治，報告要寫明。
- 模型排名：8 題的樣本不足以排名，報告只描述這組題目上的觀察。
- 自動化的雲端或批次排程：實驗一律由使用者明確啟動。

## Capabilities

### New Capabilities

- `benchmark-problems`: 題目的資料格式、隔離規則、規格要求，以及題目自我檢查。
- `benchmark-grader`: 在乾淨環境對 agent 的成果評分，輸出獨立旗標。
- `experiment-runner`: 依題目、模型、條件與次數執行實驗，記錄實驗條件，執行前確認。
- `experiment-report`: 讀取實驗結果與事件檔，產出彙整報告。

### Modified Capabilities

- `agent-tools`: 工具可以被隱藏，隱藏的工具不給模型，也不能被模型呼叫，但程式本身仍可呼叫。
- `run-telemetry`: run_start 記下隱藏的工具、temperature 與額外的請求參數。

## Impact

- Affected specs: benchmark-problems、benchmark-grader、experiment-runner、experiment-report（新增）；agent-tools、run-telemetry（修改）。
- Affected code:
  - New: `bench/problems/`（8 個題目資料夾）、`fixlab/bench/__init__.py`、`fixlab/bench/__main__.py`、`fixlab/bench/problems.py`、`fixlab/bench/grader.py`、`fixlab/bench/selfcheck.py`、`fixlab/bench/runner.py`、`fixlab/bench/report.py`、`tests/test_bench_problems.py`、`tests/test_bench_grader.py`、`tests/test_bench_selfcheck.py`、`tests/test_bench_runner.py`、`tests/test_bench_report.py`、`docs/articles/`（第 15 篇起的教學文章與圖）
  - Modified: `fixlab/cli.py`、`fixlab/workspace.py`、`README.md`、`AGENTS.md`、`docs/articles/10-protect-tests.md`
  - Removed: 無
