## Why

實驗 A、B（見 docs/benchmark-results.md 的〈後續實驗〉）排除了「量化」和「步數上限太小」：Qwen3.5-9B 在沒有 `run_tests` 時，48 次全部沒有自己宣告完成，多出來的步數都花在重複的 `grep`。剩下兩個沒分開的原因：模型本身的行為，或 system prompt 的停止條件（「有把握修對了就回覆結束」，沒有測試就沒辦法有把握）。

要分開這兩個，必須只改 prompt、其他條件不動，看它會不會停。但 system prompt 是 `fixlab/loop.py` 裡的常數，沒有任何地方可以在不改預設值的情況下加一句話。直接改常數會同時改掉所有之後的執行，也會讓黃金 trace 與之前 160 次的結果失去可比性。

對應 JD：Prompt／Context Engineering（加分 1）——AGENTS.md 已列「system prompt 規則消融」，這是它的最小實作；評估、Telemetry、實驗框架（工作 5）——prompt 也是實驗條件，要能逐項控制並記錄。

預定用它做實驗 C（不在這個變更裡執行）：對 Qwen3.5-9B 加上「如果沒有辦法跑測試，不要一直找證據；改完之後把改過的程式重讀一次，然後不呼叫任何工具、回一則簡短的結束訊息」，有 `run_tests` 與沒有兩個條件都加同一句。

## What Changes

- `fixlab` 多一個選填的選項 `--system-prompt-extra TEXT`：把這段文字接在預設 system prompt 後面（中間空一行）。沒傳時，送出的 system prompt 與現在一個字都不差。
- 空字串或只有空白的值視為錯誤，以退出碼 2 結束，不建立任何檔案。
- `run_start` 事件多一個鍵 `system_prompt_extra`（沒傳是 null），舊的事件檔讀者忽略不認識的鍵，schema 版本維持 1。
- 模型設定檔每個模型多一個**選填**欄位 `system_prompt_extra`（非空字串，或 null）。執行器有寫就用 `--system-prompt-extra` 傳給 `fixlab`，兩個條件傳同一段文字，所以「兩個條件只差一個工具」仍然成立。
- 報告的實驗設定一節顯示每個模型的 `system_prompt_extra`（沒有顯示「無」）。

## Non-Goals (optional)

- 不改預設的 system prompt。改了會破壞黃金 trace，也讓這次之後的結果無法與之前的 160 次比較。
- 不做「從檔案讀 prompt」或多段規則的消融框架。一段文字、一個選項就夠回答目前的問題；要更多再另開變更。
- 不在 `run` 指令加 prompt 選項。和 `max_steps` 同理：放在模型設定檔裡，才會和其他設定一起留下紀錄，也能用不同標籤並排比較。
- 不處理「同一個呼叫重複太多次」的保險（loop 的已知問題），那是另一個變更。
- 不在這個變更裡跑實驗 C，也不寫結果；實驗用新的模型標籤與新的輸出資料夾進行，結果之後補進 docs/benchmark-results.md。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-loop`: 迴圈的 system prompt 可以帶選填的額外文字；沒給時與現在相同。
- `run-telemetry`: `fixlab` 的 `--system-prompt-extra` 選項、不合法值的處理，以及 `run_start` 的 `system_prompt_extra` 鍵。
- `experiment-runner`: 模型設定的選填欄位 `system_prompt_extra`，以及執行器如何傳給 `fixlab`、不合法時如何拒絕。
- `experiment-report`: 報告的實驗設定一節顯示每個模型的 `system_prompt_extra`。

## Impact

- Affected specs: `agent-loop`、`run-telemetry`、`experiment-runner`、`experiment-report`（都是 modified）
- Affected code:
  - Modified: `fixlab/loop.py`（`run_agent` 接受額外文字）
  - Modified: `fixlab/cli.py`（選項、檢查、傳給 `run_agent`、`run_conditions`）
  - Modified: `fixlab/bench/runner.py`（`ModelConfig`、`load_models`、`fixlab_arguments`）
  - Modified: `fixlab/bench/report.py`（實驗設定一節）
  - Modified: `tests/test_loop.py`、`tests/test_cli.py`、`tests/test_bench_runner.py`、`tests/test_bench_report.py`
  - Modified: `README.md`（選項與模型設定欄位的說明）
  - New: none
  - Removed: none
