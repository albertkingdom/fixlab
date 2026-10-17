## Context

階段 1 完成了 agent 迴圈、六個工具、沙箱與 `fixlab PATH` 的最小入口。現況與缺口（都是讀過程式碼確認的）：

- `run_agent` 每次呼叫在函式裡新建 `messages`，跑完只回傳 `AgentResult`，對話內容丟掉；模型宣告完成時，最後那則回覆也沒有加進 `messages`。所以沒辦法接續上一個任務。
- `trace` 回呼每個回覆呼叫一次，帶一筆紀錄，但唯一的消費者 `print_step` 只在 stderr 印一行，沒有存檔。執行條件（模型、端點、日期）也沒有記在任何地方。
- `Workspace` 的政策（哪些檔案唯讀）由入口用 `read_only` 參數決定，沒有「寫入前問使用者」的機制；一次性執行沒有人在旁邊，靠結束後的快照 diff 事後審查。
- 寫入唯讀檔案被擋時，旗標只有 `blocked`，和路徑逃逸分不開。

階段 3 要統計修好率、步數、token、費用與假通過，並依 AGENTS.md 守則 3 記錄實驗條件；這些都需要執行記錄。AGENTS.md 對 telemetry 的需求是：模型版本、runtime、context 長度、token、延遲、工具、結果、是否撞步數上限、被截斷、改測試。

## Goals / Non-Goals

**Goals:**

- 每次執行留下一個結構固定的事件檔，階段 3 的彙整腳本只要讀檔，不用重跑。
- 一個 session 內可以連續下指令，後面的指令看得到前面的對話。
- 互動模式在寫檔與跑測試前問使用者；一次性模式的行為完全不變。
- 不改變迴圈的核心（程式只設保險，由模型決定下一步）。

**Non-Goals:**

- 跨 session 的記憶、單一 session 歷史長度的上限。
- 沙箱放行家目錄下的 Python、逾時後清理孤兒行程、重複呼叫偵測（階段 1 延後項目，要先看事件檔的資料）。
- 測試檔指紋偵測（階段 3）、費用換算、彙整報告、串流輸出（理由與數字見「互動模式的畫面呈現」）。

## Decisions

### 事件檔：每次執行一個 JSONL，四種事件

每次 `fixlab` 執行（一次性或一個互動 session）在 `<log-dir>/<UTC 時間>-<模型>/` 底下建一個 `events.jsonl`，一行一個 JSON 物件，共四種事件：`run_start`（執行條件，一次）、`task_start`（每個任務一次）、`trace`（`trace` 回呼的每筆紀錄）、`task_end`（每個任務的結果）。

- 替代方案 A：所有執行附加到同一個檔案。不選的原因：階段 3 若平行跑多題，各行會交錯；每次執行一個檔，彙整時列出檔案即可，刪掉一次壞掉的執行也只是刪一個資料夾。
- 替代方案 B：只存 `run_end` 的總結。不選的原因：階段 3 要看「在哪一步卡住」，需要每步的紀錄；也要在程式中途被中斷時仍有資料，所以每行寫完立刻 flush，而不是結束時一次寫。
- 與討論時的結論（`run_start`、每步、`run_end`）不同之處：結尾事件改名 `task_end` 並加上 `task_start`，因為一個互動 session 會有多個任務；一次性執行就是只有一個任務。
- 把每筆 `trace` 紀錄原樣放在 `record` 欄位裡，而不是攤平：`trace` 紀錄自己有 `event` 欄位（`tool_calls`、`done` 等），攤平會與外層的 `event` 衝突，巢狀則不需要改動 `loop.py` 的紀錄格式。
- 介面深度：`fixlab/telemetry.py` 要藏住「建目錄、避免重名、每行立刻寫入、時間戳、寫入失敗時降級」；只做 json.dumps 就太淺，不值得獨立成模組。刪掉它，階段 3 沒有資料來源，影響是實質的。

### 事件檔放在使用者家目錄，不放進被修的目錄

預設 `--log-dir` 是 `~/.fixlab/runs`。

- 原因一：放在 PATH 底下，快照 diff 會把事件檔當成新增的檔案，而且模型與被測的程式有機會讀到甚至改寫自己的紀錄，紀錄就不可信。沙箱本來就禁止測試程式讀家目錄。
- 原因二：使用者不一定從 fixlab 專案目錄執行，相對於目前目錄的 `runs/` 位置不固定。
- 替代方案：預設 `runs/`（目前目錄）。不選的原因：同上，且 `fixlab .` 時會落在 PATH 裡面。階段 3 的腳本一律明確傳 `--log-dir`。
- `--log-dir` 若落在 PATH 之內，入口以退出碼 2 拒絕，理由同原因一。

