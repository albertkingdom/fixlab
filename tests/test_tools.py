# 工具分派測試：對應 agent-tools 規格的 Tool errors never crash the loop。
# 另外驗證登記表的兩個視圖：給模型的 tool_specs() 與給 toolparse 驗證的 schemas()。
import sys
from types import SimpleNamespace

import pytest

from fixlab.toolparse import parse_message
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
