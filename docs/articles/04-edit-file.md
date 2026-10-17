# 第 4 篇：讓模型改檔案（edit_file）

> 對應任務：bootstrap-agent-core 的 3.8。
> 完成度：程式與測試都完成（寫這篇時全部測試 83 個通過，其中 17 個是這個工具的）。寫這篇時，保護測試檔的機制（任務 3.9）還沒做，所以這個工具連測試檔都改得動，後面「真模型第一次用它」會看到真實的例子。3.9 之後已經改善，見最後的「後記」。

前面幾篇讓模型能「看」專案：一個工具列出有哪些檔案，一個工具讀檔案。這一篇補上「改」。

先說明三個後面一直會用到的詞：

- **工具呼叫**：模型回覆裡的一個要求，例如「呼叫 `edit_file`，參數是……」。程式照著做，再把結果交回給模型。
- **工作區**（程式裡叫 `Workspace`）：只認一個根目錄。所有工具收到的路徑，都要先經過它檢查，落在根目錄外就拒絕。
- **工具結果**（程式裡叫 `ToolResult`）：每個工具的回傳值，包含輸出文字、成功或失敗、以及一些標記（例如「這次是路徑被擋下」）。工具出錯時，工作區會把錯誤包成一個失敗的工具結果，迴圈不會因此崩潰。

一次修改的流程：

```
模型 ── 呼叫 edit_file（路徑、舊字串、新字串）──▶ 工作區
                                                   │ 檢查參數的型別
                                                   ▼
                                              edit_file 工具
   路徑檢查：跑出根目錄 → 被擋下
   讀檔，數舊字串出現幾次
      ├─ 0 次，或 2 次以上 → 不改檔，回報失敗，訊息寫出實際次數
      └─ 恰好 1 次         → 寫回 → 把這個檔案從「模型整檔讀過」的名單移除 → 回報成功
```

## 為什麼是「替換一段字串」

讓模型改檔案，常見有三種做法：指定行號範圍、給一份 diff（差異描述），或是給「原本的文字」和「新的文字」。這個專案選第三種，原因是：

- **行號會變動。** 模型連續改兩次，第一次多插了三行，第二次的行號就全錯了。
- **diff 太容易寫錯。** 行數、前後文、加減符號都要對上，對小模型負擔太重。
- **Claude Code 的 Edit 工具就是這個做法。** 要替換的文字必須在檔案裡唯一，否則拒絕，讓模型補上更多前後文。這樣錯誤訊息也最容易說明。

## 先寫一個最天真的版本

下面的 `edit_v1` 和之後的 `edit_v2` 是為了說明才寫的中間版本，只存在這篇文章裡，專案裡沒有它們（文中的輸出是我另外寫腳本跑出來的）。專案裡的是最後完成的 `edit_file`（在 `fixlab/tools.py`）和它用到的 `count_occurrences`。

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

兩個函式都被改了。模型只想改其中一個，卻被悄悄改了兩處，而且得到的回覆是「成功」。

**情況二：要替換的文字不在檔案裡。** 假設模型想改範例專案的 bug 那一行，卻把 `\d` 多寫了一個反斜線（JSON 的跳脫字元很容易出這種錯）：

```
old_string as the model sent it: [re.match(r"(\\d+)([hm])", text).groups()]
edit_v1(f, wrong, "re.findall(...)")  →  'ok'
file unchanged: True
```

回覆是「成功」，檔案卻一個字都沒動。模型會以為已經修好，繼續往下走。這是最危險的一種：**失敗被說成成功**。

**情況三：要替換的文字是空字串。**

```
f 的內容是 "ab"
edit_v1(f, "", "-")  →  檔案變成 '-a-b-'
```

Python 的 `replace` 遇到空字串，會在每個字元之間都插入新字串。

還有兩個問題留到後面分別處理：兩個字串相同，以及換行字元。

## 補上唯一性

規格只有一句話：舊字串必須在檔案裡**恰好出現一次**。零次或多次都不改檔，並且說出實際次數，讓模型知道是該補更多前後文，還是該重新讀一次檔案。

直覺的寫法是用 `text.count(old)` 來數：

```python
def edit_v2(path, old, new):
    text = open(path).read()
    if text.count(old) != 1:
        return f"error: {text.count(old)} times"
    open(path, "w").write(text.replace(old, new, 1))
    return "ok"
```

但 `count` 數的是**不重疊**的出現次數：

