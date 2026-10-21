## Context

工具在 Workspace 以 register(名稱, 函式, schema, 說明, precheck) 登記，模型的呼叫一律經過 Workspace.call：結構檢查、precheck、confirm（互動模式由 make_asker 問使用者，只問 ASKED_TOOLS）、執行，任何預期內的錯誤都變成 ok=false。tool_specs 把 schema 補上 type object 送給模型；toolparse.validate 只檢查工具存在與必要參數；Workspace._check_args 另外檢查多餘參數與簡單型別，遇到 type 是清單時會因為字典查表而丟出 TypeError，這不在 call 的捕捉範圍內。fixlab 是同步程式，官方 SDK `mcp` 2.3.0（2026-10-02 發佈，需要 Python 3.10 以上，依賴 anyio、pydantic、httpx、starlette、opentelemetry 等）是非同步的。2026-10-21 在暫存環境實測：client 端 API 為 stdio_client(StdioServerParameters) 與 ClientSession 的 initialize、list_tools、call_tool，結果型別 CallToolResult 有 content、structured_content、is_error；stdio_client 預設只繼承 HOME、LOGNAME、PATH、SHELL、TERM、USER。實測也發現：在背景事件迴圈裡用 AsyncExitStack 分開開啟與關閉連線，會丟出「在不同的 task 退出 cancel scope」，必須由同一個 task 開啟、使用並關閉。

## Goals / Non-Goals

**Goals:**

- 互動模式下，agent 可以呼叫使用者設定的本機 MCP server 的工具，每次呼叫都經使用者確認。
- 不改 agent 迴圈；MCP 工具和內建工具走同一條 Workspace.call。
- 不裝 MCP 的人、一次性模式、benchmark 都不受影響。

**Non-Goals:**

- 不支援遠端 server、OAuth、resources、prompts、sampling、elicitation。
- 不把 server 放進沙箱、不自動讀取任何 MCP 設定檔、不讓 fixlab 當 server。

## Decisions

### 使用官方 SDK，做成選用安裝

pyproject 新增 optional-dependencies 的 mcp extra（mcp>=2.3,<3），只有 fixlab/mcp_tools.py 匯入它，而且只在給了 `--mcp-config` 時才匯入。替代方案是自己寫最小的 stdio JSON-RPC client（教學價值高、沒有依賴），使用者選擇官方 SDK：協定細節與版本更新由 SDK 處理。

### 同步介面：背景執行緒加上單一 task 管理每個連線

fixlab/mcp_tools.py 的 McpServer 類別在一條背景執行緒跑一個事件迴圈；每個 server 由一個長時間執行的 task 用 `async with stdio_client(...)` 與 `async with ClientSession(...)` 開啟、initialize、處理佇列送來的請求、收到結束訊號後在同一個 task 關閉。同步端用 concurrent.futures.Future 等結果並設逾時（啟動與列工具 30 秒、每次呼叫 60 秒）。這是實測可行的寫法（暫存環境的原型：列工具、呼叫、正常關閉都成功）。

### 只接受使用者指定的設定檔，只支援 stdio

`--mcp-config PATH` 是唯一來源，格式沿用常見的 mcpServers（command、args、env、cwd）；出現 url 等其他鍵就拒絕。設定檔的 env 合併到 SDK 預設繼承的變數上；fixlab 自己的 OPENAI_API_KEY 等不會傳給 server（SDK 預設不繼承）。cwd 沒寫就用 fixlab 啟動時的目前目錄。

### 只在互動模式開放，每次呼叫都確認

MCP server 是以使用者權限執行、不受沙箱限制的程式，它的工具可以做任何事，屬於 AGENTS.md「任意外部能力須先有白名單與確認機制」的範圍：白名單是設定檔明列的 server，確認是互動模式的逐次詢問。make_asker 的詢問判斷由 ASKED_TOOLS 改為「內建的三個寫入或執行工具，加上所有 mcp__ 開頭的工具」。確認前要讓使用者看得到這次呼叫做什麼：display.call_detail 對 MCP 工具顯示 server、原始工具名稱與參數 JSON（過長的值從中間截斷）；目前它對不認得的工具回傳空字串，只看得到工具名稱。一次性模式沒有人可以確認，給 `--mcp-config` 就拒絕。

### 工具名稱與 schema

