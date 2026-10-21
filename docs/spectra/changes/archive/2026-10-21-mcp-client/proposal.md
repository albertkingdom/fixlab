## Why

fixlab 的 agent 只有六個內建工具。AGENTS.md 階段 4 的選做項目是 Connector（MCP 或 GitHub issue 二選一）；讓 agent 能呼叫外部 MCP server 提供的工具，可以在不改 agent 迴圈的前提下擴充能力（例如查 issue、查文件），也對應 JD 的「平台 Connector」。

## What Changes

- 新增 `--mcp-config PATH`：讀使用者指定的 JSON 設定檔（`mcpServers` 格式），以 stdio 啟動列出的本機 MCP server，把它們的工具登記成 agent 的工具。不讀專案資料夾裡的設定檔：專案可能不可信。
- 使用官方 Python SDK `mcp`（2.x），做成選用安裝 `fixlab[mcp]`，不裝的人不受影響；沒裝卻給了 `--mcp-config` 時以結束碼 2 結束並說明怎麼安裝。
- MCP 工具名稱加前綴 `mcp__<server>__<tool>`，避免和內建工具同名；工具說明標明是外部工具。
- 只在互動模式開放：每次呼叫 MCP 工具都先問使用者（可選「這個工具一律放行」）。一次性模式沒有人可以確認，給了 `--mcp-config` 就以結束碼 2 結束。這是 AGENTS.md「要加任意外部能力須先有白名單與確認機制」的白名單（設定檔明列的 server）與確認。
- 工具結果取文字內容，非文字內容以一行說明代替，超過長度上限時截斷；server 回報錯誤或逾時時 ok=false，不讓迴圈中斷。
- 啟動時連不上 server、初始化或列出工具失敗、逾時，以結束碼 2 結束，不建立事件檔、不呼叫模型。
- `run_start` 記錄 MCP 設定的摘要（server 名稱、工具名稱、略過的工具與 SDK 版本），不記錄指令參數與環境變數值（可能含金鑰）。
- benchmark 執行器不需修改：它本來就不會傳 `--mcp-config`，實驗條件不變。
- README（給外部讀者）說明用法、信任模型（server 是以使用者權限執行、不受 fixlab 沙箱限制的程式，指定等於信任）與限制。

## Non-Goals

- 不支援遠端 MCP server（HTTP、SSE）、OAuth 驗證。
- 不支援 MCP 的 resources、prompts、sampling、elicitation，只用 tools。
- 不把 MCP server 放進 fixlab 的沙箱；不限制 server 自己能讀寫什麼。
- 不讓 fixlab 當 MCP server。
- 不自動讀取專案或家目錄裡的 MCP 設定檔。
- 不在 benchmark 或實驗中使用 MCP 工具。

## Capabilities

### New Capabilities

- `mcp-tools`: 以 stdio 連接使用者設定的 MCP server，把工具登記給 agent、在互動模式下逐次確認、轉換結果，以及啟動與關閉的錯誤處理。

### Modified Capabilities

- `run-telemetry`: run_start 記錄 MCP 設定摘要。

## Impact

- Affected specs: mcp-tools（新增）、run-telemetry
- Affected code:
  - New: fixlab/mcp_tools.py, tests/test_mcp_tools.py, tests/mcp_echo_server.py
  - Modified: fixlab/cli.py, fixlab/workspace.py, fixlab/display.py, pyproject.toml, README.md, tests/test_interactive.py, tests/test_packaging.py
