# 使用 MCP 工具

[回到首頁](../README.md)

互動模式下，agent 可以呼叫本機 [MCP](https://modelcontextprotocol.io) server 提供的工具，例如查 issue 或查文件。**目前只支援 stdio 傳輸**：由 fixlab 啟動本機 server，透過標準輸入／輸出通訊；不支援以 URL 連線的遠端 HTTP server（包含 Streamable HTTP 與 SSE）。需要將官方 SDK 裝進執行 fixlab 的同一個環境；依原本的安裝方式選一種：

```sh
# 原本用 uv tool 安裝：重新安裝並加入 mcp extra
uv tool install --force 'fixlab[mcp] @ git+https://github.com/albertkingdom/fixlab'

# 原本用 pipx 安裝：重新安裝並加入 mcp extra
pipx install --force 'fixlab[mcp] @ git+https://github.com/albertkingdom/fixlab'

# 開發用安裝：在 fixlab 原始碼根目錄執行
.venv/bin/python -m pip install -e '.[mcp]'
```

裝好後，在要修的專案目錄啟動（設定檔內容見下）：

```sh
fixlab --mcp-config servers.json
```

設定檔沿用常見的 `mcpServers` 格式，只支援以 `command` 啟動的本機（stdio）server：

```json
{
  "mcpServers": {
    "docs": {"command": "npx", "args": ["-y", "some-docs-mcp-server"], "env": {"DOCS_TOKEN": "..."}}
  }
}
```

- 工具在模型眼中的名稱是 `mcp__<server>__<tool>`，說明前面標著它來自哪個外部 server。
- **只在互動模式能用，每次呼叫都先問你，MCP 工具沒有「一律放行」**（回答 `a` 視為拒絕，每次都要回答 `y`）；詢問前會印出 server、工具名稱與完整的參數（非 ASCII 字元會跳脫，避免畫面和實際送出的不一樣）。參數長到畫面看不完（超過 4000 字元）的呼叫直接拒絕。一次性模式給了 `--mcp-config` 會直接拒絕，因為沒有人可以確認。
- 呼叫超過 60 秒會被取消；server 回報錯誤、結束或逾時都只讓那次呼叫失敗，不會讓 agent 停下來。
- 結束時最多花 10 秒關閉所有 server；在 macOS 與 Linux 上，不肯結束的 server 最後會被強制結束（SIGKILL），Windows 上只有 SDK 本身的關閉流程。
- 設定檔只從 `--mcp-config` 讀，fixlab 不會自動讀專案或家目錄裡的 MCP 設定：專案可能是還沒讀過的程式碼。
- 事件檔的 `run_start` 記錄 `mcp`：server 名稱、登記與略過的工具、SDK 版本；不記錄指令、參數與環境變數（可能含金鑰）。

**指定 MCP server 等於信任它。** server 是以你的權限執行的程式，**不受 fixlab 的沙箱限制**：它可以讀寫你帳號能碰到的任何檔案、連網，fixlab 的工作目錄限制與測試檔保護都管不到它自己做的事。fixlab 擋得住的只有「模型不經你同意就呼叫它的工具」。只設定你信任的 server。

## 可照做的 stdio 連線範例

下面自己建立一個只回傳固定文字的 server，不需要 Node.js 或額外的服務帳號。先依[首頁](../README.md)安裝 fixlab 並設定模型環境變數，依上方指令加入 `[mcp]` 後，為 server 建立獨立環境：

```sh
mkdir -p "$HOME/fixlab-mcp-demo"
cd "$HOME/fixlab-mcp-demo"
python3 -m venv .venv
.venv/bin/python -m pip install 'mcp>=2.3,<3'
pwd
```

在這個目錄建立 `server.py`，內容如下（使用與 fixlab 相同版本範圍的官方 MCP Python SDK）：

```python
from mcp.server.mcpserver import MCPServer

app = MCPServer("demo")


@app.tool()
def connection_status() -> str:
    """Check the MCP connection before debugging a project."""
    return "MCP connection OK."


if __name__ == "__main__":
    app.run()
```

同一目錄建立 `servers.json`。把下面兩處 `/absolute/path/fixlab-mcp-demo` 都換成剛才 `pwd` 印出的完整路徑；JSON 裡不要用 `~` 或 `$HOME`，它們不會經過 shell 展開：

```json
{
  "mcpServers": {
    "demo": {
      "command": "/absolute/path/fixlab-mcp-demo/.venv/bin/python",
      "args": ["/absolute/path/fixlab-mcp-demo/server.py"]
    }
  }
}
```

切到要修的 Python 專案，再啟動 fixlab（`servers.json` 的完整路徑也要換成自己的）：

```sh
cd /path/to/your-python-project
fixlab --mcp-config /absolute/path/fixlab-mcp-demo/servers.json
```

不必另開終端機執行 `server.py`，fixlab 會啟動及關閉它。在 `fixlab>` 輸入「修復失敗的測試；開始前先呼叫 `mcp__demo__connection_status` 確認 MCP 連線」。模型決定是否呼叫工具；若它選用該工具，確認畫面會顯示 `mcp__demo__connection_status` 與空參數 `{}`，接著詢問 `Allow? [y]es / [N]o:`。輸入 `y` 才會送出呼叫，server 回傳 `MCP connection OK.`；這只確認 MCP 連線，修復結果仍要看測試。

啟動時目前不會列出工具清單。要確認工具已載入，可開啟啟動時 `log:` 顯示的 JSONL 事件檔，在第一筆 `run_start` 的 `mcp.servers` 找到名稱 `demo`，其 `tools` 應包含 `mcp__demo__connection_status`。工具呼叫的確認畫面則表示模型已選用它；被拒絕的呼叫不會送到 server。

`--mcp-config` 的相對路徑以啟動 fixlab 時的目前目錄為準，並非設定檔所在目錄；server 的 `args` 也不會自動以設定檔目錄解析，所以這個範例一律用絕對路徑。若啟動失敗，fixlab 會顯示 server 名稱與錯誤，並在可取得時附上 server stderr 的最後幾行；先檢查 Python、`server.py` 路徑，以及該 Python 環境是否裝好 MCP SDK。
