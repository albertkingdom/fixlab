# 第 2 篇：讓模型看得到專案

> 對應任務：bootstrap-agent-core 的 3.2（工具清單）、3.3（讀檔工具 `read_file`）、3.4（列檔案工具 `list_files`）。
> 完成度：這篇寫的是前半，三個任務與測試都已完成（寫這篇時全部測試 45 個通過）。後半（迴圈、最小入口、用真模型做唯讀探索）已經寫成第 3 篇。這篇寫成時，這裡的工具還沒有被真正的模型用過，「已知限制與待驗證」那一節列的是當時還沒驗證的事，後來的結果見第 3 篇。

第 1 篇讓程式能接住模型的呼叫。但模型現在還有兩件事做不到：它不知道自己有哪些工具，也看不到專案裡有什麼。這一篇補上這兩件事：把工具清單交給模型，再做兩個最基本的工具，一個列出專案有哪些檔案，一個讀取單一檔案。

```
                      ┌─ tool_specs() ─► 送給模型：「你有這些工具」
登記表（工作區） ──────┼─ schemas()    ─► 檢查呼叫：「這個呼叫合不合法」
                      └─ call()       ─► 執行工具，結果送回給模型
```

## 模型怎麼知道有哪些工具

呼叫模型的 API 時，每次請求都要附上一份 `tools` 清單。模型只能呼叫清單上的工具，清單上沒有的，它不會知道。

這份清單從哪裡來？第 1 篇的工作區（`Workspace`）已經有一張**登記表**：工具名稱對應到執行的函式與參數規格。3.2 在登記表上補了兩個唯讀的視圖：

- `tool_specs()`：把登記表轉成 API 要的格式，送給模型看。
- `schemas()`：同一份規格，給第 1 篇的 `parse_message` 檢查「模型呼叫的工具存在嗎、必要參數齊全嗎」。

清單和檢查都從同一張登記表產生，所以不會出現「模型看得到某個工具，執行時卻說這個工具不存在」。登記時多了一個 `description` 參數，那是寫給模型看的用途說明。

這是列檔案工具實際產生的內容（縮排排版略為縮短）：

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

要注意：工作區自己不會去「告訴」模型任何事，它只是把資料準備好。真正把 `tool_specs()` 傳給 API 的是迴圈（第 3 篇）。寫這篇時，這兩個方法還沒有程式在用，只有測試在檢查。

其中 `"type": "object"` 是 API 要求的，但登記時我不讓每個工具自己寫，而是在 `tool_specs()` 統一補上。所有工具加上測試用的假工具，只要有一處漏寫，送出去的規格就不完整，而且要呼叫真模型時才會發現。代價是登記的規格和送出的不是同一個物件，所以有測試檢查登記的那份沒有被改動。

## 讀檔工具：先寫天真版本

```python
def read_file(path):
    return open(os.path.join(root, path)).read()
```

第 1 篇已經看過它讀得到工作目錄外的檔案，也看過找不到檔案會丟出例外。這一篇看另外幾種情況。我建了一個工作目錄 `ws/`，放了範例專案 timelog，再加上一個 12.3 萬字元的 `big.log`、一個空檔、一個二進位檔：

```
read_file('timelog/parser.py')    → (392 字元) '"""把工時字串換成分鐘數。\n支援 "2h"、"45m"、"1h30m" 這類寫法。"""\n\nimport re\n\n\nd'…
read_file('big.log')              → (123000 字元) '2026-10-16 INFO request handled id=00000\n2026-10-16 INFO req'…
read_file('empty.txt')            → ''
read_file('timelog')              → 例外 IsADirectoryError: [Errno 21] Is a directory: 'ws/timelog'
read_file('blob.bin')             → 例外 UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid
```

有四個問題：

1. **沒有行號。** 模型讀完 `parser.py`，想說「第 12 行有問題」或「只看第 10 到 12 行」，卻沒有任何依據可以指。
2. **大檔整個回傳。** `big.log` 的 12.3 萬字元會原封不動進入對話，而對話紀錄每一輪都會重送，成本和小模型的上下文長度都吃不消。
3. **空檔回傳空字串。** 模型收到一個什麼都沒有的結果，分不出是「檔案是空的」、「呼叫失敗」還是「出了什麼問題」。
4. **目錄、二進位檔變成例外。** 迴圈會因此崩潰。

## 補成現在的讀檔工具

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

同一批檔案，換成現在的讀檔工具：

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

