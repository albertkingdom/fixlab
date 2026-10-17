"""run_tests 用的 macOS 沙箱：把 pytest 包進 sandbox-exec，限制被測的程式能讀寫哪裡、不能連網。

被測的程式包含模型改寫過的檔案，所以它會在這裡被執行。規則（SBPL，Apple 的沙箱規則語言）
後面的會覆蓋前面的，順序就是邏輯：
  1. 預設全部允許（Python 啟動要讀的系統路徑太多，列不齊），但禁止網路。
  2. 禁止讀家目錄、fixlab 專案目錄、額外的 deny_read 目錄。
  3. 再放行自己的工作目錄與虛擬環境（所以 deny 都要寫在這條 allow 之前）。
  4. 允許讀「檔案中繼資料」（存在與否、大小），因為取得目前目錄要走過上層目錄。
  5. 只能寫工作目錄、這次執行專用的暫存目錄、/dev。
  6. （選用，protect_tests=True 才有）工作目錄裡看起來像測試檔的路徑，連寫入也不行（覆寫、新建、刪除、改名、搬移都擋）。
     測試檔是評分標準：被測的程式如果能改寫它，把失敗的測試改成 assert True，就是假通過。
     工具層（read_only）已經擋住「模型直接改測試檔」，這一條擋「模型改過的程式自己去改」。
     只有修 bug 的入口開啟它：通用的互動用法裡，補測試是正常的任務，不該鎖。
路徑一律用 -D 參數傳入，規則文字裡沒有任何字面路徑：路徑含引號或括號也不會改寫規則。
所有路徑都要先轉成真實路徑：macOS 的 /var 其實是 /private/var 的捷徑，規則比對的是真實路徑，
用捷徑寫的規則永遠對不上。

來源說明：這個寫法的結構（allow default 再逐項收緊、路徑用 -D 參數、放行 file-read-metadata、寫入只放行白名單）
參考高見龍的 KeSi（https://github.com/kaochenlong/KeSi，commit dfa0cd0）的 sandbox_spec。
第 6 條把路徑接進正規表示式的做法 (regex (string-append "^" (regex-quote (param ...)) ...)) 也來自他的規則；
他用它禁止讀取工作目錄裡的特定名稱（.env 等），這裡用來禁止寫入測試檔。
規則本身是為這個專案另外寫的（擋家目錄與專案目錄、放行虛擬環境、私有暫存目錄），文字不同，
但結構相同。sandbox_status() 的名稱，以及「沙箱不可用就直接執行、並把狀態顯示出來」的做法，也與他的 kesi.py 相同，
不能排除受他影響。因此附上他的授權聲明：

    MIT License

    Copyright (c) 2026 Eddie Kao

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

第 6 條的樣式要與 workspace.looks_like_test_file 對得上（測試會逐條比對兩邊）；
自訂的 read_only 只在工具層生效，沙箱不管。
第 6 條還擋 __pycache__（偽造 .pyc 等於改寫測試）與資料夾的刪除、改名、搬移（不然把含有測試的上層資料夾改名再複製回來，測試就消失了）。

限制：sandbox-exec 已被 Apple 標為棄用，而且只有 macOS 有。其他平台上 run_tests 直接執行，
不套任何沙箱；入口會在開始時印出 sandbox_status()，讓使用者看得到。
"""

import shutil
import sys
from pathlib import Path

# 模組載入時決定一次。測試會把它改成 None 來模擬「沒有沙箱可用」。
SANDBOX_EXEC = shutil.which("sandbox-exec") if sys.platform == "darwin" else None


def sandbox_available() -> bool:
    return SANDBOX_EXEC is not None


def sandbox_status() -> str:
    """一行文字，說明沙箱有沒有開。入口開始時印出來，沙箱是安全功能，悄悄不啟用不行。"""
    if sandbox_available():
        return "on"
    if sys.platform != "darwin":
        return "OFF (not macOS: tests run without a sandbox)"
    return "OFF (sandbox-exec not found: tests run without a sandbox)"