名稱用 `mcp__<server>__<tool>`，必須符合 `[A-Za-z0-9_-]{1,64}`（OpenAI function 名稱的限制），不符合的略過並警告、記錄在事件檔。兩個工具組出同一個名稱時（server a__b 的 c 與 server a 的 b__c）以結束碼 2 結束並列出兩者，不讓 Workspace.register 默默覆寫。說明前面加上「[external tool from MCP server <server>]」。schema 不是 object 型態的略過。MCP 工具的參數只檢查「是 JSON 物件」與 required 齊全，其他規則（型別、多餘參數、布林或巢狀子 schema、patternProperties）交給 server：fixlab 的簡單檢查不可能涵蓋所有合法的 JSON Schema，誤拒或在檢查時丟出例外都比交給 server 糟。做法是 Workspace.register 新增 loose_args 選項，MCP 工具登記時開啟，_check_args 遇到它只做這兩項檢查；內建工具不變。

### 結果轉換與錯誤

文字區塊以換行串接；其他區塊（圖片、音訊、資源）換成一行「[<type> content omitted]」。沒有文字區塊但有 structured_content 時，回傳它的 JSON。超過 8000 字元保留頭尾各 4000 字元，沿用 tools.clip_middle 的格式。is_error 為真時 ok=false。逾時、server 已結束、SDK 丟出的例外一律轉成 ok=false 的 ToolResult，在 McpServer 內處理，不往 Workspace.call 外丟。逾時不能只停止等待：每個請求在背景迴圈裡是一個可取消的 task，逾時時取消它；佇列裡的請求帶著截止時間，過期的直接丟棄，不會在逾時之後才送到 server。

### 啟動順序與關閉

CLI 在其他參數檢查、Workspace 建立與直譯器檢查之後，事件檔與模型請求之前啟動所有 server；任一失敗就關閉已啟動的、以結束碼 2 結束，訊息附上該 server stderr 的最後幾行。server 的 stderr 寫到私有暫存檔，不印到終端機（避免和互動提示混在一起），啟動失敗時附上最後幾行，結束時刪除；不另外保存（審查認為目前沒有需求，之後有除錯需要再加選項）。session 結束（EOF、/exit、Ctrl-C）時用 try/finally 關閉所有 server，總時限 10 秒：取消進行中的呼叫、丟棄佇列裡的請求、送出結束訊號，時限到了還沒結束的 server 行程直接終止；關閉過程不改變結束碼。

### 事件檔與 benchmark

run_start 新增 mcp 欄位（沒給設定時為 null），只記 server 名稱、登記的工具、略過的工具與 SDK 版本，不記指令、參數、環境變數與 cwd（可能含金鑰）。每次工具呼叫本來就以 trace 記錄。benchmark 執行器沒有修改，本來就不會傳 `--mcp-config`，不另外加需求與測試。

## Implementation Contract

- 行為：`fixlab -i --mcp-config servers.json` 啟動列出的 stdio server，模型看得到 `mcp__<server>__<tool>`，每次呼叫先問使用者；沒給設定時與現在完全相同。
- 介面：新參數 `--mcp-config PATH`；新模組 fixlab/mcp_tools.py 提供 load_config(path) → dict（不合法丟 ValueError）、start_servers(config) → list[McpServer]（失敗丟 ValueError，已啟動的會關閉）、register_mcp_tools(ws, servers) → (登記名稱, 略過名稱)（名稱碰撞丟 ValueError）、McpServer.call(tool, args) → ToolResult、close_all(servers, timeout=10)；Workspace.register 新增 loose_args；make_asker 認得 mcp__ 前綴；display.call_detail 顯示 MCP 呼叫的 server、工具與參數；run_start 新增 mcp。
- 失敗模式：設定檔不合法、沒裝 SDK、一次性模式、server 啟動或初始化或列工具失敗或逾時 → 結束碼 2、印出原因、不建事件檔、不呼叫模型。執行中的呼叫失敗 → ok=false，迴圈繼續。
- 驗收：tests/test_mcp_tools.py 用 tests/mcp_echo_server.py（以 SDK 的 MCPServer 寫的測試用 server）涵蓋設定檔驗證、名稱前綴與略過、名稱碰撞、規格表格裡的四種 schema、文字、非文字與只有 structured_content 的結果、截斷、server 錯誤、逾時後再呼叫且過期請求不被執行、server 結束後呼叫、啟動失敗、卡住的呼叫下 10 秒內結束且沒有殘留行程、stderr 暫存檔被刪除；tests/test_cli.py 涵蓋一次性模式拒絕、沒裝 SDK 的訊息（以模擬匯入失敗）、確認畫面顯示 server、工具與參數、拒絕的呼叫 server 收不到、run_start 的 mcp 欄位不含指令；沒裝 SDK 時 MCP 相關測試以 skip 標明；完整 pytest 通過。
- 範圍：新增 fixlab/mcp_tools.py、tests/test_mcp_tools.py、tests/mcp_echo_server.py；修改 fixlab/cli.py、fixlab/workspace.py、fixlab/display.py、pyproject.toml、README.md、tests/test_interactive.py（CLI 的 MCP 測試放在互動模式的測試檔）、tests/test_packaging.py。不改 agent 迴圈、沙箱與 benchmark 評分。

