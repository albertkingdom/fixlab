# 工具分派測試：對應 agent-tools 規格的 Tool errors never crash the loop。
import pytest

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
