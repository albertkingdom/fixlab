# 第 2 篇：讓模型看得到專案

> 對應任務：bootstrap-agent-core 的 3.2（工具清單）、3.3（`read_file`）、3.4（`list_files`）。
> 完成度：這篇先寫前半，三個任務與測試都已完成（`pytest` 45 個通過）。後半要等 3.5 迴圈、3.6 最小入口、3.7 用真模型唯讀探索完成後補上，所以這裡的工具還沒有被真正的模型用過，「已知限制與待驗證」那一節列的就是還沒驗證的事。

第 1 篇讓程式能接住模型的呼叫。但模型現在還有兩件事做不到：它不知道自己有哪些工具，也看不到專案裡有什麼。這一篇補上這兩件事：把工具清單交給模型，再做兩個最基本的工具，`list_files`（看專案有哪些檔案）和 `read_file`（讀一個檔案）。

```
                    ┌─ tool_specs() ─► 送給模型：「你有這些工具」
登記表（Workspace） ─┼─ schemas()    ─► parse_message：「這個呼叫合不合法」
                    └─ call()       ─► 執行工具，結果送回給模型
```

## 模型怎麼知道有哪些工具

呼叫模型的 API 時，每次請求都要附上一份 `tools` 清單。模型只能呼叫清單上的工具，清單上沒有的它不會知道。

這份清單從哪來？第 1 篇的 `Workspace` 已經有一張**登記表**：工具名稱對應到執行的函式與參數規格。3.2 在登記表上補了兩個唯讀的視圖：

- `tool_specs()`：把登記表轉成 API 要的格式，送給模型看。
- `schemas()`：同一份規格，給第 1 篇的 `parse_message` 檢查「模型呼叫的工具存在嗎、必要參數齊全嗎」。

清單和檢查都從同一張登記表產生，不會出現「模型看得到某個工具，執行時卻說 unknown tool」。註冊時多了一個 `description` 參數，那是寫給模型看的用途說明。

這是 `list_files` 實際產生的內容（縮排排版略為縮短）：

```json
{
  "type": "function",
  "function": {
    "name": "list_files",
    "description": "List the files under a directory (default: the working directory), recursively, one path per line, relative to the working directory. Skips .git, .venv, __pycache__, .pytest_cache and symbolic links. At most 200 entries are shown.",
    "parameters": {
      "type": "object",
      "properties": {
        "path": { "type": "string" }
      },
      "required": []
    }
  }
}
```

要注意：`Workspace` 自己不會去「告訴」模型任何事，它只是把資料準備好。把 `tool_specs()` 傳給 API 的是迴圈，那是 3.5。現在這兩個方法還沒有程式在用，只有測試在檢查。

其中 `"type": "object"` 是 API 要求的，但登記時我不讓每個工具自己寫，而是在 `tool_specs()` 統一補上。七個工具加上測試的假工具，只要有一處漏寫，送出去的規格就不完整，而且是呼叫真模型時才會發現。代價是登記的規格和送出的不是同一個物件，有測試檢查登記的那份沒有被改動。

## read_file：先寫天真版本

```python
def read_file(path):
    return open(os.path.join(root, path)).read()
```

第 1 篇已經看過它讀得到工作目錄外的檔案，也看過找不到檔案會丟例外。這一篇看另外幾種情況。我建了一個工作目錄 `ws/`，放了 timelog 範例專案，加上一個 12.3 萬字元的 `big.log`、一個空檔、一個二進位檔：

```
read_file('timelog/parser.py')    → (392 字元) '"""把工時字串換成分鐘數。\n支援 "2h"、"45m"、"1h30m" 這類寫法。"""\n\nimport re\n\n\nd'…
read_file('big.log')              → (123000 字元) '2026-10-16 INFO request handled id=00000\n2026-10-16 INFO req'…
read_file('empty.txt')            → ''
read_file('timelog')              → 例外 IsADirectoryError: [Errno 21] Is a directory: 'ws/timelog'
read_file('blob.bin')             → 例外 UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid
```

四個問題：

1. **沒有行號。** 模型讀完 `parser.py` 想說「第 12 行有問題」或「只看 10 到 12 行」，沒有任何依據可以指。
2. **大檔整個回。** `big.log` 的 12.3 萬字元會原封不動進入對話，而且對話歷史每一輪都會重送，成本和小模型的 context 都吃不消。
3. **空檔回空字串。** 模型收到一個什麼都沒有的結果，分不出是「檔案是空的」、「呼叫失敗」還是「出了什麼問題」。
4. **目錄、二進位檔變成例外。** 迴圈會因此崩潰。

