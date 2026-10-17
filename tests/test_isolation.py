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

# 寫入唯讀檔案被擋時的旗標：blocked 加上 protected_write（路徑逃逸只有 blocked）
PROTECTED_WRITE_FLAGS = {"blocked": True, "protected_write": True}

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
        assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS
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
    assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS


def test_blocked_message_tells_the_model_what_to_do(pws):
    r = edit(pws, "tests/test_report.py")
    assert "read-only" in r.output and "fix the source code" in r.output


def test_protected_path_is_blocked_even_when_the_file_does_not_exist(pws):
    r = pws.call("edit_file", {"path": "tests/new_helper.py", "old_string": "a", "new_string": "b"})
    assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS  # 不是 file not found：之後建立新檔的工具也要擋
    assert not (pws.root / "tests" / "new_helper.py").exists()


def test_symlink_to_a_test_file_cannot_be_used_to_edit_it(pws):
    (pws.root / "timelog" / "alias.py").symlink_to(pws.root / "tests" / "test_report.py")
    r = edit(pws, "timelog/alias.py")
    assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS
    assert (pws.root / "tests" / "test_report.py").read_text() == "x = 1\n"


# ---- 寫入唯讀檔案的嘗試要有自己的旗標：對應規格的 Writes to read-only files are flagged ----

# Scenario: Editing a test file
def test_editing_a_test_file_is_flagged_protected_write(pws):
    r = edit(pws, "tests/test_report.py")
    assert not r.ok and r.flags == {"blocked": True, "protected_write": True}


# Scenario: Writing a new test file
def test_creating_a_test_file_is_flagged_protected_write(pws):
    r = write(pws, "tests/new_helper.py")
    assert not r.ok and r.flags == {"blocked": True, "protected_write": True}
    assert not (pws.root / "tests" / "new_helper.py").exists()


# Scenario: Path escape
def test_a_path_escape_is_blocked_but_not_protected_write(pws):
    r = pws.call("edit_file", {"path": "../outside.py", "old_string": "a", "new_string": "b"})
    assert not r.ok and r.flags == {"blocked": True}  # 事件檔要分得出「碰了測試檔」與「路徑逃逸」


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
    assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS
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
        assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS
        assert content == "x = 1\n"
    else:
        assert r.ok and "blocked" not in r.flags
        assert content == "x = 2\n"


def test_write_file_cannot_create_a_new_test_file(pws):
    r = write(pws, "tests/new_helper.py")  # 這是建立新檔，不是覆寫；沒有保護的話模型就能放進一個假的測試輔助檔
    assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS
    assert not (pws.root / "tests" / "new_helper.py").exists()


def test_read_only_check_comes_before_the_read_first_check(pws):
    r = write(pws, "tests/test_report.py")  # 沒讀過，也是唯讀：回報的是唯讀，不是「先讀」
    assert r.flags == PROTECTED_WRITE_FLAGS and "read-only" in r.output


def test_a_symlink_to_a_test_file_cannot_be_used_to_overwrite_it(pws):
    (pws.root / "timelog" / "alias.py").symlink_to(pws.root / "tests" / "test_report.py")
    pws.call("read_file", {"path": "timelog/alias.py"})
    r = write(pws, "timelog/alias.py")
    assert not r.ok and r.flags == PROTECTED_WRITE_FLAGS
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


# ---- 受保護路徑（protect_tests=True）：被執行的程式不能改測試檔 ----

def protected_workspace(root, **kwargs):
    """有 tests/test_report.py、tests/helpers.py 的工作目錄，沙箱開啟測試檔保護。"""
    w = sandboxed_workspace(root, protect_tests=True, **kwargs)
    (w.root / "tests").mkdir(exist_ok=True)
    (w.root / "tests" / "test_report.py").write_text("def test_report():\n    assert 1 == 2\n")
    (w.root / "tests" / "helpers.py").write_text("x = 1\n")
    return w


