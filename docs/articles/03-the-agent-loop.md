# 第 3 篇：讓迴圈跑起來，`fixlab PATH` 與第一次真模型探索

> 對應任務：bootstrap-agent-core 的 3.5（迴圈）、3.6（最小入口 `fixlab PATH`）、3.7（用真模型對範例專案做唯讀探索）。
> 完成度：程式與測試都完成（全部測試 83 個通過，其中迴圈 5 個、入口 16 個）。迴圈裡「重試、截斷、空回覆、每步紀錄」這幾段程式已經在，但專門驗證它們的測試還沒補（排在後面的「迴圈保險」那一組）。所以第一節用腳本重現的幾個例子，目前不是專案裡的測試。

前面兩篇做好了零件：能解析模型的工具呼叫、有只認一個根目錄的工作區、有列檔案和讀檔兩個工具。這一篇把它們接起來，讓模型真的一步一步探索專案。

先說明這篇會用到的詞：

- **一步**：一次模型呼叫。模型的回覆裡可以有工具呼叫，也可以只有文字。
- **對話紀錄**（程式裡叫 `messages`）：每次請求都會整份送出。每一則訊息有一個角色：`system`（固定的行為說明）、`user`（任務與回饋）、`assistant`（模型說的話）、`tool`（工具執行的結果）。
- **token**：模型計費與計算長度的單位。**上下文長度**是一次請求最多能放多少 token。

## 誰決定下一步

專案的 AGENTS.md 把「agent」和「寫死的流程」的差別講得很清楚：**誰決定下一步**。程式寫死「先列檔案、再讀測試、再讀原始碼」，那是寫死的流程；由模型自己決定先做什麼、什麼時候算完成，才是 agent（能自己決定行動的程式）。所以迴圈只做兩件事：把工具的結果交回給模型，以及設保險（最多跑幾步）。它從不決定工具的順序。

## 先寫一個最天真的迴圈

```python
def naive_loop(client, tools, messages):
    while True:
        msg = client.chat.completions.create(model="m", messages=messages, tools=[...]).choices[0].message
        if not msg.tool_calls:
            return msg.content                      # 模型沒要呼叫工具 → 當作說完了
        for c in msg.tool_calls:
            args = json.loads(c.function.arguments)
            result = tools[c.function.name](**args) # 執行工具
            messages.append({"role": "tool", "tool_call_id": ..., "content": result})
```

十行左右，看起來能用。我寫了一個「劇本模型」（依序回傳事先排好的回覆，不連網），對它做五個壓力測試，同樣的劇本也交給專案裡的迴圈。下面是兩邊的真實輸出：

```
=== 1 工具呼叫的 JSON 壞掉
naive : crashed with JSONDecodeError: Unterminated string starting at: line 1 column 10 (char 9)
fixlab: stop_reason=done steps=2 counters={'parse_errors': 1}
        the model was told: Your tool call was invalid: bad arguments for read_file: Unterminated string starting at: line 1 column 10 (char 9). Please call a tool with valid arguments.

=== 2 呼叫不存在的工具
naive : crashed with KeyError: 'run'
fixlab: stop_reason=done steps=2 counters={'parse_errors': 1}
        the model was told: Your tool call was invalid: unknown tool: 'run'. Please call a tool with valid arguments.

=== 3 空回覆（沒有文字也沒有工具呼叫）
naive : stopped after 1 request(s), final text: None
fixlab: stop_reason=done steps=2 counters={'parse_errors': 1, 'empty_responses': 1}
        the model was told: Your reply was empty. If you are finished, reply with a short final message; otherwise call a tool.

=== 4 模型一直呼叫 read_file、不停下來
naive : still running after 50 requests (I stopped it)
fixlab: stop_reason=max_steps steps=20 counters={}

=== 5 供應商回 429（限流）
naive : crashed with RateLimitError: rate limited
fixlab: stop_reason=done steps=1 counters={'rate_limit_retries': 1}
```

天真版有三種死法：

