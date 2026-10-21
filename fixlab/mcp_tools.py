"""呼叫外部 MCP server 提供的工具（--mcp-config）。

只支援本機 stdio server：fixlab 照使用者指定的設定檔啟動它們，把它們的工具登記成 agent 的工具，
名稱是 mcp__<server>__<tool>。設定只從使用者指定的檔案讀，不讀專案或家目錄裡的設定：專案可能不可信。

MCP server 是以使用者權限執行的程式，不受 fixlab 的沙箱限制；指定它就代表信任它。
所以 MCP 工具只在互動模式開放，每次呼叫都先問使用者（見 cli.make_asker）。

官方 SDK（mcp）是選用安裝，只有真的要連 server 時才匯入。
"""

import json
import os
import re
from pathlib import Path

SERVER_NAME = re.compile(r"[A-Za-z0-9_-]+")
SERVER_KEYS = {"command", "args", "env", "cwd"}


def load_config(path: str) -> dict[str, dict]:
    """讀 --mcp-config 的設定檔，回傳 {server 名稱: {command, args, env, cwd}}。不合法就丟出 ValueError（訊息給使用者看）。
    格式沿用常見的 {"mcpServers": {名稱: {"command": ..., "args": [...], "env": {...}, "cwd": ...}}}。"""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"cannot read the MCP configuration {path}: {error}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"the MCP configuration {path} is not valid JSON: {error}") from None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise ValueError(f"the MCP configuration {path} needs an object named mcpServers")
    return {name: check_server(name, entry) for name, entry in servers.items()}


def check_server(name: str, entry) -> dict:
    if not SERVER_NAME.fullmatch(name):
        raise ValueError(f"MCP server name {name!r} may only contain letters, digits, _ and -")
    if not isinstance(entry, dict):
        raise ValueError(f"MCP server {name!r} must be an object with a command")
    if "url" in entry:
        raise ValueError(f"MCP server {name!r}: only stdio servers with a command are supported, not url")
    unknown = sorted(set(entry) - SERVER_KEYS)
    if unknown:
        raise ValueError(f"MCP server {name!r} has unknown keys: {', '.join(unknown)}")
    command = entry.get("command")
    if not isinstance(command, str) or not command:
        raise ValueError(f"MCP server {name!r} needs a command (a non-empty string)")
    args = entry.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError(f"MCP server {name!r}: args must be a list of strings")
    env = entry.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError(f"MCP server {name!r}: env must be an object of strings")
    cwd = entry.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        raise ValueError(f"MCP server {name!r}: cwd must be a string")
    return {"command": command, "args": list(args), "env": dict(env), "cwd": cwd}


START_TIMEOUT_S = 30   # 啟動、初始化、列出工具，每一步的上限
CALL_TIMEOUT_S = 60    # 每次工具呼叫的上限
PING_TIMEOUT_S = 3     # 收到「連線關閉」時，確認 server 是否還在的上限
# 關閉時，SDK 自己的停止流程是：關 stdin、等它退出、SIGTERM、再等、SIGKILL（約 6.5 秒）。正常關閉要等得比它久
# （總時限 10 秒時是 8 秒）；最後這 2 秒還沒結束的，直接 SIGKILL 它的行程群組。不原生取消 task：那會打斷 SDK 的收尾，
# 讓 task 卡住、不肯結束的 server 殘留。
FORCE_CLOSE_S = 2

# server 經過這段小程式啟動：先把自己的 pid 寫進檔案（寫完再改名，讀的人不會看到一半），再 exec 成真正的指令。
# exec 不改 pid，所以 fixlab 拿得到 server 的 pid；SDK 本身不公開它。SDK 以新的 session 啟動子行程，pid 也就是行程群組。
# Python 啟動時把 SIGPIPE、SIGXFSZ 設成忽略，被忽略的訊號會延續到 exec 之後，所以先還原。環境變數、目前目錄與 PATH 查找
# 都由 SDK 照設定傳入。指令執行不了時只印一行原因（不要 traceback），以結束碼 127 結束，和 shell 一樣。
# 只在 POSIX 系統使用；Windows 沒有 exec 與行程群組，直接交給 SDK 啟動，強制結束的那一步也就不做。
LAUNCHER = ("import os, signal, sys\n"
            "path = sys.argv[1]\n"
            "with open(path + '.tmp', 'w') as file:\n"
            "    file.write(str(os.getpid()))\n"
            "os.replace(path + '.tmp', path)\n"
            "for name in ('SIGPIPE', 'SIGXFSZ'):\n"
            "    if hasattr(signal, name):\n"
            "        signal.signal(getattr(signal, name), signal.SIG_DFL)\n"
            "try:\n"
            "    os.execvp(sys.argv[2], sys.argv[2:])\n"
            "except OSError as error:\n"
            "    print(f'cannot run {sys.argv[2]}: {error.strerror}', file=sys.stderr)\n"
            "    sys.exit(127)\n")
