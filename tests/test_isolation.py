# 路徑隔離測試：對應 workspace-isolation 規格的 Paths stay inside the workspace。
import pytest

from fixlab.workspace import ToolError, ToolResult, Workspace


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "ws"
    (root / "timelog").mkdir(parents=True)
    (root / "timelog" / "parser.py").write_text("x = 1\n")
    (tmp_path / "secret.txt").write_text("secret\n")
    (root / "link_secret").symlink_to("../secret.txt")
    w = Workspace(root)

    # 假的 read_file：只驗證路徑守門與錯誤分類，不依賴真工具的行為。
    def read_file(path: str) -> ToolResult:
        p = w.resolve_inside(path)
        if not p.is_file():
            raise ToolError(f"file not found: {path!r}")
        return ToolResult(p.read_text(), True)

    w.register("read_file", read_file, {"properties": {"path": {"type": "string"}}, "required": ["path"]})
    return w


@pytest.mark.parametrize(
    "path, blocked",
    [
        ("../secret.txt", True),
        ("sub/../../secret.txt", True),
        ("/etc/hosts", True),
        ("~/.zprofile", True),
        ("link_secret", True),
        ("timelog/parser.py", False),
    ],
)
def test_path_table(ws, path, blocked):
    r = ws.call("read_file", {"path": path})
    if blocked:
        assert not r.ok and r.flags.get("blocked") is True
    else:
        assert r.ok and "blocked" not in r.flags


# Scenario: Other errors are not blocked
def test_missing_file_is_not_blocked(ws):
    r = ws.call("read_file", {"path": "timelog/missing.py"})
    assert not r.ok and "blocked" not in r.flags
