# 使用手冊

[回到首頁](../README.md)

在目標專案執行 `fixlab` 進入互動模式；`fixlab PATH` 執行一次性修復。安裝與模型設定見[首頁](../README.md)。

## CLI 選項

`fixlab --help` 可列出所有選項；`--model NAME` 可覆寫 `FIXLAB_MODEL`，`--mcp-config PATH` 的安裝與設定見 [MCP 使用指南](mcp.md)。

選項：`-i`（互動模式，見下）、`--python PATH`（跑測試用的直譯器，見〈用專案自己的 Python 跑測試〉）、`--max-steps`（預設 20）、`--max-tokens`（預設 8192）、`--task`（換掉預設的任務文字，只用於一次性模式）、`--log-dir`、`--meta`（見〈事件檔〉）、`--hide-tool NAME`（不讓模型看到某個工具，例如 `run_tests`；可重複）、`--temperature`、`--extra-body JSON`（原樣放進請求，例如固定 OpenRouter 的供應商）、`--system-prompt-extra TEXT`（把這段文字接在預設 system prompt 後面，中間空一行；空字串會被拒絕；文字以 `-` 開頭時要寫成 `--system-prompt-extra=TEXT`）。後四個用在實驗，並記進事件檔的 `run_start`。

## 一次性模式會印什麼

- **執行中**（stderr）：被修改的目錄、沙箱狀態（`sandbox: on` 或 `sandbox: OFF (原因)`），之後每個工具呼叫一行，例如 `read_file  ok=True  flags={}`。
- **結束後**（stdout）：stop reason（`done` 模型自己宣告完成、`max_steps` 步數用完、`stuck` 連續三輪全失敗、`error` 請求失敗）、步數、token，然後是**快照 diff**，再來是 fixlab **自己再跑一次**測試的輸出，最後一行是 `RESULT: tests passed`、`RESULT: tests FAILED` 或逾時時的 `RESULT: tests FAILED (timed out)`。
- **結束碼**：0 最後那次測試通過；1 沒通過；2 輸入有誤（路徑不是目錄、沒設金鑰、沒指定模型）。

最後那次測試不聽模型怎麼說：模型可能沒跑測試就宣稱完成，所以結果以 fixlab 自己跑的為準。

## 互動模式

在要處理的專案目錄直接執行 `fixlab`，就會進入互動模式，不需要加 `.` 或 `-i`。也可用 `fixlab PATH -i` 指定其他目錄。一次讀一行當任務，同一個 session 內**保留對話**，所以修完 bug 之後可以接著說「幫那個函式加上說明文字」。

`fixlab PATH` 仍為一次性模式，可用 `fixlab PATH --task '任務內容'` 換掉任務文字；一次性模式寫檔不會詢問，所以不給 PATH 只給 `--task` 會被拒絕。`-i` 明確指定互動模式，優先於 `--task`，任務由提示字元輸入。下面是畫面的格式（使用假模型劇本示意，測試時間、token 與耗時不代表真模型的用量；差異由目前的顯示函式產生）：

```
fixlab> fix the failing test

  ▸ run_tests .
    Allow? [y]es / [a]lways for this tool / [N]o: n
    ✗ declined
  ▸ read_file timelog/parser.py
    ✓
  ▸ edit_file timelog/parser.py
    @@ line 9
     9       text = text.strip()
    10       if not re.fullmatch(r"(\d+[hm])+", text):
    11           raise ValueError(f"invalid duration: {text!r}")
    12 -     units = [re.match(r"(\d+)([hm])", text).groups()]
       +     units = re.findall(r"(\d+)([hm])", text)
    13       return sum(int(number) * (60 if unit == "h" else 1) for number, unit in units)
    Allow? [y]es / [a]lways for this tool / [N]o: y
    ✓
  ▸ run_tests .
    Allow? [y]es / [a]lways for this tool / [N]o: y
    ✓ 5 passed in 0.01s

Fixed parse_duration: it only took the first unit.

(5 steps · 50 + 25 tokens · 0 s)
```