### 事件檔寫入失敗不中斷執行

寫入發生 OSError（磁碟滿、權限）時，在 stderr 印一次警告並停止記錄，agent 照常跑完。

- 替代方案：寫不進去就中止執行。不選的原因：記錄是旁路，不該讓修 bug 的主流程因此失敗；代價是這次執行少了資料，所以警告要顯眼，`task_end` 之後的 stderr 摘要也會提到「event log incomplete」。

### 執行條件用 --meta 記錄，不自動偵測

`--meta KEY=VALUE` 可重複，原樣放進 `run_start` 的 `meta` 欄位，例如 `--meta quantization=Q4_K_M --meta context_length=32768`。自動記錄的只有程式本來就知道的：模型名稱、端點 `OPENAI_BASE_URL`、PATH、`max_steps`、`max_tokens`、沙箱狀態、fixlab 的 git commit、Python 與 openai 版本、模式。

- 原因：AGENTS.md 守則 3 要求記量化方式、runtime 版本、context 長度、種子，但 OpenAI 相容的 API 不回報這些（階段 1 的實跑紀錄裡，量化方式與 context 長度只能手填、或標「未知」）。自動偵測各家 runtime 要寫一堆特例，且不可靠。
- 替代方案：設定檔。不選的原因：多一種格式要維護；命令列旗標在階段 3 的腳本裡最好組。

### run_agent 接續既有 messages，結束時補上最後的回覆

`run_agent` 新增關鍵字參數 `messages`，預設 `None`。`None` 時行為與階段 1 完全相同。傳入一個 list 時：空 list 會先被填入系統提示，再接任務；非空 list 則直接在後面接任務（user 訊息）。傳入的 list 被原地修改，呼叫端保有它。模型宣告完成（`done`）時，最後那則 assistant 回覆也加進 `messages`，下一個任務才接得上。

- 替代方案 A：`run_agent` 回傳新的 `messages`，呼叫端自己帶回去。不選的原因：每個呼叫端都要記得接回，原地修改的寫法在互動入口最短，也不影響只要結果的一次性入口。
- 替代方案 B：讓 loop 持有 session 物件。不選的原因：多一個類別，階段 2 只有一個使用情境。
- 影響：黃金 trace 的 `requests` 是送給模型的請求，最後一則回覆是在最後一次請求之後才加入，所以 `requests` 不變；`trace` 部分會因為新增的兩個欄位與 `protected_write` 旗標而變，重新產生一次，並用 git diff 確認只多了這些。

### 互動模式用 -i，不設子命令；斜線指令只有 /reset 與 /exit

`fixlab PATH -i` 進入互動模式，沒有 `-i` 就是原本的一次性執行。階段 1 的設計決定「不設子命令」維持不變。提示字元後讀一行：空行忽略；`/exit` 或 EOF（Ctrl-D）離開；`/reset` 清空對話並印出一行確認；其他一律當成任務。

- 為什麼要 `/reset`：單一 session 的歷史長度不設上限（見 Non-Goals），使用者需要一個手動重來的出口，避免撞到小模型的 context 上限。
- 替代方案：不分模式、沒給任務就進互動。不選的原因：`fixlab PATH` 的退出碼與 `RESULT:` 行是一次性模式的契約，隱含切換會讓腳本誤入互動。
- 互動模式不在每個任務後自動再跑一次 `run_tests`（一次性模式的做法）：使用者在場，想驗證可以直接叫模型跑，所以 `task_end` 的 `final_tests` 是 null。這是階段 1 設計文件「互動模式可以改成使用者想要時才執行」的落實。

### 中斷時保留已完成的部分

互動模式在 Ctrl-C 打斷執行中的任務時，保留任務已經加進對話的訊息，由迴圈把「有 tool_calls、卻還沒有結果」的呼叫補上結果：被打斷的那一個補「使用者中斷了，執行狀態不明，重試前請先檢查現況」，同一個回覆裡排在後面、還沒開始的補「沒有執行」。入口再接一則 assistant 訊息 `[The user interrupted this task.]`，為該任務寫一筆 `stop_reason` 為 `interrupted` 的 `task_end`，印出提醒，回到提示字元。