1. **崩潰（例 1、2、5）。** 模型給了壞掉的 JSON、叫了不存在的工具，或供應商暫時忙碌，整個程式就丟出例外死掉。這些都不是程式的錯，而是模型和網路的常態。
2. **把失敗當成完成（例 3）。** 空回覆裡沒有工具呼叫，天真版就當作「模型說完了」直接結束，還回傳 `None`。使用者以為修好了，其實什麼都沒做。有些模型伺服器解析不了很長的工具呼叫時，會整個丟掉而不報錯（這是程式註解記下的已知情況，本文沒有重現它）。
3. **停不下來（例 4）。** 沒有任何上限，只要模型不說完就一直跑，每一步都花錢。例 4 是我自己在第 50 步把它中斷的。

專案裡的迴圈採取的做法是：**可以挽回的錯，變成給模型看的回饋，讓它下一步再試；不能挽回的，乾淨地結束並說明原因。**

## 現在的迴圈

每一步做四件事：問模型、解讀回覆、判斷要不要結束、執行工具。

```
messages = [系統提示, 使用者的任務文字]

for step in 1..最大步數:
    resp  = 問模型(messages)                    # 429／5xx 等一下再試；逾時不重試
    calls, errors = 解讀(resp)                  # 檢查工具呼叫；截斷、空回覆也在這裡判斷

    if 沒有 calls:
        if errors:  把錯誤當成 user 訊息回饋，進入下一步       # 不算完成
        else:       結束原因 = "done"; 結束                    # 模型自己宣告完成
    else:
        for 每個 call:  執行工具，結果以 role=tool 加進 messages
結束原因 = "max_steps"
```

迴圈回傳的結束原因只有三種：`done`（模型自己說完）、`max_steps`（步數用完）、`error`（請求失敗）。第一則 user 訊息就是任務文字，迴圈不加任何自己的內容。

### 回饋給模型的兩條路

模型做錯時，有兩條不同的路把錯誤送回它手上：

| 情況 | 在哪裡發現 | 怎麼回饋 |
|---|---|---|
| 呼叫本身不合法：工具不存在、缺必填參數、JSON 壞掉、空回覆、被截斷 | 執行**之前**，檢查工具呼叫的程式 | 一則 **user** 訊息：`Your tool call was invalid: …`（空回覆的措辭不同，見後記） |
| 呼叫合法，但執行時失敗：檔案不存在、字串找不到…… | 執行**之中**，工具丟出錯誤 | 一則 **tool** 訊息：`error: …`，並標記為失敗 |

上面的例 1、2、3 走第一條。第二條可以看第 4 篇（改檔工具的錯誤訊息）。

### 其他幾個決定

- **被截斷的回覆。** 模型的輸出撞到長度上限時，工具呼叫的 JSON 尾巴常常不見了（例如少了 `path`）。這時原本的錯誤訊息（「缺少 `path`」）會誤導模型，所以截斷時丟掉這次的呼叫，直接告訴它真正的原因：`your reply was cut off at the 8192-token output limit…`。判斷用兩個條件：回覆的結束標記是 `length`，或輸出 token 數達到上限。
- **同一個回覆裡的多個工具呼叫，全部執行。** 每個呼叫配一個編號，結果用同一個編號接在後面。
- **重試只針對 429、5xx 與連線錯誤**，依序等待 5、15、30、60、120、180、300、300 秒。**逾時不重試**：逾時通常代表模型失控地一直生成，重試只會浪費時間、掩蓋問題。為了讓這條規則成立，入口建立連線物件時用 `OpenAI(timeout=600, max_retries=0)`，不讓函式庫自己偷偷重試。
- **每一步留一筆紀錄。** 迴圈接受一個回呼函式，每次模型回覆都呼叫一次，內容有步數、延遲、token、工具名稱與參數、輸出、成功與否與標記、模型的文字與思考長度、供應商。紀錄要存成什麼格式，留給之後的統計紀錄再決定。

### 系統提示

```
You are a coding agent. Your working directory is a multi-file Python project with pytest tests (read-only).
Find the cause of the failing behavior and fix it in the source code.
Call one tool at a time and look at its result before deciding the next step.
When you are confident the fix is correct, reply with a short final message WITHOUT any tool call.
```