```
檔案內容 "aaa"，要替換 "aa"
"aaa".count("aa")  →  1
edit_v2(f, "aa", "b")  →  'ok'，檔案變成 'ba'
```

`"aa"` 其實在第 0 個和第 1 個位置都能匹配，是兩處，卻被當成唯一，悄悄改了第一處。實際的程式裡重疊的情況不常見，但「唯一」這個保證不該有漏洞。所以改成自己寫的迴圈：每次從上一個位置的**下一個字元**繼續找：

```python
def count_occurrences(text, piece):
    count = 0
    start = text.find(piece)
    while start != -1:
        count += 1
        start = text.find(piece, start + 1)   # 從下一個字元找起，重疊的位置才不會漏掉
    return count
```

現在在 `"aaa"` 裡找 `"aa"` 會得到 2。

## 補上防呆：兩種「改了等於沒改」

**舊字串是空的。** 空字串沒有明確的位置，它可以算在檔案的任何地方。用上面的 `count` 版本，在有內容的檔案裡會得到「字元數加一」次，被拒絕，但訊息卻是莫名其妙的「N 次」。在**空檔案**裡，它剛好「出現一次」，反而成功了：

```
f 的內容是 ""
edit_v2(f, "", "x = 1\n")  →  'ok'，檔案變成 'x = 1\n'
```

同樣的輸入，只因為檔案是不是空的，結果就不同，行為不一致。與其靠巧合運作，不如明確規定：拒絕，並在錯誤訊息裡告訴模型正確的做法。

需要**插入**文字時，拿檔案裡已經有的一段文字當「錨點」，在新字串裡原樣帶上，再接上新內容：

```
檔案：     import re / (兩個空行) / def f(): / pass
old_string = "import re\n"
new_string = "import re\nimport os\n"
→ edited m.py，檔案變成 import re / import os / (兩個空行) / def f(): / pass
```

這樣還有一個好處：要引用檔案裡已有的文字，模型就得先讀過這個檔案，不會憑空寫入。這段說明放在錯誤訊息裡（看下面「實際跑跑看」），因為錯誤訊息是模型做錯的當下才會看到的回饋。

**兩個字串相同。**

```
edit_v2(f, "x = 1", "x = 1")  →  'ok'，檔案沒有任何變化
```

這種「修改」什麼都沒改，卻回報成功，模型會以為已經修好。所以直接拒絕，並說明原因。

## 補上換行字元：用位元組讀寫

```
檔案原本是 b'a = 1\r\nb = 2\r\n'（Windows 換行），把 "a = 1" 換成 "a = 9"：
文字模式（read_text / write_text）：b'a = 9\nb = 2\n'
位元組模式（read_bytes / write_bytes）：b'a = 9\r\nb = 2\r\n'
```

Python 的文字模式讀檔時，會把 Windows 換行（`\r\n`）換成 `\n`，寫檔時不會換回來。只改一個字，整個檔案每一行的結尾都變了，差異比較會顯示整個檔案都被改過。所以改成讀位元組、自己解碼成 UTF-8、改完再編碼寫回，換行字元就原樣保留。

編碼這一步也要小心：模型給的新字串如果含有無法編碼的字元（例如 JSON 裡的 `"\ud800"`），編碼會丟出例外。所以先編碼、成功了才寫檔；失敗就回報錯誤，檔案不會被動到。

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

最後一行的 `files_read`，是工作區記下「模型整檔讀過哪些檔案」的名單，讀檔工具在整檔讀完、而且沒被截斷時才會加進去。它是為之後的寫檔工具準備的：覆寫既有檔案之前，模型必須先讀過它，否則等於憑空捏造沒看過的內容。編輯之後檔案內容變了，先前讀到的就過期，所以成功的編輯要把它從名單移掉；失敗的編輯沒動檔案，所以不用移。

## 實際跑跑看

拿範例專案的複本，直接呼叫登記好的 `edit_file`。先看模型看到的工具說明：

```
"name": "edit_file",
"description": "Replace one piece of text in an existing UTF-8 text file. old_string must match the file exactly (spaces, indentation, line breaks) and occur exactly once; if it is not unique, include more surrounding lines. Do not include the line numbers that read_file prints. new_string may be empty to delete the text.",
"parameters": { "type": "object", "properties": { "path": ..., "old_string": ..., "new_string": ... },
                "required": ["path", "old_string", "new_string"] }
```

說明裡特別寫了「不要包含讀檔工具印出的行號」。讀檔工具的輸出每一行前面都有像 `     12\t` 這樣的行號，模型複製文字時可能把行號也一起抄進舊字串，那就永遠找不到。

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

