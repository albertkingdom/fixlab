## Context

run_tests 以 Workspace.python 啟動 pytest，CLI 一律傳入 sys.executable，所以被修專案的測試在 fixlab 的環境裡跑。沙箱的 sandbox_paths 以直譯器路徑往上兩層當成 VENV 放行讀取，但沒有放行基底 Python；基底 Python 在家目錄底下（uv 管理的 Python、pyenv）時，標準函式庫與 libpython 被家目錄規則擋住（已知限制，2026-10-17 與 installable-package 驗證時都重現過 dyld 錯誤）。benchmark 的評分器直接建立 Workspace，執行器呼叫 cli.main。

第一版設計會自動偵測目標目錄的 `.venv`。實作後的 code review（本機 review 與 Codex 交叉檢查）發現兩個根本問題：專案控制的 pyvenv.cfg 可以讓沙箱放行家目錄任一子資料夾（例如 ~/.ssh），以及偵測到的直譯器在任何確認之前就被執行。因此縮小範圍：直譯器只由使用者以 `--python` 指定。設計依據是本專案自己的程式、實測與 review 結果。

## Goals / Non-Goals

**Goals:**

- 使用者可以用 `--python` 讓 run_tests 使用被修專案自己的環境，專案的依賴不用裝進 fixlab 的環境。
- 基底 Python 在家目錄底下時，run_tests 仍能在沙箱裡執行，而且沙箱不會因此放行家目錄的其他部分。
- 專案裡的檔案不能決定執行哪個直譯器；指定的環境在工作目錄內時，模型與被測的程式都改不了它。

**Non-Goals:**

- 不自動偵測專案內的環境（之後另開 change，需要先設計信任機制）。
- 不支援非 Python 或不用 pytest 的專案、不支援 Windows 的 venv 結構。
- 不自動安裝 pytest；不改 pytest 的啟動參數、環境變數白名單與外掛設定。

## Decisions

### 直譯器只由使用者指定，不自動偵測

順序只有 `--python` 與 sys.executable。不讀專案內的 `.venv`：被修的專案可能是剛 clone 的陌生程式碼，自動偵測等於讓它的檔案決定執行什麼、沙箱放行什麼。使用者打 `--python` 是明確的信任表示。`--python` 含路徑分隔符號時，以啟動 fixlab 的目錄轉成絕對路徑（不解析符號連結，venv 的 python 是連結）；裸名稱用 shutil.which 從 PATH 找。檢查、Workspace、沙箱、事件檔用同一個絕對路徑。邏輯放在 fixlab/interpreter.py 的 choose_interpreter。

### 基底 Python 從 pyvenv.cfg 讀並嚴格檢查，每個 Workspace 只算一次

基底取直譯器解析連結後的真實位置往上兩層：venv 的 python 通常是指向基底的連結，這樣也跟得過放捷徑的資料夾（~/.local/bin，此時 pyvenv.cfg 的 home 指向捷徑資料夾，取它的上一層會錯）。只有解析後仍在環境裡（以 --copies 建立的 venv）才用 pyvenv.cfg 的 home。拒絕的情況：home 不是絕對路徑（相對路徑會依 fixlab 的目前目錄解析，結果不可預期）；基底底下沒有 lib/python3.N/os.py（不是 Python 安裝，例如被寫成 ~/.ssh/bin）；基底是家目錄或上層；基底就是或位在工作目錄、fixlab 專案目錄、deny_read 之內；基底包含工作目錄或 deny_read。基底包含 fixlab 專案目錄則允許：fixlab 用 pip 裝進一般的 Python 時就在它的 site-packages 裡，放行讀取只讓測試讀得到已安裝的 fixlab 程式。標準函式庫檢查只證明「長得像 Python 安裝」，不證明可信；可信由使用者指定 `--python` 這件事負責，檢查是擋打錯字與明顯的誤設定。Workspace.base 在第一次用到時算一次，連失敗的結果一起記住；wrap_command 的 base 改為必填，不在每次 run_tests 重讀，事件檔記錄的也就是沙箱實際放行的值。沒有沙箱的平台不計算也不檢查基底（標準函式庫的位置因平台而異，Linux 有 lib64、Windows 是 Lib），事件檔記為 null。環境目錄只有在它是 venv（有 pyvenv.cfg）時才放行讀取；不是 venv 的直譯器（~/.local/bin/python3）往上兩層可能是 ~/.local，只放行基底。

