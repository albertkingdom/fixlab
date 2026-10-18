# 第 14 篇：改檔和跑測試之前先問你（權限提示）

> 對應任務：stage2-cli-telemetry 的 1.4 與 3.3。
> 完成度：完成（寫這篇時全部測試 379 個通過；權限相關的有 23 個：互動模式 16、Workspace 4、迴圈 2、一次性模式 1）。

互動模式（第 13 篇）有人在旁邊。這一篇讓 `fixlab` 在動手改東西之前，先問一聲。

## 為什麼現在要問

一次性的 `fixlab PATH` 沒有人在旁邊可以問，所以我們用**事後審查**：結束時印出快照差異，再自己跑一次測試（第 3 篇）。互動模式不一樣，使用者就在螢幕前，與其事後才發現模型改了不該改的，不如在它動手之前讓使用者決定。

## 先試最天真的做法，看它怎麼壞掉

最直覺的寫法：在每個會寫入的工具裡，直接問一句。

```python
def edit_file(ws, path, old_string, new_string):
    if input("Allow? [y/N]: ") != "y":
        return ToolResult("declined", False)
    ...
```

它有三個問題：

1. **沒有人在的時候會當掉。** 一次性模式沒有人可以回答，`input()` 在標準輸入已經關掉的情況下的實際反應是：

```
$ python3 -c "input('Allow? [y/N]: ')" < /dev/null
EOFError: EOF when reading a line
```

   整個工具呼叫以例外收場，違反「工具錯誤不能讓迴圈崩潰」。
2. **三個會寫入的工具要各抄一份**（改檔、寫檔、跑測試），漏一個就是漏洞。
3. **政策和工具混在一起。** 「要不要問」是使用者的偏好，不是改檔這個動作的一部分；一次性模式、互動模式、之後 benchmark 的批次執行，各自的答案都不一樣，卻共用同一份工具程式。

## 做法：Workspace 的一個參數

「哪些檔案唯讀」這件事，專案一開始就選了同一個結構：由**建立 Workspace 的入口**決定，迴圈不管（`read_only` 參數，第 4 篇）。確認也照這個辦法：

```python
Workspace(root, read_only=looks_like_test_file, confirm=ask)
```

`confirm(工具名稱, 參數)` 回傳 True 才執行。**預設是「全部放行」**，所以一次性模式不傳它，行為完全不變。`Workspace.call` 的順序是：

1. 工具存在嗎？不存在就回錯誤。
2. 參數合法嗎？不合法就回錯誤。
3. **`confirm`**：回 False 就不執行。
4. 執行工具。

確認放在參數檢查**之後**：不合法的呼叫本來就不會執行，拿去問使用者沒有意義。放進 Workspace 而不是迴圈，是因為這個專案對「agent」的定義是**由模型決定下一步，程式只設保險**；政策放進迴圈，迴圈就開始像一個寫死的流程了。

使用者拒絕的呼叫，結果是 `ok=false`，旗標 `denied`，輸出：

```
error: the user declined this call. Do not retry it unchanged; try a different approach or ask the user what they want.
```

這句話是寫給**模型**看的：告訴它不要原樣重送，換個做法或問使用者。

## 互動入口的提示函式

互動模式傳進去的 `confirm`，只對會改東西的三個工具問：`edit_file`、`write_file`、`run_tests`。讀取類（`read_file`、`list_files`、`grep`）直接放行。

問題長這樣（要動什麼已經在前面的標題行與 `-`／`+` 差異裡，第 13 篇）：

```
    Allow? [y]es / [a]lways for this tool / [N]o:
```

| 輸入 | 結果 |
|---|---|
| `y`、`yes`（不分大小寫、去掉前後空白） | 這次放行 |
| `a`、`always` | 這次放行，而且**這個 session 內**同一個工具之後都不再問 |
| `n`、空行、`yes please`、其他任何東西 | 拒絕 |
| 輸入結束（Ctrl-D） | 拒絕 |
| Ctrl-C | 中斷整個任務（第 13 篇） |

