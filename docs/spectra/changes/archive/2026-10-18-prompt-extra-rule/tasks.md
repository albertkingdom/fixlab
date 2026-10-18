## 1. 先寫測試（實作前應該先失敗）

- [x] 1.1 在 `tests/test_loop.py` 為需求「The system prompt can carry extra text」寫測試：沒有 `messages` 時，第一個請求的 system message 是預設 prompt、一個空行、額外文字；沒給額外文字時請求與以前相同；傳入已有內容的 `messages` 時不新增第二則 system 訊息。驗證：`.venv/bin/python -m pytest tests/test_loop.py -k system_prompt_extra` 在實作前失敗、實作後通過。
- [x] 1.2 在 `tests/test_cli.py` 為需求「The system prompt can be extended from the command line」寫測試：給 `--system-prompt-extra` 時 `run_start` 記錄原文且第一個請求的 system message 以它結尾；沒給時 `run_start` 是 `null`；`""` 與 `"   "` 以退出碼 2 結束、訊息點名選項、沒有事件檔；`" a "` 被接受；互動模式的第一個任務也帶著它。驗證：`.venv/bin/python -m pytest tests/test_cli.py -k system_prompt_extra`。
- [x] 1.3 在 `tests/test_bench_runner.py` 為需求「A model entry can add text to the system prompt」寫測試：兩個條件的參數都含 `--system-prompt-extra` 與同一段文字、其餘只差條件 meta 與隱藏工具；沒寫或寫 `null` 時參數裡沒有它；5、`true`、`["a"]`、`""`、`"   "` 在載入時拋 `ConfigError`，訊息有模型標籤與值；用假 client 跑一次，`run_start` 與第一個請求都帶著該文字。驗證：`.venv/bin/python -m pytest tests/test_bench_runner.py -k system_prompt_extra`。
- [x] 1.4 在 `tests/test_bench_report.py` 為需求「The report states the extra system prompt of each model」寫測試：有設定的模型那一行含 `system_prompt_extra` 加上原文，沒設定的顯示 `system_prompt_extra 無`。驗證：`.venv/bin/python -m pytest tests/test_bench_report.py -k system_prompt_extra`。

## 2. 實作

- [x] 2.1 `fixlab/loop.py` 的 `run_agent` 多一個關鍵字參數 `system_prompt_extra`（預設 `None`），只在對話是空、要放入 system prompt 時使用；預設 prompt 的文字不改。這是設計決定「由 `run_agent` 的新參數組 prompt，不由命令列組好再傳 `messages`」與「接在預設 prompt 後面，不整段替換」。驗證：任務 1.1 的測試通過，且 `tests/test_trace_golden.py` 仍通過。
- [x] 2.2 `fixlab/cli.py` 多選項 `--system-prompt-extra`，空字串或只有空白時以退出碼 2 結束（設計決定「空字串視為錯誤，不是「沒給」」），一次性與互動模式的每次 `run_agent` 呼叫都傳它，`run_conditions` 記錄 `system_prompt_extra`。驗證：任務 1.2 的測試通過。
- [x] 2.3 `fixlab/bench/runner.py` 的 `ModelConfig` 多選填欄位 `system_prompt_extra`，`load_models` 檢查（非空白字串或 `null`，其他拋 `ConfigError`），`fixlab_arguments` 有值就為兩個條件都傳同一段（設計決定「放在模型設定檔，不放 `run` 指令」與「兩個條件傳同一段文字」）。驗證：任務 1.3 的測試通過。
- [x] 2.4 `fixlab/bench/report.py` 的實驗設定一節，每個模型那一行加上 `system_prompt_extra` 與原文或「無」。驗證：任務 1.4 的測試通過。
- [x] 2.5 跑完整測試，確認沒弄壞既有行為。驗證：`.venv/bin/python -m pytest -q` 全部通過，且 `.venv/bin/python -m fixlab.bench run --models bench/models.json --out /tmp/plan-check-2` 印出的計畫仍是 160 次、不呼叫模型。

## 3. 文件

- [x] 3.1 `README.md` 補上 `--system-prompt-extra` 與模型設定的選填欄位 `system_prompt_extra`：意思、合法值、沒寫就是預設 prompt、文字會接在預設 prompt 後面。驗證：內容審閱，名稱與規格一致。

## 4. 收尾檢查

- [x] 4.1 `spectra validate prompt-extra-rule` 通過；`spectra analyze prompt-extra-rule` 沒有 Critical 與 Warning。驗證：兩個指令的輸出。
- [x] 4.2 依 AGENTS.md 完成 code review，blocking 與 important 問題都解決後才歸檔。驗證：review 結果（依 `review-findings` skill 處理）。