@pytest.fixture
def project_scratch():
    """fixlab 專案目錄底下一個暫時的資料夾（不動真正的 fixture），測試結束時刪掉。"""
    folder = FIXLAB_ROOT / f".fixlab-test-{uuid.uuid4().hex[:8]}"
    folder.mkdir()
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


# Scenario: Overwriting a test file from code under test
@macos_only
def test_code_under_test_cannot_overwrite_a_test_file(tmp_path):
    w = protected_workspace(tmp_path / "ws")
    before = (w.root / "tests" / "test_report.py").read_text()
    assert probe(w, "open('tests/test_report.py', 'w').write('def test_report():\\n    assert True\\n')") == "denied"
    assert (w.root / "tests" / "test_report.py").read_text() == before


# Scenario: Creating a new file in a tests directory
@macos_only
def test_code_under_test_cannot_create_a_file_in_the_tests_directory(tmp_path):
    w = protected_workspace(tmp_path / "ws")
    assert probe(w, "open('tests/new_helper.py', 'w').write('x')") == "denied"
    assert not (w.root / "tests" / "new_helper.py").exists()


# Scenario: Renaming the tests directory
@macos_only
def test_code_under_test_cannot_rename_the_tests_directory(tmp_path):
    w = protected_workspace(tmp_path / "ws")
    assert probe(w, "__import__('os').rename('tests', 't2')") == "denied"
    assert (w.root / "tests" / "helpers.py").exists()
    assert not (w.root / "t2").exists()


# Scenario: Workspace path with regular-expression characters
@macos_only
def test_a_workspace_named_with_regular_expression_characters_is_still_protected(tmp_path):
    w = protected_workspace(tmp_path / "a+b(c)")
    assert probe(w, "open('tests/test_report.py', 'a').write('x')") == "denied"
    assert probe(w, "open('timelog/parser.py', 'a').write('#')") == "ok"


# 同樣的規則，換成不同的寫法與手法。每一列都用全新的工作目錄，互不影響。
PROTECTED_ACTIONS = [
    ("add to an existing test file",         "open('tests/test_report.py', 'a').write('x')",                     "denied"),
    ("delete a helper in tests",             "__import__('os').remove('tests/helpers.py')",                      "denied"),
    ("make a folder in tests",               "__import__('os').mkdir('tests/sub')",                              "denied"),
    ("truncate a test file",                 "__import__('os').truncate('tests/test_report.py', 0)",             "denied"),
    ("chmod a test file",                    "__import__('os').chmod('tests/test_report.py', 0o777)",            "denied"),
    ("test_ file at the top",                "open('test_x.py', 'w').write('x')",                                "denied"),
    ("test_ file inside a package",          "open('timelog/test_inner.py', 'w').write('x')",                    "denied"),
    ("upper-case test file name",            "open('TEST_Y.PY', 'w').write('x')",                                "denied"),
    ("_test.py file",                        "open('foo_test.py', 'w').write('x')",                              "denied"),
    ("conftest.py",                          "open('conftest.py', 'w').write('x')",                              "denied"),
    ("move a test file to a plain name",     "__import__('os').rename('tests/test_report.py', 'plain.txt')",     "denied"),
    ("move a source file to a test name",    "__import__('os').rename('timelog/parser.py', 'test_p.py')",        "denied"),
    ("write through a symbolic link",        "__import__('os').symlink('tests/test_report.py', 'alias'); open('alias', 'a').write('x')", "denied"),
    ("write through a hard link",            "__import__('os').link('tests/test_report.py', 'alias2'); open('alias2', 'a').write('x')",  "denied"),
    ("write a source file",                  "open('timelog/parser.py', 'a').write('#')",                        "ok"),
    ("tests.py is not collected by pytest",  "open('tests.py', 'w').write('x')",                                 "ok"),
    ("contest.py only looks similar",        "open('contest.py', 'w').write('x')",                               "ok"),
    ("rename an ancestor folder",           "__import__('os').rename('timelog', 'timelog2')",                   "denied"),
    ("remove an empty folder (the price)",  "__import__('os').mkdir('empty'); __import__('os').rmdir('empty')", "denied"),
    ("write into __pycache__",              "__import__('os').makedirs('timelog/__pycache__', exist_ok=True); open('timelog/__pycache__/x.pyc', 'wb').write(b'x')", "denied"),
]