預設是拒絕（大寫的 `N`）：只有明確打 `y` 或 `a` 才會執行，打錯字不會放行。輸入結束時沒有人可以同意，也是拒絕。

為什麼 `run_tests` 也要問？它會執行程式，而被執行的程式包含模型剛剛改寫過的檔案。它跑在沙箱裡（第 9 篇），但使用者應該知道什麼時候它在跑。

### 真實的一次

下面是用真模型（qwen3.5-9b，OpenRouter）跑的一次互動，那時還是舊的畫面格式（路徑省略）。使用者第一次被問 `run_tests` 時回答 `n`：

```
fixlab>  fix the failing test
run_tests .
Allow? [y]es / [a]lways for this tool / [N]o: n
run_tests  ok=False  flags={'denied': True}
list_files  ok=True  flags={}
read_file  ok=True  flags={}
read_file  ok=True  flags={}
read_file  ok=True  flags={}
edit_file timelog/parser.py: replace '…' with '…'
Allow? [y]es / [a]lways for this tool / [N]o: y
edit_file  ok=True  flags={}
run_tests tests/test_report.py
Allow? [y]es / [a]lways for this tool / [N]o: y
```

模型被拒絕之後**沒有卡住也沒有重複**：它改成先列檔案、讀三個檔、改檔，改完才再問一次要不要跑測試。事件檔的計數器記著 `denied_calls: 1`、`tests_passed: 1`，8 步完成。這只是一次樣本，但它說明了「拒絕」這句話確實被模型當成資訊。

## 拒絕算失敗

被拒絕的呼叫會計入**連續失敗保險**（第 11 篇）：連續三輪、每個呼叫都失敗，任務就以 `stuck` 結束。

旗標用獨立的 `denied`，不和 `blocked` 混在一起：`blocked` 是**規則**擋下的（路徑逃逸、寫唯讀檔案），`denied` 是**人**決定的。事件檔要分得出來，之後統計才不會把「使用者不同意」算成「模型亂來」。實際輸出，使用者連續三次拒絕同一個改檔：

```
  ▸ edit_file timelog/parser.py
    - [re.match(r"(\d+)([hm])", text).groups()]
    + re.findall(r"(\d+)([hm])", text)
    Allow? [y]es / [a]lways for this tool / [N]o: n
    ✗ declined
  … 同樣的再兩次 …

(stopped: stuck · 3 steps · 30 + 15 tokens · 0 s)
```

要不要這樣算，我不確定。使用者連拒三次，可能就是不想讓它做這件事，這時停下來很合理；但這也會把使用者的選擇記成「卡住」。設計文件把它列為待觀察的問題，先照這樣做，用過之後再調整。

## 「一律放行」的範圍

`a` 放行的是**整個工具**：放行一次 `edit_file`，這個 session 之後所有的 `edit_file` 都不問（唯讀的測試檔仍然擋得住，那是另一道規則）。它在 `/reset` 之後仍然有效，離開就沒了。

這個範圍比較粗。高見龍的 KeSi 比較細：改檔與寫檔的授權記在**每個檔案路徑**，shell 指令記在**每個完整的指令字串**，所以放行「改 `a.py`」不會連帶放行「改 `b.py`」。他也有 `/permissions` 看目前授權了什麼、`/revoke` 全部收回。我們目前都沒有。

取捨是：粗的範圍問得少，但放行的範圍大。因為修 bug 時模型常常連續改好幾個檔，一個檔問一次會很煩；但如果以後要在更大的範圍用，細的做法比較安全。這是之後可以改的地方，不是已經證明這樣比較好。

## 一個不夠好的地方：問了才被擋

目前的順序是「先問使用者，再執行工具」，而「這個檔案是不是唯讀」是在工具**執行時**才檢查的。所以可能出現這樣：