### 啟動前檢查用與 run_tests 完全相同的沙箱

CLI 先完成其他參數檢查並建立 Workspace（不建任何檔案），再檢查直譯器，最後才建事件檔與 client 請求。檢查用 Workspace 的設定包同一個沙箱（相同的 WS、VENV、BASE、PROJECT、deny_read、protect_tests 與環境變數白名單），目前目錄設成私有暫存目錄，逾時 10 秒。檢查程式印出「FIXLAB-CHECK 3.N」一行再 import pytest；只解析帶前綴的那一行，啟動時其他輸出不影響。不加 -P、-E、-s：-P 舊版本不認得會連版本都印不出來，-E、-s 會和 run_tests 的搜尋路徑不一致。版本低於 3.11 或匯入失敗，就以結束碼 2 結束。環境目錄等於或包含工作目錄時也拒絕，否則所有專案檔案都會被當成環境而無法修改。從 `--python` 一路跟符號連結到真正的執行檔，經過的每個位置都必須在專案外面；唯一例外是專案裡一個真的 venv 資料夾（本身與上層都不是連結、有 pyvenv.cfg），它整個被鎖住。專案裡其他位置被測的程式都寫得到，換掉其中一個連結或執行檔，下一次 run_tests 就跑假的 Python（code review 第三輪在真的沙箱裡重現：中間經過專案裡的 scripts/py、或環境沒有 pyvenv.cfg 時寫入保護沒套上）。這一條取代前幾輪逐條補路徑的做法。沙箱另外以 ENV 參數（直譯器往上兩層，不論是不是 venv）拒絕寫入，與放行讀取的 VENV 分開。

### 工作目錄內的測試環境唯讀

Workspace 從直譯器推出環境目錄（與沙箱的 VENV 同一個計算），在 resolve_writable 擋下環境目錄底下的寫入。沙箱一律拒絕寫入 VENV；環境在工作目錄內時，另外以參數傳入 VENV 與它在工作目錄內的每一層上層，拒絕刪除、改名這些資料夾（改名上層再改回來可以繞過路徑規則）。這與 protect_tests 無關。hard link 已實測：建立指向 VENV 內檔案的連結時就被拒絕，補測試鎖住。

### benchmark 固定用 fixlab 自己的直譯器

執行器呼叫 cli.main 時加上 `--python sys.executable`，實驗用的直譯器明確寫在參數裡。評分器維持直接建立 Workspace、使用預設直譯器。

### 事件檔記錄測試直譯器

run_start 新增 test_python（path、source、base），既有的 python 欄位維持記錄 fixlab 自己的版本。schema 維持 1，因為只新增欄位。

### README 對外說明信任模型

README 是給外部讀者的：說明 `--python` 的用法、指定等於信任那個環境（它的 Python 與套件會在沙箱裡執行，基底目錄會被放行讀取）、為什麼不自動偵測 `.venv`，以及仍然存在的限制。

## Implementation Contract

