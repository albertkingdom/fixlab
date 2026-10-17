# 路徑隔離測試：對應 workspace-isolation 規格的 Paths stay inside the workspace。
import pytest

from fixlab.tools import register_tools
from fixlab.workspace import ToolError, ToolResult, Workspace, looks_like_test_file


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


# ---- 測試檔保護：對應規格的 Test files cannot be written ----

PROTECTED_TABLE = [
    ("tests/test_report.py", True),
    ("tests/helpers.py", True),
    ("conftest.py", True),
    ("TEST_REPORT.PY", True),
    ("timelog/test_formatting.py", True),
    ("notes/test_notes.txt", True),
    ("Tests/data/cases.json", True),
    ("timelog/parser.py", False),
    ("timelog/contest.py", False),
    ("timelog/tests.py", False),
]


def edit(w, path):
    return w.call("edit_file", {"path": path, "old_string": "x = 1", "new_string": "x = 2"})


def make_project(root):
    for rel, _ in PROTECTED_TABLE:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n")
    return root


@pytest.fixture
def pws(tmp_path):
    """表格裡的十個檔案都存在、內容都是 x = 1 的 Workspace，用 looks_like_test_file 鎖測試檔，登記了真的工具。"""
    root = make_project(tmp_path / "ws")
    w = Workspace(root, read_only=looks_like_test_file)
    register_tools(w)
    return w


# Scenario: Protected and unprotected relative paths
@pytest.mark.parametrize("rel, protected", PROTECTED_TABLE)
def test_edit_file_protected_path_table(pws, rel, protected):
    r = edit(pws, rel)
    content = (pws.root / rel).read_text()
    if protected:
        assert not r.ok and r.flags == {"blocked": True}
        assert content == "x = 1\n"  # 檔案沒被動到
    else:
        assert r.ok and "blocked" not in r.flags
        assert content == "x = 2\n"


# Scenario: Workspace located under a tests directory
def test_workspace_under_a_tests_directory_is_not_affected(tmp_path):
    root = tmp_path / "tests" / "fixtures" / "timelog"
    for rel in ("timelog/parser.py", "tests/test_report.py"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x = 1\n")
    w = Workspace(root, read_only=looks_like_test_file)
    register_tools(w)

    assert edit(w, "timelog/parser.py").ok
    r = edit(w, "tests/test_report.py")
    assert not r.ok and r.flags == {"blocked": True}


def test_blocked_message_tells_the_model_what_to_do(pws):
    r = edit(pws, "tests/test_report.py")
    assert "read-only" in r.output and "fix the source code" in r.output


def test_protected_path_is_blocked_even_when_the_file_does_not_exist(pws):
    r = pws.call("edit_file", {"path": "tests/new_helper.py", "old_string": "a", "new_string": "b"})
    assert not r.ok and r.flags == {"blocked": True}  # 不是 file not found：之後建立新檔的工具也要擋
    assert not (pws.root / "tests" / "new_helper.py").exists()


def test_symlink_to_a_test_file_cannot_be_used_to_edit_it(pws):
    (pws.root / "timelog" / "alias.py").symlink_to(pws.root / "tests" / "test_report.py")
    r = edit(pws, "timelog/alias.py")
    assert not r.ok and r.flags == {"blocked": True}
    assert (pws.root / "tests" / "test_report.py").read_text() == "x = 1\n"


# Scenario: No rule by default
def test_nothing_is_read_only_by_default(tmp_path):
    w = Workspace(make_project(tmp_path / "ws"))  # 沒有傳 read_only
    register_tools(w)
    r = edit(w, "tests/test_report.py")
    assert r.ok and "blocked" not in r.flags
    assert (w.root / "tests" / "test_report.py").read_text() == "x = 2\n"


# Scenario: Custom rule
def test_custom_rule_locks_only_the_files_it_names(tmp_path):
    w = Workspace(make_project(tmp_path / "ws"), read_only=lambda rel: rel.as_posix() == "tests/test_report.py")
    register_tools(w)

    r = edit(w, "tests/test_report.py")
    assert not r.ok and r.flags == {"blocked": True}
    assert edit(w, "tests/helpers.py").ok  # 一般會被當成測試檔的其他檔案，這個規則下可以改