## 補成現在的 read_file

```python
def read_file(ws, path, start_line=None, end_line=None):
    p = ws.resolve_inside(path)              # 第 1 篇的路徑守門
    # 不存在、是目錄、不是 UTF-8 文字 → ToolError，變成文字回給模型
    lines = 檔案內容.splitlines()
    # 空檔 → "(empty file)"
    # 每行加上「6 位靠右的行號 + tab」，只取 start_line 到 end_line
    # 超過 20000 字元 → 切掉，結尾註明
    # 整檔、沒被截斷的讀取 → 記進 ws.files_read
```

同一批檔案，換成現在的 `read_file`：

```
-- read_file({'path': 'timelog/parser.py'})  ok=True flags={}
     1	"""把工時字串換成分鐘數。
     2	支援 "2h"、"45m"、"1h30m" 這類寫法。"""
     3	
     4	import re
     5	
     6	
     7	def parse_duration(text):
     8	    """回傳 text 代表的分鐘數，格式不對時拋 ValueError。"""
     9	    text = text.strip()
    10	    if not re.fullmatch(r"(\d+[hm])+", text):
    11	        raise ValueError(f"invalid duration: {text!r}")
    12	    units = [re.match(r"(\d+)([hm])", text).groups()]
    13	    return sum(int(number) * (60 if unit == "h" else 1) for number, unit in units)
-- read_file({'path': 'timelog/parser.py', 'start_line': 10, 'end_line': 12})  ok=True flags={}
    10	    if not re.fullmatch(r"(\d+[hm])+", text):
    11	        raise ValueError(f"invalid duration: {text!r}")
    12	    units = [re.match(r"(\d+)([hm])", text).groups()]
-- read_file({'path': 'empty.txt'})  ok=True flags={}
(empty file)
-- read_file({'path': 'timelog'})  ok=False flags={}
error: 'timelog' is a directory, not a file; use list_files to see what it contains
-- read_file({'path': 'blob.bin'})  ok=False flags={}
error: not a UTF-8 text file: 'blob.bin'
-- read_file({'path': 'timelog/nope.py'})  ok=False flags={}
error: file not found: 'timelog/nope.py'
```

`big.log` 的結果只顯示頭尾（完整輸出 20111 字元）：

```
-- read_file({'path': 'big.log'})  ok=True flags={}
     1	2026-10-16 INFO request handled id=00000
     2	2026-10-16 INFO request handled id=00001
     3	2026-10-16 INFO request handled id=00002
   ...
   417	2026-10-16 INFO request h
[truncated: 143999 characters in total, showing the first 20000; use start_line and end_line to read the rest]
```

逐項說明：

- **行號格式**：行號靠右補空白到 6 格，後面接一個 tab。格式的依據是 Claude Code 的 Read 工具和 `cat -n`，不是我自己發明的。靠右對齊讓第 9 行和第 10 行的程式碼縮排起點落在同一欄，對縮排敏感的 Python 比較不會看錯。tab 是行號和原文之間唯一的分隔，不會和程式碼開頭的空白混在一起。
- **行範圍**：`start_line`、`end_line` 從 1 起算、含頭尾。起點小於 1、終點小於起點、起點超過檔案行數，都回 `ok=False` 的說明。
- **截斷**：超過 20000 字元就切掉，結尾明講總共多少字元、被切掉了，並指引用行範圍讀剩下的。一定要明講，否則模型會以為自己已經看完整個檔案。
- **所有錯誤都是文字**：目錄、二進位檔、找不到檔案都變成 `ok=False` 加一行說明，沒有例外。二進位檔那一項是 3.3 補的：解碼失敗的 `UnicodeDecodeError` 不是 `OSError`，第 1 篇的 `call()` 接不到，不處理就會讓迴圈崩潰。
- **`files_read`**：整檔、沒帶行範圍、沒被截斷的讀取，會把檔案記進 `Workspace.files_read`。上面的例子裡，`parser.py` 和 `empty.txt` 在裡面，讀了一段的、被截斷的、讀失敗的都不在。這是給 4.3 的 `write_file` 用的：覆寫既有檔案前要查模型是不是真的看過整個檔案。現在還沒有程式在用它。

## list_files：先寫天真版本