注意兩點。第一，它**不點名任何工具**：之後要做「有／沒有跑測試工具」兩組的對照實驗，要求提示詞一致、只差工具。第二，最後一句把「沒有工具呼叫的回覆」定義成宣告完成，這就是迴圈判斷 `done` 的依據。

### 步數上限 20

預設最多 20 步。多檔專案的探索比單一檔案多很多步，所以設得比較高。**這個數字沒有實測依據**，只是初始值，階段 3 會用實際跑出來的步數分佈來校準。下面真模型的紀錄只能說明 20 步夠範例專案用，說明不了更大的專案。

## fixlab PATH

迴圈需要一個能啟動它的東西。這是一個只供實跑檢查用的最小入口，不是正式的指令列介面：

```
$ fixlab --help
usage: fixlab [-h] [--model MODEL] [--max-steps MAX_STEPS]
              [--max-tokens MAX_TOKENS] [--task TASK]
              path

Let the agent fix the failing tests in PATH. PATH is edited in place.
```

沒有子命令，就是 `fixlab PATH`。連線的位址、金鑰、模型由環境變數 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`FIXLAB_MODEL` 指定（用 Ollama 時金鑰可以填任意值），也可以用 `--model` 覆寫。`--task` 可以換掉預設的任務文字，預設是 `The tests fail under pytest. Find the cause and fix it.`，送給模型的就是這句英文。

### 它直接改你給的目錄

**`fixlab PATH` 不複製、不寫回，直接修改 `PATH`。** 原因是它屬於一次性執行，跑的時候沒有人在旁邊，不能像互動式工具那樣在每次寫入前問使用者（詢問權限是階段 2 的事）。所以改成**事後審查**：

1. 跑之前，對 `PATH` 底下的檔案拍一份**記憶體快照**：記下每個檔案的相對路徑和內容。跳過 `.git`、`__pycache__` 這類目錄與符號連結，規則和列檔案工具一樣。
2. 跑完再拍一份，比較兩份，印出新增、刪除、修改的檔案。範圍**包含測試檔**，因為改測試檔正是假通過的主要手法。

比較的輸出長這樣（用函式直接餵兩份快照得到的真實輸出）：

```diff
binary file changed: img.bin
new file: new.py
--- a/new.py
+++ b/new.py
@@ -0,0 +1 @@
+hi
deleted file: old.txt
--- a/old.txt
+++ b/old.txt
@@ -1 +0,0 @@
-bye
--- a/tests/test_report.py
+++ b/tests/test_report.py
@@ -1 +1 @@
-assert x == 1
+assert True
--- a/timelog/parser.py
+++ b/timelog/parser.py
@@ -1,2 +1,2 @@
 a = 1
-b = 2
+b = 3
```

#### 怎麼讀這份輸出

這是 **unified diff** 格式（統一格式的差異比較），`git diff` 和 `diff -u` 用的是同一種，來歷見本文最後的參考來源。在 GitHub 這類會上色的地方，`+` 開頭的行是綠色、`-` 開頭的行是紅色、`@@` 開頭的行是另一種顏色。上面的區塊標成 `diff`，所以會上色。

先看最小的一種，新增一個只有一行 `hi` 的檔案：

```diff
new file: new.py
--- a/new.py
+++ b/new.py
@@ -0,0 +1 @@
+hi
```

| 這一行 | 意思 |
|---|---|
| `new file: new.py` | 專案自己加的標題，**不屬於**標準格式。同類的還有 `deleted file: …` 和 `binary file changed: …` |
| `--- a/new.py` | 舊版，也就是執行前的快照。`a/`、`b/` 沿用 git 的習慣，只是「前」和「後」的標籤，不是資料夾 |
| `+++ b/new.py` | 新版，也就是執行後的現況 |
| `@@ -0,0 +1 @@` | 這一段改動的位置，下面解釋 |
| `+hi` | 一行內容。開頭是 `+`：只在新版有（新增）；開頭是 `-`：只在舊版有（刪除）；開頭是空白：兩邊都有（沒變，只是給你看前後文） |