- 原因：模型的 API 要求每個 assistant 的 tool_calls 都有對應的 tool 結果，留下缺結果的呼叫，之後每個請求都會被拒絕，所以一定要處理；而保留已完成的部分，模型才知道前面發生了什麼（讀過哪些檔、改過哪個檔），不會重做，也不會不知道檔案已經被改了。
- 替代方案 A：把這個任務的訊息整個丟掉（原本的做法，任務 3.2）。不選的原因：已經執行的修改還留在檔案裡，對話卻不記得，模型下一個任務會在不知情的狀況下面對被改過的檔案。這是讀了高見龍 KeSi 的做法之後改的，他保留已完成的部分並補上「沒有執行」的結果。
- 原本否決補結果的理由是「要猜哪些呼叫已執行、哪些沒有」，這個理由不成立：迴圈本來就依序執行呼叫，知道中斷時停在第幾個。唯一不確定的是被打斷的那個本身（可能跑到一半），所以它的結果寫「狀態不明」，不寫「沒有執行」。
- 補結果放在 `fixlab/loop.py` 的執行工具那一段，因為「每個 tool_calls 都要有結果」是迴圈建立的對話結構，不該由入口去猜；入口只負責接上 assistant 的中斷說明與畫面。
- 在提示字元上按 Ctrl-C：離開，與 EOF 相同。請求失敗（`error`）仍然丟掉該任務，理由不變：對話停在一則沒有回覆的 user 訊息，沒有可保留的完成內容。

### 權限提示做成 Workspace 的 confirm 參數

`Workspace(..., confirm=...)`，`confirm(工具名稱, 參數) -> bool`，預設為全部放行。`Workspace.call` 在參數檢查通過、執行工具之前呼叫它；回傳 False 就不執行，回傳 `ToolResult(ok=False)` 並設 `denied` 旗標。

- 替代方案 A：提示放在迴圈裡。不選的原因：AGENTS.md 要求迴圈只設保險，政策放進迴圈會讓它變成 workflow，每個入口也得重寫。替代方案 B：提示放在各工具裡。不選的原因：散在三個工具、容易漏。與 `read_only` 同樣的模式：政策由建立 Workspace 的入口決定，這是階段 1 就選的結構。
- 互動入口的 `confirm` 只對 `edit_file`、`write_file`、`run_tests` 提問；讀取類工具直接放行。提問時顯示：edit_file 顯示路徑與新舊字串（各最多 200 字元）、write_file 顯示路徑與字元數、run_tests 顯示目標。回答 `y` 這次放行、`a` 這個 session 內該工具一律放行、其他（含空白）拒絕。標準輸入已結束（EOF）也當作拒絕。
- 一次性模式不傳 `confirm`，行為不變。
- 已知不夠好：會被擋下的呼叫（例如改測試檔）仍會先問使用者一次，答應之後才被擋。見 Risks。

### 被拒絕的呼叫算失敗，旗標獨立為 denied

使用者拒絕的呼叫回 `ok=false`，旗標 `denied`，計數器 `denied_calls`，並回給模型一段說明，教它不要原樣重試、可以改做法或請使用者說明。因為 `ok=false`，它計入連續失敗保險：連續三輪全被拒絕，迴圈以 `stuck` 結束。

- 與 `blocked` 分開：`blocked` 是規則擋下（路徑逃逸、唯讀檔案），`denied` 是人決定的；事件檔要分得出來，階段 3 才能統計。
- 替代方案：拒絕不算失敗。不選的原因：模型可能一直重複同一個被拒絕的請求，沒有保險會浪費步數與使用者的耐心。

### 每步紀錄補截斷與原始呼叫數

`trace` 的步驟紀錄新增 `truncated`（這個回覆是否被輸出長度上限截斷）與 `reply_tool_calls`（回覆原本帶了幾個原生工具呼叫，包含不合法、被丟掉的）。

- 原因：階段 1 的設計文件記下「要記下每個回覆原本的呼叫數，包含被擋下的」；目前 `truncated` 只在計數器裡，看不出是哪一步。這兩個欄位用 `fixlab/loop.py` 手上已有的資訊算出，不需要新機制。

### 寫入唯讀檔案的嘗試用 protected_write 旗標

