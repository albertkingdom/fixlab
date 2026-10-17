# 第 4 篇：讓模型改檔案，edit_file

> 對應任務：bootstrap-agent-core 的 3.8（`edit_file`）。
> 完成度：程式與測試都完成（`pytest` 83 個通過，其中 17 個是 `edit_file` 的）。測試檔保護（3.9）還沒做，所以這個工具現在連測試檔都改得動，下面「真模型第一次用它」會看到這件事真的發生。

前面幾篇讓模型能「看」：`list_files` 看專案有哪些檔案，`read_file` 讀一個檔案。這一篇補上「改」。

先定義幾個詞，後面會一直用到：

- **工具呼叫（tool call）**：模型回覆裡的一個要求，例如「呼叫 `edit_file`，參數是 …」。程式照著執行，再把結果送回給模型。
- **Workspace**：只認一個根目錄的物件，所有工具的路徑都要先過它的 `resolve_inside()`，落在根目錄外就拒絕。
- **ToolResult**：每個工具的回傳值，有輸出文字、`ok`（成功與否）和 `flags`（例如 `blocked` 表示路徑被擋）。工具丟出 `ToolError` 時，Workspace 會把它轉成 `ok=False` 的 ToolResult，迴圈不會崩潰。

```
模型 ── edit_file(path, old_string, new_string) ──▶ Workspace.call
                                                     │ 參數型別檢查
                                                     ▼
                                              tools.edit_file
   resolve_inside(path)                    路徑守門，跑出根目錄 → blocked
   讀檔，數 old_string 出現幾次
      ├─ 0 次或 2 次以上 → 不改檔，ok=False，訊息寫實際次數
      └─ 恰好 1 次       → 寫回 → 把該檔從 files_read 移除 → ok=True
```

## 為什麼是「替換一段字串」

讓模型改檔案，常見有三種做法：給行號範圍、給 unified diff、給「原本的文字和新的文字」。`design.md` 選第三種，理由是：

- **行號會漂移。** 模型連續改兩次，第一次插入三行，第二次的行號就全錯了。
- **diff 太容易寫錯。** 它要求行數、前後文、`+`／`-` 全部對得上，對小模型負擔太重。
- **這是 Claude Code 的 Edit 工具的語意。** 要替換的文字必須在檔案裡唯一，否則拒絕，讓模型補更多前後文。錯誤訊息也最容易解釋。

## 先寫一個最天真的版本

下面的 `edit_v1` 和之後的 `edit_v2` 是為了說明才寫的中間版本，只存在於這篇文章（我另外用腳本跑出文中的輸出），專案裡沒有它們。專案裡的是最後的 `edit_file`（`fixlab/tools.py`）和它用到的 `count_occurrences`。

```python
def edit_v1(path, old, new):
    text = open(path).read()
    open(path, "w").write(text.replace(old, new))
    return "ok"
```

三行，看起來夠用。實際跑幾個情況：

**情況一：要替換的文字出現兩次。**

```
改之前：                改之後（呼叫 edit_v1(f, "return 0", "return 1") 回 'ok'）：
def a():                def a():
    return 0                return 1

def b():                def b():
    return 0                return 1
```

兩個函式都被改了。模型只想改其中一個，卻被悄悄改了兩處，而且回的是 `ok`。

**情況二：要替換的文字不在檔案裡。** 假設模型要改 timelog 的 bug 那一行，把 `\d` 多寫了一個反斜線（JSON 跳脫很容易出這種錯）：

```
old_string as the model sent it: [re.match(r"(\\d+)([hm])", text).groups()]
edit_v1(f, wrong, "re.findall(...)")  →  'ok'
file unchanged: True
```

回 `ok`，檔案一個字都沒動。模型會以為已經修好了，繼續往下走。這是最危險的一種：**失敗被說成成功**。

**情況三：要替換的文字是空字串。**

```
f 的內容是 "ab"
edit_v1(f, "", "-")  →  檔案變成 '-a-b-'
```

`str.replace("", x)` 會在每個字元之間都插入 `x`。

還有兩個問題留到下面分別處理：「兩個字串相同」和換行字元。

## 補上唯一性

規格只有一句話：`old_string` 必須在檔案裡**恰好出現一次**。零次或多次都不改檔，並且說出實際次數，讓模型知道該補更多前後文，還是該重新讀一次檔案。

直覺的寫法是 `text.count(old)`：

```python
def edit_v2(path, old, new):
    text = open(path).read()
    if text.count(old) != 1:
        return f"error: {text.count(old)} times"
    open(path, "w").write(text.replace(old, new, 1))
    return "ok"
```

但 `str.count` 數的是**不重疊**的出現次數：