`big.log` 的結果只顯示頭尾（完整輸出共 20111 字元）：

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

- **行號格式**：行號靠右補空白到 6 格，後面接一個 tab。格式的依據是 Claude Code 的讀檔工具和 `cat -n`，不是我自己發明的。靠右對齊，讓第 9 行和第 10 行的程式碼縮排起點落在同一欄，對縮排敏感的 Python 比較不會看錯。tab 是行號和原文之間唯一的分隔，不會和程式碼開頭的空白混在一起。
- **行範圍**：`start_line`、`end_line` 從 1 起算，含頭尾。起點小於 1、終點小於起點、起點超過檔案行數，都會回報失敗並附上說明。
- **截斷**：超過 20000 字元就切掉，結尾明講總共多少字元、被切掉了，並指引用行範圍讀剩下的部分。一定要明講，否則模型會以為自己已經看完整個檔案。
- **所有錯誤都是文字**：目錄、二進位檔、找不到檔案，都變成「失敗加一行說明」，沒有例外。二進位檔那一項是 3.3 補上的：解碼失敗的 `UnicodeDecodeError` 不屬於作業系統錯誤（`OSError`），第 1 篇的 `call()` 接不到，不處理就會讓迴圈崩潰。
- **`files_read`**：整檔、沒帶行範圍、沒被截斷的讀取，會把檔案記進工作區的 `files_read` 名單。上面的例子裡，`parser.py` 和 `empty.txt` 在名單裡，只讀一段的、被截斷的、讀取失敗的都不在。這份名單是給之後的寫檔工具用的：覆寫既有檔案之前，要查模型是不是真的看過整個檔案。寫這篇時還沒有程式在用它。

## 列檔案工具：先寫天真版本

```python
def list_files():
    return [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]
```

在同一個 `ws/` 上（我另外放了 `.git/`、`timelog/__pycache__/`，和一個指向 `../secret.txt` 的符號連結 `link_secret`）：

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

另外一個放了 250 個檔案的目錄，這個寫法也會一次全部回傳（輸出 `count ws2: 250`）。問題有：

1. **路徑帶著根目錄前綴。** 這裡的 `ws/` 是我用相對路徑縮短的；實際使用時，那是一長串暫存目錄的絕對路徑。模型把 `ws/timelog/parser.py` 拿去呼叫讀檔工具，但讀檔工具的路徑是相對於工作目錄的，就找不到了。
2. **列出一堆不該看的。** `.git/` 和 `__pycache__/` 對找 bug 沒有幫助，只會佔掉輸出。
3. **列出符號連結。** `link_secret` 指向工作目錄外面。這個函式在沙箱外，由 Python 程式直接執行，如果模型之後能靠它讀到外面的內容，路徑守門就被繞過了。
4. **順序不固定。** `os.walk` 的順序取決於檔案系統，同一個專案在不同機器上可能不一樣，測試也沒辦法寫固定的預期結果。
5. **沒有上限。** 專案大一點，就是一長串。
6. **空結果是空串列。** 和讀檔工具的空檔一樣，模型分不出是「真的沒有檔案」還是「出錯了」。

## 補成現在的列檔案工具

先把「走訪檔案」獨立出來，放在 `workspace.py`。因為之後的搜尋內容，和測試檔指紋掃描，都要遵守一模一樣的規則，各寫一份會慢慢不一致：

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

`yield` 讓函式變成產生器：每找到一個檔案就吐出一個，呼叫的一方用 `for` 或 `sorted()` 一個一個拿。`yield from` 是把另一個產生器（這裡是對下一層子資料夾的呼叫）吐出來的東西，原樣轉吐出去。

我一開始用的是 `os.walk`，要靠「就地修改它交給你的 `dirnames` 串列」來剪掉不想進的目錄。那個寫法有效，但特殊到需要註解才看得懂，而且少打一個 `[:]` 就會悄悄失效，不會報錯。這個專案以教學為目的，要求程式讀起來像偽碼，所以改成上面的遞迴寫法。

列檔案工具本身：

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

