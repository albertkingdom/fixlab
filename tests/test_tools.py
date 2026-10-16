# 工具分派測試：對應 agent-tools 規格的 Tool errors never crash the loop。
# 另外驗證登記表的兩個視圖：給模型的 tool_specs() 與給 toolparse 驗證的 schemas()，以及 read_file 的行為。
import sys
from types import SimpleNamespace

import pytest

from fixlab.toolparse import parse_message
from fixlab.tools import MAX_READ_CHARS, register_tools
from fixlab.workspace import ToolResult, Workspace


@pytest.fixture
def ws(tmp_path):
    w = Workspace(tmp_path)

    # 假工具：edit_file 到任務 3.5 才有，這裡只驗證參數型別檢查。
    def edit_file(path: str, old_string: str, new_string: str) -> ToolResult:
        return ToolResult("edited", True)

    schema = {
        "properties": {k: {"type": "string"} for k in ("path", "old_string", "new_string")},
        "required": ["path", "old_string", "new_string"],
    }
    w.register("edit_file", edit_file, schema)
    return w


# Scenario: Unknown tool
def test_unknown_tool(ws):
    r = ws.call("bash", {"command": "ls"})
    assert not r.ok and "unknown tool" in r.output and "blocked" not in r.flags


# Scenario: Wrong argument type
def test_wrong_argument_type(ws):
    r = ws.call("edit_file", {"path": "a.py", "old_string": 5, "new_string": "y"})
    assert not r.ok and "must be a string" in r.output and "blocked" not in r.flags


def test_missing_and_unexpected_arguments(ws):
    assert "missing" in ws.call("edit_file", {"path": "a.py"}).output
    r = ws.call("edit_file", {"path": "a", "old_string": "x", "new_string": "y", "extra": 1})
    assert not r.ok and "unexpected" in r.output


def test_os_error_becomes_result(ws):
    def boom() -> ToolResult:
        raise PermissionError("denied")

    ws.register("boom", boom, {"properties": {}, "required": []})
    r = ws.call("boom", {})
    assert not r.ok and "denied" in r.output


def _reply_with_call(name: str, arguments: str):
    """假的 API 回覆：只有一個原生 tool call，parse_message 只讀這幾個欄位。"""
    call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))
    return SimpleNamespace(content=None, tool_calls=[call])


def test_tool_specs_describe_registered_tools(ws):
    schema = {"properties": {"path": {"type": "string"}}, "required": ["path"]}
    ws.register("read_file", lambda path: ToolResult(path, True), schema, description="Read a file.")
    specs = {s["function"]["name"]: s for s in ws.tool_specs()}
    assert list(specs) == ["edit_file", "read_file"]  # 依登記順序
    spec = specs["read_file"]
    assert spec["type"] == "function"
    assert spec["function"]["description"] == "Read a file."
    assert spec["function"]["parameters"] == {"type": "object", **schema}
    assert "type" not in ws.schemas()["read_file"]  # 登記的 schema 本身沒被改動


def test_schemas_feed_parse_message(ws):
    ok = parse_message(
        _reply_with_call("edit_file", '{"path": "a.py", "old_string": "x", "new_string": "y"}'), ws.schemas()
    )
    assert [c.name for c in ok.calls] == ["edit_file"] and ok.errors == []
    bad = parse_message(_reply_with_call("edit_file", '{"path": "a.py", "old_string": "x"}'), ws.schemas())
    assert bad.calls == [] and "missing" in bad.errors[0]


def test_python_defaults_to_current_interpreter(tmp_path):
    assert Workspace(tmp_path).python == sys.executable
    assert Workspace(tmp_path, python="/venv/bin/python").python == "/venv/bin/python"  # 不 resolve，原樣保留


# ---- read_file：對應 agent-tools 規格的 read_file returns numbered lines ----


@pytest.fixture
def rws(tmp_path):
    """登記了真工具的 Workspace。"""
    w = Workspace(tmp_path)
    register_tools(w)
    return w


def read(w, path, **kwargs):
    return w.call("read_file", {"path": path, **kwargs})


# Scenario: Whole small file
def test_read_whole_file_with_trailing_newline(rws):
    (rws.root / "rules.py").write_text("def grace_days():\n    return 3\n")
    r = read(rws, "rules.py")
    assert r.ok and r.output == "     1\tdef grace_days():\n     2\t    return 3"
    assert rws.root / "rules.py" in rws.files_read


# Scenario: Line range
def test_read_line_range(rws):
    (rws.root / "big.py").write_text("".join(f"line {i}\n" for i in range(1, 101)))
    r = read(rws, "big.py", start_line=40, end_line=42)
    assert r.output.splitlines() == ["    40\tline 40", "    41\tline 41", "    42\tline 42"]
    assert rws.root / "big.py" not in rws.files_read  # 部分讀取不算讀過整檔


# Scenario: Empty file
def test_read_empty_file(rws):
    (rws.root / "empty.py").write_text("")
    r = read(rws, "empty.py")
    assert r.ok and r.output == "(empty file)"


# Scenario: Missing file
def test_read_missing_file_is_not_blocked(rws):
    r = read(rws, "nope.py")
    assert not r.ok and "file not found" in r.output and "blocked" not in r.flags


def test_read_directory_is_an_error(rws):
    (rws.root / "pkg").mkdir()
    r = read(rws, "pkg")
    assert not r.ok and "directory" in r.output


def test_read_truncates_and_says_so(rws):
    (rws.root / "long.txt").write_text("".join(f"{i:04d} {'x' * 70}\n" for i in range(1000)))  # 約 7.5 萬字元
    r = read(rws, "long.txt")
    assert r.ok
    body, note = r.output.rsplit("\n", 1)
    assert len(body) == MAX_READ_CHARS
    assert note.startswith("[truncated: ") and "characters in total" in note
    assert rws.root / "long.txt" not in rws.files_read  # 被截斷的讀取不算讀過整檔


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"start_line": 0}, "at least 1"),
        ({"start_line": 3, "end_line": 2}, "smaller than start_line"),
        ({"start_line": 9}, "past the end"),
    ],
)
def test_read_bad_line_range(rws, kwargs, message):
    (rws.root / "a.py").write_text("x = 1\ny = 2\n")
    r = read(rws, "a.py", **kwargs)
    assert not r.ok and message in r.output


def test_read_binary_file_does_not_crash(rws):
    (rws.root / "blob.bin").write_bytes(b"\xff\xfe\x00\x80")
    r = read(rws, "blob.bin")
    assert not r.ok and "UTF-8" in r.output


def test_read_outside_workspace_is_blocked(rws):
    r = read(rws, "../secret.txt")
    assert not r.ok and r.flags == {"blocked": True}


def test_read_file_is_offered_to_the_model(rws):
    spec = rws.tool_specs()[0]["function"]
    assert spec["name"] == "read_file"
    assert spec["parameters"]["required"] == ["path"]
    assert set(spec["parameters"]["properties"]) == {"path", "start_line", "end_line"}
