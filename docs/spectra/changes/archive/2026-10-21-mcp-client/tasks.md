## 1. 依賴與設定檔

- [x] 1.1 依「使用官方 SDK，做成選用安裝」與 The MCP SDK is an optional dependency，pyproject.toml 新增 mcp extra（mcp>=2.3,<3），在開發用 .venv 安裝；tests/test_packaging.py 或新測試確認核心依賴沒有增加。
- [x] 1.2 [after: 1.1] 依「只接受使用者指定的設定檔，只支援 stdio」與 MCP servers come only from a file the user names，實作 fixlab/mcp_tools.py 的 load_config：tests/test_mcp_tools.py 先寫測試涵蓋合法設定、非 JSON、缺 mcpServers、缺 command、url 鍵、型別錯誤、server 名稱不合法，確認失敗再實作到通過。

## 2. 連線與工具

- [x] 2.1 [after: 1.2] 依「同步介面：背景執行緒加上單一 task 管理每個連線」與 Startup failures stop before any model request and servers are closed at exit，實作 McpServer 與 start_servers，並新增 tests/mcp_echo_server.py（SDK 的 MCPServer，提供 shout、一個回傳錯誤的工具、一個回傳圖片的工具、一個會睡很久的工具、一個讓行程結束的工具）：測試涵蓋啟動、列工具（含分頁）、啟動失敗時關閉已啟動的 server 並附上 stderr 最後幾行、close_all 在有卡住的呼叫時 10 秒內結束且沒有殘留行程、stderr 暫存檔在結束時刪除，先失敗再通過。
- [x] 2.2 [after: 2.1] 依「工具名稱與 schema」與 MCP tools join the tool list with a prefix，實作 register_mcp_tools，並在 Workspace.register 新增 loose_args（MCP 工具只檢查參數是物件與 required）：測試涵蓋前綴名稱、說明標記、過長名稱與非 object schema 被略過並警告、名稱碰撞以 ValueError 拒絕、規格表格裡的四種 schema，且既有工具的測試全部仍通過。
- [x] 2.3 [after: 2.2] 依「結果轉換與錯誤」與 MCP results are text, bounded, and never crash the loop，實作 McpServer.call 的結果轉換：測試涵蓋文字、非文字區塊、只有 structured_content、超過 8000 字元截斷、is_error、逾時（測試中把時限改短）後再呼叫同一個 server 仍得到回應且過期的請求沒有被執行、server 結束後呼叫回 ok=false。

## 3. CLI、權限與事件檔

- [x] 3.1 [after: 2.3] 依「只在互動模式開放，每次呼叫都確認」「啟動順序與關閉」與 MCP tools are offered only in interactive mode and every call is confirmed，CLI 新增 `--mcp-config`：一次性模式拒絕、沒裝 SDK 的訊息、在事件檔與模型請求前啟動 server、session 結束（EOF、/exit、Ctrl-C）時呼叫 close_all；make_asker 對 mcp__ 工具詢問；display.call_detail 在確認前顯示 server、工具名稱與參數 JSON。tests/test_cli.py 涵蓋這些情況、確認畫面的內容與「拒絕的呼叫不會送到 server」，先失敗再通過。
- [x] 3.2 [after: 3.1] 依「事件檔與 benchmark」與 run_start records the MCP configuration summary：run_start 加入 mcp 欄位（沒給設定時為 null），測試確認內容與不含指令參數。

## 4. 文件與驗證

- [x] 4.1 [after: 3.2] 更新 README.md（給外部讀者）：安裝 `fixlab[mcp]`、設定檔格式與範例、只在互動模式、每次確認、信任模型（server 以使用者權限執行、不受沙箱限制，指定等於信任）、事件檔記錄的內容與限制；以內容審查對照規格驗證。
- [x] 4.2 [after: 4.1] 執行完整 pytest（含與不含 mcp extra 各一次）；以 tests/mcp_echo_server.py 實際啟動 `fixlab -i --mcp-config`，送 EOF 確認啟動、工具登記、run_start 的 mcp 欄位與結束後沒有殘留行程；把結果記錄在本檔的驗證紀錄。

## 驗證紀錄

- 2026-10-21：每項任務的新測試都先確認失敗再實作。開發用 .venv 只單獨安裝 mcp 2.3.0（沒有重裝 fixlab，保留 .venv/bin/fixlab 的自訂啟動器）。
- 實作中發現：SDK 回報 server 結束的方式是 MCPError「Connection closed」，背景 task 不會結束，所以另外記住「server 已結束」，之後的呼叫直接回報不可用。
- 完整 pytest：有 mcp extra 676 passed；在只裝 openai、pytest、regex 的暫存環境 638 passed、5 skipped（MCP 連線相關測試略過，「沒裝 SDK 的訊息」測試通過）。
- 實際啟動：timelog 複本中以 `fixlab --mcp-config servers.json`（tests/mcp_echo_server.py）啟動互動模式並送 EOF：結束碼 0，run_start 的 mcp 記錄 sdk_version 2.3.0 與 7 個 mcp__echo__ 工具、skipped 為空，不含指令與參數；結束後 server 行程已不存在，fixlab-mcp- 暫存檔都已刪除。
- code review 後與 Codex 討論，修正必要的七筆：啟動中的 server 關閉時取消並等 SDK 結束子行程（行程殘留已重現）；連線關閉改看錯誤代碼再 ping 確認（server 錯誤訊息含 Connection closed 會停用 server，已重現）；確認畫面顯示完整參數並跳脫非 ASCII、超過 4000 字元直接拒絕；server 與工具名稱改查登記時的對照表；事件檔的工具歸屬改用登記結果；--hide-tool 可以隱藏 MCP 工具。新增測試皆先確認失敗。
- code review 第二輪後與 Codex 討論，修正兩筆：關閉時改走 SDK 自己的停止流程（忽略 SIGTERM 的 server 殘留已重現），啟動中的 server 改用事件通知停止；結果行的錯誤文字跳脫不可列印字元。完整 pytest 685 passed。
- code review 第三輪修正兩筆（上一輪修正帶進來的）：強制取消後等 task 跑完才停止事件迴圈；啟動中通知停止時也放入結束訊號，避免剛好啟動完成的競態。
- code review 第四輪後與 Codex 討論做法，修正兩筆：強制結束改為 SIGKILL server 的行程群組（經啟動程式取得 pid），不再取消 task；等待時不吞 Ctrl-C，關閉途中按 Ctrl-C 先強制結束全部 server 再往上丟；整個關閉共用一個時限。新增強制結束、Ctrl-C 與啟動程式保留環境的測試。
- code review 第五輪修正六筆小問題：啟動程式也還原 SIGXFSZ；指令執行不了時以一行訊息說明；規格、設計與註解改成以 SIGKILL 強制結束的描述；關閉的每一步都接住 Ctrl-C；已結束的 server 不送訊號、不退而對單一 pid 送訊號；Windows 不使用啟動程式。
- 依使用者決定，MCP 工具移除「一律放行」：每次呼叫都問，只有 y/yes 放行，a/always 視為拒絕；內建工具不變。新增兩個測試（a 被拒絕且不到 server、兩次呼叫問兩次），其中拒絕 a 的測試先確認失敗。完整 pytest 692 passed，spectra validate 與 analyze 無 Critical 與 Warning。
