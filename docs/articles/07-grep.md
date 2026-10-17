# 第 7 篇：在檔案內容裡搜尋（grep）

> 對應任務：bootstrap-agent-core 的 4.1。
> 完成度：程式與測試都完成（寫這篇時全部測試 132 個通過，其中 16 個是這個工具的）。

前面的模型靠「列出檔案」和「讀一個檔案」探索專案。專案小的時候夠用；專案大一點，問題就變成：**某個名字在哪裡被用到？** 例如 `parse_duration` 被哪些檔案呼叫。如果只能一個檔案一個檔案讀，又慢又花 token。

一般的做法是在終端機用 `grep`。但這個專案**刻意不給模型任意的指令列工具**（理由是安全），所以模型沒辦法自己下 `grep`。這一篇做一個專用的搜尋工具來補上。

先說明三個詞：

- **正規表示式**：一種描述「要找什麼樣的文字」的寫法，也叫搜尋規則。例如 `def \w+` 的意思是「`def` 加一個空白，再接一串字母」。
- **逾時**：給一件事設時間上限，超過就強制停下。
- **災難性回溯**：某些搜尋規則碰到特定字串，電腦會慢到幾乎卡死，後面有專門一節。

## 先寫一個最天真的版本

```python
def grep_v1(root, pattern):
    results = []
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            for number, line in enumerate(open(path), start=1):
                if re.search(pattern, line):
                    results.append(f"{path}:{number}:{line.rstrip()}")
    return results
```

（`grep_v1` 只存在這篇文章裡，專案裡沒有它。）

十行不到，在一般專案上確實能用。我準備了一個工作目錄 `ws/`：範例專案 timelog，加上一個指向工作目錄外面的符號連結 `link_secret`、一個二進位檔、一個 `.git` 目錄、一個 `__pycache__` 目錄，還有一個有 120 行 `hit` 的檔案。下面是真實的結果。

**問題一：讀到工作目錄外面的檔案。**

```
== 1 要找的是符號連結指向的東西  grep_v1('password')
   1 筆；前幾筆：
      ws/link_secret:1:password=hunter2
```

`link_secret` 指向 `../secret.txt`，那是工作目錄外面的檔案，天真版本照樣讀了。路徑守門被繞過了。

**問題二：只要有一個二進位檔，所有搜尋都崩潰。**

```
== 2 工作目錄裡有一個二進位檔  grep_v1('def')
   例外 UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 4: invalid start byte
```

不管搜尋什麼，只要工作目錄裡有一個圖片或編譯過的檔案，整個搜尋就丟出例外，連其他檔案的結果都拿不到。

**問題三：結果裡混著不該看的。**

```
== 3 一般搜尋  grep_v1('def parse_duration')
   2 筆；前幾筆：
      ws/timelog/parser.py:7:def parse_duration(text):
      ws/timelog/__pycache__/parser.txt:1:def parse_duration
```

第二筆來自 `__pycache__`，那是 Python 的快取，對找 bug 沒有幫助。路徑前面還帶著 `ws/`，真實使用時那是一長串暫存目錄的絕對路徑，模型拿去讀檔會找不到。

**問題四：沒有輸出上限。**

```
== 4 120 行都符合  grep_v1('hit')
   120 筆；前幾筆：
      ws/many.txt:1:hit
      ...
```

120 筆全部回傳，專案大一點就是幾千行，全部進入對話，而對話紀錄每一輪都會重送。

**問題五：搜尋規則寫錯，就丟出例外。**

```
== 5 無效的規則  grep_v1('(')
   例外 PatternError: missing ), unterminated subpattern at position 0
```

模型寫錯一個括號，整個程式崩潰，模型也看不到錯在哪裡。

**問題六：某些規則會慢到卡死。** 這個最特別，下一節專門說明。

## 災難性回溯

先看實測。同一條規則 `(a+)+$`，字串是 N 個 `a` 加一個 `!`（用 Python 內建的 `re`）：

```
22 個 a  0.23 秒
24 個 a  0.91 秒
26 個 a  3.64 秒
```

每多 2 個字元，慢 4 倍。照這個速度，40 個 `a` 要好幾個小時（這是推算，我沒有真的等）。而且 `re` 沒有辦法中斷它，程式就卡在那裡。