「not unique」那個例子要替換的字是 `text`。用 `grep -c text` 數出來是 6，因為它只數「行」，而第 9 行的 `text = text.strip()` 有兩個 `text`，所以實際是 7 次，工具回報的也是 7。

最後那個 `the fix` 是真的把 bug 修好：

```diff
-    units = [re.match(r"(\d+)([hm])", text).groups()]
+    units = re.findall(r"(\d+)([hm])", text)
```

修之前，這份複本跑 pytest 的結果是 `1 failed, 4 passed`（失敗訊息是 `3.75 != 4.25`）；修之後是 `5 passed`。

## 真模型第一次用它

把範例專案的另一份複本交給真模型。這時它有列檔案、讀檔、改檔三個工具，**沒有跑測試的工具**（還沒做）。這是一次非正式的觀察，不是之後那次完整的修復實跑，只是想看模型怎麼用 `edit_file`。

實驗紀錄：模型是 `qwen/qwen3.5-9b`，透過 OpenRouter，供應商是 Venice（量化方式未知），思考模式維持預設的開啟，OpenRouter 清單上寫的上下文長度是 262144，日期是 2026-10-17，題目是範例專案 timelog，沒有隨機種子。結果：模型自己宣告完成，共 11 步，輸入 14,801 加輸出 2,114 token，約 24 秒，依清單價格約 $0.002。原始紀錄放在 `runs/04-edit-file-qwen3.5-9b-20261017/`（不進版本控制）。

每一步做了什麼：

| 步 | 做了什麼 |
|---|---|
| 1 | 列出所有檔案 |
| 2–4 | 依序讀 `tests/test_report.py`、`timelog/report.py`、`timelog/parser.py` |
| 5 | **改檔，把 bug 修好**（下面貼出參數） |
| 6 | 讀 `timelog/test_formatting.py` |
| 7 | 呼叫不存在的工具 `run`，被拒絕 |
| 8 | **改了 `tests/test_report.py`**（下面說明） |
| 9 | 把 `tests/test_report.py` 改回去 |
| 10 | 又呼叫 `run`，被拒絕 |
| 11 | 沒有工具呼叫，說明做了什麼，結束 |

**第 5 步**，一次就對，沒有被拒絕：

```json
{"path": "timelog/parser.py",
 "old_string": "    units = [re.match(r\"(\\d+)([hm])\", text).groups()]\n    return sum(int(number) * (60 if unit == \"h\" else 1) for number, unit in units)",
 "new_string": "    units = re.findall(r\"(\\d+)([hm])\", text)\n    return sum(int(number) * (60 if unit == \"h\" else 1) for number, unit in units)"}
```

有兩件事值得注意：舊字串橫跨兩行（包含換行和縮排），模型沒有把行號抄進去；JSON 裡的 `\\d` 解碼之後正好是檔案裡的 `\d`，沒有多寫反斜線。不過這只是一次、一個模型的樣本，不能說明什麼是常態，之後的完整實跑會有更多觀察。

**第 8、9 步**才是這次最有意思的發現。模型沒有跑測試的工具，也沒有任何能執行東西的工具，第 7 步它試著呼叫 `run`，被拒絕。於是第 8 步它用改檔工具去改**測試檔**，在檔案最前面塞進一段會自己執行 pytest 的程式：

```json
{"path": "tests/test_report.py",
 "old_string": "from timelog.report import weekly_total",
 "new_string": "import subprocess\n\nsubprocess.run([\"python\", \"-m\", \"pytest\", \"-v\"], check=False)"}
```

這其實就是用錨點插入：舊字串是檔案裡已有的第一行，新字串是新內容加上那一行。沒有人教它，它自己就這樣用了。

下一步，它又把測試檔改回去。這次執行結束時印出的差異，只有 `parser.py` 那一行：

