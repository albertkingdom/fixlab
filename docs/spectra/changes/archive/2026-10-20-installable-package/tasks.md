## 1. 套件設定

- [x] 1.1 實作「以 setuptools 的套件自動尋找取代固定清單」、「測試以讀設定比對目錄，不在測試中建 wheel」與 Regular installs include every fixlab subpackage：先新增 tests/test_packaging.py，用 tomllib 讀 pyproject.toml 的 packages.find include 樣式，比對 fixlab 底下所有含 __init__.py 的目錄並確認 tests 不符合，確認它在舊設定下失敗；再把 pyproject.toml 改成 packages.find（include fixlab 與 fixlab.*），以該測試通過驗證。

## 2. 文件與驗證

- [x] 2.1 [after: 1.1] 依「README 分成一般使用者安裝與開發者設定」與 The README documents installation for users，在 README.md 新增一般使用者安裝段落（開頭註明只支援以 pytest 測試的 Python 專案、uv tool install、pipx install、三個環境變數、不讀 .env、沙箱只在 macOS、macOS 的 Python 不能在家目錄底下、uv 加 --no-managed-python、uv tool install --with 與 pipx inject 加入被修專案依賴、benchmark 需要 clone），對應「以文件避開兩個既有限制，不在此變更修改沙箱」，原 editable 安裝標為開發用；以內容審查逐項對照規格的 scenario 驗證。
- [x] 2.2 [after: 2.1] 執行完整 pytest；以家目錄底下的暫存 UV_TOOL_DIR 與 UV_TOOL_BIN_DIR（和真實安裝位置一樣受沙箱的家目錄規則影響）從專案目錄做非 editable 的 uv tool install，安裝時加 --no-managed-python，確認 fixlab --help 結束碼 0、工具 Python 可匯入 fixlab.bench，並用工具 Python 對 timelog 範例的暫存複本直接呼叫 run_tests（不呼叫模型），確認沙箱 on、pytest 回報範例的失敗測試、沒有 dyld 或 ModuleNotFoundError，之後刪除暫存目錄並確認 ~/.local/bin/fixlab 未被更動；把結果記錄在本檔的驗證紀錄。

## 驗證紀錄

- 2026-10-20：tests/test_packaging.py 在舊設定（packages 固定清單）下失敗，改為 packages.find 後通過；完整 pytest 564 passed。
- 在家目錄底下的暫存目錄做非 editable 安裝，三種方式結果如下（run_tests 都對 timelog 範例的暫存複本執行，未呼叫模型）：
  - uv tool install --no-managed-python：基底 Python 為 Homebrew 3.14；fixlab --help 結束碼 0；可匯入 fixlab.bench；sandbox on，pytest 回報 1 failed, 4 passed（範例的 test_mixed_entries），沒有 dyld 或 ModuleNotFoundError。
  - pipx install（未加參數）：基底 Python 為 Homebrew 3.14；結果同上。
  - uv tool install（預設）：uv 選用家目錄底下的 uv 管理 Python 3.12；--help 與匯入正常，但 run_tests 出現 dyld Library not loaded（file system sandbox blocked open()），重現已知限制，README 因此改用 --no-managed-python。
- 原本設計寫的 /opt/homebrew/bin/python3 在這台電腦不存在（Homebrew 只提供帶版本號的檔名），README 改為不寫死路徑。
- code review 後：測試改照 setuptools 規則（沒寫 include 等於全部包含）並檢查 namespaces 關閉，先確認在未設 namespaces = false 時失敗；README 改用 OWNER 佔位、說明 --with 會取代、補 pipx 與舊版 uv 的寫法、更新過時的已知限制；完整 pytest 565 passed。
- code review 第二輪後：測試改照 setuptools 的走法找套件（沒有 __init__.py 的資料夾不往下找），暫時建立 fixlab/zz_probe/inner/__init__.py 確認測試會失敗後移除；README 拿掉作者本機設定的段落（README 是給外部讀者），demo 手冊改指向 README 的安裝段落；README 補上基底 Python 檢查方式與工具環境放在家目錄底下沒關係的說明；完整 pytest 565 passed。
- code review 第三輪後：檢查指令改為 uv python find --system --no-managed-python '>=3.11'（原本的寫法在有 .venv 的目錄會印出該 venv，在這台電腦實測：新寫法印出 Homebrew 3.14，舊寫法印出專案 .venv）並補 pipx environment --value PIPX_DEFAULT_PYTHON；spec 改為「基底 Python」不能在家目錄底下；demo 手冊說明需要 clone。
- 依使用者決定刪除 docs/local-cli-setup.md（作者本機紀錄，與 README 矛盾）；主 spec interactive-session 的 @trace 是上一個 change 的歷史紀錄，不手動修改。
- code review 第四輪通過（無阻擋與重要）；依使用者決定修正五筆建議：README 補上先安裝 Python 3.11 以上與 ~/.local/bin 不在 PATH 的處理，spec scenario 與 design 改為描述照 setuptools 走法的檢查，design 的 pipx 說明與 README 一致，demo 手冊改用 type -a。
- 驗證後已刪除暫存目錄；~/.local/bin/fixlab 的 shasum 與安裝前相同；uv tool list 與 pipx list 沒有留下 fixlab。