```
檔案內容 "aaa"，要替換 "aa"
"aaa".count("aa")  →  1
edit_v2(f, "aa", "b")  →  'ok'，檔案變成 'ba'
```

`"aa"` 其實在位置 0 和位置 1 都能匹配，是兩處，卻被當成唯一，悄悄改了第一處。真實程式裡重疊的情況不常見，但「唯一」這個承諾不該有漏洞。改成自己寫的迴圈：每次從上一個位置的**下一個字元**往後找：

```python
def count_occurrences(text, piece):
    count = 0
    start = text.find(piece)
    while start != -1:
        count += 1
        start = text.find(piece, start + 1)   # 從下一個字元找起，重疊的位置才不會漏掉
    return count
```

`"aaa"` 裡找 `"aa"` 現在得到 2。

## 補防呆：兩種「改了等於沒改」

**空的 `old_string`。** 空字串沒有明確的位置，它可以算在檔案的任何地方。用上面的 `count` 版本，非空檔案裡會得到「字元數加一」次，被拒絕，訊息卻是莫名其妙的「N 次」。但在**空檔案**裡它剛好「出現一次」，就成功了：

```
f 的內容是 ""
edit_v2(f, "", "x = 1\n")  →  'ok'，檔案變成 'x = 1\n'
```

同樣的輸入，因為檔案是不是空的而得到不同結果，行為不一致。與其靠巧合運作，不如明確規定：拒絕，並在錯誤訊息裡告訴模型正確的做法。

需要**插入**文字時，拿檔案裡已經有的一段文字當「錨點」，在 `new_string` 裡原樣帶上，再接上新內容：

```
檔案：     import re / (兩個空行) / def f(): / pass
old_string = "import re\n"
new_string = "import re\nimport os\n"
→ edited m.py，檔案變成 import re / import os / (兩個空行) / def f(): / pass
```

這樣還多一個好處：要引用檔案裡已有的文字，模型就得先讀過這個檔案，不會憑空寫入。這個提示放在錯誤訊息裡（見下面「跑起來」），因為錯誤訊息是模型做錯的當下才會看到的回饋。

**兩個字串相同。**

```
edit_v2(f, "x = 1", "x = 1")  →  'ok'，檔案沒有任何變化
```

這種「修改」什麼都沒改，卻回成功，模型會以為已經修好。直接拒絕，並說明原因。

## 補換行字元：用 bytes 讀寫

```
檔案原本是 b'a = 1\r\nb = 2\r\n'（Windows 換行），把 "a = 1" 換成 "a = 9"：
文字模式（read_text / write_text）：b'a = 9\nb = 2\n'
bytes 模式（read_bytes / write_bytes）：b'a = 9\r\nb = 2\r\n'
```

Python 的文字模式讀檔時會把 `\r\n` 換成 `\n`，寫檔時不會換回來。只改一個字，整個檔案的每一行結尾都變了，diff 會是整檔都改。所以改成讀 bytes、自己解碼成 UTF-8、改完再編碼寫回，換行字元原樣保留。

編碼那一步也要小心：模型給的 `new_string` 如果含孤立的 surrogate 字元（JSON 的 `"\ud800"`），`encode("utf-8")` 會丟例外。所以先編碼、成功了才寫檔，失敗就回錯誤，檔案不會被動到。

## 最後的 edit_file

```python
def edit_file(ws, path, old_string, new_string):
    p = ws.resolve_inside(path)                          # 路徑守門
    # 檔案不存在、是目錄 → ToolError
    if old_string == "":            raise ToolError("old_string must not be empty. To insert text, use a nearby line ... as old_string ...")
    if old_string == new_string:    raise ToolError("old_string and new_string are identical, nothing to change")

    text = p.read_bytes().decode("utf-8")                # 不是 UTF-8 → ToolError

    count = count_occurrences(text, old_string)
    if count == 0:  raise ToolError("old_string occurs 0 times in ... must match the file exactly ...")
    if count > 1:   raise ToolError(f"old_string occurs {count} times in ... Include more surrounding lines ...")

    data = text.replace(old_string, new_string, 1).encode("utf-8")   # 先編碼，失敗就不動檔案
    p.write_bytes(data)
    ws.files_read.discard(p)                             # 模型沒看過編輯後的全文
    return ToolResult(f"edited {path}", True)
```

最後一行的 `files_read` 是 Workspace 記下「模型整檔讀過哪些檔案」的集合，`read_file` 整檔且沒被截斷時才加進去。它是為之後的 `write_file` 準備的：覆寫既有檔案前，模型必須讀過它，否則等於憑空捏造沒看過的內容。編輯之後檔案內容變了，之前讀的就過期，所以成功的編輯要把它移掉。失敗的編輯沒動檔案，所以不移。

## 跑起來

拿 timelog 範例專案的複本，直接呼叫登記好的 `edit_file`。先看模型看到的工具說明：