寫入唯讀檔案而被擋時，`ToolResult` 的旗標除了 `blocked` 還多 `protected_write`。實作上為唯讀檔案另開 `PathBlocked` 的子類別，`Workspace.call` 依類別加旗標。

- 原因：AGENTS.md 要的 telemetry 有「改測試」。階段 3 才做指紋偵測，但「模型試過改測試檔」現在就能記，成本是一個旗標。事件檔裡的 `tool_calls` 本來就帶 `flags`，不用另開欄位。
- 迴圈把工具回傳的旗標轉成計數器時，`protected_write` 計入 `protected_write_calls`（與 `blocked_calls`、`denied_calls` 命名一致）；原本的做法是「為真的旗標用旗標自己的名字當計數器」，新旗標會自動變成名叫 `protected_write` 的計數器，名字和其他不一致，所以改用一張明確的對照表。`task_end` 的 `counters` 因此直接帶這個數字。
- 替代方案：用錯誤訊息文字比對。不選的原因：脆弱，訊息措辭一改就失效。

### 互動模式的畫面呈現

互動模式每個工具呼叫排成一組：標題行 `▸ 工具 路徑`、（改檔時）`-`／`+` 的差異、（要問時）問題、結果行 `✓`／`✗ 原因`；任務結束後印一行用量當結尾，答案前後各空一行；全部印到標準輸出；顏色只在終端機且沒設 `NO_COLOR` 時才開。畫面的邏輯放在新的 `fixlab/display.py`（只回傳字串，不直接印），`fixlab/cli.py` 用一個 `Workspace` 的子類別在呼叫前後印出。

- 起因：任務 3.5 用真模型實跑時，使用者說畫面「有點醜」。當時的輸出是 debug 格式（`edit_file  ok=True  flags={}`），沒有縮排、沒有分層，權限摘要用 `repr`（`\d` 變成 `\\d`），工具進度走標準錯誤、問題走標準輸出，兩邊在終端機上錯開。
- 為什麼用 `Workspace` 的子類別覆寫 `call`：一次工具呼叫的顯示要包住「標題、問題、結果」三段，問題是在 `call` 裡面問的，所以要在 `call` 前後印。替代方案 A：在 `trace` 回呼裡印。不選的原因：`trace` 是整步結束後才觸發，標題會晚於問題出現，一個回覆有多個呼叫時順序還會亂。替代方案 B：在 `Workspace` 加兩個 `on_call`、`on_result` 參數。不選的原因：只有互動入口需要，子類別就夠了，不用再多一個介面。
- 全部印到標準輸出：互動模式的畫面是一整個介面，混用兩個串流在終端機上會錯開。一次性模式不變，仍然把每個工具一行印到標準錯誤。
- 改檔顯示成 `-`／`+` 而不是 `repr`：使用者要判斷「要不要放行」，需要看到真正的換行與縮排；每段最多 10 行、每行最多 200 字元，避免洗版。每個 `edit_file` 都顯示差異（包含「一律放行」之後），因為事後也想知道改了什麼。
- 參考：高見龍 KeSi 的畫面（`kesi.py`，commit `dfa0cd0`，2026-10-17 讀完整的輸出程式）用說話者標籤（`你 >`、`KeSi >`）、縮排分層、固定的方括號標籤（`[執行工具]`、`[需要授權]`、`[已擋下]`）、每輪結束一行用量與費用；沒有顏色，工具參數整個字典照印，不顯示工具結果。採用的想法：縮排分層與每輪結尾的用量行；不同之處：這裡顯示結果行與差異、參數只顯示重點、沒有費用（階段 3）、不串流。
- 不串流：2026-10-17 用真實執行的事件檔量到，每一步等待 1.1 到 5.0 秒、多半約 1.4 秒，8 步裡只有最後一步是文字回覆（257 個 token、2.8 秒），串流只會讓最後那則回覆早幾秒出現；而 OpenAI 相容的 API 要自己拼回分段送來的工具呼叫，各家伺服器行為不一致，用量也要靠伺服器支援特定選項才拿得到，重試、截斷、中斷、黃金 trace 與假 client 的測試都得跟著改。等到用本機大模型、一次回覆要等十幾秒以上的時候再做，先看事件檔的 `latency_s`。

### 設計依據與參考來源

依據是 AGENTS.md 的 telemetry 需求、階段 1 的程式缺口（上面 Context）與階段 1 設計文件留給階段 2 的項目。參考來源（只當參考，不當依據）：