### 為什麼會這樣

`(a+)+$` 的意思是：「從頭到尾都是 `a`，可以分成好幾堆，每堆至少一個 `a`。」而字串最後有個 `!`，所以答案很明顯：**不符合**。

但電腦不會一眼看出來。它是照著規則一種一種試：把 4 個 `a` 分成怎樣的幾堆，都試一遍，每一種分完，後面都是 `!`，都失敗，才敢說不符合。4 個 `a` 的所有分法：

```
aaaa
aaa | a
aa | aa
aa | a | a
a | aaa
a | aa | a
a | a | aa
a | a | a | a
```

分法的總數是 2 的 (n−1) 次方，**每多一個 `a` 就變成兩倍**：

| `a` 的個數 | 要試的分法 |
|---|---|
| 4 | 8 |
| 10 | 512 |
| 20 | 524,288 |
| 26 | 33,554,432 |
| 40 | 549,755,813,888（約 5500 億） |

### 分堆為什麼是多餘的

你可能會問：全都是 `a`，為什麼要分堆？答案是：**分堆本來就是多餘的，是這條規則寫得不好**。`(a+)+` 多包了一層括號，同一段文字就有很多種「讀法」，而電腦看不出這些讀法其實等價，每一種都認真試一遍。同一個字串，寫成沒有巢狀的 `a+$`：

```
a+$       結果=沒有符合   耗時 0.0000 秒
(a+)+$    結果=沒有符合   耗時 3.6374 秒
```

結果完全一樣，一個瞬間，一個 3.6 秒。判斷標準是：**同一段文字在規則底下有很多種不同的讀法，再遇到注定失敗的輸入，電腦就得全部試遍**。真實世界常見的 `(\w+\s?)+$` 就是這種結構。

### 這和模型有什麼關係

要說清楚：**`(a+)+$` 是教學例子，是我們寫在規格和測試裡的，沒有任何模型寫過它。** 搜尋規則是模型填的，所以理論上它可能寫出這種規則；但今天這個工具才剛做好，還沒有真模型用過，沒有證據顯示它會這樣寫。模型實際會寫的搜尋規則通常很單純，例如找函式定義。

這是**防禦性的設計**：機率可能很低，但一旦發生，後果是整個程式卡死、必須強制中斷。設一個逾時，成本很小。

## 最後的 grep

```python
def grep(ws, pattern, path="."):
    if pattern == "": raise ToolError("pattern must not be empty")
    try:    matcher = regex.compile(pattern)
    except regex.error as e: raise ToolError(f"invalid regular expression: {e}")

    start = ws.resolve_inside(path)                      # 路徑守門
    # 路徑不存在 → ToolError
    files = {相對路徑: 檔案}   # 單一檔案就搜它；資料夾就用 iter_files 走訪（跳過清單、不跟隨符號連結）

    deadline = time.monotonic() + GREP_TOTAL_TIMEOUT_S   # 整體 5 秒
    for name in sorted(files):                           # 依相對路徑字串排序
        try:    text = files[name].read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError): continue   # 不是文字檔，略過
        for number, line in enumerate(text.splitlines(), start=1):
            try:    found = matcher.search(line[:2000], timeout=GREP_LINE_TIMEOUT_S)   # 只比對前 2000 字元；單行 1 秒
            except TimeoutError: raise ToolError("pattern too slow: ...")
            if found: 記下 f"{name}:{number}:{縮短到 200 字元的行}"（最多 100 行，其餘只計數）
            if time.monotonic() > deadline: 停止，附上 "search stopped after 5s"
    # 沒有任何符合 → "no matches"
```

這裡用的是第三方的 `regex` 套件，不是內建的 `re`。原因就是前面的實測：`re` 沒辦法中斷，而 `regex` 的比對可以帶 `timeout`。

### 跑起來

同一個工作目錄，換成最後的版本（真實輸出）：

