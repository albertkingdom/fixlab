# 第 5 篇：讓模型跑測試（run_tests）

> 對應任務：bootstrap-agent-core 的 3.10。
> 完成度：程式與測試都完成（寫這篇時全部測試 112 個通過，其中 12 個是這個工具與環境變數的）。沙箱（限制測試程式能讀寫哪裡）還沒做，所以這個工具現在執行的程式，權限和你自己的帳號一樣大。

前面幾篇的模型能看、能改，卻不能驗證：改完之後它不知道修好了沒有。第 4 篇那次實驗裡，模型為了跑測試，先呼叫了不存在的工具，接著竟然去改測試檔。這一篇補上這個缺口：給它一個跑測試的工具。

先說明三個後面會用到的詞：

- **行程**：一個正在執行的程式。一個行程可以再啟動別的行程，後者叫**子行程**。
- **環境變數**：每個行程都帶著的一組「名稱＝值」設定，例如 `PATH`（去哪裡找程式）、`LANG`（語言與編碼）。你開終端機時 shell 設好的那些，就是環境變數。
- **結束碼**：行程結束時回報的一個數字，慣例上 0 代表成功。pytest 的結束碼：0 是全部通過，1 是有測試失敗，4 是用法錯誤，5 是沒有收集到任何測試。

## 先寫一個最天真的版本

```python
def run_tests_v1(root):
    r = subprocess.run([sys.executable, "-m", "pytest"], cwd=root, capture_output=True, text=True)
    return r.stdout
```

（`run_tests_v1` 只存在這篇文章裡，專案裡沒有它。）

五行不到，在範例專案上確實能跑。但我拿它做了七個檢查，下面是真實的結果。

**問題一：子行程繼承了整份環境變數。** 我放了一個假的金鑰 `sk-demo-123` 在環境變數裡，再讓一個測試把它印出來：

```
測試輸出裡出現金鑰： True
```

下一節專門說明這件事。

**問題二：跑完之後，工作目錄多出垃圾。**

```
新增： ['.pytest_cache', 'tests/__pycache__', 'timelog/__pycache__']
```

這些快取檔不是模型或使用者改的，卻會出現在結束時的差異比較裡，混淆「這次到底改了什麼」。

**問題三：pytest 會往上層資料夾找設定。** 當工作目錄放在這個專案自己的資料夾裡面（範例專案就是 `tests/fixtures/timelog`），pytest 找到了上層的設定檔：

```
['rootdir: /path/to/fixlab', 'configfile: pyproject.toml']
```

測試結果因此受到專案之外的設定影響。目前還沒有沙箱，所以只是多讀了一個檔案；設計文件記錄過一次實驗：沙箱禁止讀取專案目錄之後，pytest 會因為讀不到這個設定檔而直接崩潰。

**問題四：目標看起來像選項，會騙過工具。**

先說背景。`run_tests` 有一個 `target` 參數，是模型填的，例如 `tests/test_report.py`，意思是「只跑這個檔案」。這個字串會直接接在 pytest 指令的後面。

但模型也可能填出以 `-` 開頭的字串，例如 `--collect-only`（只列出有哪些測試，不執行）或 `--version`（印出 pytest 的版本號）。pytest 看到 `-` 開頭，會把它當成**選項**，不是檔案路徑。

這會出事，因為這兩個選項都會讓 pytest 以結束碼 0 結束，而 `run_tests` 把「結束碼 0」解讀成「測試通過」。結果是：一個**根本沒有跑任何測試**的呼叫，卻回報「通過」，模型會以為自己修好了。

命令列有個慣例：`--` 代表「它後面的都不是選項」。我原本以為加上 `--` 就安全了。實測三種寫法的結果（範例專案，真實輸出）：

| 目標 | 直接放 | 前面加 `--` | 加 `--` 並加 `./` 前綴 |
|---|---|---|---|
| `--version` | 結束碼 0，印出版本號 | **結束碼 0，還是印出版本號** | 結束碼 4，找不到路徑 |
| `--collect-only` | 結束碼 0，只列出測試、沒有執行 | 結束碼 4，找不到路徑 | 結束碼 4，找不到路徑 |