- **路徑相對於工作目錄**，不是相對於被列出的那個資料夾。第二個例子 `list_files({'path': 'timelog'})` 的輸出仍然是 `timelog/parser.py`，模型可以直接拿去讀檔，不用再自己拼路徑。
- **依完整相對路徑的字串排序**，所以輸出可以預測。排序在列檔案工具裡做，不在走訪函式裡做：逐層排序排不出整體的字串順序（例如 `a.py` 要排在 `a/b.py` 之前），所以走訪函式不保證順序。
- **遞迴列出全部，不是只列一層。** 理由是範例專案很小，一次看到整個結構，可能比逐層點開更省步數。這是假設，還沒驗證，見下一節。
- **空結果明確回報。** 回 `no files listed` 並標記成功，和失敗的呼叫分得開。

## 怎麼驗證

測試都在 `tests/test_tools.py`（寫這篇時共 28 個，其中 3 個對應 3.2、12 個對應讀檔、9 個對應列檔案）：

- **工具清單（3.2）**：`tool_specs()` 含工具的名稱、說明，以及帶 `"type": "object"` 的參數；`schemas()` 餵給 `parse_message` 時，合法的呼叫通過、缺必填參數的被擋；Python 直譯器的設定。
- **讀檔**：整個檔案（含結尾換行）、行範圍、空檔、缺檔、目錄、截斷、三種不合理的行範圍、二進位檔、路徑逃逸被擋、出現在工具清單裡；只有整檔讀取才會進 `files_read`。
- **列檔案**：小專案的排序、250 個檔案的上限、符號連結、沒有檔案可列、快取資料夾在任何深度都被跳過、子資料夾的路徑相對於工作目錄、路徑不存在或是個檔案、`..` 被擋。

## 已知限制與待驗證

寫這篇時，這些工具的輸出格式都還沒被真正的模型看過。下面前四項已經記進設計文件的風險清單，也列入後來真模型探索的觀察項目，要看模型的實際反應才知道要不要調整。結果（簡短版）：範例專案的檔案太小，沒有觸發截斷；行號格式沒有出問題；遞迴列出是否省步數，仍然無法判斷。詳見第 3 篇與設計文件的風險清單。

- **截斷可能切在一行中間。** 上面 `big.log` 的例子就是：第 417 行只剩 `2026-10-16 INFO request h`。結尾的說明沒有告訴模型最後完整的是第幾行。另外，說明裡的「143999 characters in total」算的是加了行號之後的輸出，不是原檔的 12.3 萬字元，兩者會對不起來。
- **行號靠右補空白的格式，沒有和不補空白的版本比較過。** 它對小模型是否真的比較清楚，目前只是推測。
- **「遞迴列出全部比較省步數」只是假設。** 另外，遞迴加上 200 筆的上限，專案變大時，依路徑排序的後段資料夾會被整個截掉，模型只知道被省略了幾筆。
- **明確指定 `path=".git"` 會列出裡面的檔案。** 跳過清單只作用在往下走訪的時候，規格沒有定義這種情況。
- **讀檔只認 UTF-8。** 其他編碼的文字檔（例如 Big5）會被當成不是文字檔。
- **遞迴版遇到讀不了的子資料夾，整次列檔案都會失敗。** 走訪時丟出權限錯誤，`call()` 接住後回報失敗。目前的工作目錄都是自己建的，不會發生。
- **`files_read` 和 `iter_files` 寫這篇時只有這兩個工具在用。** 其他會用到的工具（寫檔、搜尋內容、測試檔指紋）當時還沒做。

## 參考來源

看過高見龍 KeSi 的程式（MIT 授權，Copyright (c) 2026 Eddie Kao）：他的讀檔工具直接回傳原始文字，沒有行號；列檔案工具用 `iterdir()` 只列一層，資料夾後面加 `/`，依檔名排序，上限也是 200；搜尋檔名的工具才是依完整相對路徑排序。這個專案的行號格式來自 Claude Code 的讀檔工具與 `cat -n`，遞迴列出全部是規格自己的決定，不是參考他的。

採用的想法只有一個：「空結果要明確回報，讓模型分得出沒找到與沒執行成功」，出自他的〈讓 Agent 看見專案〉。他的版本在資料夾是空的、和內容全被過濾掉時，回的是同一句話；這個專案的 `no files listed` 同樣不區分這兩種情況。

讀檔工具對二進位檔回錯誤文字，他的程式也有這個處理。我是從「工具的錯誤不能讓迴圈崩潰」這條規格推出來的，寫完才看到他也這樣做。

## 下一篇

第 3 篇：把迴圈接上，把工具清單真的送給模型；做最小入口 `fixlab PATH`；用真模型對範例專案做一次唯讀探索，上面那些待驗證的事在那裡有答案。
