# 路徑隔離測試：對應 workspace-isolation 規格的 Paths stay inside the workspace。
import re
import shutil
import socket
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

import fixlab.sandbox as sandbox
from fixlab.tools import register_tools
from fixlab.workspace import FIXLAB_ROOT, ToolError, ToolResult, Workspace, looks_like_test_file


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


# ---- 子行程的環境變數：對應規格的 Child processes get a minimal environment ----


def workspace_with_test(tmp_path, body):
    """只有一個測試的 Workspace，測試印出環境然後故意失敗（失敗時 pytest 才會顯示印出的內容）。"""
    root = tmp_path / "ws"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_env.py").write_text(body)
    w = Workspace(root)
    register_tools(w)
    return w


# Scenario: API key in the parent environment
def test_child_process_does_not_get_api_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
    w = workspace_with_test(tmp_path, "import os\n\ndef test_env():\n    print(dict(os.environ))\n    assert False\n")

    output = w.call("run_tests", {}).output

    assert "1 failed" in output  # 測試真的跑了，也真的印出了環境
    assert "sk-test-123" not in output
    assert "OPENAI_API_KEY" not in output and "OPENROUTER_API_KEY" not in output


# Scenario: Allowed variables pass through
def test_allowed_variables_reach_the_child_process(tmp_path, monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    w = workspace_with_test(tmp_path, "import os\n\ndef test_lang():\n    print(os.environ['LANG'])\n    assert False\n")

    assert "en_US.UTF-8" in w.call("run_tests", {}).output


def test_run_tests_writes_no_bytecode_into_the_workspace(tmp_path):
    w = workspace_with_test(tmp_path, "def test_ok():\n    assert True\n")
    w.call("run_tests", {})
    assert not list(w.root.rglob("__pycache__"))


# ---- write_file 也要過同一個唯讀判定（Test files cannot be written 對 write_file 同樣成立）----


def write(w, path):
    return w.call("write_file", {"path": path, "content": "x = 2\n"})


# Scenario: Protected and unprotected relative paths（write_file 那一欄）
@pytest.mark.parametrize("rel, protected", PROTECTED_TABLE)
def test_write_file_protected_path_table(pws, rel, protected):
    pws.call("read_file", {"path": rel})  # 先整檔讀過，排除「沒讀過」這個理由，只看唯讀判定
    r = write(pws, rel)
    content = (pws.root / rel).read_text()
    if protected:
        assert not r.ok and r.flags == {"blocked": True}
        assert content == "x = 1\n"
    else:
        assert r.ok and "blocked" not in r.flags
        assert content == "x = 2\n"


def test_write_file_cannot_create_a_new_test_file(pws):
    r = write(pws, "tests/new_helper.py")  # 這是建立新檔，不是覆寫；沒有保護的話模型就能放進一個假的測試輔助檔
    assert not r.ok and r.flags == {"blocked": True}
    assert not (pws.root / "tests" / "new_helper.py").exists()


def test_read_only_check_comes_before_the_read_first_check(pws):
    r = write(pws, "tests/test_report.py")  # 沒讀過，也是唯讀：回報的是唯讀，不是「先讀」
    assert r.flags == {"blocked": True} and "read-only" in r.output


def test_a_symlink_to_a_test_file_cannot_be_used_to_overwrite_it(pws):
    (pws.root / "timelog" / "alias.py").symlink_to(pws.root / "tests" / "test_report.py")
    pws.call("read_file", {"path": "timelog/alias.py"})
    r = write(pws, "timelog/alias.py")
    assert not r.ok and r.flags == {"blocked": True}
    assert (pws.root / "tests" / "test_report.py").read_text() == "x = 1\n"


def test_default_workspace_lets_write_file_overwrite_test_files(tmp_path):
    root = tmp_path / "ws"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_a.py").write_text("x = 1\n")
    w = Workspace(root)  # 沒有傳 read_only
    register_tools(w)
    w.call("read_file", {"path": "tests/test_a.py"})
    assert write(w, "tests/test_a.py").ok


# ---- 沙箱：對應規格的 Tests run in a sandbox（只有 macOS 有 sandbox-exec）----

macos_only = pytest.mark.skipif(not sandbox.sandbox_available(), reason="sandbox-exec is only available on macOS")
HOME = Path.home().resolve()


def sandboxed_workspace(root, **kwargs):
    root.mkdir(parents=True, exist_ok=True)
    (root / "timelog").mkdir(exist_ok=True)
    (root / "timelog" / "parser.py").write_text("def parse_duration(text):\n    return 0\n")
    w = Workspace(root, **kwargs)
    register_tools(w)
    return w


def probe(w, action):
    """在 run_tests 裡執行一行程式，回傳結果：ok、denied（PermissionError）或 error:例外名稱。

    做法：寫一個測試檔，執行 action，然後故意讓測試失敗並把結果放進失敗訊息（失敗時 pytest 才會顯示）。"""
    code = (
        "def test_probe():\n"
        "    try:\n"
        f"        {action}\n"
        "        outcome = 'ok'\n"
        "    except PermissionError:\n"
        "        outcome = 'denied'\n"
        "    except Exception as e:\n"
        "        outcome = 'error:' + type(e).__name__\n"
        "    raise AssertionError('PROBE=' + outcome)\n"
    )
    (w.root / "tests").mkdir(exist_ok=True)
    (w.root / "tests" / "test_probe.py").write_text(code)
    output = w.call("run_tests", {"target": "tests/test_probe.py"}).output
    found = re.search(r"AssertionError: PROBE=(\S+)", output)  # 不能只找 PROBE=：pytest 顯示的原始碼那一行也有
    assert found, output
    return found.group(1)


@pytest.fixture
def home_scratch():
    """家目錄底下一個暫時的資料夾，測試結束時刪掉。"""
    folder = HOME / f".fixlab-test-{uuid.uuid4().hex[:8]}"
    folder.mkdir()
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


# Scenario: Network access
@macos_only
def test_sandbox_blocks_network_access(tmp_path):
    w = sandboxed_workspace(tmp_path / "ws")
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        port = server.getsockname()[1]  # 本機的伺服器確實在聽，連得上的話一定連得上
        assert probe(w, f"__import__('socket').create_connection(('127.0.0.1', {port}), timeout=3)") == "denied"
    finally:
        server.close()


# Scenario: Reading outside the workspace
@macos_only
def test_sandbox_reading_table(tmp_path, home_scratch):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "note.txt").write_text("secret\n")
    (home_scratch / "fake_key").write_text("sk-fake-123\n")
    w = sandboxed_workspace(tmp_path / "ws", deny_read=(secrets,))

    rows = [
        (f"open({str(secrets / 'note.txt')!r}).read()", "denied"),                  # 額外的 deny_read 目錄裡的檔案
        (f"open({str(FIXLAB_ROOT / 'AGENTS.md')!r}).read()", "denied"),             # fixlab 專案根目錄的 AGENTS.md
        (f"open({str(home_scratch / 'fake_key')!r}).read()", "denied"),             # 家目錄裡的假金鑰檔
        ("__import__('os').listdir(__import__('os').path.expanduser('~/.ssh'))", "denied"),   # 列出 ~/.ssh
        (f"open({str(FIXLAB_ROOT / '.git' / 'HEAD')!r}).read()", "denied"),         # 專案根目錄的 .git/HEAD
        ("open('timelog/parser.py').read()", "ok"),                                   # 工作目錄裡的檔案
        ("__import__('regex')", "ok"),                                                # 虛擬環境裡安裝的套件
    ]
    for action, expected in rows:
        assert probe(w, action) == expected, action