`@@ -0,0 +1 @@` 的格式是：

```
@@ -舊版的起始行,行數  +新版的起始行,行數 @@
```

`-` 指舊版，`+` 指新版。行數是 1 的時候會省略，所以 `+1` 等於 `+1,1`。照這個規則讀：

| 標頭 | 舊版 | 新版 | 意思 |
|---|---|---|---|
| `@@ -0,0 +1 @@` | 從第 0 行起共 0 行（什麼都沒有） | 從第 1 行起共 1 行 | **新增**一個 1 行的檔案（舊版根本沒有這個檔案） |
| `@@ -1 +0,0 @@` | 從第 1 行起共 1 行 | 共 0 行 | **刪除**一個 1 行的檔案（`old.txt`） |
| `@@ -1 +1 @@` | 第 1 行 | 第 1 行 | 同一個檔案的第 1 行被換成別的內容（`tests/test_report.py`） |
| `@@ -1,2 +1,2 @@` | 從第 1 行起共 2 行 | 從第 1 行起共 2 行 | 這一段有 2 行，其中一行被改了（`timelog/parser.py`） |

最後一種，把每一行都標出來：

```diff
--- a/timelog/parser.py
+++ b/timelog/parser.py
@@ -1,2 +1,2 @@
 a = 1
-b = 2
+b = 3
```

第一行 ` a = 1` 開頭是空白，代表沒變。第二行 `-b = 2` 是舊版有、新版沒有的；第三行 `+b = 3` 是新版才有的。合起來就是「`b = 2` 被改成 `b = 3`」。

沒有任何變動時，印出 `no changes`。不能用 UTF-8 解碼的檔案，只說 `binary file changed`。內容有變、但差異是空的（例如只改了結尾換行），也會明講，不會悄悄漏掉。

為什麼不直接用 `git diff`：它會把你原本就還沒提交的修改一起列出來，分不清哪些是這次執行改的；新增的檔案預設也不顯示；而且要求 `PATH` 是 git 倉庫。快照只反映這一次執行。git 仍然是你自己的還原手段。

因為是直接修改，**沙箱完成前，只對自己寫的範例專案的複本執行**，絕不對 `tests/fixtures/timelog` 本身執行。否則模型修好 bug 之後，`test_fixture.py` 預期的「未修時恰好 1 個失敗」就壞了：

```
cp -R tests/fixtures/timelog /某個暫存目錄/timelog-try
fixlab /某個暫存目錄/timelog-try
```

### 錯誤

三種輸入錯誤都以退出碼 2 結束，並給明白的訊息（真實輸出）：

```
fixlab: error: OPENAI_API_KEY is not set (any placeholder value works for Ollama)
fixlab: error: no model: pass --model or set FIXLAB_MODEL
fixlab: error: not a directory: /no/such/dir
```

### 它的限制

結束時的差異比較，只比對開頭與結尾。改了又改回去的，看不出來，只有每一步的紀錄裡有（第 4 篇有一個真實的例子）。

## 第一次讓真模型跑

入口準備好之後，我對範例專案的複本跑了一次。這時只提供了列檔案和讀檔兩個工具，**模型沒辦法修**，這次只看它怎麼探索專案。這是觀察，不是通過與否的門檻。

實驗紀錄：模型是 `qwen/qwen3.5-9b`，透過 OpenRouter，供應商是 Venice（量化方式未知），思考模式維持預設的開啟，OpenRouter 清單上寫的上下文長度是 262144，執行環境是 OpenRouter 的 API（沒有版本號），`openai` 函式庫 3.31.0，Python 3.14.8，日期 2026-10-17，題目是範例專案 timelog，沒有隨機種子。結果：結束原因是步數用完，共 20 步，輸入 45,962 加輸出 2,816 token，約 43 秒，依清單價格約 $0.005。原始紀錄放在 `runs/3.7-qwen3.5-9b-20261017/`（不進版本控制）。

終端機上看到的：

