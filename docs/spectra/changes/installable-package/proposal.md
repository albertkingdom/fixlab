## Why

目前只有作者本機能從任何目錄執行 fixlab：它依賴專案內手動建立的 venv 與自寫啟動器。其他人照 README 只能 clone 後以 editable 方式安裝；而一般（非 editable）安裝時，pyproject 只列出最上層套件，fixlab.bench 子套件不會被裝進去。

## What Changes

- pyproject 的套件設定改為自動尋找 fixlab 底下所有子套件，讓非 editable 安裝也包含 fixlab.bench。
- README 新增「一般使用者安裝」段落：開頭註明只支援以 pytest 測試的 Python 專案；以 uv tool install 或 pipx install 從 git URL 安裝、需要設定的三個環境變數（OPENAI_BASE_URL、OPENAI_API_KEY、FIXLAB_MODEL）、沙箱只在 macOS 啟用的提醒、macOS 上 fixlab 的 Python 不能在家目錄底下（uv 安裝加 --no-managed-python，避開沙箱擋住 uv 管理的 Python）、以 uv tool install --with 或 pipx inject 加入被修專案的第三方依賴，以及 benchmark 需要 clone 專案才有題目。
- 開發者的 clone 加 editable 安裝說明保留，標示為開發用；README 是寫給外部讀者的，拿掉作者本機啟動器的段落，demo 手冊改指向 README 的安裝段落。

## Non-Goals

- 不 push、不發佈到 PyPI。
- 不改 CLI 行為，不新增 .env 自動載入。
- 不把 bench/problems 題目打包進套件；benchmark 仍從 clone 的專案執行。
- 不提供 Linux 沙箱。
- 不支援非 Python 或不用 pytest 的專案；多語言驗證器屬於之後的階段。
- 不修改沙箱或 run_tests 使用的直譯器；讓 run_tests 改用目標專案自己的 Python 並放行其基底 Python，另開 change 處理。

## Capabilities

### New Capabilities

- `package-distribution`: fixlab 作為一般 Python 套件安裝時，提供 fixlab 指令並包含所有子套件。

### Modified Capabilities

(none)

## Impact

- Affected specs: package-distribution（新增）
- Affected code:
  - Modified: pyproject.toml, README.md, .gitignore, docs/cli-demo.md
  - New: tests/test_packaging.py
  - Removed: docs/local-cli-setup.md