- **每個工具呼叫一組**：標題行、改檔的差異（整個檔案改前與改後的比對，只列有變的地方，前後各 3 行上下文、帶改前的行號；每處變動的連續刪除或新增最多 10 行、最多 8 處）、問題、結果行（`✓`，或 `✗` 加原因：`declined`、`blocked`、測試失敗的摘要）。最後一行是步數、token 與耗時；耗時是牆上時間，包含你思考與回答問題的時間。全部印到標準輸出；顏色只在終端機、而且沒設 `NO_COLOR` 時才開。
- **權限提示**：`edit_file`、`write_file`、`run_tests` 之前會問。`y` 這次放行；`a` 這個 session 內同一個工具都不再問（放行 `edit_file` 就是任何檔案，測試檔仍然唯讀）；其他任何輸入、空行、輸入結束都是拒絕。讀取類工具不問。工具一定會拒絕的呼叫（空路徑、唯讀檔、找不到要改的文字、新舊文字相同、沒讀過就覆寫）也不問，直接顯示 `✗` 和原因。被拒絕的呼叫算失敗，連續三輪全被拒絕任務會以 `stuck` 結束。
- **指令**：`/reset` 清空對話、`/exit`（或 Ctrl-D、在提示字元按 Ctrl-C）離開、空行忽略，其他都當任務。
- **Ctrl-C 打斷任務**：已完成的部分留在對話裡，沒有結果的工具呼叫補上「被中斷」的結果，下一個任務看得到前面做到哪裡；但被打斷的那個呼叫可能已經執行了一半，檔案可能已被改過。請求失敗也一樣：任務已經執行過工具就保留，接上說明並提醒檔案可能已被改過；還沒執行過任何工具（第一個請求就失敗、或只收到空回覆）才整個丟掉。
- **不自動再跑一次測試**（一次性模式才會）：你在場，想驗證可以直接叫模型跑。**一次性模式從不問任何問題。**
- **不跨 session 保存對話**，離開就沒了；對話也沒有長度上限，每一步會越來越貴，用 `/reset` 重來。

## 用專案自己的 Python 跑測試

`run_tests` 預設用執行 fixlab 的那個 Python。被修的專案需要第三方套件時，用 `--python` 指定專案自己的環境，套件裝在專案的環境裡就好，不用加進 fixlab 的環境：

```
fixlab --python .venv/bin/python
```

`--python` 的相對路徑以啟動 fixlab 時的目前目錄為準，不會以 `PATH` 指定的目標專案為準。從別的目錄操作時，可用絕對路徑，例如 `fixlab /path/to/project --python /path/to/project/.venv/bin/python`。

指定的 Python 要 3.11 以上（`run_tests` 用 `-P` 啟動 pytest，舊版本沒有這個參數），而且裝了 pytest；不符合時一開始就以結束碼 2 結束並說明原因，不會呼叫模型。用的是哪個直譯器、從哪裡來，記在事件檔 `run_start` 的 `test_python`。

**指定 `--python` 等於信任那個環境。** 它的 Python 與套件會在沙箱裡執行；如果它的基底 Python 裝在家目錄底下（uv、pyenv 下載的 Python），沙箱會放行讀取那個安裝目錄（只有那個目錄，家目錄的其他地方仍然讀不到）。fixlab 會檢查這個基底目錄：`pyvenv.cfg` 的 `home` 必須是絕對路徑、目錄裡要有 Python 的標準函式庫、不能是家目錄本身或上層、不能和專案目錄重疊；環境也不能透過專案裡的符號連結指到別處（測試可能把連結換掉）。不符合就拒絕執行。這些檢查擋得住打錯路徑與明顯的誤設定，擋不住一個刻意做壞的 Python 環境，所以只指定你自己建立或信任的環境。

**為什麼不自動偵測專案裡的 `.venv`：** 被修的專案可能是剛 clone 下來、還沒讀過的程式碼。自動使用它的 `.venv`，等於讓專案裡的檔案決定 fixlab 執行哪個程式、沙箱放行哪個目錄：`.venv/pyvenv.cfg` 裡的一行設定就可能讓沙箱放行 `~/.ssh`，而 `.venv/bin/python` 會在你確認任何事情之前就被執行。所以 fixlab 只在你用 `--python` 明確指定時才使用專案的環境。