MAX_RESULT_CHARS = 8000  # 結果超過就保留頭尾各一半
STDERR_TAIL_LINES = 5  # 啟動失敗時附上 server stderr 的最後幾行


def import_sdk():
    """匯入官方 SDK；沒裝就丟出 ValueError，告訴使用者怎麼裝。只有真的要連 server 時才呼叫。"""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.types import PaginatedRequestParams
    except ImportError:
        raise ValueError("--mcp-config needs the MCP SDK: install it with  pip install 'fixlab[mcp]'") from None
    return ClientSession, StdioServerParameters, stdio_client, PaginatedRequestParams


class McpServer:
    """一個以 stdio 連線的 MCP server，給同步的 fixlab 用。

    SDK 是非同步的（anyio），而且連線的開啟與關閉必須在同一個 task 裡：所以每個 server 一條背景執行緒、
    一個事件迴圈，由一個長時間執行的 task 開啟連線、處理佇列送來的請求、收到結束訊號後在同一個 task 關閉。
    同步端用 concurrent.futures.Future 等結果。"""

    def __init__(self, name: str, entry: dict):
        import asyncio
        import concurrent.futures
        import tempfile
        import threading

        self.name = name
        self.tools = []
        self._sdk = import_sdk()
        # 私有暫存目錄：server 的 stderr（不印到終端機，免得和互動提示混在一起）與 pid 檔，結束時刪除
        self._private = Path(tempfile.mkdtemp(prefix=f"fixlab-mcp-{name}-"))
        self.errlog_path = str(self._private / "stderr.log")
        self._pid_path = self._private / "pid"
        self._errlog = open(self.errlog_path, "w+", encoding="utf-8", errors="replace")
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name=f"mcp-{name}", daemon=True)
        self._thread.start()
        self._ready = concurrent.futures.Future()
        self._queue = None
        self._current = None  # 正在執行的呼叫（asyncio.Task），中斷時取消它
        self._gone = False  # server 的行程已經結束（連線被關閉）
        self._closing = None  # asyncio.Event：要求關閉。啟動中的 server 收到它就停止等待，正常離開連線讓 SDK 結束子行程
        self._task = asyncio.run_coroutine_threadsafe(self._serve(entry), self._loop)

    def wait_ready(self) -> None:
        """等連線、初始化與列出工具完成。失敗或逾時丟出 ValueError，訊息附上 stderr 的最後幾行。"""
        import concurrent.futures
        try:
            self._ready.result(START_TIMEOUT_S * 3)
        except concurrent.futures.TimeoutError:
            raise ValueError(self._failure("did not start in time")) from None
        except Exception as error:  # noqa: BLE001 — SDK 與子行程的錯誤種類很多，一律轉成訊息
            raise ValueError(self._failure(describe(error))) from None

    def _failure(self, what: str) -> str:
        self._errlog.flush()
        tail = Path(self.errlog_path).read_text(encoding="utf-8", errors="replace").strip().splitlines()[-STDERR_TAIL_LINES:]
        detail = ("; its stderr ended with: " + " | ".join(tail)) if tail else ""
        return f"MCP server {self.name!r} {what}{detail}"

    async def _serve(self, entry: dict) -> None:
        import asyncio
        ClientSession, StdioServerParameters, stdio_client, PaginatedRequestParams = self._sdk
        import sys
        if os.name == "posix":
            command, args = sys.executable, ["-I", "-S", "-c", LAUNCHER, str(self._pid_path), entry["command"], *entry["args"]]
        else:
            command, args = entry["command"], entry["args"]
        params = StdioServerParameters(command=command, args=args, env=entry["env"] or None, cwd=entry["cwd"])
        self._queue = asyncio.Queue()
        self._closing = asyncio.Event()
        try:
            async with stdio_client(params, errlog=self._errlog) as (read, write), \
                    ClientSession(read, write) as session:
                await self._starting(session.initialize())
                tools, cursor = [], None
                while True:  # 工具清單可能分頁
                    page = await self._starting(
                        session.list_tools(params=PaginatedRequestParams(cursor=cursor) if cursor else None))
                    tools += page.tools
                    cursor = page.next_cursor
                    if not cursor:
                        break
                self.tools = tools
                self._ready.set_result(True)
                await self._handle_requests(session)
        except BaseException as error:
            if not self._ready.done():
                self._ready.set_exception(error if isinstance(error, Exception) else RuntimeError("cancelled"))
            if not isinstance(error, (Exception, asyncio.CancelledError)):
                raise

    async def _starting(self, coroutine):
        """啟動中的一步：最多等 START_TIMEOUT_S 秒，期間要求關閉就取消這一步並丟出 ClosingWhileStarting。
        例外會讓 async with 正常離開，SDK 照自己的流程結束子行程；不取消整個 task，免得打斷那個流程。"""
        import asyncio
        step = asyncio.ensure_future(coroutine)
        closing = asyncio.ensure_future(self._closing.wait())
        try:
            done, _ = await asyncio.wait({step, closing}, timeout=START_TIMEOUT_S, return_when=asyncio.FIRST_COMPLETED)
        finally:
            closing.cancel()
        if step in done:
            return step.result()
        step.cancel()
        try:
            await step
        except BaseException:  # noqa: BLE001 — 被取消或失敗都無所謂，接下來就要離開了
            pass
        if self._closing.is_set():
            raise ClosingWhileStarting()
        raise TimeoutError(f"no answer within {START_TIMEOUT_S}s")

    async def _handle_requests(self, session) -> None:
        import asyncio
        import time
        while True:
            job = await self._queue.get()
            if job is None:
                return
            make, future, deadline = job
            remaining = deadline - time.monotonic()
            if remaining <= 0 or future.done():  # 已經逾時或被放棄的請求：不送到 server
                if not future.done():
                    future.set_exception(TimeoutError())
                continue
            self._current = asyncio.ensure_future(make(session))
            try:
                future.set_result(await asyncio.wait_for(self._current, remaining))
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():  # 是整個 server 要關閉，不是這個呼叫被取消
                    raise
                if not future.done():
                    future.set_exception(TimeoutError())
            except Exception as error:  # noqa: BLE001 — 轉交給同步端，變成 ok=false 的結果
                if not future.done():
                    future.set_exception(error)
            finally:
                self._current = None

    def request(self, make, timeout: float):
        """把 make(session) 交給背景的 task 執行，等結果。逾時丟出 TimeoutError；server 已結束丟出 ConnectionError。"""
        import concurrent.futures
        import time
        if self._task.done() or self._gone:
            raise ConnectionError(f"MCP server {self.name!r} is not available (it has exited)")
        future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (make, future, time.monotonic() + timeout))
        try:
            return future.result(timeout + 1)
        except concurrent.futures.TimeoutError:
            future.cancel()
            self._cancel_current()
            raise TimeoutError() from None
        except KeyboardInterrupt:  # 使用者按 Ctrl-C：取消進行中的呼叫再往上丟，讓互動模式照常處理
            future.cancel()
            self._cancel_current()
            raise

    def _cancel_current(self) -> None:
        current = self._current
        if current is not None:
            self._loop.call_soon_threadsafe(current.cancel)

    def call(self, tool: str, args: dict):
        """呼叫一個工具，回傳 ToolResult。任何錯誤都變成 ok=false，不往外丟（Ctrl-C 除外）。"""
        from fixlab.workspace import ToolResult
        try:
            result = self.request(lambda session: session.call_tool(tool, args), CALL_TIMEOUT_S)
        except TimeoutError:
            return ToolResult(f"error: the MCP tool {tool!r} on server {self.name!r} did not answer within "
                              f"{CALL_TIMEOUT_S}s and was cancelled", False, {"timed_out": True})
        except Exception as error:  # noqa: BLE001
            if self._connection_lost(error):  # server 的行程結束了，之後的呼叫直接拒絕
                self._gone = True
                return ToolResult(f"error: MCP server {self.name!r} is not available (it has exited)", False)
            return ToolResult(f"error: MCP server {self.name!r}: {describe(error)}", False)
        return ToolResult(result_text(result), not result.is_error)

    def _connection_lost(self, error: Exception) -> bool:
        """SDK 用代碼 CONNECTION_CLOSED（-32000）回報連線關閉，但這也是 server 自己回錯誤時常用的代碼：
        所以再 ping 一次，ping 不通才算 server 真的結束了。"""
        from mcp import MCPError
        from mcp.types import CONNECTION_CLOSED
        if not isinstance(error, MCPError) or error.code != CONNECTION_CLOSED:
            return False
        try:
            self.request(lambda session: session.send_ping(), PING_TIMEOUT_S)
        except Exception:  # noqa: BLE001 — ping 不通：連線真的斷了
            return True
        return False

    def begin_close(self) -> None:
        """送出結束訊號並取消進行中的呼叫；佇列裡還沒執行的請求會被丟棄（結束訊號排在它們前面）。
        還在啟動中的 server 不會讀佇列：通知它停止等待，讓它正常離開連線，SDK 照自己的流程結束子行程。"""
        self._cancel_current()
        if not self._ready.done():
            self._loop.call_soon_threadsafe(self._stop_starting)
            return

        def stop():
            if self._queue is not None:
                while not self._queue.empty():
                    job = self._queue.get_nowait()
                    if job is not None and not job[1].done():
                        job[1].set_exception(ConnectionError("fixlab is closing the MCP servers"))
                self._queue.put_nowait(None)
            else:
                self._task_cancel()
        self._loop.call_soon_threadsafe(stop)

    def task_done(self) -> bool:
        return self._task.done()

    def _stop_starting(self) -> None:
        if self._closing is None:  # 背景 task 還沒開始跑：還沒有子行程，直接取消即可
            self._task_cancel()
            return
        self._closing.set()
        # 主執行緒判斷「還在啟動中」之後，啟動可能剛好完成、已經在等佇列：結束訊號也放進佇列，兩種情況都收得到
        self._queue.put_nowait(None)

    def _task_cancel(self) -> None:
        import asyncio
        for task in asyncio.all_tasks(self._loop):
            task.cancel()

    def wait_closed(self, deadline: float) -> bool:
        """等背景 task 結束，最多等到 deadline（time.monotonic()）。回傳是否已經結束。
        Ctrl-C 不在這裡吞掉，交給 close_all 處理。"""
        import concurrent.futures
        import time
        try:
            self._task.result(max(deadline - time.monotonic(), 0))
        except concurrent.futures.TimeoutError:
            return False
        except Exception:  # noqa: BLE001 — 被取消（concurrent.futures.CancelledError 也是 Exception）或出錯都算結束了
            pass
        return True

    def kill(self) -> None:
        """直接結束 server 的行程群組。不取消背景 task：原生取消會打斷 SDK 的收尾，讓 task 卡住；
        行程結束後 SDK 讀到輸出結束，task 自己就會跑完。"""
        import signal
        if self._gone or not hasattr(os, "killpg"):  # 已經結束的 server，pid 可能被別的行程重用：不送訊號
            return
        try:
            pid = int(self._pid_path.read_text())
        except (OSError, ValueError):  # 還沒寫出 pid：行程可能還沒啟動，或啟動程式已經失敗結束
            return
        try:
            os.killpg(pid, signal.SIGKILL)  # 行程群組不存在就表示它已經結束；不退而對單一 pid 送訊號
        except (ProcessLookupError, PermissionError):
            pass

    def finish_close(self, deadline: float) -> None:
        """停止事件迴圈、刪除私有暫存目錄。等事件迴圈結束最多到 deadline。"""
        import shutil
        import time
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(max(deadline - time.monotonic(), 0))
        self._errlog.close()
        shutil.rmtree(self._private, ignore_errors=True)