```
  ▸ edit_file tests/test_report.py
    - assert
    + pass
    Allow? [y]es / [a]lways for this tool / [N]o: y
    ✗ blocked: 'tests/test_report.py' is read-only and cannot be modified. If it is a test file, fix the source code instead.
```

使用者放行了一個**注定會被擋下**的呼叫。體驗不好，而且有一個副作用：如果使用者在這裡回答 `n`，事件檔裡記的是 `denied`，不是 `protected_write`，「模型試過改測試檔」這件事就沒有被記到。

這是 code review 找到的，設計文件把它列為已知取捨。要修的話，做法是讓提示函式先問 `read_only`，對唯讀檔案根本不提問。我沒有現在做，因為模型實際上幾乎不會去改測試檔（第 4 篇那次是沒有跑測試的工具時才發生），先看實際使用會不會常碰到。

## 一次性模式從不問

`fixlab PATH`（沒有 `-i`）不傳 `confirm`，所以不會問任何問題，也不會有任何呼叫被拒絕。有一個測試把 `input()` 換成「一被呼叫就失敗」，確認一次性模式整個跑完都沒碰它。

## 與 KeSi 的對照

我讀了他的 `check_permission` 與 `ask_user`。

| | 高見龍 KeSi | fixlab |
|---|---|---|
| 會問的工具 | 改檔、寫檔、shell 指令 | `edit_file`、`write_file`、`run_tests`（沒有任意 shell） |
| shell 指令 | 先過規則分類：直接放行、直接擋下、或問 | 不需要：沒有任意 shell |
| 「都好」的範圍 | 每個檔案、每個完整指令 | 整個工具 |
| 看與收回授權 | `/permissions`、`/revoke` | 沒有 |
| 回答 | `y`／`yes`、`a`／`all`，其他拒絕 | `y`、`a`（不分大小寫），其他拒絕 |
| 沒有人可以問 | 標準輸入不是終端機就自動拒絕 | 輸入結束（EOF）才拒絕 |
| 被拒絕算失敗 | 算，連續 3 輪停 | 相同 |
| 問題裡顯示什麼 | 檔案路徑；指令顯示完整內容與理由 | 路徑加 `-`／`+` 差異（前面的標題行） |

有一個差異值得注意：他在標準輸入**不是終端機**時就自動拒絕；我們只有在輸入**結束**時才拒絕。如果有人把輸入用管線餵進去（`echo ... | fixlab -i`），我們會把管線裡的下一行當成回答，他則一律拒絕。

## 已知限制

- **授權範圍比較粗**，而且沒有 `/permissions` 與 `/revoke` 可以看和收回。
- **問了才被擋**，見上。
- **連續被拒絕三輪算 `stuck`**，這個算法還沒有實際使用的經驗。
- **管線輸入會被當成回答**（他的做法是不在終端機就拒絕）。
- **只有互動模式會問**；一次性模式靠事後的差異與重跑測試。

## 參考來源

- **高見龍 KeSi**（`kesi.py`，MIT 授權，Copyright (c) 2026 Eddie Kao，commit `dfa0cd0`，2026-10-17 讀）：設計時只看過 commit 標題（「permission gate with session grants」），`y`／`a`／`N` 與「這個 session 都好」的想法與他相同，不能排除受他影響；完成之後才讀了 `check_permission` 與 `ask_user`，做了上面的對照。`confirm` 參數放在 Workspace、`denied` 旗標與 `blocked` 分開、先檢查參數再問，是依這個專案自己的結構（由入口決定政策、迴圈只設保險）設計的。
- **Claude Code 的行為**：寫檔與執行指令前會問「這次允許、這個 session 一律允許、拒絕」三種，是 `y`／`a`／`N` 的來源（憑使用經驗，沒有重新查文件）。

## 下一篇

階段 2 的收尾：README 與 `stage-2` 的 tag。
