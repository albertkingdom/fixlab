## Why

run_tests 一律用 fixlab 自己的直譯器跑被修專案的測試：被修專案需要的第三方套件必須裝進 fixlab 的環境（用 uv、pipx 安裝時是隔離的環境，一般使用者很難處理）。另外沙箱擋住家目錄底下的讀取，只放行 fixlab 自己的 venv，基底 Python 在家目錄底下（uv 管理的 Python、pyenv）時 run_tests 一啟動就失敗。這兩個是 installable-package 留下的已知限制。

## What Changes

- 新增 `--python PATH` 參數，指定 run_tests 使用的直譯器（例如專案自己的 `.venv/bin/python`）。沒有指定時沿用 fixlab 自己的直譯器，行為與現在相同。
- 不自動偵測目標目錄的 `.venv`：被修的專案可能不可信，偵測等於讓專案裡的檔案決定執行什麼、沙箱放行什麼（code review 發現 pyvenv.cfg 可以讓沙箱放行 ~/.ssh，而且偵測到的直譯器會在任何確認之前被執行）。使用者用 `--python` 明確指定，代表信任那個環境。
- 沙箱改為放行「測試用直譯器的環境」與「它的基底 Python 安裝目錄」的讀取，解掉「基底 Python 在家目錄底下時 run_tests 失敗」的已知限制。基底由 pyvenv.cfg 讀出並嚴格檢查：home 必須是絕對路徑、必須是真的 Python 安裝（有標準函式庫）、不能是家目錄或上層、不能和工作目錄、fixlab 專案目錄、deny_read 重疊。每個 Workspace 只算一次。
- 啟動前（其他參數檢查之後、建立事件檔與呼叫模型之前）在與 run_tests 完全相同的沙箱裡檢查直譯器：存在、可執行、3.11 以上、匯入得了 pytest、環境目錄不包含工作目錄。失敗以結束碼 2 結束並說明原因。
- 測試用環境位於工作目錄內時，工具與沙箱都不准寫入它，也不准刪除、改名它與它在工作目錄內的上層資料夾，避免竄改環境裡的 pytest 偽造通過；不論 protect_tests 是否開啟。
- `run_start` 事件記錄實際使用的測試直譯器、來源（option、default）與基底目錄。
- benchmark 執行器明確以 `--python` 指定 fixlab 自己的直譯器。
- README（給外部讀者）說明 `--python` 的用法、信任模型（指定等於信任該環境）、為什麼不自動偵測 `.venv`，並更新已知限制。

## Non-Goals

- 不自動偵測 `.venv` 或任何專案內的環境；需要另外設計信任機制，之後另開 change。
- 不支援非 Python 或不用 pytest 的專案。
- 不在測試用環境裡自動安裝 pytest 或任何套件。
- 不改變 pytest 的啟動參數、環境變數白名單、外掛自動載入的關閉。
- 不支援 Windows 的 venv 目錄結構（Scripts/python.exe）。

## Capabilities

### New Capabilities

- `test-interpreter`: 決定 run_tests 使用哪個 Python 直譯器（只由使用者指定）、啟動前的檢查，以及 benchmark 的固定設定。

### Modified Capabilities

- `workspace-isolation`: 沙箱放行測試用環境與經過檢查的基底 Python；工作目錄內的測試用環境唯讀。
- `run-telemetry`: run_start 記錄測試直譯器、來源與基底。

## Impact

- Affected specs: test-interpreter（新增）、workspace-isolation、run-telemetry
- Affected code:
  - New: fixlab/interpreter.py, tests/test_interpreter.py
  - Modified: fixlab/cli.py, fixlab/sandbox.py, fixlab/workspace.py, fixlab/tools.py, fixlab/bench/runner.py, tests/test_cli.py, tests/test_isolation.py, tests/test_bench_runner.py, README.md
