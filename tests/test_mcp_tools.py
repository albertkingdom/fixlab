# 呼叫外部 MCP server 的工具（fixlab/mcp_tools.py）。設定檔的檢查不需要 SDK；
# 連線的測試用 tests/mcp_echo_server.py，沒裝 mcp extra 時略過。

import json

import pytest

from fixlab.mcp_tools import load_config


def write_config(tmp_path, data) -> str:
    path = tmp_path / "servers.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return str(path)


# ── MCP servers come only from a file the user names ──────────────────────


def test_a_valid_configuration_is_loaded(tmp_path):
    path = write_config(tmp_path, {"mcpServers": {"echo": {"command": "python", "args": ["s.py"],
                                                         "env": {"A": "1"}, "cwd": "/tmp"}}})
    assert load_config(path) == {"echo": {"command": "python", "args": ["s.py"], "env": {"A": "1"}, "cwd": "/tmp"}}


def test_optional_keys_get_defaults(tmp_path):
    path = write_config(tmp_path, {"mcpServers": {"echo": {"command": "python"}}})
    assert load_config(path) == {"echo": {"command": "python", "args": [], "env": {}, "cwd": None}}


@pytest.mark.parametrize("data, words", [
    ("{not json", "not valid JSON"),
    ({"servers": {}}, "mcpServers"),
    ({"mcpServers": []}, "mcpServers"),
    ({"mcpServers": {"echo": {"args": []}}}, "command"),
    ({"mcpServers": {"echo": {"url": "https://example.com/mcp"}}}, "only stdio"),
    ({"mcpServers": {"echo": {"command": "python", "extra": 1}}}, "extra"),
    ({"mcpServers": {"echo": {"command": "python", "args": "s.py"}}}, "args"),
    ({"mcpServers": {"echo": {"command": "python", "env": {"A": 1}}}}, "env"),
    ({"mcpServers": {"echo": {"command": "python", "cwd": 3}}}, "cwd"),
    ({"mcpServers": {"bad name": {"command": "python"}}}, "server name"),
    ({"mcpServers": {"echo": "python"}}, "echo"),
])
def test_invalid_configurations_are_refused(tmp_path, data, words):
    with pytest.raises(ValueError, match=words):
        load_config(write_config(tmp_path, data))


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(ValueError, match="cannot read"):
        load_config(str(tmp_path / "missing.json"))


# ── 連線：需要 mcp extra ─────────────────────────────────────────────────

import os
import sys
import time
from pathlib import Path

mcp = pytest.importorskip("mcp", reason="the mcp extra is not installed")

from fixlab import mcp_tools  # noqa: E402
from fixlab.mcp_tools import close_all, start_servers  # noqa: E402

ECHO = str(Path(__file__).with_name("mcp_echo_server.py"))


@pytest.fixture
def echo_env(tmp_path):
    """測試用 server 的環境變數：記錄收到的呼叫與行程編號。"""
    return {"ECHO_CALLS": str(tmp_path / "calls.txt"), "ECHO_PID": str(tmp_path / "pids.txt")}


def echo_config(env, name="echo"):
    return {name: {"command": sys.executable, "args": [ECHO], "env": env, "cwd": None}}


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def pids(env):
    return [int(line) for line in Path(env["ECHO_PID"]).read_text().split()]


def calls(env):
    path = Path(env["ECHO_CALLS"])
    return path.read_text().split() if path.exists() else []


@pytest.fixture
def echo(echo_env):
    servers = start_servers(echo_config(echo_env))
    yield servers[0]
    close_all(servers)


# Scenario: Valid configuration（啟動並列出工具）
def test_a_server_starts_and_lists_its_tools(echo):
    assert echo.name == "echo"
    assert [tool.name for tool in echo.tools][:3] == ["shout", "fail", "picture"]


# Scenario: Server command not found
def test_a_server_that_cannot_start_is_named(tmp_path):
    config = {"broken": {"command": str(tmp_path / "no-such-command"), "args": [], "env": {}, "cwd": None}}
    with pytest.raises(ValueError, match="broken"):
        start_servers(config)


