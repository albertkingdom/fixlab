## Context

pyproject.toml 的 setuptools 設定以固定清單列出套件，只有最上層的 fixlab。editable 安裝直接指向原始碼目錄，所以作者看不出缺漏；一般安裝（uv tool install、pipx install、pip install 非 editable）時，fixlab.bench 不會被裝進去。README 的快速開始只寫了 clone 加 editable 安裝，沒有給一般使用者的裝法。設計依據是本專案自己的套件設定與安裝方式，無新增外部參考。

## Goals / Non-Goals

**Goals:**

- 一般安裝包含 fixlab 與所有子套件，fixlab 指令可從任何目錄執行。
- README 提供一般使用者的安裝步驟與必要設定。

**Non-Goals:**

- 不 push、不發佈到 PyPI。
- 不改 CLI 行為，不新增 .env 自動載入。
- 不把 bench/problems 題目打包進套件。
- 不提供 Linux 沙箱。
- 不支援非 Python 或不用 pytest 的專案。
- 不修改沙箱規則或 run_tests 的直譯器選擇（另開 change）。

## Decisions

### 以 setuptools 的套件自動尋找取代固定清單

改用 tool.setuptools.packages.find，include 設為 fixlab 與 fixlab.*，並設 namespaces = false：setuptools 預設會把沒有 __init__.py 的資料夾也當成 namespace 套件，關掉後打包內容才和含 __init__.py 的目錄一致。新增子套件時不必再改設定，也不會把 tests 或 bench/problems 當成套件。替代方案是在固定清單補上 fixlab.bench，但下次新增子套件又會漏。

### 測試以讀設定比對目錄，不在測試中建 wheel

專案 venv 沒有 setuptools，建 wheel 需要網路下載建置依賴，不適合放進 pytest。測試改為用 tomllib 讀 pyproject.toml 的設定，照 setuptools 的規則判斷（沒寫 include 等於全部包含），並照 setuptools 關閉 namespaces 時的走法找套件（沒有 __init__.py 的資料夾不再往下找）。確認 where 是專案根目錄、namespaces 關閉、fixlab 底下每個含 __init__.py 的目錄都被走到且被包含，而被包含的只有 fixlab 的套件。實際安裝的驗證（uv tool install）在實作時手動執行一次並記錄。

### README 分成一般使用者安裝與開發者設定

新增「安裝（一般使用者）」段落放在快速開始之前，給 uv tool install 與 pipx install 兩種 git URL 指令；原本的 clone 加 editable 安裝改標為開發用。git URL 以佔位帳號表示，因為專案尚未設定遠端。

### 以文件避開兩個既有限制，不在此變更修改沙箱

沙箱擋住家目錄底下的讀取，uv tool install 預設可能選用 uv 管理、位於家目錄底下的 Python，run_tests 會因此失敗；run_tests 用 fixlab 自己的直譯器，被修專案的依賴必須裝進隔離的工具環境。README 的 uv 安裝指令加上 --no-managed-python（實測：這台電腦沒有 /opt/homebrew/bin/python3，寫死路徑不可靠；uv 預設選到家目錄底下的 uv 管理 Python 3.12 並重現 dyld 失敗），pipx 預設使用它自己所在的 Python（用 Homebrew 裝的 pipx 就是 Homebrew 的 Python；裝在 pyenv 等家目錄底下的 Python 時要用 --python 指定），並說明 uv tool install --with 與 pipx inject。根本修法（run_tests 改用目標專案的 Python、沙箱放行其基底 Python）會改變 workspace-isolation 規格與 benchmark 評分前提，另開 change。

## Implementation Contract

- 行為：從專案目錄做非 editable 的 uv tool install 後，fixlab 指令可執行，工具自己的 Python 可匯入 fixlab.bench。CLI 行為不變。
- 介面：pyproject.toml 的 tool.setuptools.packages.find include 為 fixlab 與 fixlab.*、namespaces 為 false；console script 仍為 fixlab 指向 fixlab.cli:main。
- 失敗模式：子套件不符合 include 樣式時，tests/test_packaging.py 失敗並列出漏掉的套件名稱。
- 驗收：tests/test_packaging.py 通過；完整 pytest 通過；以家目錄底下的暫存 UV_TOOL_DIR 與 UV_TOOL_BIN_DIR（和真實安裝位置一樣在家目錄底下）執行 uv tool install（非 editable，加 --no-managed-python），確認 fixlab --help 結束碼 0、工具 Python 可匯入 fixlab.bench，並用工具 Python 對 timelog 範例的暫存複本直接呼叫 run_tests 工具（不呼叫模型），確認沙箱狀態為 on、pytest 回報範例的失敗測試、沒有 dyld 或 ModuleNotFoundError；驗證後刪除暫存目錄，不影響使用者現有的 ~/.local/bin/fixlab；README 內容審查符合 package-distribution 規格的安裝段落要求。
- 範圍：只改 pyproject.toml、README.md、.gitignore（忽略本機安裝產生的 build/）、docs/cli-demo.md（改指向 README 的安裝段落），新增 tests/test_packaging.py。刪除 docs/local-cli-setup.md：它是作者本機啟動器的紀錄，README 是給外部讀者的，這份文件又和「fixlab 不讀 .env」矛盾。

## Risks / Trade-offs

- 實際安裝驗證需要網路下載 setuptools 與依賴 → 只在實作時手動執行並記錄結果，不放進 pytest。
- 一般安裝後 python -m fixlab.bench 的預設題目路徑指向套件旁的 bench/problems，安裝版不存在 → README 說明 benchmark 需要 clone 專案。
- README 的 git URL 以 OWNER 為佔位值（不用角括號，避免貼進 shell 時被當成重新導向）→ 設定遠端後要換成實際網址。
- 一般安裝後 fixlab_commit 一律是 null，事件檔沒有可追查的 fixlab 版本；安裝版執行 python -m fixlab.bench 時，找不到題目目錄的錯誤訊息不清楚 → code review 延後的建議，留給後續 change（run_start 記 importlib.metadata.version、bench 找不到題目時明確提示需要 clone）。
- 使用者若沒照 README 加 --no-managed-python，或用 pyenv 這類在家目錄底下的 Python，uv 可能選到家目錄底下的 Python，run_tests 仍會失敗 → 已知限制段落保留說明，根本修正留給後續 change。