```
-- 1 符號連結指向的東西  pattern='password'  ok=True flags={}
    no matches
-- 2 有二進位檔、有 .git、有 __pycache__  pattern='def'  ok=True flags={}
    tests/test_report.py:4:def test_single_unit_entries():
    tests/test_report.py:8:def test_mixed_entries():
       ...
    timelog/test_formatting.py:8:def test_whole_hours():
    timelog/test_formatting.py:12:def test_minutes_only():
-- 3 一般搜尋  pattern='def parse_duration'  ok=True flags={}
    timelog/parser.py:7:def parse_duration(text):
-- 4 120 行都符合  pattern='hit'  ok=True flags={}
    many.txt:1:hit
    many.txt:2:hit
       ...
    many.txt:100:hit
    [20 more matches omitted; use a more specific pattern or path]
-- 5 無效的規則  pattern='('  ok=False flags={}
    error: invalid regular expression: missing ) at position 1
-- 7 沒有符合  pattern='zzz'  ok=True flags={}
    no matches
```

對照前面五個問題：符號連結沒有被讀、二進位檔被略過、`.git` 與 `__pycache__` 沒有出現、路徑相對於工作目錄、輸出限制在 100 行並註明省略多少、寫錯的規則變成模型看得到的錯誤訊息。

「沒有符合」明確回報 `no matches`，而且標記成功，這樣模型分得出「搜尋過了，沒有」和「搜尋失敗了」。

還有幾個細節：

- **一行很長**，輸出時只顯示前 200 字元，再加 `...`（比對仍是前 2000 字元）。一行壓縮過的 5 萬字元的程式碼，如果整行放進輸出，100 行就會把對話塞滿。
- **預設區分大小寫**。工具說明告訴模型可以用 `(?i)` 開頭來忽略大小寫。
- **規則被拒絕時，回報原因**，不是回「沒找到」。這點在後面和 ripgrep 的比較會再提到。

### 一個我沒料到的發現

我照規格寫測試，規格原本舉的就是 `(a+)+$`，字串是 40 個 `a` 加 `!`，預期「1 秒內回報太慢」。結果測試過不了：

```
-- 8 (a+)+$ 在 regex 套件下  pattern='(a+)+$'  ok=True flags={}
    no matches
-- 9 (a|aa)+$ 在 regex 套件下  pattern='(a|aa)+$'  ok=False flags={}  (1.00s)
    error: pattern too slow: matching one line took more than 1s (slow.txt:1). Use a simpler pattern.
```

`regex` 套件對 `(a+)+$` 做了最佳化，一下子就比完。真正會卡住的是寫法略有不同的 `(a|aa)+$`（意思是「一個 `a` 或兩個 `a`，重複」，同樣有很多種讀法）。所以規格和測試都改用 `(a|aa)+$`。

這也說明為什麼要設逾時，而不是「避開幾個已知的壞規則」：你很難事先知道哪一個規則會出事。

最後，整體時間上限的行為（測試時把上限調成 0 秒）：

```
-- 10 整體時間上限調成 0 秒  pattern='hit'  ok=True flags={}
    many.txt:1:hit
    [search stopped after 0s; the results above may be incomplete]
```

已經找到的結果保留，後面註明搜尋被中止，結果可能不完整。

## 和 ripgrep 比較

`ripgrep`（指令是 `rg`）是目前最常用的搜尋工具。高見龍的 KeSi 和 Claude Code 的 Grep 都是建在它上面。我把同樣的檢查，用本機安裝的 ripgrep 15.2.0 跑了一遍（真實輸出）：

```
-- 符號連結指向的東西  結束碼=1
     (沒有輸出)
-- 一般搜尋（有二進位檔、.git、__pycache__）  結束碼=0
     ./timelog/__pycache__/parser.txt:1:def parse_duration
     ./timelog/parser.py:7:def parse_duration(text):
-- 無效的規則  結束碼=2
     rg: regex parse error:
-- (a|aa)+$ 對 40 個 a 加 !  結束碼=1  (0.004s)
-- (a|aa)+$ 對 20 萬個 a 加 !  結束碼=1  (0.004s)
```

| | ripgrep | 這個專案的 grep |
|---|---|---|
| 災難性回溯 | **不會發生**：引擎的比對時間和輸入長度成正比，20 萬個字元也是 0.004 秒 | 會發生，靠逾時補救 |
| 速度 | 快很多 | 慢，但小專案沒差 |
| `__pycache__` 裡的檔案 | 沒有 `.gitignore` 時也會搜（本例中出現了） | 固定跳過 |
| 符號連結 | 加 `--no-follow` 就不跟隨 | 一律不跟隨 |
| 要不要另外安裝 | 要（Claude Code 隨產品附帶一份；這個專案沒有附） | 只多一個 pip 套件 |
| 路徑前綴 | 輸出帶 `./` | 相對於工作目錄，沒有前綴 |