- 行為：`--python PATH` 讓 run_tests 用指定的直譯器；沒給時與現在相同，專案內的 `.venv` 不會被使用也不會被執行。基底 Python 在家目錄底下時 run_tests 正常，家目錄其他部分仍讀不到。
- 介面：新參數 `--python PATH`；fixlab/interpreter.py 提供 choose_interpreter(option) 回傳 (絕對路徑, 來源)、environment_of(python)、find_base(python, root, project_root, deny_read)、check_interpreter(workspace) 在失敗時丟出 ValueError；Workspace 新增 environment 與 base 屬性；sandbox.wrap_command 改為接收 base 並在環境位於工作目錄內時加入資料夾刪除與改名的拒絕；run_start 新增 test_python。
- 失敗模式：直譯器不存在或不可執行、版本低於 3.11、匯入不了 pytest、環境包含工作目錄、pyvenv.cfg 的 home 不是絕對路徑、基底不是 Python 安裝、基底是家目錄或上層、基底與受保護目錄重疊 → 結束碼 2、印出原因、不建立事件檔、不呼叫模型。
- 驗收：tests/test_interpreter.py 涵蓋路徑正規化與 find_base 的每一種拒絕；tests/test_isolation.py 涵蓋基底在家目錄底下可執行、家目錄其餘部分仍拒絕、環境內寫入、hard link 與上層改名被拒；tests/test_cli.py 涵蓋專案 `.venv` 不被使用、相對路徑、檢查失敗的結束碼與沒有事件檔、啟動輸出雜訊不影響檢查、run_start 的 test_python；tests/test_bench_runner.py 涵蓋執行器傳入 `--python`；完整 pytest 通過；以 uv 管理的 Python 3.12 建立的專案 `.venv` 透過 `--python` 實際跑一次。
- 範圍：只改 fixlab/cli.py、fixlab/sandbox.py、fixlab/workspace.py、fixlab/tools.py、fixlab/bench/runner.py、README.md 與對應測試，新增 fixlab/interpreter.py 與 tests/test_interpreter.py。

## Risks / Trade-offs

- 不自動偵測 `.venv`：使用者要自己加 `--python .venv/bin/python` → README 說明；自動偵測留給之後另開的 change，需要先解決「確認前不執行專案程式」與「專案檔案不能擴大沙箱放行範圍」。
- 標準函式庫檢查只證明形狀：指定的環境若是惡意的，它的 Python 本來就會在沙箱裡執行；這屬於使用者指定 `--python` 時承擔的信任，README 寫明。
- 放行基底 Python 的整個安裝目錄：對 uv 或 pyenv 是單一版本的目錄，影響有限。
- 被修專案的環境要有 pytest、Python 要 3.11 以上：不符合時啟動失敗並說明，不自動安裝、不改用其他直譯器。
- 啟動前檢查會先建立 Workspace 再執行一次直譯器，每次啟動多一次沙箱內的程序；benchmark 每次執行也多一次。
- code review 第四輪延後的意見（與 Codex 討論，在「使用者以 --python 信任該環境，不可信的是模型與被測的程式」的威脅模型下判定不必在此修）：
  - venv 內部的項目（pyvenv.cfg 本身、site-packages 裡的 _pytest）若事先就是指向工作目錄的連結，被測的程式改那個工作目錄檔案就能換掉標準函式庫或 pytest。需要環境事先含有這種連結，屬於使用者信任的環境內容；連結鏈的檢查只涵蓋直譯器本身。
  - 沙箱放行讀取的 VENV 每次 run_tests 重新判斷 pyvenv.cfg 是否存在，沒有和 base 一起快取；要改變結果需要沙箱外的程式在執行中途建立 pyvenv.cfg。
- 環境與工作目錄的包含關係、基底與受保護目錄的重疊、家目錄判斷，都改用檔案系統身分（裝置與 inode）比對，macOS 不分大小寫時路徑寫法不同也認得（沙箱比對路徑不分大小寫，字面比對會讓檢查放過、沙箱照樣放行）。
- code review 第五輪延後的意見（與 Codex 討論後判定不必在此修）：
  - `--python` 含 `..` 時不正規化，被測的程式把穿過的專案內資料夾換成連結即可換掉直譯器；只在 protect_tests 關閉（非 CLI 呼叫）時重現，CLI 下資料夾改名與刪除都被擋。
  - 不是 venv 的直譯器放在 ~/bin 時，環境（往上兩層）是家目錄而被拒絕，錯誤訊息容易誤解；屬可用性問題，會安全地停止。日後處理時要一併調整 ENV 寫入保護的範圍。