`--` 對 `--collect-only` 有效，對 `--version` 卻沒有用：pytest 對 `--version` 另外處理，內部原因我沒有查，這只是實測的結果。

最保險的做法是再加一個 `./` 前綴。`./--version` 不是以 `-` 開頭，不可能被當成選項，pytest 會把它當成「目前資料夾裡一個叫 `--version` 的檔案」，找不到，以結束碼 4 結束，正確地回報「沒有跑任何測試」。這個陷阱是我寫完工具後，單元測試才抓到的。

要說清楚的是：這是**防禦性的設計，不是我們看到模型犯了這個錯**。寫這篇的時候，還沒有真模型呼叫過 `run_tests`，沒有任何紀錄顯示模型會填出這種目標。它防的是更一般的情況：模型給的參數對工具來說是外部輸入，不能假設它「應該是路徑」。模型可能不穩定，也可能被專案裡的某段文字誤導，換一個行為不同的模型也可能不同。這類問題有個名字，叫「參數注入」：外部給的字串被當成指令的選項，而不是資料。就算模型完全穩定，這個洞還是在，所以仍然要補。

**問題五：沒有逾時。** 一個無窮迴圈的測試，會讓整個流程永遠卡住：

```
等了 3 秒還沒結束（我在第 3 秒把它中斷；沒有這個保險會一直等下去）
```

**問題六：輸出太長，只留開頭，就看不到結果。** 一個失敗的測試印了 10000 個字元：

```
全部 10600 字元；只留前 4000 的最後一行是：'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
完整輸出的最後一行是：'1 failed in 0.01s'
```

pytest 把最重要的資訊（失敗摘要與最後一行結果）放在輸出的**尾端**。只留開頭，模型就看不到到底通過了沒有。

**問題七：測試裡呼叫 `input()`，會不會卡住等輸入？**

```
E       OSError: pytest: reading from stdin while output is captured!  Consider using `-s`.
```

不會：pytest 自己已經把標準輸入換掉，會直接報錯。所以這一項我沒找到真正的問題，後面的最終版仍然把標準輸入接到空裝置，只是多一層保險（例如測試啟動的別的程式，不一定遵守 pytest 的設定）。

## 為什麼需要 child_environment

這是前面問題一的完整說明。

Python 啟動子行程時，**預設會把父行程的整份環境變數都傳過去**。`fixlab` 執行時，你的 `OPENAI_API_KEY`（OpenRouter 的金鑰）就在環境變數裡。`run_tests` 啟動的 pytest 會執行專案的程式，**包含模型剛剛改寫過的檔案**。只要那段程式印出環境變數，金鑰就會走這條路：

```
測試程式印出環境變數
  → 變成測試的輸出
  → 作為工具結果送回給模型
  → 送到模型供應商（OpenRouter、Venice）
  → 寫進每一步的紀錄檔，甚至貼進文章
```

不一定是惡意：模型為了除錯，隨手寫一句 `print(os.environ)` 就會發生。

專案的做法是只傳白名單裡的變數：

```python
CHILD_ENV_NAMES = ("PATH", "LANG", "LC_ALL", "TMPDIR")

def child_environment():
    env = {}
    for name in CHILD_ENV_NAMES:
        if name in os.environ:
            env[name] = os.environ[name]
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env
```

同一個假金鑰，兩種做法，子行程看得到什麼：

```
不指定 env（預設：整份環境變數都繼承）
   dict_keys(['HOME', 'PATH', 'LANG', 'OPENAI_API_KEY']) | key = sk-demo-123
env=child_environment()（白名單）
   dict_keys(['PATH', 'LANG', 'PYTHONDONTWRITEBYTECODE']) | key = None
```