def result_text(result) -> str:
    """工具結果轉成給模型看的文字：文字區塊以換行串接，其他區塊（圖片、音訊、資源）換成一行說明；
    沒有文字但有結構化內容時回傳它的 JSON。太長就從中間截斷。"""
    from fixlab.tools import clip_middle
    lines = [block.text if block.type == "text" else f"[{block.type} content omitted]" for block in result.content]
    if not any(block.type == "text" for block in result.content) and result.structured_content is not None:
        lines.append(json.dumps(result.structured_content, ensure_ascii=False))
    return clip_middle("\n".join(lines), MAX_RESULT_CHARS)


class ClosingWhileStarting(Exception):
    """啟動中被要求關閉。"""


def describe(error: BaseException) -> str:
    """例外的一行說明。SDK 有時把多個錯誤包成 ExceptionGroup，取第一個真正的原因。"""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    text = str(error).strip()
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


def start_servers(config: dict[str, dict]) -> list[McpServer]:
    """啟動設定檔裡的每個 server，等它們都準備好。任何一個失敗就關閉全部、丟出 ValueError（訊息含 server 名稱）。"""
    servers = []
    try:
        for name, entry in config.items():
            server = McpServer(name, entry)
            servers.append(server)
            server.wait_ready()
    except BaseException:
        close_all(servers)
        raise
    return servers