```
editing in place: /…/timelog-run1
list_files  ok=True  flags={}
read_file  ok=True  flags={}
read_file  ok=True  flags={}
… （共 18 行，另外 2 步是無效的工具呼叫，不印）
stop reason: max_steps  steps: 20  tokens: 45962 prompt + 2816 completion

changes since start:
no changes
```

完整的 20 步（從每一步的紀錄整理）：

| 步 | 做了什麼 |
|---|---|
| 1 | 列出檔案，一次就回傳全部 6 個 |
| 2 | 呼叫不存在的工具 `pytest`，被拒絕 |
| 3–5 | 讀 `tests/test_report.py`、`timelog/report.py`、`timelog/parser.py` |
| 6 | 用文字說出原因（見下），同時又讀一次 `parser.py` |
| 7–13 | 連續讀 `parser.py` 七次（第 13 步還指定了第 1 到 15 行） |
| 14、16 | 重複列出檔案 |
| 15、17、19、20 | 又讀 `parser.py` |
| 18 | 呼叫不存在的工具 `open`，被拒絕 |

第 6 步模型說的話：

```
The issue is in `timelog/parser.py` line 12. The regex `re.match(r"(\d+)([hm])", text)` only captures
the **first** unit (e.g., "1h") and ignores the rest (e.g., "30m").
The test `weekly_total(["1h30m", "45m", "2h"])` expects `4.25` hours (255 minutes), but the current
code only parses "1h" = 60 minutes, ignoring "30m".
Let me fix the parser:
```

**做得好的地方**：

- 20 個回覆的結束標記都是 `tool_calls`，也就是模型原生的工具呼叫格式完全正常。
- 第 5 步讀到 `parser.py`，第 6 步就說對了原因（第 12 行，`re.match` 只取第一個單位）。行號引用正確，也用過指定行範圍的讀法。
- 一次列檔案就看到所有檔案，不用逐層點開。

**做得不好的地方**：

- **後面 14 步在原地打轉。** 模型說了「Let me fix the parser」，但它沒有可以改檔案的工具，只好不停重讀。步數上限在這裡發揮了作用：沒有它，迴圈會一直跑下去。目前沒有「連續呼叫一模一樣的工具」的偵測，設計上已決定留到階段 2，看實際紀錄再決定。這次因為缺少改檔工具而被混淆，所以也不能當成「小模型常重複呼叫」的證據。
- **憑空叫出不存在的工具。** `pytest` 和 `open`，分別是它想跑測試、想開檔案。目前的回饋只說「工具不存在」，沒有列出有哪些工具可用。

**多一個工具之後**（改檔工具完成後，同一個模型、同一題又跑了一次，細節在第 4 篇）：

| | 只有列檔案、讀檔 | 多了改檔 |
|---|---|---|
| 結束原因 | 步數用完 | 模型自己宣告完成 |
| 步數 | 20 | 11 |
| token | 輸入 45,962 加輸出 2,816 | 輸入 14,801 加輸出 2,114 |
| 找到原因 | 第 6 步 | 第 5 步就改好了 |
| 最後的差異比較 | `no changes` | 只有 `parser.py` 那一行 |

兩次的差別是缺少一個工具：沒有它，模型知道答案卻做不到，只能在原地打轉到步數用完。這兩次都只各跑一次，模型的輸出有隨機性，不能當成嚴謹的對照實驗。它說明的是這個迴圈面對「做不到」時的反應：不會自己停下來，要靠步數上限。

還有兩個數字很有意思。每一步都要把整份對話紀錄重送一次，所以輸入 token 一路增加：第 1 步 528，第 20 步 4,148，加起來就是 45,962。這就是為什麼每個工具的輸出都要有長度上限。至於「一次列出全部檔案比較省步數」這個假設，這次仍然驗證不了：範例專案只有 6 個檔案，太小了。

## 怎麼驗證