# Scenario: Writing outside the workspace
@macos_only
def test_sandbox_blocks_writing_to_the_home_directory(tmp_path, home_scratch):
    w = sandboxed_workspace(tmp_path / "ws")
    target = home_scratch / "written.txt"
    assert probe(w, f"open({str(target)!r}, 'w').write('x')") == "denied"
    assert not target.exists()


@macos_only
def test_sandbox_blocks_writing_outside_the_workspace_and_allows_inside(tmp_path):
    w = sandboxed_workspace(tmp_path / "ws")
    assert probe(w, "open('/tmp/fixlab-sandbox-test.txt', 'w').write('x')") == "denied"
    assert probe(w, "open('inside.txt', 'w').write('x')") == "ok"
    assert (w.root / "inside.txt").exists()


# Scenario: Profile has no literal paths（不需要 sandbox-exec，任何平台都能測）
def test_profile_text_has_no_literal_paths(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    command = sandbox.wrap_command(["python", "-V"], root, sys.executable, FIXLAB_ROOT, (secrets,), tmp_path / "tmp")
    profile = command[command.index("-p") + 1] if "-p" in command else sandbox.build_profile(1)
    for path in (root, FIXLAB_ROOT, HOME, secrets, tmp_path / "tmp"):
        assert str(path) not in profile
    assert profile == sandbox.build_profile(1)


# 實驗發現：規則裡的路徑必須是真實路徑（macOS 的 /var 是 /private/var 的捷徑）
@macos_only
def test_a_workspace_given_as_a_symbolic_link_still_works(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    w = sandboxed_workspace(link)
    assert probe(w, "open('inside.txt', 'w').write('x')") == "ok"


# 實際使用時，工作目錄就在家目錄底下
@macos_only
def test_a_workspace_inside_the_home_directory_works(home_scratch):
    w = sandboxed_workspace(home_scratch / "ws")
    assert probe(w, "open('timelog/parser.py').read()") == "ok"
    assert probe(w, "open('inside.txt', 'w').write('x')") == "ok"
    assert probe(w, "open(" + repr(str(home_scratch / "outside.txt")) + ", 'w').write('x')") == "denied"


# 每次執行有專屬的暫存目錄，tmp_path 不會把垃圾寫進工作目錄
def test_tmp_path_does_not_pollute_the_workspace(tmp_path):
    w = sandboxed_workspace(tmp_path / "ws")
    (w.root / "tests").mkdir(exist_ok=True)
    (w.root / "tests" / "test_tmp.py").write_text("def test_tmp(tmp_path):\n    (tmp_path / 'a.txt').write_text('x')\n    assert str(tmp_path) == 'x'\n")
    before = {p.relative_to(w.root).as_posix() for p in w.root.rglob("*")}

    output = w.call("run_tests", {"target": "tests/test_tmp.py"}).output

    used = re.search(r"assert '(\S+)' == 'x'", output).group(1)  # 失敗訊息裡帶著 tmp_path 的真實位置
    assert not used.startswith(str(w.root))
    assert not Path(used).exists()  # 跑完整個目錄都刪掉了
    after = {p.relative_to(w.root).as_posix() for p in w.root.rglob("*")}
    assert after == before


# 啟動失敗不能被當成通過
def test_a_python_that_fails_to_start_is_not_a_pass(tmp_path):
    w = sandboxed_workspace(tmp_path / "ws", python="/usr/bin/false")
    r = w.call("run_tests", {})
    assert r.flags["tests_passed"] is False


# 沒有沙箱可用時直接執行，並且說清楚
def test_without_a_sandbox_tests_still_run_and_the_status_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "SANDBOX_EXEC", None)
    assert sandbox.sandbox_status().startswith("OFF")
    w = sandboxed_workspace(tmp_path / "ws")
    (w.root / "tests").mkdir()
    (w.root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    assert w.call("run_tests", {}).flags["tests_passed"] is True
