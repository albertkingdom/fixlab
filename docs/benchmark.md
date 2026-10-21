# Benchmark 操作

[回到首頁](../README.md)

先依[開發指南](development.md)建立環境；結果與實驗條件見[實驗報告](benchmark-results.md)。

8 道題在 `bench/problems/`，每題一個資料夾（給 agent 的 `project`、藏起來的 `hidden/fix` 與 `hidden/keep`、標準解 `solution`、`problem.json`）。在 fixlab 原始碼根目錄執行，指令都是 `.venv/bin/python -m fixlab.bench ...`（若已啟用該虛擬環境，可簡寫為 `python -m fixlab.bench ...`）：

**正式實驗 `run --confirm` 必須在 macOS 且 `sandbox-exec` 可用時執行**，否則會被拒絕，以免 agent 跑測試時讀到隱藏測試。未加 `--confirm` 的計畫預覽不需要沙箱。`check`、`grade` 在沒有沙箱時仍可執行，但測試程式不受沙箱保護。

| 指令 | 做什麼 | 花錢嗎 |
|---|---|---|
| `check [題目...] [--repeat N]` | 題目自我檢查：原始專案與套上標準解後各組測試的結果、重跑看會不會 flaky、失敗輸出不能點名 bug 檔 | 不花錢，只跑 pytest；全部 8 題約 2 分鐘 |
| `grade 題目 工作目錄` | 在乾淨的暫存目錄用原版測試與隱藏測試評分，印 JSON（`fixed`、`broke_existing`、`overfit`、`invalid`） | 不花錢 |
| `run --models bench/models.json --out 資料夾` | 展開（題目、模型、條件、次數）；沒有 `--confirm` 只印計畫；有 `--confirm` 才真的呼叫模型，可續跑 | **加 `--confirm` 才會花錢**；2026-10-18 的 160 次實驗約 $0.41、59 分鐘，見[結果報告](benchmark-results.md)，重跑的費用與時間會隨模型、價格及回覆而變 |
| `report results.jsonl --models bench/models.json` | 把結果變成 markdown 報告 | 不花錢 |

`bench/models.json` 的每個模型可以寫選填的 `max_steps`（1 以上的整數）：這個模型每次執行的步數上限，兩個條件用同一個值。沒寫（或寫 `null`）就用 fixlab 自己的預設 20；寫成 0、負數、小數、字串或 `true` 會在載入時被拒絕，一次都不跑。

同樣可以寫選填的 `system_prompt_extra`（有看得見的字的字串，或 `null`）：這個模型每次執行都在預設 system prompt 後面接這段文字，兩個條件傳同一段，用來做 prompt 的消融實驗；沒寫就是預設 prompt。寫成數字、`true`、清單、空字串或只有空白，會在載入時被拒絕，一次都不跑。

教學文章第 15 到 19 篇依序說明題目、評分器、自我檢查、實驗執行器與結果；第 20 篇是後續實驗，找出 Qwen 沒有 `run_tests` 時停不下來的原因。