- **迴圈**（`tests/test_loop.py`，5 個），用劇本模型驗證：
  - 任務文字就是第一則 user 訊息，工具清單就是登記表產生的那一份。
  - 模型依自己的決定「讀、改、跑測試、結束」四步，得到「模型自己宣告完成」。
  - 最大步數設成 3 時停在第 3 步，預設是 20 步。
  - 系統提示不含任何工具名稱（有／沒有跑測試工具兩組實驗的前提）。
- **入口**（`tests/test_cli.py`，16 個）：
  - 只讀的執行結束後，目錄內容不變，印出 `no changes`。
  - 每個工具呼叫印一行，含工具名稱與成功與否。
  - 指向目錄外的符號連結，讀檔會被擋下。
  - 預設任務文字可以被 `--task` 取代。
  - 三種輸入錯誤各給訊息，退出碼為 2。
  - 快照會跳過資料夾與符號連結。
  - 差異比較涵蓋修改、新增、刪除、非 UTF-8、測試檔被改、沒變的不出現、全部沒變印 `no changes`、只改結尾換行。

入口的測試用劇本模型，不連網；真模型那次是手動觀察，沒有納入自動測試。

## 已知限制

- **20 步沒有實測依據。** 見上。
- **沒有重複呼叫的偵測，也還沒有連續失敗的保險。** 前者留到階段 2，後者已排在後面的任務。
- **系統提示說測試檔是唯讀，但這個提示本身強制不了任何事。** 第 4 篇有個真實的例子：模型用改檔工具去改了測試檔。擋下這件事的機制是後面的任務。
- **不串流。** 每一步要等完整回覆才開始處理。
- **不支援不使用原生工具呼叫格式的模型。** 如果模型把 JSON 寫在文字裡，會被當成純文字，看起來就像第 1 步就「完成」了。所以入口結束時一定印出結束原因和步數，讓你看得出來。
- **無法從入口關掉模型的思考模式。** 這次的紀錄只能照預設開著。
- **迴圈保險的專門測試還沒補。** 重試、截斷、空回覆、每步紀錄這幾段程式已經在，但第一節的五個例子是我另外寫腳本重現的，不是專案裡的測試。
- **入口會直接修改 `PATH`。** 沙箱完成前，只能對自己寫的複本跑。

## 參考來源

看過高見龍 KeSi 的 `kesi.py`（MIT 授權，Copyright (c) 2026 Eddie Kao，commit `dfa0cd0`，2026-10-17 查證）裡的 `run_agent` 與 `main()`。

- **他的做法**：互動式的對話介面，指令不帶任何參數，在你 `cd` 進去的目錄工作；每次寫入前問使用者；串流輸出；迴圈最多 20 圈（`MAX_TURNS = 20`），另有 `MAX_TOOL_FAILURES = 3`，一整輪的工具全部失敗才累計；連線錯誤轉成給「人」看的訊息（他的註解寫著「這裡的讀者是人，不是模型」）。
- **採用的想法**：「連續失敗只算整輪全失敗」（這個專案的連續失敗保險還沒做，會照這個算法）。
- **他的示範腳本做了類似的事**：他 Day 13 的示範（`examples/day13/demo.py`）會在結束後對原始檔案內容印 diff，註解寫「驗收要看的是 diff，不是只看 pytest 最後一行，把測試改掉也算一種作弊」，也會在結束後再跑一次 pytest。這跟這個專案的快照差異、結束後再跑一次測試是同樣的想法，不能排除我受了他的影響。差異是：他比對的是寫死在示範裡的原始檔案內容，只涵蓋示範的那幾個檔案；這個專案對任意目錄在執行前拍快照，涵蓋新增與刪除的檔案。
- **沒有採用的**：對話介面、權限詢問、串流，都是階段 2 以後的事。`fixlab PATH` 是一次性執行，所以改用事後的快照差異，代替事前的詢問。他的連線錯誤是給人看的，這個專案裡可以挽回的錯誤是給模型看的回饋。
- **一個要老實說的巧合**：這個專案的預設步數 20 和連續失敗上限 3，數字和他的 `MAX_TURNS = 20`、`MAX_TOOL_FAILURES = 3` 完全一樣。設計文件把 20 記為「沒有實測依據的初始值」，我無法排除自己是受他影響才選了同樣的數字，所以在這裡註明；階段 3 會用實際紀錄校準，不會沿用到最後。