- 高見龍 KeSi（repo `dfa0cd0`，2026-10-17 clone）：沒有 JSONL 事件記錄；token 與費用記在記憶體裡的記帳物件，用 `/cost` 或每輪結束時印出，程式結束就沒了，所以事件記錄沒有可參考的做法。互動模式的斜線指令 `/exit`、`/reset`、`/cost` 是從 `kesi.py` 看到的；commit 標題有「add tool permission gate with session grants」與「keep history consistent on interrupt」，這個設計的 y／a／N 提示與中斷處理與它們想法相同，我沒有讀那兩個實作，不能排除受他影響。截斷訊息的做法、`confirm` 參數、`denied` 旗標與記錄格式是依 fixlab 自己的結構設計。
- Claude Code 的行為：寫檔與執行指令前會問「這次允許、這個 session 一律允許、拒絕」三種，是 y／a／N 的來源（憑使用經驗，今天沒有重新查文件）。

## Implementation Contract

**範圍內**：事件檔、`run_agent` 接續對話、互動模式、權限提示、兩個新的每步欄位、`protected_write` 旗標、README 更新與 `stage-2` tag。**範圍外**：見 Non-Goals。

**命令列**（`fixlab/cli.py`）

- 新增 `-i` / `--interactive`、`--log-dir DIR`（預設 `~/.fixlab/runs`）、`--meta KEY=VALUE`（可重複）。
- 退出碼 2 新增兩種：`--meta` 的值沒有 `=`；`--log-dir` 落在 PATH 之內。一次性模式的退出碼 0／1／2 與最後一行 `RESULT:` 維持不變。
- 開始時在 stderr 印一行 `log: <events.jsonl 的路徑>`。

**事件檔**（`fixlab/telemetry.py`）

- `EventLog(log_dir, model)`：建立 `<log_dir>/<%Y%m%dT%H%M%SZ>-<model>/events.jsonl`，model 中不屬於字母、數字、點、底線、減號的字元換成減號；資料夾已存在則加 `-2`、`-3`，永不覆寫或附加到既有檔案。`write(event, **fields)` 寫一行並立刻 flush，每行自動加 `event` 與 `ts`（UTC，ISO 8601，毫秒，結尾 Z）。OSError 時印一次警告到 stderr，之後的 `write` 靜默略過。
- `run_start`：`schema`（整數 1）、`mode`（`once` 或 `interactive`）、`model`、`base_url`、`path`、`max_steps`、`max_tokens`、`sandbox`、`fixlab_commit`（取不到時為 null）、`python`、`openai`、`meta`（物件）。
- `task_start`：`task`（從 1 起算的序號）、`text`。
- `trace`：`task`、`record`（`trace` 回呼的紀錄原樣）。
- `task_end`：`task`、`stop_reason`、`steps`、`counters`、`prompt_tokens`、`completion_tokens`、`seconds`、`final_tests`（一次性模式為 `{"tests_passed": bool, "timed_out": bool}`，互動模式為 null）、`changed_files`（一次性模式為 `{"added": [...], "modified": [...], "deleted": [...]}`，路徑相對於 PATH 且排序；互動模式為 null）。
- 檔案內不含費用；token 數原樣記錄。

**迴圈**（`fixlab/loop.py`）

- `run_agent(client, model, ws, task, *, messages=None, max_steps=..., request_extra=None, trace=...)`。契約見 Decisions。結束 `done` 時追加 `{"role": "assistant", "content": 回覆文字或空字串}`。
- 步驟紀錄新增 `truncated`（bool）、`reply_tool_calls`（int）。
- 工具回傳旗標 `denied` 時，計數器 `denied_calls` 加一；旗標 `protected_write` 計入 `protected_write_calls`（都與 `blocked_calls` 並列，由一張旗標對計數器名稱的對照表決定）。

**Workspace**（`fixlab/workspace.py`）

- `Workspace(..., confirm=allow_everything)`；`confirm(name, args) -> bool`。`call` 的順序：工具存在 → 參數檢查 → `confirm` → 執行。拒絕的結果：`ToolResult("error: the user declined this call. Do not retry it unchanged; try a different approach or ask the user what they want.", False, {"denied": True})`。
- 寫入唯讀檔案被擋：旗標 `{"blocked": True, "protected_write": True}`。路徑逃逸維持只有 `blocked`。

**互動入口**（`fixlab/cli.py`）

