## 1. 直譯器選擇與基底檢查

- [x] 1.1 依「直譯器只由使用者指定，不自動偵測」與 The command line chooses the test interpreter，改寫 fixlab/interpreter.py 的 choose_interpreter：只看 `--python` 與 sys.executable，含路徑分隔符號時轉成絕對路徑（不解析連結），裸名稱用 shutil.which；tests/test_interpreter.py 先改寫測試涵蓋 option、default、相對路徑、裸名稱、專案 `.venv` 不被選用並確認失敗，再實作到通過。
- [x] 1.2 [after: 1.1] 依「基底 Python 從 pyvenv.cfg 讀並嚴格檢查，每個 Workspace 只算一次」與 The sandbox allows the test interpreter and its base Python，find_base 加入 root、project_root、deny_read 參數與五種拒絕（home 非絕對、沒有標準函式庫、家目錄或上層、與工作目錄或專案目錄或 deny_read 重疊）；測試逐項涵蓋規格的 pyvenv.cfg 表格，先失敗再通過。

## 2. 沙箱與唯讀

- [x] 2.1 [after: 1.2] Workspace 建立時計算 environment 與 base 並存成屬性，wrap_command 改為接收 base、不再自行重算，run_tests 傳入 ws.base；保留既有「基底在家目錄底下可執行、家目錄其餘部分仍拒絕」的沙箱測試並改用新介面，確認全部通過。
- [x] 2.2 [after: 2.1] 依「工作目錄內的測試環境唯讀」與 The test environment inside the workspace is read-only，沙箱在環境位於工作目錄內時拒絕刪除、改名環境目錄與它在工作目錄內的每一層上層；tests/test_isolation.py 新增 protect_tests 關閉時改名 `tools`（環境為 tools/env）被拒，以及建立指向環境內檔案的 hard link 被拒，先失敗（改名）再通過。

## 3. CLI、benchmark 與事件檔

- [x] 3.1 [after: 2.2] 依「啟動前檢查用與 run_tests 完全相同的沙箱」與 The test interpreter is checked before the run starts，check_interpreter 改為接收 Workspace、用同一個沙箱設定、解析帶「FIXLAB-CHECK」前綴的版本行、拒絕包含工作目錄的環境；CLI 把檢查移到其他參數檢查與 Workspace 建立之後、事件檔之前，並移除 `.venv` 偵測。tests/test_cli.py 涵蓋專案 `.venv` 不被使用、相對 `--python`、啟動雜訊不影響檢查、環境包含工作目錄被拒，並保留既有的不存在、舊版本、缺 pytest 測試，先失敗再通過。
- [x] 3.2 [after: 3.1] 依「事件檔記錄測試直譯器」與 run_start records the test interpreter，以 `--python` 指定環境時 run_start 的 test_python 記錄絕對 path、source=option 與 base；在 tests/test_cli.py 驗證。
- [x] 3.3 [after: 3.1] 依「benchmark 固定用 fixlab 自己的直譯器」與 The benchmark uses fixlab's own interpreter，確認執行器傳入 `--python sys.executable` 且 run_start 記錄 source=option；tests/test_bench_runner.py 改寫原本依賴 `.venv` 偵測的測試。

## 4. 文件與驗證

- [x] 4.1 [after: 3.3] 依「README 對外說明信任模型」更新 README.md：安裝與選項段落說明 `--python` 用法與信任模型（指定等於信任該環境、基底目錄會被放行讀取）、為什麼不自動偵測 `.venv`；安全段落與已知限制同步；以內容審查對照本變更的三份規格驗證。
- [x] 4.2 [after: 4.1] 執行完整 pytest；在家目錄底下的暫存專案以 uv 管理的 Python 3.12 建立 `.venv`（含 pytest 與一個第三方套件），用 `--python .venv/bin/python` 啟動並送 EOF 確認 run_start 的 test_python，再用該 Workspace 直接呼叫 run_tests（不呼叫模型）確認在沙箱中匯入第三方套件並回報真實結果；另確認沒有 `--python` 時 `.venv` 不被執行。把結果記錄在本檔的驗證紀錄。

## 驗證紀錄

- 2026-10-20：第一版（自動偵測 `.venv`）實作後的 code review 與 Codex 交叉檢查發現：專案控制的 pyvenv.cfg 能讓沙箱放行 ~/.ssh、偵測到的直譯器在確認前被執行、檢查用的沙箱較寬鬆等問題。依使用者決定縮小範圍為只支援 `--python`，規格、設計、任務改寫後重新實作。
- 每項任務的新測試都先確認失敗再實作。重現過的問題：家目錄底下的 uv 管理 Python 3.12 在沙箱中出現 dyld Library not loaded（file system sandbox blocked open()）；protect_tests 關閉時可改名環境的上層資料夾。hard link 指向環境內檔案在建立時即被拒（加測試鎖住）。實作時發現 Homebrew 的標準函式庫位於 Frameworks/Python.framework/Versions/3.N/lib，標準函式庫檢查一併接受。
- 完整 pytest 609 passed。
- code review 第二輪後（只支援 --python 的版本）修正：環境經過專案內的符號連結時拒絕；只有 venv 才放行環境目錄；基底改由直譯器的真實位置推算（跟得過 ~/.local/bin 捷徑資料夾）；基底包含 fixlab 自己的安裝位置時允許；沒有沙箱時不計算基底；PATH 找到的相對路徑轉成絕對路徑；基底的失敗結果也只算一次；wrap_command 的 base 必填。新增測試皆先確認失敗。
- 以家目錄底下的暫存專案驗證（.venv 由 uv 管理的 Python 3.12 建立，裝 pytest 與 attrs，程式 import attrs）：
  - `--python .venv/bin/python` 啟動互動模式並送 EOF：run_start 的 test_python 為 path=<proj>/.venv/bin/python、source=option、base=~/.local/share/uv/python/cpython-3.12.3-macos-aarch64-none。
  - 以該環境建立 Workspace（protect_tests 開啟），check_interpreter 通過後呼叫 run_tests（未呼叫模型）：sandbox on，pytest 匯入 attrs 並回報真實的 1 failed。
  - 不加 `--python` 啟動：test_python.source 為 default；把 .venv/bin/python 換成會留下記號檔的腳本，記號檔沒有出現，確認專案的 .venv 沒有被執行。
  - 驗證後刪除暫存目錄。
- code review 第三輪（連續三輪有阻擋）後依使用者決定改成單一規則：直譯器的連結鏈經過專案時，只能在一個真的 venv 資料夾內；沒有 pyvenv.cfg 的環境照樣禁止寫入；非 venv 直譯器不因環境位置被拒；放行讀取的 venv 不得與 deny_read 重疊。重現的兩種攻擊都寫成測試。完整 pytest 626 passed。
- code review 第四輪後與 Codex 討論，只修必要的三筆：環境與工作目錄的包含判斷改用檔案系統身分（大小寫不同的路徑，工具層與沙箱的改名保護都會失效，已重現）；放行讀取的 venv 不得是或包含 fixlab 自己的目錄（site-packages 內的安裝除外）。另兩筆記在 design.md 的 Risks。完整 pytest 631 passed。
- code review 第五輪後與 Codex 討論，只修必要的兩筆：find_base 的重疊與家目錄判斷改用檔案系統身分（大小寫不同的 --python 能讓測試讀到 fixlab 的 .env，已重現）；基底包含 fixlab checkout（不在 site-packages）時拒絕。另兩筆記在 design.md 的 Risks。完整 pytest 634 passed。