**unified diff 格式的來歷**（Wikipedia〈Diff〉與 GNU diffutils 手冊，2026-10-17 查閱）：最早的 `diff` 由 Douglas McIlroy 與 James Hunt 在貝爾實驗室寫成，隨 1974 年的 Unix 第 5 版發行。unified 格式由 Wayne Davison 在 1990 年 8 月的 `unidiff` 工具裡發明，約一個月後 Richard Stallman 把它加進 GNU diff，1991 年 1 月的 GNU diff 1.15 首次出現；POSIX.1-2008 才把 `-u` 正式納入標準。沒有哪個組織「制定」過它，是一個被 `patch`、`git` 等工具沿用而成為事實標準的約定。GNU 手冊對標頭的說明：一段改動只有一行時，只寫起始行號，否則寫成「起始行,行數」；行首空白代表兩邊共有，`+` 是新增，`-` 是刪除。`a/` 與 `b/` 的前綴是 git 的習慣。這個專案的輸出由 Python 標準函式庫的 `difflib.unified_diff` 產生，不是自己拼的。

## 後記：3.11 之後，結束時自己再跑一次測試

模型說「修好了」，只是它的宣稱。它可能沒跑測試就宣告完成，也可能測試失敗卻還是宣告完成。所以入口在模型結束之後，**自己再跑一次測試**，結果不依賴模型怎麼說。

這一步只屬於一次性模式：沒有人在旁邊看，所以由程式代替。之後的互動模式有使用者在看，可以改成使用者想要時才執行。

輸出的最後一行固定是結論，一眼就看得到；結論也決定結束碼：

| 結束碼 | 意思 |
|---|---|
| 0 | 最後那次測試通過 |
| 1 | 跑完了，但最後的測試沒通過（包含逾時） |
| 2 | 輸入有誤（沒設金鑰、路徑不是資料夾等，前面已經有了） |

下面是用劇本模型跑出來的真實輸出（不是真的模型），兩種結果：

```
===== 模型什麼都沒做就宣告完成
stop reason: done  steps: 1  tokens: 10 prompt + 5 completion

changes since start:
no changes

final test run:
.F...                                                                    [100%]
...（pytest 的失敗內容，略）
1 failed, 4 passed in 0.01s

RESULT: tests FAILED
[結束碼 1]

===== 模型用改檔工具修好 bug 才宣告完成
stop reason: done  steps: 2  tokens: 20 prompt + 10 completion

changes since start:
--- a/timelog/parser.py
+++ b/timelog/parser.py
@@ -9,5 +9,5 @@
...（略）
-    units = [re.match(r"(\d+)([hm])", text).groups()]
+    units = re.findall(r"(\d+)([hm])", text)
     return sum(int(number) * (60 if unit == "h" else 1) for number, unit in units)

final test run:
.....                                                                    [100%]
5 passed in 0.01s

RESULT: tests passed
[結束碼 0]
```

還有一個順序上的細節：先跑最後的測試，**再**拍「之後」的快照。這樣，測試程式在執行過程中動了什麼檔案（例如測試會寫出一個新檔），也會出現在差異比較裡。測試裡有一個專門檢查這件事。

## 補充：空回覆的回饋措辭已改

上面例 3 的輸出是改過之後的版本。原本的回饋是 `Your tool call was invalid: empty response ... Please call a tool with valid arguments.`。後來第一次完整的真模型修復（見 README 的實跑紀錄）裡，兩次空回覆都出現在模型已經驗證完畢、只差說一句結論的時候，這句回饋卻叫它「呼叫工具」，措辭有誤導，模型要再多回一次才給出結論。現在改成同時涵蓋兩種情況：`Your reply was empty. If you are finished, reply with a short final message; otherwise call a tool.`

## 下一篇

第 4 篇是改檔工具：讓模型真的能改檔案。其中有一次真實的紀錄，模型為了跑測試，竟然去改了測試檔。