def test_a_server_that_exits_at_once_shows_its_stderr(tmp_path):
    script = tmp_path / "dies.py"
    script.write_text("import sys\nprint('cannot find the token', file=sys.stderr)\nsys.exit(1)\n")
    config = {"dies": {"command": sys.executable, "args": [str(script)], "env": {}, "cwd": None}}
    with pytest.raises(ValueError, match="cannot find the token"):
        start_servers(config)


def test_when_one_server_fails_the_started_ones_are_closed(tmp_path, echo_env):
    config = {**echo_config(echo_env),
              "broken": {"command": str(tmp_path / "no-such-command"), "args": [], "env": {}, "cwd": None}}
    with pytest.raises(ValueError, match="broken"):
        start_servers(config)
    deadline = time.monotonic() + 5
    while any(alive(pid) for pid in pids(echo_env)) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not any(alive(pid) for pid in pids(echo_env))


# Scenario: Clean exit
def test_closing_leaves_no_process_and_no_stderr_file(echo_env):
    servers = start_servers(echo_config(echo_env))
    errlog = Path(servers[0].errlog_path)
    assert "echo server starting" in errlog.read_text()
    close_all(servers)
    assert not any(alive(pid) for pid in pids(echo_env))
    assert not errlog.exists()


# Scenario: Exit while a call is stuck
def test_closing_with_a_stuck_call_finishes_in_time(echo_env, monkeypatch):
    import threading
    servers = start_servers(echo_config(echo_env))
    stuck = threading.Thread(target=servers[0].call, args=("slow", {"seconds": 120}), daemon=True)
    stuck.start()
    deadline = time.monotonic() + 5
    while "slow-start" not in calls(echo_env) and time.monotonic() < deadline:
        time.sleep(0.05)
    started = time.monotonic()
    close_all(servers, timeout=10)
    assert time.monotonic() - started < 10
    assert not any(alive(pid) for pid in pids(echo_env))


# ── MCP tools join the tool list with a prefix（用假的 server，不啟動行程）──────

from types import SimpleNamespace  # noqa: E402

from fixlab.mcp_tools import register_mcp_tools  # noqa: E402
from fixlab.workspace import ToolResult, Workspace  # noqa: E402


class FakeServer:
    def __init__(self, name, tools):
        self.name = name
        self.tools = [SimpleNamespace(name=tool, description=f"does {tool}", input_schema=schema)
                      for tool, schema in tools.items()]
        self.received = []

    def call(self, tool, args):
        self.received.append((tool, args))
        return ToolResult("ok", True)


def test_tools_are_registered_with_a_prefix_and_marked_external(tmp_path):
    ws = Workspace(tmp_path)
    server = FakeServer("echo", {"shout": {"type": "object", "properties": {"text": {"type": "string"}}}})
    registered, skipped = register_mcp_tools(ws, [server])
    assert registered == {"echo": ["mcp__echo__shout"]} and skipped == {"echo": []}
    spec = next(s for s in ws.tool_specs() if s["function"]["name"] == "mcp__echo__shout")
    assert spec["function"]["description"].startswith("[external tool from MCP server echo]")
    assert spec["function"]["parameters"]["properties"] == {"text": {"type": "string"}}
    assert ws.call("mcp__echo__shout", {"text": "hi"}).ok
    assert server.received == [("shout", {"text": "hi"})]


def test_bad_names_and_schemas_are_skipped_with_a_warning(tmp_path, capsys):
    ws = Workspace(tmp_path)
    server = FakeServer("echo", {"x" * 60: {"type": "object"}, "has space": {"type": "object"},
                                 "listy": {"type": "array"}, "fine": {"type": "object"}})
    registered, skipped = register_mcp_tools(ws, [server])
    assert registered == {"echo": ["mcp__echo__fine"]}
    assert sorted(skipped["echo"]) == sorted([f"mcp__echo__{'x' * 60}", "mcp__echo__has space", "mcp__echo__listy"])
    assert "x" * 60 in capsys.readouterr().err


