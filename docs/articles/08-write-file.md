# 第 8 篇：建立與覆寫整個檔案（write_file）

> 對應任務：bootstrap-agent-core 的 4.2。
> 完成度：程式與測試都完成（寫這篇時全部測試 161 個通過，其中 29 個是這個工具的）。

改檔工具（第 4 篇）只能改**已經存在**的檔案裡的一段文字。如果要**建立新檔案**，或是把**整個檔案換掉**，就需要另一個工具：`write_file`。

先老實說一件事：**到目前為止，沒有任何一次真模型的修復用到它。** 六次真實紀錄裡，模型只靠列檔案、讀檔、改檔、跑測試就修好了範例專案，也沒有一次嘗試過呼叫一個叫「寫檔」的工具。那它為什麼還要存在？下一節說明。

## 什麼時候需要它

| 情況 | `edit_file` 做得到嗎 |
|---|---|
| 改一個函式裡的一行 | 做得到，而且更安全 |
| **建立新檔案**（例如缺了一個模組、缺了 `__init__.py`） | **做不到**，它只改已存在的檔案 |
| 把整個檔案重寫 | 做得到但很麻煩，要把整個檔案當成舊字串 |
| 為新功能加檔案、寫文件 | 做不到 |

所以它的價值是：**它提供別的工具都沒有的能力（建立檔案）**。這是它和暫緩的 `glob`（依檔名找檔案，理由見設計文件）不同的地方：`glob` 的功能被遞迴的列檔案工具涵蓋了，所以暫緩；`write_file` 沒有替代品。

它也不是只有「互動式」的工具才需要，而是跟任務的種類有關：

- **修 bug**：多半用 `edit_file` 就夠。但可以想像有一類 bug 需要新檔案，例如套件缺了 `__init__.py` 導致匯入失敗（這只是推論，我們的題目裡還沒有遇到）。
- **一般的程式開發助手**（幫我加一個功能、建立一份說明文件）：一定需要。

目前階段 1 的題目都是第一類，所以現在是備而不用。每多一個工具，每一步送給模型的輸入大約多 100 到 150 token（設計文件記了實測：2 個工具 528、3 個 672、4 個 778 token），這是它的代價。

## 先寫一個最天真的版本

```python
def write_v1(root, path, content):
    open(os.path.join(root, path), "w").write(content)
    return "ok"
```

（`write_v1` 只存在這篇文章裡，專案裡沒有它。）

兩行。下面對它做六個檢查，都是對範例專案的複本做的，輸出是真實的。

**問題一：沒讀過就整檔覆寫，把原本的檢查弄丟了。** 假設模型沒有讀 `parser.py`，就憑印象寫了一份「應該長這樣」的 `parse_duration`：

```
行數 13 → 6；測試結果：5 passed in 0.01s
parse_duration('abc') 原本會丟 ValueError，現在回傳： 0
```

這個例子最值得看：**測試全部通過**（修好了那個 bug），但原本的輸入檢查被整個丟掉，`parse_duration('abc')` 從丟出錯誤變成默默回傳 0。可見的測試看不出這個退步。「整檔覆寫是最容易弄壞東西的操作」，原因就在這裡。

**問題二：讀過之後，你在編輯器裡改了檔案，模型照舊內容整檔覆寫。**

```
使用者的註解還在嗎： False
```

你的修改悄悄消失了。`fixlab` 是直接修改你給它的目錄，你在編輯器裡同時動這個目錄是真實會發生的事。

**問題三：上層資料夾不存在。**

```
例外 FileNotFoundError: [Errno 2] No such file or directory: '/var/folders/…
```

**問題四：路徑跑出工作目錄。** 絕對路徑會蓋掉前面的根目錄，`../` 也能往上跳：

```
outside.txt 被建立： True ｜ ../escaped.txt 被建立： True
```

**問題五：覆寫測試檔，把失敗的測試改成通過。**

```
改之前： 1 failed, 4 passed in 0.01s
改之後： 4 passed in 0.01s   （bug 還在，這是假通過）
```