**在技術上，ripgrep 比較好**：又快，又沒有災難性回溯。這個專案選擇自己實作，是取捨：不想多一個要安裝的外部程式，路徑限制、跳過清單、符號連結的規則和列檔案工具完全一致，不用在外部指令上再處理一次。

### 一個用 ripgrep 才會踩到的坑

我第一次跑 ripgrep 時，**所有搜尋都沒有輸出**，連最基本的 `def parse_duration` 都找不到。原因是我沒有給路徑參數。

```
同一個指令，沒給路徑，標準輸入沿用呼叫端（不是終端機）：
    結束碼 1 輸出: ''
明確給路徑 . 之後：
    ./timelog/parser.py:7:def parse_duration(text):
```

我的推測是：ripgrep 在沒有給路徑、而標準輸入不是終端機時，會以為你要搜尋「從管線傳進來的內容」，而不是目前的資料夾。加上明確的路徑就好了。這個推測符合上面的對照（只差在有沒有給路徑），但我沒有去讀它的原始碼確認。高見龍的程式永遠給明確的路徑，也把標準輸入接到空裝置，避開了這個坑。

## 怎麼驗證

測試在 `tests/test_tools.py`（16 個）：

- **規格的情境**：找定義、無效的規則、120 筆只回 100 行並註明省略、災難性回溯（改用 `(a|aa)+$`）、不跟隨符號連結。
- **略過的東西**：不是 UTF-8 的檔案、`.git` 與 `__pycache__`。
- **範圍**：限定在單一檔案或資料夾、路徑不存在、路徑跑出工作目錄（被擋下）。
- **限制**：整體時間上限（測試中縮短）、長行縮短、只比對每行前 2000 字元。
- **細節**：結果依路徑再依行號排序、空規則、預設區分大小寫與 `(?i)`、出現在工具清單。

## 已知限制

- **慢。** 純 Python 逐行比對，大專案比 ripgrep 慢很多。
- **沒有遵守 `.gitignore`。** 只用固定的跳過清單。
- **不支援跨行比對。**
- **整個檔案讀進記憶體。** 一個很大的檔案會佔很多記憶體。
- **讀不了的檔案會悄悄略過**，不會告訴模型有哪些檔案沒搜。
- **一行逾時就整個搜尋失敗。** 即使其他檔案都已經搜完，也不會回報已找到的結果。
- **規則的語法是 Python 的**，和 ripgrep 的略有不同，例如某些跳脫寫法。

## 參考來源

- **高見龍 KeSi**（`kesi.py`，MIT 授權，Copyright (c) 2026 Eddie Kao，commit `dfa0cd0`，2026-10-17 查證）：他的 `grep` 呼叫 ripgrep，帶 `--no-config`、`--no-follow`、`--max-columns 200`，總時間上限 10 秒，永遠給明確的路徑。**採用的想法：每行輸出限制長度**（他是 `--max-columns 200`，這個專案的上限也是 200 字元）。**不同之處**：他用外部的 ripgrep，這個專案用純 Python。
- **Claude Code**（官方文件〈Tools reference〉與〈Troubleshooting〉，2026-10-17 查閱）：它的 Grep 建在 ripgrep 上，隨產品附帶一份執行檔；在 macOS、Linux 上，Grep 與 Glob 預設不在工具清單，模型透過 Bash 工具呼叫內嵌的 `find` 和 `grep`。這個專案刻意不給任意的指令列，所以才需要專用的搜尋工具。它的文件還提到，早期版本把被 ripgrep 拒絕的輸入回報成「找不到檔案」，v2.1.208 才改成真正的錯誤，這跟這個專案「失敗不能說成成功」的做法一致。
- **`regex` 套件**的 `timeout` 參數：自己實驗確認可用，單行逾時剛好 1.0 秒。
- **ripgrep** 的 Windows 支援與安裝方式：官方 README，2026-10-17 查閱。

## 下一篇

還沒做的工具：建立新檔（`write_file`）。之後是限制測試程式能讀寫哪裡的沙箱。
