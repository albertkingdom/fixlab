## Why

第一次完整實驗（第 19 篇）裡，Qwen3.5-9B 在沒有 `run_tests` 的條件下 40 次全部撞到步數上限（20 步），一次都沒有自己宣告完成；其中 12 次在上限前其實已經改完。步數上限 20 是階段 1 訂的初始值，沒有用資料校準，所以我們分不出「它真的停不下來」還是「只是步數不夠」。

要回答這個問題，必須能在同一個實驗裡只改步數上限、其他條件不動。但實驗執行器（`python -m fixlab.bench run`）目前沒有任何地方可以設定步數上限：`--max-steps` 只有 `fixlab` 自己有，執行器呼叫 `fixlab` 時從來不傳。

對應 JD：評估、Telemetry、實驗框架（工作 5、加分 1）——讓實驗條件可以逐項控制，是實驗框架的基本能力；Prompt／Context Engineering（加分 1）——步數上限也是 agent 行為的參數之一。

## What Changes

- 模型設定檔（`bench/models.json` 的格式）每個模型多一個**選填**欄位 `max_steps`（正整數）。
- 執行器組 `fixlab` 命令列時，模型有寫 `max_steps` 就加上 `--max-steps N`；沒寫就完全不傳，行為與現在相同，既有的設定檔與 160 次結果不受影響。
- 設定檔載入時檢查 `max_steps`：不是正整數就以設定錯誤拒絕，訊息指出是哪個模型。
- 步數上限本來就會記進事件檔的 `run_start`（`max_steps` 欄位），不需要新增記錄。

## Non-Goals (optional)

- 不在 `run` 指令加 `--max-steps` 選項。那會讓所有模型共用同一個值，但實驗需要「同一個模型不同上限」或「不同模型不同上限」，放在模型設定裡才能各自指定，也才會跟其他模型設定一起留在檔案裡。
- 不改 `fixlab` 的預設步數上限（`DEFAULT_MAX_STEPS = 20`）。要不要改預設值，等實驗結果再決定，另開變更。
- 不自動校準步數上限。
- 不重跑第一次完整實驗的 160 次，也不改動它的結果。
- 不在這個變更裡跑實驗或寫實驗結果；實驗用新的設定檔與新的輸出資料夾進行，結果之後補進 `docs/benchmark-results.md`（註明是後續實驗）。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `experiment-runner`: 模型設定的欄位多了選填的 `max_steps`，以及執行器如何把它傳給 `fixlab`、不合法時如何拒絕。

## Impact

- Affected specs: `experiment-runner`（modified）
- Affected code:
  - Modified: `fixlab/bench/runner.py`（`ModelConfig`、`load_models`、`fixlab_arguments`）
  - Modified: `fixlab/bench/report.py`（報告的實驗設定一節顯示每個模型的 `max_steps`；沒設定顯示「預設」）
  - Modified: `tests/test_bench_runner.py`
  - Modified: `tests/test_bench_report.py`
  - Modified: `README.md`（模型設定欄位的說明）
  - Modified: `docs/articles/18-experiment-runner.md`（模型設定一節補一句 `max_steps`）
  - New: none
  - Removed: none