**問題六：內容有無法編碼的字元，寫到一半失敗。**

```
例外 UnicodeEncodeError
report.py 原本 271 bytes，現在 0 bytes（開檔時就被清空了）
```

這個最糟：Python 的 `open(..., "w")` 在**開檔的那一刻**就把檔案清空了，然後才開始寫、才發現編不了碼。例外丟出來時，原本的檔案已經沒了。

## 最後的 write_file

```python
def write_file(ws, path, content):
    p = ws.resolve_writable(path)                      # 路徑守門 + 唯讀（測試檔）檢查，放在最前面
    data = content.encode("utf-8")                     # 先編碼，失敗時還沒動任何東西
    if p.exists():
        # 是資料夾 → 錯誤
        check_overwrite_allowed(ws, p, path)           # 沒整檔讀過、或讀過之後被改了 → 拒絕
        action = "overwrote"
    else:
        p.parent.mkdir(parents=True, exist_ok=True)    # 上層資料夾不存在就建立
        action = "created"
    p.write_bytes(data)
    ws.files_read[p] = file_digest(data)               # 模型知道自己剛寫了什麼
    return ToolResult(f"{action} {path} ({len(content)} characters)", True)
```

同樣的六個情況（真實輸出）：

```
-- 1 沒讀過就覆寫
   ok=False flags={}
   error: 'timelog/parser.py' already exists. You must read the file first with read_file (the whole file; a partial or cut-off read does not count) before overwriting it.
   檔案行數仍是 13
-- 1b 只讀了前 5 行再覆寫
   ok=False flags={}
   error: 'timelog/parser.py' already exists. You must read the file first ...
-- 1c 整檔讀過之後覆寫
   ok=True flags={}
   overwrote timelog/parser.py (6 characters)
-- 2 讀過之後，使用者改了檔案
   ok=False flags={}
   error: 'timelog/formatting.py' has changed since you read it. You must read the file first again before overwriting it.
   使用者的註解還在嗎： True
-- 3 上層資料夾不存在
   ok=True flags={}
   created notes/deep/summary.txt (2 characters)
-- 4a 絕對路徑
   ok=False flags={'blocked': True}
   error: absolute paths are not allowed: '/var/folders/…/outside.txt'
-- 4b ../ 跑出去
   ok=False flags={'blocked': True}
   error: path is outside the working directory: '../escaped.txt'
   工作目錄外有東西被建立： False
-- 5 覆寫測試檔
   ok=False flags={'blocked': True}
   error: 'tests/test_report.py' is read-only and cannot be modified. If it is a test file, fix the source code instead.
-- 5b 建立新的測試輔助檔
   ok=False flags={'blocked': True}
   error: 'tests/new_helper.py' is read-only and cannot be modified. If it is a test file, fix the source code instead.
-- 6 無法編碼的內容
   ok=False flags={}
   error: content cannot be encoded as UTF-8
   report.py 原本 271 bytes，現在 271 bytes
```

注意幾件事：

- **第 5b 項**：連「建立一個新的測試輔助檔」也被擋下。唯讀檢查放在檢查檔案存不存在**之前**，所以不存在的測試路徑也擋得住，不然模型可以放進一個假的 `tests/helpers.py`。
- **第 6 項**：先編碼、成功了才動檔案，原本的 271 bytes 完好無缺。
- **錯誤訊息都寫了接下來該怎麼做**，這是模型看得到的回饋。

## 為什麼要「記有沒有讀過」，還要記指紋

`edit_file` 有一道天然的保險：舊字串必須和檔案裡**完全一樣**才會動手，所以它本身就是「模型看過這段文字」的證明。`write_file` 沒有這種證明，給什麼就寫什麼。所以要另外用「有沒有讀過」來代替證明。

規則是：**既有的檔案，必須整檔讀過才能覆寫。**「整檔」的意思是：沒有帶行範圍，也沒有被截斷。只讀一部分就整檔覆寫，等於憑空捏造沒看過的部分。