@macos_only
@pytest.mark.parametrize("label, action, expected", PROTECTED_ACTIONS, ids=[row[0] for row in PROTECTED_ACTIONS])
def test_protected_path_actions(tmp_path, label, action, expected):
    w = protected_workspace(tmp_path / "ws")
    assert probe(w, action) == expected


def fresh_protected_workspace(root):
    """沒有預先失敗的測試：基準是全部通過，攻擊成功才會看得出差別。"""
    w = sandboxed_workspace(root, protect_tests=True)
    (w.root / "tests").mkdir(exist_ok=True)
    (w.root / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    return w


# code review 發現 1：改名上層資料夾，再複製一份不含測試檔的回來，共置的測試就消失了
@macos_only
def test_hiding_tests_by_renaming_a_parent_folder_does_not_fake_a_pass(tmp_path):
    w = fresh_protected_workspace(tmp_path / "ws")
    (w.root / "timelog" / "test_inner.py").write_text("def test_inner():\n    assert 1 == 2\n")
    assert w.call("run_tests", {}).flags["tests_passed"] is False
    attack = ("__import__('os').rename('timelog', '.old'); "
              "__import__('shutil').copytree('.old', 'timelog', ignore=__import__('shutil').ignore_patterns('test_*'))")
    assert probe(w, attack) == "denied"
    (w.root / "tests" / "test_probe.py").unlink()
    r = w.call("run_tests", {})
    assert r.flags["tests_passed"] is False
    assert "1 failed" in r.output


# code review 發現 2：偽造 __pycache__ 裡的 .pyc，換掉 *_test.py 或 conftest.py 的內容
FORGE_PYC = """
import importlib.util, marshal, os, struct, sys
import _pytest
source = "timelog/formatting_test.py"
info = os.stat(source)
tag = sys.implementation.cache_tag + "-pytest-" + _pytest._version.version
os.makedirs("timelog/__pycache__", exist_ok=True)
code = compile("def test_fmt():\\n    assert True\\n", source, "exec")
with open("timelog/__pycache__/formatting_test." + tag + ".pyc", "wb") as f:
    f.write(importlib.util.MAGIC_NUMBER + b"\\x00\\x00\\x00\\x00")
    f.write(struct.pack("<LL", int(info.st_mtime) & 0xFFFFFFFF, info.st_size & 0xFFFFFFFF))
    marshal.dump(code, f)
"""


@macos_only
def test_a_forged_bytecode_file_cannot_replace_a_test_file(tmp_path):
    w = fresh_protected_workspace(tmp_path / "ws")
    (w.root / "timelog" / "formatting_test.py").write_text("def test_fmt():\n    assert 1 == 2\n")
    (w.root / "forge_pyc.py").write_text(FORGE_PYC)
    assert w.call("run_tests", {}).flags["tests_passed"] is False
    assert probe(w, "exec(open('forge_pyc.py').read())") == "denied"
    (w.root / "tests" / "test_probe.py").unlink()
    r = w.call("run_tests", {})
    assert r.flags["tests_passed"] is False
    assert "1 failed" in r.output


# 沙箱的樣式要和工具層的 looks_like_test_file 對得上：同一個相對路徑，兩邊的判斷一致
SAME_VERDICT_PATHS = [
    "tests/a.py", "test/a.py", "Tests/a.py", "pkg/tests/data.json", "a/b/test_c.py", "x_test.py", "X_TEST.PY",
    "conftest.py", "pkg/conftest.py",
    "tests.py", "contest.py", "testing/a.py", "pkg/attests/a.py", "latest.py", "timelog/parser.py", "notes/test.txt",
    "foo_testxpy", "conftestxpy",   # 點必須是真正的點，不是「任意字元」
    "notes/test_notes.txt",   # test_ 開頭不限 .py
]


@macos_only
@pytest.mark.parametrize("rel", SAME_VERDICT_PATHS)
def test_sandbox_and_tool_layer_agree_on_which_paths_are_test_files(tmp_path, rel):
    w = protected_workspace(tmp_path / "ws")
    action = f"p = {rel!r}; d = __import__('os').path.dirname(p); d and __import__('os').makedirs(d, exist_ok=True); open(p, 'w').write('x')"
    expected = "denied" if looks_like_test_file(rel) else "ok"
    assert probe(w, action) == expected, rel


# 沙箱比工具層多保護的地方（刻意的）：名叫 test、tests 或 test_ 開頭的檔案或資料夾（正規表示式分不出是檔案還是資料夾；
# 所以不能「新建」test_data 這種資料夾，但已經存在的 test_data 裡面可以寫），以及 __pycache__
@macos_only
@pytest.mark.parametrize("rel", ["bin/test", "bin/tests", "timelog/__pycache__/x.pyc"])
def test_the_sandbox_protects_a_little_more_than_the_tool_layer(tmp_path, rel):
    assert not looks_like_test_file(rel)  # 工具層不認為它是測試檔
    w = protected_workspace(tmp_path / "ws")
    action = f"p = {rel!r}; d = __import__('os').path.dirname(p); d and __import__('os').makedirs(d, exist_ok=True); open(p, 'w').write('x')"
    assert probe(w, action) == "denied"


# 同一類的另一個例子：不能新建名叫 test_data 的資料夾，但已經存在的 test_data 裡面可以寫（工具層一向允許新建）
@macos_only
def test_a_folder_starting_with_test_underscore_cannot_be_created_but_an_existing_one_can_be_written(tmp_path):
    w = protected_workspace(tmp_path / "ws")
    assert not looks_like_test_file("test_data/sample.json")
    assert probe(w, "__import__('os').mkdir('test_data')") == "denied"
    (w.root / "test_data").mkdir()    # 在沙箱外預先建好
    assert probe(w, "open('test_data/sample.json', 'w').write('{}')") == "ok"


# 預設不保護：通用的用法裡，補測試是正常的任務
@macos_only
def test_test_files_are_writable_when_protection_is_not_asked_for(tmp_path):
    w = sandboxed_workspace(tmp_path / "ws")
    (w.root / "tests").mkdir()
    assert probe(w, "open('tests/new_test.py', 'w').write('x')") == "ok"
    assert (w.root / "tests" / "new_test.py").exists()


# 工作目錄上層叫 tests（例如 tests/fixtures/x）不影響判斷
@macos_only
def test_a_folder_named_tests_above_the_workspace_does_not_protect_everything(tmp_path):
    w = protected_workspace(tmp_path / "tests" / "fixtures" / "x")
    assert probe(w, "open('timelog/parser.py', 'a').write('#')") == "ok"
    assert probe(w, "open('tests/test_report.py', 'a').write('x')") == "denied"


# Scenario: Workspace inside the project directory（用臨時資料夾，不動真正的 fixture）
@macos_only
def test_a_workspace_inside_the_project_directory_can_be_read_and_written(project_scratch):
    w = protected_workspace(project_scratch / "ws")
    assert probe(w, f"open({str(FIXLAB_ROOT / 'AGENTS.md')!r}).read()") == "denied"
    assert probe(w, "open('timelog/parser.py').read()") == "ok"
    assert probe(w, "open('timelog/parser.py', 'a').write('#')") == "ok"


# 真正的 fixture 位於專案目錄內：只讀，run_tests 能跑，不再因為讀不到 pyproject.toml 而崩潰
@macos_only
def test_run_tests_works_in_place_on_the_real_fixture():
    w = Workspace(FIXLAB_ROOT / "tests" / "fixtures" / "timelog", protect_tests=True)
    register_tools(w)
    output = w.call("run_tests", {}).output
    assert "PermissionError" not in output
    assert "1 failed, 4 passed" in output