## Risks / Trade-offs

- MCP server 不受沙箱限制，可以讀寫使用者權限內的任何檔案、連網 → README 寫明「指定等於信任」，只開放互動模式並逐次確認；fixlab 的工作目錄保護與測試檔保護管不到 server 自己做的事。
- 依賴變多：SDK 帶進 pydantic、starlette、opentelemetry 等 → 做成選用安裝。
- SDK 2.x 的 API 仍在演進（1.x 到 2.x 已有更名，例如 FastMCP 改名 MCPServer）→ 版本鎖在 >=2.3,<3，介面集中在 fixlab/mcp_tools.py。
- 開發環境的測試需要安裝 mcp extra；沒裝時相關測試 skip，CI 若要涵蓋需另外安裝。
- 事件檔不記 server 的指令與參數：實驗重現時需要另外保存設定檔；但 MCP 不用於實驗。
- 確認畫面的 server 與工具名稱由登記時記下的對照表（Workspace.external_tools）提供；參數完整顯示、非 ASCII 一律跳脫，超過 4000 字元直接拒絕（code review 指出：截斷會讓使用者同意看不到的內容，未跳脫的方向控制字元能讓畫面和實際參數不同）。
- 關閉時不原生取消背景 task：SDK 自己的停止流程（關 stdin、等待、SIGTERM、再等、SIGKILL，約 6.5 秒）會被原生取消打斷，忽略 SIGTERM 的 server 會殘留（code review 第二輪重現）。正常關閉走佇列的結束訊號；啟動中的 server 以事件通知它停止等待、正常離開連線；正常關閉最多等 8 秒（比 SDK 的停止流程久），最後 2 秒還沒結束的才強制結束（見下一條），之後仍等 SDK 回收行程再停止事件迴圈。通知啟動中的 server 停止時也把結束訊號放進佇列，啟動剛好完成的情況也收得到。
- 強制結束不取消 task，改成直接 SIGKILL server 的行程群組：SDK 不公開子行程的 pid，原生取消又會讓 task 卡在 SDK 的收尾（code review 第四輪重現）。所以 server 經過一段極小的啟動程式啟動（fixlab 自己的 Python，-I -S），它把 pid 寫進私有暫存檔（寫完再改名）、還原 SIGPIPE，再 exec 成設定的指令；exec 不改 pid，SDK 以新 session 啟動子行程，所以 pid 就是行程群組。環境變數、目前目錄與 PATH 查找由 SDK 照設定傳入，和直接啟動一樣。pid 只在這次連線期間使用，結束時連同暫存目錄刪除；macOS 沒有穩定的行程 handle，pid 重用的風險無法完全排除，但只在 task 尚未結束時才送訊號。整個關閉共用一個 10 秒時限（包括停止事件迴圈）；關閉途中按 Ctrl-C 會直接進入強制結束，所有 server 收尾後才往上丟。
- 結果行的錯誤文字把不可列印字元改成跳脫寫法：外部工具的錯誤可能回顯模型給的參數，原樣印出能讓模型控制終端機、遮住下一次確認。
- SDK 回報連線關閉用的代碼 -32000 也是 server 自己回錯誤時常用的代碼，所以收到時再 ping 一次，不通才算 server 結束。
- code review 延後的意見（與 Codex 討論後判定不必在此修）：啟動 server 時按 Ctrl-C 會印出 Python traceback（server 仍會被關閉）；多個 server 依序啟動，總時間是加總；確認畫面與結果的截斷各有一份程式。
- 「這個工具一律放行」已對 MCP 工具移除（依使用者決定，原本保留、Codex 建議拿掉）：MCP server 在沙箱外以使用者的權限執行，每次呼叫確認是唯一擋住模型的關卡；放行一次，模型之後可以送任何未經檢視的參數。內建的 edit_file、write_file、run_tests 仍保留。之後可考慮在設定檔加每個工具的 `autoApprove` 清單，由使用者事先指定。