def protected_path_patterns() -> list[str]:
    """與 looks_like_test_file 對應的路徑樣式，加上位元碼快取。每個都從工作目錄之後的 / 開始比對，(.*/)? 表示中間可以隔任意層資料夾。

    不用特別處理大小寫：SBPL 的正規表示式本來就不分大小寫（2026-10-17 在區分大小寫的磁碟映像上實測，
    全小寫的樣式照樣擋下 TEST_Y.PY 與 Tests/）。
    """
    return [
        "/(.*/)?tests?(/.*)?$",             # 任何一層資料夾叫 tests 或 test：資料夾本身與底下全部
        "/(.*/)?test_[^/]*$",               # 檔名以 test_ 開頭
        "/(.*/)?[^/]*_test[.]py$",          # 檔名以 _test.py 結尾（[.] 是一個真正的點）
        "/(.*/)?conftest[.]py$",            # conftest.py
        # pytest 載入測試時會先讀 __pycache__ 裡的 .pyc；偽造一個 .pyc 就等於改寫了測試，所以整個資料夾都擋。
        # 位元碼本來就被 PYTHONDONTWRITEBYTECODE=1 關掉，正常的流程不需要寫它。
        "/(.*/)?__pycache__(/.*)?$",
    ]


def build_profile(deny_count: int, protect_tests: bool = False) -> str:
    """沙箱規則文字。裡面只有 (param "名稱")，路徑由 -D 另外傳；deny_count 是額外禁止讀取的目錄數。"""
    extra_denies = "".join(f'(deny file-read* (subpath (param "DENY_{i}")))' for i in range(deny_count))
    profile = (
        "(version 1)(allow default)(deny network*)"
        '(deny file-read* (subpath (param "HOME")))'
        '(deny file-read* (subpath (param "PROJECT")))'
        + extra_denies
        + '(allow file-read* (subpath (param "WS")) (subpath (param "VENV")))'
        "(allow file-read-metadata)"
        '(deny file-write* (require-not (require-any (subpath (param "WS")) (subpath (param "TMP")) (subpath "/dev"))))'
    )
    if protect_tests:
        patterns = "|".join(protected_path_patterns())
        # ^ 加上被跳脫的工作目錄開頭，所以工作目錄「上層」有叫 tests 的資料夾（例如 tests/fixtures/x）不受影響
        profile += f'(deny file-write* (regex (string-append "^" (regex-quote (param "WS")) "({patterns})")))'
        # 資料夾不能刪除、改名、搬移：否則把含有測試的上層資料夾改名、再複製一份不含測試的回來，測試就憑空消失了
        # （pytest 會略過 .old 這種點開頭的資料夾）。代價：被測的程式不能 rmdir 或改名工作目錄裡的資料夾。
        profile += '(deny file-write-unlink (require-all (subpath (param "WS")) (vnode-type DIRECTORY)))'
    return profile


def sandbox_paths(root: Path, python: str, project_root: Path, deny_read: tuple, tmp: Path) -> dict[str, Path]:
    """規則用到的路徑，全部轉成真實路徑。"""
    paths = {
        "WS": root,
        "HOME": Path.home(),
        "PROJECT": project_root,
        # 虛擬環境由 python 路徑往上兩層推得（.venv/bin/python → .venv）。python 本身刻意不解析：
        # 它是指向 Homebrew Python 的捷徑，解析後就找不到虛擬環境的套件了。
        "VENV": Path(python).absolute().parent.parent,
        "TMP": tmp,
    }
    for i, folder in enumerate(deny_read):
        paths[f"DENY_{i}"] = folder
    return {name: Path(path).resolve() for name, path in paths.items()}


def wrap_command(command: list[str], root: Path, python: str, project_root: Path, deny_read: tuple, tmp: Path,
                 protect_tests: bool = False) -> list[str]:
    """把指令包進 sandbox-exec。"""
    paths = sandbox_paths(root, python, project_root, deny_read, tmp)
    definitions = [arg for name, path in paths.items() for arg in ("-D", f"{name}={path}")]
    return [SANDBOX_EXEC, *definitions, "-p", build_profile(len(deny_read), protect_tests), *command]