光記「有沒有讀過」不夠，因為前面的問題二：讀過之後，檔案可能被別人改了。所以讀檔的當下，除了記下「這個檔案讀過了」，還要記下一個**指紋**（內容的雜湊值：把整個檔案內容算成一串固定長度的字，內容只要差一個字，這串字就完全不同）。覆寫前再算一次目前的指紋，和當時記的比較，不一樣就拒絕。

記錄何時成立、何時清除：

| 事件 | 記錄 |
|---|---|
| 整檔讀檔成功 | 記下檔案，連同當時的指紋 |
| 只讀一段、被截斷、讀取失敗 | 不記 |
| 改檔工具成功 | 清除（模型沒看過改完之後的全文） |
| 寫檔工具成功 | 記下新內容的指紋（模型知道自己剛寫了什麼） |
| 讀過之後，被別人改了 | 指紋對不上，拒絕，並清除過期的記錄 |

## 怎麼驗證

測試在 `tests/test_tools.py`（15 個）和 `tests/test_isolation.py`（14 個）：

- **規格的六個情境**：建立新檔、沒讀過就覆寫、整檔讀過後覆寫、只讀一部分不算、被截斷的讀取不算、改檔之後的讀取過期。
- **讀過之後被外部改動**：模擬使用者在編輯器加了一行註解，覆寫被拒絕、註解沒被蓋掉；重新讀過之後才放行。
- **記錄的規則**：成功的寫入算讀過（可以連續覆寫）、新檔可以再覆寫、失敗的讀取不留記錄。
- **錯誤情況**：上層資料夾自動建立、目標是資料夾、無法編碼的內容不建出檔案、路徑跑出工作目錄被擋、Windows 換行原樣寫入。
- **唯讀檢查**：測試檔的十列表格（先讀過，只看唯讀判定）、建立新的測試檔被擋、唯讀檢查早於「先讀」檢查、符號連結指向測試檔也擋、預設的工作區不鎖。
- **出現在工具清單，說明裡提醒要先整檔讀過。**

## 已知限制

- **不是原子寫入。** 寫到一半被中斷，檔案會是半成品。直接覆寫目標檔，沒有先寫暫存檔再取代。
- **建立新檔有競爭的空窗。** 先檢查不存在、再寫，如果這之間剛好有別的程式建立了同名檔，會被蓋掉。階段 1 單一程序、一次一個工具呼叫，風險低。
- **不能附加內容。** 只能整檔取代；要加一段文字，用改檔工具，以既有的一行當錨點。
- **內容相同也照寫。** 不會先比較。
- **到目前為止沒有真實案例用過。** 它的價值是推論，不是量到的。

## 參考來源

- **高見龍 KeSi**（`kesi.py`，MIT 授權，Copyright (c) 2026 Eddie Kao，commit `dfa0cd0`，2026-10-17 查證）：他的 `write_file` 在讀檔時記下內容的 sha256，覆寫前重新計算比較，不一樣就叫模型重讀；寫入時先寫暫存檔、再用 `os.replace` 整個取代；建立新檔用「只在不存在時才建立」的模式；內容相同回「不需要覆寫」。他的第 10 天文章標題就是〈write_file 的防呆機制〉。**採用的想法：記指紋、覆寫前比對。** 暫存檔取代、只在不存在時建立、內容相同的處理，這個專案先不做，已記進風險清單。
- **Claude Code**（官方文件〈Tools reference〉，2026-10-17 查閱）：Write 工具「建立新檔或覆寫既有檔案，不會附加或合併」。覆寫前要不要先讀，依模型而定：Opus 4.6、Haiku 4.5 以及更舊的模型一律要求先讀，較新的模型在某些條件下可以不讀；只讀一部分的不算。文件也寫了，舊版本（v2.1.208 之前）對讀過之後在磁碟上被改過的檔案拒絕編輯，之後對編輯放寬，因為舊字串要和目前內容完全吻合才會套用；整檔覆寫沒有這種保險，所以這個專案保留了指紋比對。這個專案以小模型為主，因此一律要求先讀。

## 下一篇

測試檔的指紋偵測，以及限制測試程式能讀寫哪裡的沙箱。
