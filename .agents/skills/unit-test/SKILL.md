---
name: unit-test
description: "替 fixlab 的變更撰寫或修改測試：測試放哪裡、用劇本假模型（FakeClient）驗證 agent 迴圈而不呼叫真實 LLM、timelog 範例專案與 tmp_path 工作區、規格對應註解、golden trace 的重新產生規則、沙箱測試的平台限制、benchmark 題目的自我檢查。當使用者說「寫測試」「補測試」「加單元測試」「測試怎麼寫」，或實作新行為、修 bug、處理 review 發現的問題需要測試時使用。"
---

# 測試（fixlab）

**測試不得呼叫真實模型、不連網、不需要金鑰。** agent 迴圈用「寫好劇本的假模型」驗證；真模型的行為屬於 benchmark，不屬於單元測試。

## 跑法

```bash
.venv/bin/python -m pytest -q                        # 全部，約 2 分鐘
.venv/bin/python -m pytest tests/test_loop.py -q     # 單檔
.venv/bin/python -m pytest -q -k "step_limit"        # 依名稱
.venv/bin/python -m fixlab.bench check               # benchmark 題目自我檢查（不花錢）
```

CI 在 macOS 跑（`pip install -e '.[mcp]'`），因為沙箱只在 macOS 啟用。`pyproject.toml` 的 `norecursedirs` 排除了 `tests/fixtures` 與 `bench/problems`：那裡是給 agent 修的專案，測試本來就會失敗，**不能被收集**，新增這類目錄時要確認沒被收集。

## 放哪裡、怎麼命名

- `tests/test_<模組名>.py` 對應 `fixlab/<模組名>.py`；benchmark 相關是 `test_bench_*.py`。
- **檔案開頭用註解寫它驗證哪份規格**，例如 `# agent 迴圈的單元測試：對應 agent-loop 規格`（`test_loop.py`、`test_isolation.py` 這樣寫）；需要時在個別測試上方用 `# 規格：<Requirement 名稱>` 標出對應的 Requirement（`test_trace_golden.py` 這樣寫）。不是每個檔案都有對應的規格（例如 `test_cli.py`、`test_packaging.py`）。
- 測試名稱寫「在什麼情況下，會怎樣」；一個行為一個測試，邊界值（剛好等於上限、空輸入）各自一個。
- 註解用繁體中文，識別字用英文。

## 常用的測試替身

| 需求 | 做法 | 範例 |
|---|---|---|
| 驗證 agent 迴圈 | `FakeClient(replies)`：依序回傳劇本裡的回覆，並記下每次請求收到的對話與工具清單；劇本項目可以是例外物件（含 `KeyboardInterrupt`）。用 `native(name, **args)` 造原生 tool call | `tests/test_loop.py` |
| 需要一個工作區 | `Workspace(tmp_path)`，或複製範例專案：`copy_fixture(tmp_path)`（`tests/fixtures/timelog`，含已知的 bug 與修法 `BUGGY`／`FIXED`） | `test_tools.py`、`test_fixture.py` |
| openai 的例外 | 用 `openai.APIConnectionError` 等自己造，需要 `httpx` 的 Request／Response（openai 3.x 用 `httpx2`，測試檔有相容的 import） | `test_loop.py` |
| 檔案系統 | 一律 `tmp_path`，不寫到專案目錄、不依賴 `~/.fixlab` | |
| 環境變數 | `monkeypatch.setenv`，不依賴開發機的設定 | |
| MCP | `tests/mcp_echo_server.py` 這個本機 stdio 假 server | `test_mcp_tools.py` |

## 寫什麼

1. **新行為**：先寫測試，確認它**會失敗**且原因正確，再實作。
2. **修 bug／處理 review 意見**：先寫能重現的測試，確認失敗，再修；commit 訊息 `fix(review): ...`（見 `review-findings`）。
3. **安全邊界**要寫「該擋」與「不該擋」成對的案例：路徑穿越（`../`、絕對路徑、`~`、符號連結）與正常路徑；測試檔唯讀與一般檔案可改。
4. **保險機制**（步數上限、連續失敗上限）要驗證觸發，也要驗證沒觸發時不會誤停。
5. **Golden trace**：`tests/golden/trace_golden.json` 是迴圈行為的基準，包含完整對話、工具清單與每筆 trace。只有**刻意改變行為**時才重新產生：

   ```bash
   UPDATE_GOLDEN=1 .venv/bin/python -m pytest tests/test_trace_golden.py
   git diff tests/golden/
   ```

   逐處確認 diff 都是你要的才 commit，commit 訊息說明為什麼行為變了。**不手改 golden，也不為了讓測試通過而重新產生。**
6. **Benchmark 題目**：新增或修改題目要同時通過 `fixlab.bench check`（原始專案與標準解的測試結果、重跑不 flaky、失敗輸出不點名 bug 檔）。**不為了讓數字好看而改題目**；任何調整寫進結果報告。

## 平台

沙箱測試只有 macOS 會真的執行。在其他平台寫沙箱相關測試時，用 `skipif` 並寫明原因，不要讓它在 Linux 上默默通過。

## 不要做

- 不放真實金鑰、真實模型輸出的長篇內容；假模型的劇本要短、要能看懂。
- 不為了讓測試通過而放寬斷言或刪掉案例；測試與規格衝突時，改程式或另開 Spectra change。
- 不依賴測試執行順序；不 `sleep` 等待，需要時間就注入時鐘（`EventLog` 的 `now` 參數可注入）。

## 完成前

全部測試通過再回報；寫清楚實際執行了哪些、哪些被 skip 與原因，以及是否在 macOS 跑過沙箱測試。