def test_two_tools_with_the_same_combined_name_are_refused(tmp_path):
    ws = Workspace(tmp_path)
    one, two = FakeServer("a__b", {"c": {"type": "object"}}), FakeServer("a", {"b__c": {"type": "object"}})
    with pytest.raises(ValueError, match="mcp__a__b__c"):
        register_mcp_tools(ws, [one, two])


# Scenario: Schemas the simple check does not understand
@pytest.mark.parametrize("schema, args, reaches", [
    ({"type": "object", "properties": {"x": {"type": ["string", "null"]}}}, {"x": "a"}, True),
    ({"type": "object", "properties": {"x": True}}, {"x": 1}, True),
    ({"type": "object", "patternProperties": {"^y": {}}, "additionalProperties": False}, {"y1": 1}, True),
    ({"type": "object", "required": ["x"]}, {}, False),
])
def test_only_required_arguments_are_checked(tmp_path, schema, args, reaches):
    ws = Workspace(tmp_path)
    server = FakeServer("s", {"t": schema})
    register_mcp_tools(ws, [server])
    result = ws.call("mcp__s__t", args)
    assert result.ok == reaches and (server.received == [("t", args)]) == reaches
    if not reaches:
        assert "missing" in result.output


# ── MCP results are text, bounded, and never crash the loop（真的 server）────────


def test_a_text_result(echo):
    result = echo.call("shout", {"text": "hi"})
    assert result.ok and result.output == "HI"


def test_other_content_is_named_in_one_line(echo):
    result = echo.call("picture", {})
    assert result.ok and result.output == "a caption\n[image content omitted]"


# Scenario: Structured result only
def test_structured_content_is_returned_as_json(echo):
    result = echo.call("answer", {})
    assert result.ok and json.loads(result.output) == {"answer": 42}


def test_a_long_result_is_cut_in_the_middle(echo):
    result = echo.call("long", {"size": 9000})
    assert result.ok and len(result.output) < 8200
    assert result.output.startswith("x" * 4000) and result.output.endswith("x" * 4000)
    assert "9000" in result.output  # 截斷說明寫出原本的長度


# Scenario: Server error
def test_a_server_error_is_not_ok(echo):
    result = echo.call("fail", {})
    assert not result.ok and "fail" in result.output


# Scenario: Call that times out
def test_a_call_that_times_out_is_cancelled_and_the_server_still_answers(echo, echo_env, monkeypatch):
    monkeypatch.setattr(mcp_tools, "CALL_TIMEOUT_S", 1)
    result = echo.call("slow", {"seconds": 30})
    assert not result.ok and result.flags.get("timed_out")
    after = echo.call("shout", {"text": "again"})
    assert after.ok and after.output == "AGAIN"
    time.sleep(0.5)
    assert calls(echo_env).count("slow-start") == 1 and "slow-end" not in calls(echo_env)


# Scenario: Server exits during the session
def test_a_server_that_exited_is_reported(echo):
    echo.call("quit", {})
    deadline = time.monotonic() + 5
    result = echo.call("shout", {"text": "hi"})
    while result.ok and time.monotonic() < deadline:
        result = echo.call("shout", {"text": "hi"})
    assert not result.ok and "not available" in result.output


# ── code review 修正（與 Codex 討論後只修必要的）─────────────────────────────


def test_a_server_error_that_mentions_a_closed_connection_does_not_disable_the_server(echo):
    result = echo.call("upstream", {})
    assert not result.ok and "upstream database" in result.output
    after = echo.call("shout", {"text": "still here"})
    assert after.ok and after.output == "STILL HERE"


def test_closing_a_server_that_is_still_starting_leaves_no_process(tmp_path):
    # 一個永遠不回應初始化的 server：關閉時它還在啟動中。
    pid_file = tmp_path / "pid"
    script = tmp_path / "hangs.py"
    script.write_text("import os, signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"  # 連 SIGTERM 都不理
                      f"open({str(pid_file)!r}, 'w').write(str(os.getpid()))\ntime.sleep(120)\n")
    server = mcp_tools.McpServer("hangs", {"command": sys.executable, "args": [str(script)], "env": {}, "cwd": None})
    deadline = time.monotonic() + 5
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    started = time.monotonic()
    close_all([server], timeout=10)
    assert time.monotonic() - started < 10.5
    assert not alive(int(pid_file.read_text()))


