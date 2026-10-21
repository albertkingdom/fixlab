"""測試用的 MCP server（stdio）：tests/test_mcp_tools.py 與 tests/test_cli.py 啟動它。用官方 SDK 的 MCPServer 寫成。
每個工具對應一種要測的情況。收到的呼叫依序寫進環境變數 ECHO_CALLS 指定的檔案，測試用它確認「某個呼叫沒有送到 server」。"""

import asyncio
import os
import sys

from mcp.server.mcpserver import Image, MCPServer
from mcp import MCPError
from mcp.types import CONNECTION_CLOSED, CallToolResult

app = MCPServer("echo")


def record(name: str) -> None:
    path = os.environ.get("ECHO_CALLS")
    if path:
        with open(path, "a", encoding="utf-8") as file:
            file.write(name + "\n")


@app.tool()
def shout(text: str) -> str:
    """Return the text in upper case."""
    record("shout")
    return text.upper()


@app.tool()
def fail() -> str:
    """Always fail."""
    record("fail")
    raise ValueError("something went wrong on the server")


@app.tool()
def picture() -> list:
    """Return a picture and a caption."""
    record("picture")
    return ["a caption", Image(data=b"\x89PNG\r\n\x1a\n", format="png")]


@app.tool()
def answer() -> CallToolResult:
    """Return only structured content."""
    record("answer")
    return CallToolResult(content=[], structured_content={"answer": 42})


@app.tool()
def long(size: int) -> str:
    """Return a long text."""
    record("long")
    return "x" * size


@app.tool()
async def slow(seconds: float) -> str:
    """Sleep, then answer."""
    record("slow-start")
    await asyncio.sleep(seconds)
    record("slow-end")
    return "done"


@app.tool()
def upstream() -> str:
    """Fail with an error from the server that only looks like a closed connection."""
    record("upstream")
    raise MCPError(CONNECTION_CLOSED, "Connection closed by upstream database")


@app.tool()
def quit() -> str:
    """Stop the server process."""
    record("quit")
    os._exit(0)


if __name__ == "__main__":
    if os.environ.get("ECHO_STUBBORN"):  # 模擬不肯結束的 server：不理 SIGTERM，stdin 關閉後也繼續活著
        import atexit
        import signal
        import time
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        atexit.register(time.sleep, 120)
    if os.environ.get("ECHO_PID"):  # 測試用它確認結束後沒有殘留的行程
        with open(os.environ["ECHO_PID"], "a", encoding="utf-8") as file:
            file.write(f"{os.getpid()}\n")
    print("echo server starting", file=sys.stderr)
    app.run()