```
"name": "edit_file",
"description": "Replace one piece of text in an existing UTF-8 text file. old_string must match the file exactly (spaces, indentation, line breaks) and occur exactly once; if it is not unique, include more surrounding lines. Do not include the line numbers that read_file prints. new_string may be empty to delete the text.",
"parameters": { "type": "object", "properties": { "path": ..., "old_string": ..., "new_string": ... },
                "required": ["path", "old_string", "new_string"] }
```

說明裡特別寫了「不要包含 `read_file` 印出的行號」。`read_file` 的輸出每行前面有 `     12\t` 這樣的行號前綴，模型複製文字時可能把前綴一起抄進 `old_string`，那就永遠找不到。

幾種呼叫的結果：

```
-- near miss: \d written as \\d
   ok=False flags={}
   error: old_string occurs 0 times in 'timelog/parser.py'. It must match the file exactly, including
   spaces and indentation, and must not include line numbers. Use read_file to check the current text.
-- not unique
   ok=False flags={}
   error: old_string occurs 7 times in 'timelog/parser.py', but it must occur exactly once.
   Include more surrounding lines to make it unique.
-- empty old_string
   ok=False flags={}
   error: old_string must not be empty. To insert text, use a nearby line that already exists as
   old_string and repeat it in new_string together with the new text.
-- identical
   ok=False flags={}
   error: old_string and new_string are identical, nothing to change
-- outside the workspace
   ok=False flags={'blocked': True}
   error: path is outside the working directory: '../x.py'
-- the fix
   ok=True flags={}
   edited timelog/parser.py
```

「not unique」那個例子要替換的是 `text`。`grep -c text` 回 6，因為只數「行」，而第 9 行的 `text = text.strip()` 有兩個 `text`，所以實際是 7 次，工具回報的是 7。

最後那個 `the fix` 是真的把 bug 修好：

```
-    units = [re.match(r"(\d+)([hm])", text).groups()]
+    units = re.findall(r"(\d+)([hm])", text)
```

在修之前，這個複本跑 pytest 是 `1 failed, 4 passed`（失敗訊息是 `3.75 != 4.25`）；修之後 `5 passed`。

## 真模型第一次用它

把 timelog 的另一份複本交給真模型，工具有 `list_files`、`read_file`、`edit_file`，**沒有 `run_tests`**（還沒做）。這是一次非正式的觀察，不是 3.12 那次完整的修復 smoke，只為了看模型怎麼用 `edit_file`。

紀錄的欄位：模型 `qwen/qwen3.5-9b`，經 OpenRouter，provider 是 Venice（量化未知），thinking 預設開啟，OpenRouter 清單上的 context 是 262144，日期 2026-10-17，題目是 timelog，沒有隨機種子。結果：stop reason `done`，11 步，14,801 prompt 加 2,114 completion token，約 24 秒，依清單價格約 $0.002。原始紀錄在 `runs/04-edit-file-qwen3.5-9b-20261017/`（不進版控）。

每一步做了什麼：

| 步 | 做了什麼 |
|---|---|
| 1 | `list_files` |
| 2–4 | 依序讀 `tests/test_report.py`、`timelog/report.py`、`timelog/parser.py` |
| 5 | **`edit_file` 修好 bug**（下面貼出參數） |
| 6 | 讀 `timelog/test_formatting.py` |
| 7 | 呼叫不存在的工具 `run`，被拒絕 |
| 8 | **`edit_file` 改了 `tests/test_report.py`**（下面說明） |
| 9 | `edit_file` 把 `tests/test_report.py` 改回去 |
| 10 | 又呼叫 `run`，被拒絕 |
| 11 | 沒有工具呼叫，說明做了什麼，結束 |

**第 5 步**，一次就對，沒有被拒絕：

```json
{"path": "timelog/parser.py",
 "old_string": "    units = [re.match(r\"(\\d+)([hm])\", text).groups()]\n    return sum(int(number) * (60 if unit == \"h\" else 1) for number, unit in units)",
 "new_string": "    units = re.findall(r\"(\\d+)([hm])\", text)\n    return sum(int(number) * (60 if unit == \"h\" else 1) for number, unit in units)"}
```

兩件值得注意的事：`old_string` 跨了兩行（含換行和縮排），模型沒有把行號抄進去；JSON 裡的 `\\d` 解碼後正是檔案裡的 `\d`，沒有多寫反斜線。這只是一次、一個模型的樣本，不能說明什麼是常態，3.12 會有更多觀察。

**第 8、9 步**才是這次最有意思的發現。模型沒有 `run_tests`，也沒有任何能執行東西的工具，第 7 步它試著呼叫 `run`，被拒絕。於是第 8 步它用 `edit_file` 改了**測試檔**，在檔案最前面塞進一段會自己執行 pytest 的程式：