| 變數 | 為什麼需要 |
|---|---|
| `PATH` | 找到可執行檔 |
| `LANG`、`LC_ALL` | 文字編碼與地區設定，輸出中文才不會亂碼 |
| `TMPDIR` | 暫存資料夾的位置 |
| `PYTHONDONTWRITEBYTECODE=1` | 這個是我們加上去的，不是繼承來的：讓 Python 不在工作目錄產生 `__pycache__`，解決上面的問題二 |

沒有傳 `HOME`：設計文件記錄過實驗，用沙箱啟動虛擬環境裡的 Python 和 pytest，不需要 `HOME`、`VIRTUAL_ENV` 或 `PYTHONPATH`。

### 為什麼是白名單，不是黑名單

黑名單是「把名字像金鑰的變數移除」。不選它的原因是金鑰的名字無法窮舉：`OPENAI_KEY`、`STRIPE_SK`、`GH_PAT`……漏掉一個就洩漏。白名單反過來：只傳明確需要的，沒列出的一律不傳，之後新增的變數預設也是安全的。代價是：如果被測專案的測試需要某個特定的環境變數，得明確加進白名單，階段 1 不開放設定。

### 它擋不住什麼

白名單只擋**環境變數**這一條路。沙箱完成前，測試程式仍然可以直接讀你家目錄裡的檔案，例如 `~/.ssh`，或其他專案的 `.env`。那是沙箱階段要處理的事。所以目前只對自己寫的範例專案的複本執行。

## 最後的 run_tests

```python
def run_tests(ws, target="."):
    relative_target = ws.resolve_inside(target).relative_to(ws.root).as_posix()   # 路徑守門
    if relative_target != ".":
        relative_target = "./" + relative_target       # 加 ./ 前綴，--version 才會變成路徑
    command = [ws.python, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "-c", "/dev/null", "--rootdir=.", "--confcutdir=.", "--", relative_target]
    try:
        done = subprocess.run(command, cwd=ws.root, env=child_environment(), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=RUN_TESTS_TIMEOUT_S)
        output, timed_out, passed = done.stdout, False, done.returncode == 0
    except subprocess.TimeoutExpired as e:
        output, timed_out, passed = e.stdout or b"", True, False
    text = output.decode("utf-8", errors="replace")
    if timed_out:
        text += f"\n[tests timed out after {RUN_TESTS_TIMEOUT_S}s]"
    return ToolResult(clip_middle(text), True, {"tests_passed": passed, "timed_out": timed_out})
```

指令是固定的，每個參數對應前面的一個問題：

- `-c /dev/null`、`--rootdir=.`、`--confcutdir=.`：不讓 pytest 往上層資料夾找設定和共用的測試設定檔（問題三）。
- `-p no:cacheprovider`：不產生 `.pytest_cache`（問題二）。
- `--` 加上目標的 `./` 前綴：確保目標只會被當成路徑（問題四）。
- `timeout=10`：逾時（問題五）。10 秒放在一個模組常數裡，測試無窮迴圈時可以改短，不用真的等。
- 標準輸入接到空裝置，標準錯誤併進標準輸出，讓模型看到的是 pytest 原本的順序。

### 失敗的測試不是工具錯誤

不管測試通過與否，這個工具都回報「成功」（`ok=True`），結果放在標記裡：`tests_passed`（結束碼是 0 才是 `True`）和 `timed_out`。因為失敗的測試正是模型需要的資訊，不是工具出了錯；如果把它當成工具失敗，連續失敗的保險（之後的任務）也會誤以為模型卡住了。

### 輸出太長：留頭尾

```python
def clip_middle(text, limit=4000):
    if len(text) <= limit:
        return text
    half = limit // 2
    note = f"[truncated: {len(text)} characters in total, showing the first {half} and the last {half}]"
    return text[:half] + "\n" + note + "\n" + text[-half:]
```

保留頭尾各 2000 字元，中間註明總長度。讀檔工具則只留開頭，因為它能用行範圍補讀剩下的；跑測試沒有這種補讀的辦法，所以要保留尾端的結果。

### 跑起來

