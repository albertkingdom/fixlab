## 1. 先寫測試（實作前應該先失敗）

- [x] 1.1 在 `tests/test_bench_runner.py` 為需求「A model entry can set the step limit of its runs」寫 `fixlab_arguments` 的測試：模型有 `max_steps: 40` 時，`with_tests` 與 `no_tests` 兩個條件的參數都含 `--max-steps` 接著 `40`；模型沒有該欄位時參數裡沒有 `--max-steps`。驗證：`.venv/bin/python -m pytest tests/test_bench_runner.py -k "step_limit or max_steps"` 在實作前失敗、實作後通過。
- [x] 1.2 在同一個測試檔為 `load_models` 寫參數化測試：`max_steps` 為 0、-5、2.5、"40"、true 時拋出 `ConfigError`，訊息含模型 label 與該值；為 1 和 40 時正常載入且 `ModelConfig.max_steps` 等於該值；沒寫時為 `None`。驗證：同上，指令加 `-k "step_limit or max_steps"`。
- [x] 1.3 寫一個用假 client 的端到端測試：模型設定 `max_steps: 3`，假模型每步都呼叫工具，這次執行的 `results.jsonl` 那一行 `stop_reason` 為 `max_steps`、`steps` 為 3，事件檔 `run_start` 記錄 `max_steps` 為 3。驗證：`.venv/bin/python -m pytest tests/test_bench_runner.py -k "step_limit or max_steps"`。

## 2. 實作

- [x] 2.1 `fixlab/bench/runner.py` 的 `ModelConfig` 多一個選填欄位 `max_steps`（預設 `None`），`load_models` 讀入並檢查：只接受 ≥ 1 的整數，布林要特別排除（Python 的 `True` 也算整數）。不合法就拋 `ConfigError`，訊息寫出模型 label 與值。驗證：任務 1.2 的測試通過。
- [x] 2.2 `fixlab_arguments` 在 `max_steps` 不是 `None` 時加上 `--max-steps N`，兩個條件都加；是 `None` 時完全不加。驗證：任務 1.1 與 1.3 的測試通過。
- [x] 2.3 跑完整測試，確認沒弄壞既有行為（特別是沒有 `max_steps` 的既有設定檔，參數與以前完全相同）。驗證：`.venv/bin/python -m pytest -q` 全部通過，且 `.venv/bin/python -m fixlab.bench run --models bench/models.json --out /tmp/plan-check` 印出的計畫仍是 160 次、不呼叫模型。

- [x] 2.4 需求「The report states the settings of each model」：報告的「實驗設定」一節顯示每個模型的 `max_steps`，沒設定時顯示「預設」，設定取自模型設定檔，讓不同模型或同一模型用不同上限的實驗看得出來（code review 第二輪發現）。驗證：`.venv/bin/python -m pytest tests/test_bench_report.py -k step_limit` 通過。

## 3. 文件

- [x] 3.1 `README.md` 的模型設定說明補上選填的 `max_steps`（意思、合法值、沒寫時用 fixlab 預設的 20）。驗證：內容審閱，欄位名稱與規格一致。
- [x] 3.2 `docs/articles/18-experiment-runner.md` 的「設定檔」一節補一句 `max_steps`：為什麼要放在模型設定裡（同一個實驗可以只改步數上限）。驗證：內容審閱，用白話寫、先講情境再講欄位。

## 4. 收尾檢查

- [x] 4.1 `spectra validate runner-max-steps` 通過；`spectra analyze runner-max-steps` 沒有 Critical 與 Warning。驗證：兩個指令的輸出。
- [ ] 4.2 依 AGENTS.md 完成 code review，blocking 與 important 問題都解決後才歸檔。驗證：review 結果（依 `review-findings` skill 處理）。