```json
{"path": "tests/test_report.py",
 "old_string": "from timelog.report import weekly_total",
 "new_string": "import subprocess\n\nsubprocess.run([\"python\", \"-m\", \"pytest\", \"-v\"], check=False)"}
```

這其實是用錨點插入的實例：`old_string` 是檔案裡已有的第一行，`new_string` 是新內容加上那一行，沒有人教它，它自己就這樣用了。

下一步又改回去。這次的最後一份 CLI 輸出，diff 只有 `parser.py` 那一行：

```
stop reason: done  steps: 11  tokens: 14801 prompt + 2114 completion

changes since start:
--- a/timelog/parser.py
+++ b/timelog/parser.py
@@ -9,5 +9,5 @@
     text = text.strip()
     if not re.fullmatch(r"(\d+[hm])+", text):
         raise ValueError(f"invalid duration: {text!r}")
-    units = [re.match(r"(\d+)([hm])", text).groups()]
+    units = re.findall(r"(\d+)([hm])", text)
     return sum(int(number) * (60 if unit == "h" else 1) for number, unit in units)
```

這暴露了兩個問題：

1. **`edit_file` 現在擋不住改測試檔。** 這正是 3.9 要做的事。模型的動機不是作弊，只是想跑測試，但同樣的手段也能把失敗的測試改成通過。
2. **結束時的 diff 只比較開頭和結尾。** 改了又改回去的，diff 看不到。第 8、9 步只有每步的紀錄（JSONL）裡看得到。所以 diff 是「最後狀態的安全網」，不是「過程的安全網」。

## 怎麼驗證

| 測試檔 | 驗證什麼 |
|---|---|
| `tests/test_tools.py`（共 45 個，其中 17 個對應 `edit_file`） | **規格三個情境**：唯一、2 次、0 次；**邊界**：重疊的匹配、空的 `new_string` 當刪除、空的 `old_string` 與兩字串相同（共 2 個）、空的 `old_string` 的訊息教模型怎麼插入、用錨點插入文字、空檔案不被填入、成功才移出 `files_read` 而失敗不移、CRLF 保留、無法編成 UTF-8 的 `new_string`、缺檔／目錄／二進位檔、路徑逃逸被擋；**出現在 `tool_specs()`**：必填參數與說明裡提到行號；**整合**：對 timelog 複本用真的 `edit_file` 套上修法，pytest 全過 |

## 已知限制

- **不是原子寫入。** `write_bytes` 寫到一半程式被殺掉，檔案會是半成品。階段 1 不處理。
- **測試檔保護還沒有。** 上面第 8 步是真的發生了的例子，3.9 解決。
- **diff 看不到「改了又改回去」。** 要查過程只能看每步紀錄。
- **只認 UTF-8。** 其他編碼的檔案會被當成不是文字檔。
- **0 次匹配的訊息沒有指出差在哪裡。** 現在只說「必須完全一致」。如果 3.12 看到模型常因為縮排或跳脫失敗，再考慮指出最接近的那一行。
- **一次只改一處。** 要改多處得呼叫多次，每次都是一步。
- **不能建立新檔案。** `edit_file` 只改既有的檔案，空的 `old_string` 也不能拿來建立。建立新檔要等 `write_file`；它完成之後，空 `old_string` 的錯誤訊息再補上這一句。

## 參考來源

看過高見龍 KeSi 的 `kesi.py`（MIT，Copyright (c) 2026 Eddie Kao，commit `dfa0cd0`，2026-10-17 查證）裡的 `edit_file`。採用了兩個想法：

1. **用 bytes 讀寫以保留換行字元。** 他的程式是 `read_bytes().decode("utf-8")` 加 `write_bytes(...encode("utf-8"))`。我原本用文字模式，實測確認會把 `\r\n` 悄悄換成 `\n`，才改成這樣。
2. **判斷唯一時要把重疊的匹配也算進去。** 他先 `find` 一次，再從下一個位置 `find` 一次。fixlab 的規格要求回報實際次數，所以自己寫成上面的 `count_occurrences` 迴圈。

「空的 `old_string`」與「兩個字串相同」兩項檢查，是我設計時自己先想到的，之後才發現他的程式和 Claude Code 的 Edit 工具也這樣擋。他的成功訊息會帶「從第幾行開始」，fixlab 刻意不採用，保持只回 `edited <path>`。說明裡提醒不要抄行號，是因為 fixlab 的 `read_file` 有行號、他的沒有。

「替換唯一的一段文字」這個語意的依據是 Claude Code 的 Edit 工具。

## 下一篇

3.9 讓 `edit_file` 改不了測試檔，正好擋住上面第 8 步那種做法。