```python
def list_files():
    return [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]
```

在同一個 `ws/` 上（我另外放了 `.git/`、`timelog/__pycache__/` 和一個指向 `../secret.txt` 的符號連結 `link_secret`）：

```
ws/link_secret
ws/empty.txt
ws/big.log
ws/blob.bin
ws/tests/test_report.py
ws/.git/config
ws/.git/HEAD
ws/timelog/__init__.py
ws/timelog/formatting.py
ws/timelog/parser.py
ws/timelog/test_formatting.py
ws/timelog/report.py
ws/timelog/__pycache__/parser.cpython-314.pyc
```

另外一個放了 250 個檔案的目錄，這個寫法也會一次全部回傳（`count ws2: 250`）。問題：

1. **路徑帶著根目錄前綴。** 這裡的 `ws/` 是我用相對路徑縮短的；實際使用時是一長串暫存目錄的絕對路徑。模型把 `ws/timelog/parser.py` 拿去呼叫 `read_file`，路徑是相對於工作目錄的，就找不到了。
2. **列出一堆不該看的。** `.git/` 和 `__pycache__/` 對找 bug 沒有幫助，只會佔掉輸出。
3. **列出符號連結。** `link_secret` 指向工作目錄外面。這個函式在沙箱外以 Python 行程執行，模型之後如果能靠它讀到外面的內容，路徑守門就被繞過了。
4. **順序不固定。** `os.walk` 的順序取決於檔案系統，同一個專案在不同機器上可能不一樣，測試也沒辦法寫固定的預期結果。
5. **沒有上限。** 專案大一點就是一長串。
6. **空結果是空串列。** 跟 `read_file` 的空檔一樣，模型分不出「真的沒有檔案」和「出錯了」。

## 補成現在的 list_files

先把「走訪檔案」獨立出來，放在 `workspace.py`，因為之後的 `glob`、`grep` 和測試檔指紋掃描要遵守一模一樣的規則，各寫一份會漂移：

```python
SKIP_DIRS = frozenset({".git", ".venv", "__pycache__", ".pytest_cache"})

def iter_files(folder):
    for entry in folder.iterdir():
        if entry.is_symlink():
            continue                         # 不跟隨、也不列出符號連結
        if entry.is_dir():
            if entry.name not in SKIP_DIRS:
                yield from iter_files(entry) # 子資料夾的檔案由同一個函式產生，原樣轉吐出去
        else:
            yield entry
```

`yield` 讓函式變成產生器：每找到一個檔案就吐出一個，呼叫端用 `for` 或 `sorted()` 一個一個拿。`yield from` 是把另一個產生器（這裡是對子資料夾的下一層呼叫）吐出來的東西原樣轉吐出去。

我一開始用的是 `os.walk`，要靠「就地修改它交給你的 `dirnames` 串列」來剪掉不想進的目錄。那個寫法有效，但特殊到需要註解才看得懂，而且少打一個 `[:]` 就悄悄失效，不會報錯。教學導向的專案要求程式讀起來像偽碼，所以改成上面的遞迴寫法。

`list_files` 本身：

```python
def list_files(ws, path="."):
    start = ws.resolve_inside(path)           # 路徑守門
    # 不存在、不是目錄 → ToolError
    names = sorted(相對於工作目錄的路徑 for 每個 iter_files(start) 吐出的檔案)
    # 沒有檔案 → "no files listed"
    # 超過 200 筆 → 只留前 200，結尾註明省略幾筆
```

結果：

```
-- list_files({})  ok=True flags={}
big.log
blob.bin
empty.txt
tests/test_report.py
timelog/__init__.py
timelog/formatting.py
timelog/parser.py
timelog/report.py
timelog/test_formatting.py
-- list_files({'path': 'timelog'})  ok=True flags={}
timelog/__init__.py
timelog/formatting.py
timelog/parser.py
timelog/report.py
timelog/test_formatting.py
```

`.git/`、`__pycache__/` 和符號連結都不見了。250 個檔案的目錄：

```
-- list_files() on 250 files: 201 lines
pkg/mod_000.py
pkg/mod_001.py
...
pkg/mod_199.py
[50 more entries omitted; list a subdirectory to see them]
```

只有 `.git` 目錄時：

```
-- list_files() with only .git: True 'no files listed'
```

幾個決定：