def test_registration_reports_tools_per_server(tmp_path):
    ws = Workspace(tmp_path)
    a, a_ = FakeServer("a", {"x": {"type": "object"}}), FakeServer("a_", {"x": {"type": "object"}})
    registered, skipped = register_mcp_tools(ws, [a, a_])
    assert registered == {"a": ["mcp__a__x"], "a_": ["mcp__a___x"]} and skipped == {"a": [], "a_": []}
    assert ws.external_tools["mcp__a___x"] == ("a_", "x")


def test_a_server_that_ignores_sigterm_is_killed_on_close(echo_env):
    servers = start_servers(echo_config({**echo_env, "ECHO_STUBBORN": "1"}))
    started = time.monotonic()
    close_all(servers, timeout=10)
    assert time.monotonic() - started < 10.5
    deadline = time.monotonic() + 3
    while any(alive(pid) for pid in pids(echo_env)) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not any(alive(pid) for pid in pids(echo_env))


# ── 強制關閉：SDK 的停止流程來不及時，直接結束 server 的行程群組 ─────────────────


def wait_gone(env, seconds=3):
    deadline = time.monotonic() + seconds
    while any(alive(pid) for pid in pids(env)) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not any(alive(pid) for pid in pids(env))


def test_the_forced_step_kills_a_stubborn_server(echo_env, monkeypatch):
    monkeypatch.setattr(mcp_tools, "FORCE_CLOSE_S", 9)  # 正常關閉只留 1 秒，一定會走到強制的那一步
    servers = start_servers(echo_config({**echo_env, "ECHO_STUBBORN": "1"}))
    started = time.monotonic()
    close_all(servers, timeout=10)
    assert time.monotonic() - started < 10.5
    assert wait_gone(echo_env)


def test_ctrl_c_while_closing_still_kills_the_servers_and_is_raised_again(echo_env, monkeypatch):
    servers = start_servers(echo_config({**echo_env, "ECHO_STUBBORN": "1"}))
    real_wait = mcp_tools.McpServer.wait_closed
    interrupted = []

    def ctrl_c_once(self, deadline):
        if not interrupted:
            interrupted.append(True)
            raise KeyboardInterrupt
        return real_wait(self, deadline)

    monkeypatch.setattr(mcp_tools.McpServer, "wait_closed", ctrl_c_once)
    with pytest.raises(KeyboardInterrupt):
        close_all(servers, timeout=10)
    assert wait_gone(echo_env)


def test_the_launcher_keeps_the_command_s_environment_and_directory(tmp_path):
    # server 經過啟動程式再 exec：環境變數、目前目錄與 PATH 查找都要和直接啟動一樣。
    out = tmp_path / "out.txt"
    script = tmp_path / "probe.py"
    script.write_text("import os\n"
                      f"open({str(out)!r}, 'w').write(os.getcwd() + '|' + os.environ.get('PROBE', ''))\n")
    (tmp_path / "work").mkdir()
    config = {"probe": {"command": "python3", "args": [str(script)], "env": {"PROBE": "yes",
              "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}, "cwd": str(tmp_path / "work")}}
    with pytest.raises(ValueError):  # 它不是 MCP server，啟動會失敗；只看它怎麼被啟動
        start_servers(config)
    cwd, probe = out.read_text().split("|")
    assert Path(cwd).resolve() == (tmp_path / "work").resolve() and probe == "yes"


def test_a_missing_command_is_named_in_one_line(tmp_path):
    config = {"broken": {"command": "no-such-command-xyz", "args": [], "env": {}, "cwd": None}}
    with pytest.raises(ValueError) as caught:
        start_servers(config)
    assert "cannot run no-such-command-xyz" in str(caught.value)
    assert "execvp" not in str(caught.value)


def test_a_server_that_already_exited_is_not_signalled(echo, monkeypatch):
    killed = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: killed.append(pid))
    echo.call("quit", {})
    echo.call("shout", {"text": "x"})  # 確認 server 已結束（_gone）
    echo.kill()
    assert killed == []