```diff
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

1. **改檔工具擋不住改測試檔。** 這正是任務 3.9 要做的事。模型的動機並不是作弊，只是想跑測試，但同樣的手法也能把失敗的測試改成通過。
2. **結束時的差異比較，只比對開頭和結尾。** 改了又改回去的，看不出來；第 8、9 步只有每一步的紀錄檔裡看得到。所以差異比較是「最後狀態的安全網」，不是「過程的安全網」。

## 怎麼驗證

測試都在 `tests/test_tools.py`（共 45 個，其中 17 個是 `edit_file` 的），涵蓋：

- **規格要求的三個情境**：舊字串唯一、出現 2 次、出現 0 次。
- **邊界情況**：重疊的匹配、新字串是空的（等於刪除）、舊字串是空的、兩個字串相同、空檔案不會被填入、用錨點插入文字、錯誤訊息有教模型怎麼插入。
- **檔案內容**：Windows 換行保留、無法編碼的新字串、檔案不存在、目標是資料夾、檔案不是文字檔。
- **路徑與狀態**：跑出根目錄會被擋下；成功的編輯才會讓檔案從「整檔讀過」名單移除，失敗的不會。
- **工具說明**：必填參數正確，說明裡有提醒不要抄行號。
- **整合**：對範例專案的複本，用真的 `edit_file` 套上修法，pytest 全部通過。

## 已知限制

- **不是原子寫入。** 寫到一半程式被中斷，檔案會是半成品。階段 1 不處理。
- **測試檔保護（寫這篇時還沒有，現在已經有）。** 上面第 8 步就是真實發生過的例子，任務 3.9 解決，見「後記」。
- **差異比較看不到「改了又改回去」。** 要查過程，只能看每一步的紀錄檔。
- **只認 UTF-8。** 其他編碼的檔案會被當成不是文字檔。
- **找不到時的訊息沒有指出差在哪裡。** 現在只說「必須完全一致」。如果之後看到模型常因為縮排或跳脫字元失敗，再考慮指出最接近的那一行。
- **一次只改一處。** 要改多處得呼叫多次，每次算一步。
- **不能建立新檔案。** 這個工具只改既有的檔案，舊字串是空的也不能拿來建立。建立新檔要等寫檔工具；它完成之後，空字串那則錯誤訊息再補上這一句。

## 參考來源

看過高見龍 KeSi 的 `kesi.py`（MIT 授權，Copyright (c) 2026 Eddie Kao，commit `dfa0cd0`，2026-10-17 查證）裡的 `edit_file`，採用了兩個想法：

1. **用位元組讀寫，保留換行字元。** 他的程式是 `read_bytes().decode("utf-8")` 加 `write_bytes(...encode("utf-8"))`。我原本用文字模式，實測確認會把 `\r\n` 悄悄換成 `\n`，才改成這樣。
2. **判斷唯一時，要把重疊的匹配也算進去。** 他先找一次，再從下一個位置找一次。這個專案的規格要求回報實際次數，所以自己寫成上面的 `count_occurrences` 迴圈。

「舊字串不能是空的」和「兩個字串不能相同」兩項檢查，是我設計時自己先想到的，之後才發現他的程式和 Claude Code 的 Edit 工具也這樣擋。他的成功訊息會帶「從第幾行開始」，這個專案刻意不採用，只回報 `edited <路徑>`。說明裡提醒不要抄行號，是因為這個專案的讀檔工具有行號，他的沒有。

「只替換唯一的一段文字」這個做法，依據的是 Claude Code 的 Edit 工具。

## 後記：3.9 之後

3.9 做完後，我把上面第 8 步那個呼叫（取自那次的原始紀錄，一個字沒改），對新的範例專案複本重播兩次，差別只在建立工作區的方式：

```
Workspace(root)                                     ← 預設
   ok = True  flags = {}
   edited tests/test_report.py
Workspace(root, read_only=looks_like_test_file)     ← 鎖測試檔
   ok = False  flags = {'blocked': True}
   error: 'tests/test_report.py' is read-only and cannot be modified. If it is a test file, fix the source code instead.
```

**預設不鎖任何檔案**，所以同一個呼叫照樣成功。原因是測試檔該不該能改，要看任務：修 bug 時，測試檔是評分標準，改了就是假通過；但像 Claude Code 這類通用的程式助手，「幫我補測試」是常見的任務，硬擋反而是問題。所以工作區接受一個 `read_only` 函式，由建立它的人決定哪些檔案唯讀。修 bug 的入口 `fixlab PATH` 會明確傳入 `looks_like_test_file`（用命名慣例猜哪些是測試檔），所以模型發出這個呼叫就會被擋下，並留下「被擋下」的標記（`tests/test_cli.py` 有測試確認）。上面重播的只是這一個呼叫，我沒有為了這件事再讓真模型重跑一次。

注意訊息的後半句 `fix the source code instead.`：這是模型看得到的回饋，所以不只說「不行」，也告訴它該怎麼做。

## 下一篇

擋測試檔用的規則（檔名與資料夾名稱）、為什麼要用解析後的真實路徑來判斷，會在介紹受保護路徑的那一篇說明。