- **路徑相對於工作目錄**，不是相對於被列出的那個目錄。第二個例子 `list_files({'path': 'timelog'})` 輸出仍是 `timelog/parser.py`，模型直接拿去呼叫 `read_file`，不用再拼路徑。
- **排序依完整相對路徑的字串**，所以輸出可預測。排序在 `list_files` 做，不在 `iter_files` 裡面做：逐層排序排不出整體的字串順序（例如 `a.py` 要排在 `a/b.py` 之前），所以走訪函式不保證順序。
- **遞迴列出全部，不是只列一層。** 理由是範例專案小，一次看到整個結構可能比逐層點開省步數。這是假設，還沒驗證，見下一節。
- **空結果明確回報。** `no files listed` 加 `ok=True`，和失敗的呼叫分得開。

## 怎麼驗證

| 測試檔 | 驗證什麼 |
|---|---|
| `tests/test_tools.py`（28 個，其中 3 個對應 3.2、12 個對應 `read_file`、9 個對應 `list_files`） | **3.2**：`tool_specs()` 含工具的名稱、說明與帶 `"type": "object"` 的參數；`schemas()` 餵給 `parse_message` 時合法呼叫通過、缺必填參數被擋；`python` 設定。**`read_file`**：整檔（含結尾換行）、行範圍、空檔、缺檔、目錄、截斷、三種不合理的行範圍、二進位檔、路徑逃逸被擋、出現在 `tool_specs()`；整檔讀取才進 `files_read`。**`list_files`**：小專案排序、250 檔上限、符號連結、無檔可列、快取目錄在任何深度都被跳過、子目錄路徑相對於工作目錄、路徑不存在或是檔案、`..` 被擋 |

## 已知限制與待驗證

這些工具的輸出格式都還沒被真正的模型看過。下面前四項已記進 `design.md` 的 Risks 和 3.7 的觀察清單，要等 3.7 看模型的實際反應才知道要不要調整。

- **截斷可能切在一行中間。** 上面 `big.log` 的例子就是：第 417 行只剩 `2026-10-16 INFO request h`。結尾的說明沒有告訴模型最後完整的是第幾行。另外，說明裡的「143999 characters in total」算的是加了行號之後的輸出，不是原檔的 12.3 萬字元，兩者會對不起來。
- **行號靠右補空白的格式，沒有和不補空白的版本比較過。** 它對小模型是否真的比較清楚，目前只是推測。
- **「遞迴列出全部比較省步數」只是假設。** 另外，遞迴加 200 筆上限，專案變大時依路徑排序的後段目錄會被整個截掉，模型只知道省略筆數。
- **明確指定 `path=".git"` 會列出裡面的檔案。** 跳過清單只作用在往下走訪時，規格沒有定義這種情況。
- **`read_file` 只認 UTF-8。** 其他編碼的文字檔（例如 Big5）會被當成不是文字檔。
- **遞迴版遇到讀不了的子目錄，整次 `list_files` 會失敗。** `iterdir()` 丟出 `PermissionError`，`call()` 接住後回 `ok=False`。目前的工作目錄都是自己建的複本，不會發生。
- **`files_read` 和 `iter_files` 目前只有 `read_file`、`list_files` 在用。** 另外的使用者（`write_file`、`glob`、`grep`、測試檔指紋）還沒做。

## 參考來源

看過高見龍 KeSi 的程式（MIT，Copyright (c) 2026 Eddie Kao）：他的 `read_file` 直接回原始文字，沒有行號；`list_files` 用 `iterdir()` 只列一層，目錄後面加 `/`，依檔名排序，上限也是 200；`glob_files` 才是依完整相對路徑排序。fixlab 的行號格式來自 Claude Code 的 Read 工具與 `cat -n`，遞迴列出全部是規格自己的決定，不是參考他的。

採用的想法只有一個：「空結果要明確回報，讓模型分得出沒找到與沒執行成功」，出自他的〈讓 Agent 看見專案〉。他的版本在目錄是空的和內容全被過濾掉時回同一句話，fixlab 的 `no files listed` 同樣不區分這兩種情況。

`read_file` 對二進位檔回錯誤文字，他的程式也有這個處理。我是從「工具錯誤不能讓迴圈崩潰」的規格推出來的，寫完才看到他也這樣做。

## 下一篇（後半）

3.5 把迴圈接上，把 `tool_specs()` 真的送給模型；3.6 做最小入口 `fixlab`；3.7 用真模型對 timelog 做一次唯讀探索，上面那些待驗證的事會在那時有答案。