## 事件檔

每次執行（一次性或一個互動 session）都會寫一個 JSON Lines 檔：預設在 `~/.fixlab/runs/<UTC 時間>-<模型>/events.jsonl`，開始時 stderr 會印 `log: <路徑>`。階段 3 的統計腳本要讀的就是它。

- `--log-dir DIR` 換位置；不能在被修的目錄裡面（會被拒絕，退出碼 2），不然快照 diff 會看到它，模型與被測的程式也碰得到自己的紀錄。省略 PATH 時若目前目錄是家目錄或更上層，不論有沒有 `--log-dir` 都會被拒絕，請到專案目錄執行或指定 PATH。
- `--meta KEY=VALUE`（可重複）記下 API 不會告訴我們的實驗條件，例如 `--meta quantization=Q4_K_M --meta context_length=32768`。
- 一行一個事件，只有四種：

| 事件 | 什麼時候寫 | 內容 |
|---|---|---|
| `run_start` | 開始，一次 | 模式、模型、端點、步數上限、沙箱狀態、fixlab 的 git commit、`meta` |
| `task_start` | 每個任務開始 | 任務序號與文字 |
| `trace` | 迴圈每交出一筆紀錄（通常每步一行） | 整筆紀錄放在 `record`：步數、延遲、token、模型要求的工具呼叫與結果、是否被截斷 |
| `task_end` | 每個任務結束 | stop reason、步數、計數器、token、耗時；一次性模式另有最後的測試結果與改了哪些檔 |

**trace 是什麼**：迴圈每問模型一次（一步），就把這一步的紀錄交給一個叫 trace 回呼的函式；事件檔裡的 `trace` 行和畫面上的進度都是它產生的。欄位的完整說明與一次真實執行的內容見[第 12 篇](articles/12-event-log.md)。

要注意：事件檔裡有模型的回覆與工具的輸出，可能包含目標專案的原始碼或祕密，不要隨意分享。不記費用，只記 token。

## 快照 diff 是什麼，限制在哪

開始前，`fixlab` 把目錄裡每個檔案的內容記在記憶體裡；結束後再記一次，比對出新增、刪除、修改的檔案（不能以 UTF-8 解碼的檔只印 `binary file changed`）。**測試檔也在範圍內**，所以測試被改了看得到。限制：

- 跳過 `.git`、`.venv`、`__pycache__`、`.pytest_cache`，也不看符號連結；這些地方的變動不會出現。
- 只比對 PATH 底下。程式如果寫到目錄之外（macOS 沙箱可用時會擋，見[安全與限制](safety.md)），diff 看不到。
- 整棵樹讀進記憶體，不適合很大的專案；讀不了的檔案（例如沒有讀取權限）會讓入口在印出結果前出錯。
- 它不是版本控制。`fixlab` 直接改你的檔案，**請對有備份或已 commit 的目錄使用**。

## 六個工具

| 工具 | 做什麼 | 值得知道的規則 |
|---|---|---|
| `read_file` | 讀檔，每行附行號，可指定行範圍 | 輸出上限 20000 字元，超過會註明總量 |
| `list_files` | 遞迴列出所有檔案 | 上限 200，跳過 `.git`、`.venv` 等 |
| `grep` | 搜尋檔案內容，輸出 `路徑:行號:內容` | 自己實作；單行 1 秒、整體 5 秒的時間上限，上限 100 行 |
| `edit_file` | 把檔案裡**恰好出現一次**的字串換掉 | 0 次或多次都不改，並回報實際次數 |
| `write_file` | 建立新檔，或整個覆寫 | 覆寫既有檔案前必須先整檔讀過，而且讀過之後沒被別人改 |
| `run_tests` | 在工作目錄跑 pytest，可指定目標檔案或目錄 | 固定參數、忽略專案的 pytest 設定檔、不自動載入外掛；10 秒逾時、輸出最多 4000 字元（留頭尾）；macOS 沙箱可用時啟用 |

**沒有任意 shell**，也沒有 `glob`（`list_files` 是遞迴的，目前沒有需要依檔名過濾的情境）。