- 提示字元 `fixlab> `。流程見 Decisions。每個任務各寫 `task_start` 與 `task_end`；`/reset` 之後任務序號繼續遞增，事件檔不截斷。
- 權限提示的格式：先印一行摘要（工具名稱與路徑或目標），再印 `Allow? [y]es / [a]lways for this tool / [N]o: `。

**驗收**

- 一次性 `fixlab PATH`：除了多一個事件檔與 `log:` 那一行，stdout 與退出碼和階段 1 相同。
- 互動：第一個任務讀檔，第二個任務的請求裡帶有第一個任務的對話。
- 既有測試（260 個）除黃金 trace 的比對檔與 `test_golden_covers_the_intended_cases` 裡被擋下那一步的旗標斷言外，不改動也通過；黃金檔重新產生一次，git diff 只能多出 `truncated`、`reply_tool_calls` 與 `protected_write`，`requests` 部分一個字都不變。

## Risks / Trade-offs

- [會被擋下的呼叫仍會先問使用者] → 使用者回答 y 之後才發現它被擋，體驗不好。先接受；若實際使用常碰到，再讓入口的 `confirm` 先用 `read_only` 判斷、對唯讀檔案不提問。
- [單一 session 的對話越來越長，小模型的 context 會滿（Ollama 用 32768）] → `/reset` 是手動出口；事件檔裡每步的 `prompt_tokens` 會顯示成長的曲線，有資料後再決定要不要自動截斷或摘要。
- [被打斷的那個呼叫可能已經執行了一半（例如測試跑到一半、檔案寫了一半）] → 它的結果寫「狀態不明，重試前請先檢查現況」，讓模型自己去確認；中斷時另外印提醒，使用者可用 `/reset`。
- [事件檔含模型回覆與工具輸出（各最多 2000 字元），可能含目標專案的原始碼或祕密] → 放在使用者家目錄、不進版控；README 要寫明不要隨意分享事件檔。階段 1 已記的風險「對別人的 repo 執行前要限制 read_file 讀 .env」仍未處理，這個變更不處理。
- [`final_tests` 與 `changed_files` 在互動模式是 null] → 階段 3 的腳本只對一次性模式的紀錄算修好率；互動模式的紀錄用來看行為，不用來評分。
- [任務 2.4 的觀察（2026-10-17，是觀察不是通過門檻）。模型 qwen/qwen3.5-9b，經 OpenRouter，provider 為 Venice，對 timelog 副本跑一次：8 步，prompt 12,818 加 completion 1,249 token（依清單價格約 $0.0015），17.4 秒，最後 5 passed。事件檔 11 行、7,340 位元組、最長一行 1,155 字元，每行可解析，`task_end` 的 token 與畫面印的相同；只用這個檔算得出步數、token、延遲、各工具次數與最後測試結果。缺口：`fixlab_commit` 只記 git HEAD，不知道當時的工作樹有沒有未提交的修改，用髒的工作樹跑出的結果會被記在乾淨的 commit 名下] → 階段 3 的實驗在乾淨的工作樹上跑；之後若要自動分辨，在 `run_start` 加一個 `fixlab_dirty`（`git status --porcelain` 非空）。
- [互動模式 footer 的耗時是整個任務的時間，包含使用者思考與回答權限問題的時間（2026-10-17 實跑：任務一 123.87 秒，其中模型每步只有 1 到 5 秒）] → footer 與 `task_end.seconds` 是「牆上時間」；要看模型本身的延遲，用每步 `record.latency_s`。
- [`schema` 版本的演進] → 目前是 1；之後改欄位時遞增，彙整腳本要檢查版本。
- [互動模式的手感（提示字元、換行、Ctrl-C）無法完全用自動測試涵蓋] → 測試用注入的輸入與假 client；另有一項手動任務用真終端機與真模型各跑一次並記錄。

## Migration Plan

不需要遷移：沒有既有資料格式，一次性模式的對外行為不變。回復方式就是不傳 `-i`、`--log-dir`、`--meta`；事件檔是額外產物，刪除不影響程式。

## Open Questions

- 單一 session 歷史的上限與處理方式（截斷、摘要）：等事件檔有實際長度再決定。
- 互動模式是否要在每個任務前後也拍快照、填入 `changed_files`：先不做，需要時再加。
- 被拒絕的呼叫連續三輪就 `stuck` 是否太嚴：先照這樣做，實際使用後調整。