同樣的七個檢查，換成最後的版本（真實輸出）：

```
-- 1 環境變數
   ok=True flags={'tests_passed': False, 'timed_out': False}
   測試輸出裡出現金鑰： False | 測試印出的值： ['None']
-- 2 工作目錄新增的東西： （沒有）
-- 3 固定指令的設定來源： ['rootdir: /path/to/fixlab/tests/fixtures/timelog', 'configfile: ../../../../../../../../dev/null']
-- 4 目標 --version
   ok=True flags={'tests_passed': False, 'timed_out': False}
   ERROR: file or directory not found: ./--version
-- 5 無窮迴圈（逾時調成 1 秒）
   ok=True flags={'tests_passed': False, 'timed_out': True}
   [tests timed out after 1s]
-- 6 輸出太長
   ok=True flags={'tests_passed': False, 'timed_out': False}
   長度 4082；中間的註解：[truncated: 10600 characters in total, showing the first 2000 and the last 2000]
   最後一行：'1 failed in 0.01s'
```

第 3 項的 `configfile` 是 `/dev/null`（顯示成一長串 `../`），也就是沒有讀任何設定檔，`rootdir` 是工作目錄本身。

範例專案本身的結果：

```
.F...                                                                    [100%]
=================================== FAILURES ===================================
______________________________ test_mixed_entries ______________________________

    def test_mixed_entries():
        total = weekly_total(["1h30m", "45m", "2h"])
>       assert total == 4.25, f"{total} != 4.25"
E       AssertionError: 3.75 != 4.25
E       assert 3.75 == 4.25

tests/test_report.py:10: AssertionError
=========================== short test summary info ============================
FAILED tests/test_report.py::test_mixed_entries - AssertionError: 3.75 != 4.25
1 failed, 4 passed in 0.02s
```

標記是 `{'tests_passed': False, 'timed_out': False}`。用第 4 篇的改檔工具把 bug 修好之後再跑一次，是 `5 passed`，標記變成 `tests_passed: True`。

## 逾時：先用最簡單的做法

上面用的是最簡單的逾時：`subprocess.run(timeout=…)`。我原本擔心它有問題，做了實驗。

**我原本以為會卡住不返回，實測不會。** 設逾時 1 秒，呼叫端就是 1.0 秒返回。這個假設是錯的。

**真正的問題是孤兒行程。** 讓測試行程再啟動一個孫行程（`sleep`），然後逾時：

```
A) subprocess.run(timeout=1)：逾時後，孫行程 sleep 還活著嗎？
   還在跑的 sleep 7.31 行程數： 1
B) Popen(start_new_session=True) + killpg：
   還在跑的 sleep 7.32 行程數： 0
```

簡單逾時只殺得到最上層的 pytest，它啟動的子行程變成孤兒，繼續在背景跑。做法 B 先讓子行程自成一個「行程群組」，逾時時對整個群組送出結束訊號。群組是作業系統的設計：新行程預設屬於啟動它的行程所在的群組，所以一棵行程樹預設都在同一組；用 `start_new_session=True` 啟動的子行程會自成新群組，它的所有後代都繼承這個群組：

```
我（呼叫端）: 行程 60442 群組 60440
預設                         child (60443, 60440) grandchild (60444, 60440)
start_new_session=True       child (60445, 60445) grandchild (60446, 60445)
```

每個括號是（行程編號，群組編號）。預設時子行程和孫行程都在我自己的群組（60440），殺這一組連我自己都會被殺；用新群組時，它們在 60445，對 60445 送一次結束訊號就能清乾淨。

**我最後選了簡單逾時**，理由是：階段 1 的範例專案沒有任何測試會啟動子行程，這個問題目前碰不到；多做會多約 6 行程式。風險已經記進設計文件的風險清單，附上這個實驗的數字，並寫明之後要改成哪個做法。要注意它不是理論：第 4 篇那次，模型在測試檔裡塞了一段會自己執行 pytest 的程式；如果真的被執行，pytest 會一層一層啟動自己，逾時只殺得掉最上層。現在測試檔被擋下了，但同樣的手法放進原始碼檔案就擋不住。