def close_all(servers: list[McpServer], timeout: float = 10) -> None:
    """關閉所有 server，全部共用一個時限（timeout 秒）：先送出結束訊號，讓 SDK 照自己的流程結束子行程；
    最後 FORCE_CLOSE_S 秒還沒結束的，直接結束它的行程群組。過程中按 Ctrl-C 也不會跳過任何 server：
    直接進入強制結束，全部收尾完才把 Ctrl-C 往上丟。"""
    import time
    deadline = time.monotonic() + timeout
    interrupted = False
    def each(step) -> None:  # 每個 server 都做到，中途按 Ctrl-C 也不跳過後面的 server
        nonlocal interrupted
        for server in servers:
            try:
                step(server)
            except KeyboardInterrupt:
                interrupted = True

    each(lambda server: server.begin_close())
    each(lambda server: interrupted or server.wait_closed(deadline - FORCE_CLOSE_S))
    each(lambda server: server.task_done() or server.kill())
    each(lambda server: server.wait_closed(deadline))  # 強制結束後也要等 SDK 回收行程，否則留下 zombie
    each(lambda server: server.finish_close(deadline))
    if interrupted:
        raise KeyboardInterrupt


TOOL_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")  # OpenAI function 名稱的限制


def register_mcp_tools(ws, servers) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """把每個 server 的工具登記到 ws，名稱是 mcp__<server>__<tool>。回傳 ({server: 登記的名稱}, {server: 略過的名稱})，
    並在 ws.external_tools 記下每個名稱的來源（server 名稱可能含 _，不能從組合後的名稱反推）。
    名稱不合格或 schema 不是 object 的略過並警告；兩個工具組出同一個名稱就丟出 ValueError，
    否則後登記的會默默蓋掉先登記的。"""
    import sys
    registered, skipped, owners = {}, {}, {}
    for server in servers:
        registered[server.name], skipped[server.name] = [], []
        for tool in server.tools:
            combined = f"mcp__{server.name}__{tool.name}"
            if combined in owners:
                raise ValueError(f"two MCP tools would both be named {combined}: {owners[combined]} and "
                                 f"tool {tool.name!r} of server {server.name!r}; rename one of the servers")
            owners[combined] = f"tool {tool.name!r} of server {server.name!r}"
            schema = tool.input_schema
            if not TOOL_NAME.fullmatch(combined) or not isinstance(schema, dict) or schema.get("type", "object") != "object":
                print(f"warning: skipping MCP tool {combined}: its name must match [A-Za-z0-9_-]{{1,64}} "
                      "and its input schema must be an object", file=sys.stderr)
                skipped[server.name].append(combined)
                continue
            description = f"[external tool from MCP server {server.name}] {tool.description or ''}".strip()
            ws.register(combined, make_caller(server, tool.name), schema, description, loose_args=True)
            ws.external_tools[combined] = (server.name, tool.name)
            registered[server.name].append(combined)
    return registered, skipped


def make_caller(server, tool: str):
    """Workspace 用關鍵字參數呼叫工具；MCP 的參數名稱不一定是合法的 Python 名稱，所以收成 dict 再轉交。"""
    return lambda **args: server.call(tool, args)