## 怎麼驗證

測試在 `tests/test_tools.py`（9 個）和 `tests/test_isolation.py`（3 個）：

- **結果標記**：對範例專案，失敗時 `tests_passed` 是 `False`、輸出含 `1 failed` 與失敗的訊息；用改檔工具修好之後是 `True`、`5 passed`。
- **目標**：指定單一測試檔，只跑那個檔案的測試；目標是 `--version`，會回報找不到路徑，不是印出版本；目標在工作目錄外，會被擋下。
- **逾時**：一個無窮迴圈的測試，逾時被調成 1 秒，標記 `timed_out` 為 `True`，輸出含 `timed out after 1s`。
- **工作目錄乾淨**：跑完之後沒有 `.pytest_cache`，也沒有 `__pycache__`。
- **輸出太長**：長度被控制在上限附近，有截斷的註解，而且最後一行的結果還在。
- **工具說明**：必填參數是空的（`target` 可省略）。
- **環境變數**：把兩個假金鑰放進環境變數，讓測試印出整份環境，輸出裡沒有金鑰的值，也沒有變數名稱；`LANG` 設成 `en_US.UTF-8` 之後，測試印得出來。

## 已知限制

- **孤兒行程。** 見上一節。
- **沒有輸出量的上限。** 測試印出無限多輸出時，記憶體會在 10 秒內持續增加。高見龍的程式有 1 MB 的讀取上限，階段 1 先不處理。
- **`tests_passed` 只看結束碼是不是 0。** 任何讓 pytest 以 0 結束的情況都算通過，`--version` 就是一例，已用 `./` 前綴擋掉。沒有收集到任何測試時結束碼是 5，算未通過。之後若發現其他讓結束碼為 0 卻沒有真的跑測試的路徑，再補檢查。
- **沒有沙箱。** 環境變數白名單擋得住金鑰，擋不住讀家目錄的檔案或連網。
- **測試的設定檔被忽略。** 固定的指令不讀專案自己的 pytest 設定，如果被測專案靠設定檔才能正常跑測試，會跑不起來；階段 1 只服務自己寫的範例專案。

## 參考來源

看過高見龍 KeSi 的 `kesi.py`（MIT 授權，Copyright (c) 2026 Eddie Kao，commit `dfa0cd0`，2026-10-17 查證）裡的 `run_command`。

- **他的做法**：可以執行任意指令；環境變數用**黑名單**，移除幾個固定名稱（例如 `AWS_ACCESS_KEY_ID`、`DATABASE_URL`）以及名稱以 `_API_KEY`、`_TOKEN`、`_PASSWORD` 等結尾的變數；啟動時標準輸入接到空裝置；用 `start_new_session` 讓指令自成行程群組，**不論逾時與否**，指令結束後都會對整個群組先送結束訊號、等 3 秒再強制殺掉，清掉殘留的子行程；輸出超過 1 MB 時也一樣中止；輸出超過 8000 位元組時，保留頭尾各一半、中間註明省略多少位元組；逾時 120 秒。
- **採用的想法**：輸出太長時保留頭尾，這個想法來自他的程式（我在規劃時就看到了）；標準輸入接到空裝置，他的程式也這樣做，讀了之後才採用。
- **沒有採用的**：黑名單。理由是名稱無法窮舉，在設計文件裡有寫。行程群組與輸出上限，他的程式都有，我們先不做，風險已經記下來。
- **自己發現的**：`--version` 的陷阱、結束碼 0 的誤判，都是單元測試抓到的；對 pytest 9.1.1 的行為（2026-10-17）是自己的實驗，不是文件。孤兒行程的實驗也是自己做的。

## 下一篇

3.11 讓入口在模型結束之後，自己再跑一次 `run_tests`，把最後的測試結果和差異比較一起印出來。模型可能沒跑測試就宣稱完成，所以不能全信它。
