# 工具分派測試：對應 agent-tools 規格的 Tool errors never crash the loop。
# 另外驗證登記表的兩個視圖：給模型的 tool_specs() 與給 toolparse 驗證的 schemas()，以及 read_file 的行為。
import sys
import time
from types import SimpleNamespace

import pytest

from fixlab.toolparse import parse_message
from fixlab.tools import MAX_READ_CHARS, register_tools
from fixlab.workspace import ToolResult, Workspace
from test_fixture import BUGGY, FIXED, copy_fixture, run_pytest  # timelog 範例專案與它的 bug／修法


@pytest.fixture
def ws(tmp_path):
    w = Workspace(tmp_path)

    # 這個 edit_file 是假的，什麼都不做，只用來驗證參數型別檢查（真的在 fixlab/tools.py）。
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


# ---- list_files：對應規格的 list_files shows the project layout ----


def touch(root, *paths):
    for rel in paths:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n")


def lines_of(result):
    return result.output.splitlines()


# Scenario: Small project
def test_list_files_small_project_sorted(rws):
    touch(rws.root, "timelog/report.py", "tests/test_report.py", "timelog/parser.py")
    r = rws.call("list_files", {})
    assert r.ok and lines_of(r) == ["tests/test_report.py", "timelog/parser.py", "timelog/report.py"]


# Scenario: Too many files
def test_list_files_caps_at_200_and_counts_the_rest(rws):
    touch(rws.root, *[f"pkg/mod_{i:03d}.py" for i in range(250)])
    lines = lines_of(rws.call("list_files", {}))
    assert len(lines) == 201
    assert lines[0] == "pkg/mod_000.py" and lines[199] == "pkg/mod_199.py"
    assert lines[200].startswith("[50 more entries omitted")


# Scenario: Symbolic link inside the workspace
def test_list_files_ignores_symbolic_links(rws):
    touch(rws.root, "pkg/real.py")
    (rws.root / "link_secret").symlink_to("../secret")  # 指向外面（連目標都不存在）
    (rws.root / "link_file.py").symlink_to("pkg/real.py")
    (rws.root / "link_dir").symlink_to("pkg", target_is_directory=True)
    assert lines_of(rws.call("list_files", {})) == ["pkg/real.py"]


# Scenario: Nothing to list
def test_list_files_nothing_to_list(rws):
    touch(rws.root, ".git/config", ".venv/lib/x.py", "pkg/__pycache__/x.pyc", ".pytest_cache/v/cache")
    r = rws.call("list_files", {})
    assert r.ok and r.output == "no files listed"


def test_list_files_skips_cache_directories_at_any_depth(rws):
    touch(rws.root, "pkg/a.py", "pkg/__pycache__/a.pyc", "pkg/sub/.pytest_cache/n")
    assert lines_of(rws.call("list_files", {})) == ["pkg/a.py"]


def test_list_files_subdirectory_paths_are_relative_to_the_workspace(rws):
    touch(rws.root, "timelog/parser.py", "tests/test_report.py")
    assert lines_of(rws.call("list_files", {"path": "timelog"})) == ["timelog/parser.py"]


@pytest.mark.parametrize("path, message", [("nope", "directory not found"), ("a.py", "not a directory")])
def test_list_files_bad_path_is_an_error(rws, path, message):
    touch(rws.root, "a.py")
    r = rws.call("list_files", {"path": path})
    assert not r.ok and message in r.output and "blocked" not in r.flags


def test_list_files_outside_workspace_is_blocked(rws):
    r = rws.call("list_files", {"path": ".."})
    assert not r.ok and r.flags == {"blocked": True}


# ---- edit_file：對應規格的 edit_file replaces one unique string ----

# timelog 的 bug 那一行（\d 是字面的反斜線加 d，小模型最常在這裡把跳脫寫錯）
BUGGY_LINE = r'    units = [re.match(r"(\d+)([hm])", text).groups()]'
FIXED_LINE = r'    units = re.findall(r"(\d+)([hm])", text)'


def edit(w, path, old, new):
    return w.call("edit_file", {"path": path, "old_string": old, "new_string": new})


def write_parser(root, text=None):
    path = root / "timelog" / "parser.py"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text if text is not None else f"def parse_duration(text):\n{BUGGY_LINE}\n    return units\n")
    return path


# Scenario: Unique match
def test_edit_unique_match_replaces_it(rws):
    parser = write_parser(rws.root)
    r = edit(rws, "timelog/parser.py", r'[re.match(r"(\d+)([hm])", text).groups()]', r're.findall(r"(\d+)([hm])", text)')
    assert r.ok and r.output == "edited timelog/parser.py"
    assert parser.read_text() == f"def parse_duration(text):\n{FIXED_LINE}\n    return units\n"


# Scenario: Ambiguous match
def test_edit_ambiguous_match_leaves_file_unchanged(rws):
    original = "def a():\n    return 0\n\ndef b():\n    return 0\n"
    parser = write_parser(rws.root, original)
    r = edit(rws, "timelog/parser.py", "return 0", "return 1")
    assert not r.ok and "2 times" in r.output and "blocked" not in r.flags
    assert parser.read_text() == original


# Scenario: No match
def test_edit_no_match_leaves_file_unchanged(rws):
    parser = write_parser(rws.root)
    original = parser.read_text()
    r = edit(rws, "timelog/parser.py", "this text is not in the file", "x")
    assert not r.ok and "0 times" in r.output and "blocked" not in r.flags
    assert parser.read_text() == original


def test_edit_counts_overlapping_matches(rws):
    parser = write_parser(rws.root, "aaa\n")
    r = edit(rws, "timelog/parser.py", "aa", "b")  # "aa" 在 "aaa" 的位置 0 與 1 都匹配，不是唯一
    assert not r.ok and "2 times" in r.output
    assert parser.read_text() == "aaa\n"


def test_edit_with_empty_new_string_deletes_the_text(rws):
    parser = write_parser(rws.root, "x = 1\ny = 2\n")
    assert edit(rws, "timelog/parser.py", "y = 2\n", "").ok
    assert parser.read_text() == "x = 1\n"


@pytest.mark.parametrize("old, new, message", [
    ("", "x", "must not be empty"),
    ("x = 1", "x = 1", "identical"),
])
def test_edit_rejects_pointless_requests(rws, old, new, message):
    parser = write_parser(rws.root, "x = 1\n")
    r = edit(rws, "timelog/parser.py", old, new)
    assert not r.ok and message in r.output
    assert parser.read_text() == "x = 1\n"


def test_edit_empty_old_string_message_explains_how_to_insert(rws):
    write_parser(rws.root, "x = 1\n")
    r = edit(rws, "timelog/parser.py", "", "y = 2\n")
    assert not r.ok and "To insert text" in r.output and "new_string" in r.output


def test_edit_inserts_text_next_to_an_anchor(rws):
    parser = write_parser(rws.root, "import re\n\n\ndef f():\n    pass\n")
    r = edit(rws, "timelog/parser.py", "import re\n", "import re\nimport os\n")
    assert r.ok
    assert parser.read_text() == "import re\nimport os\n\n\ndef f():\n    pass\n"


def test_edit_empty_old_string_does_not_fill_an_empty_file(rws):
    parser = write_parser(rws.root, "")
    r = edit(rws, "timelog/parser.py", "", "x = 1\n")
    assert not r.ok
    assert parser.read_text() == ""


# Requirement 的最後一句：成功的編輯讓該檔不再算整檔讀過
def test_successful_edit_removes_file_from_files_read(rws):
    parser = write_parser(rws.root, "x = 1\n")
    read(rws, "timelog/parser.py")
    assert parser in rws.files_read

    assert not edit(rws, "timelog/parser.py", "nope", "y").ok
    assert parser in rws.files_read  # 失敗的編輯沒有改檔，讀過的內容仍然有效

    assert edit(rws, "timelog/parser.py", "x = 1", "x = 2").ok
    assert parser not in rws.files_read


def test_edit_keeps_windows_line_endings(rws):
    parser = rws.root / "crlf.py"
    parser.write_bytes(b"a = 1\r\nb = 2\r\n")
    assert edit(rws, "crlf.py", "a = 1", "a = 9").ok
    assert parser.read_bytes() == b"a = 9\r\nb = 2\r\n"


def test_edit_new_string_that_cannot_be_encoded_leaves_file_unchanged(rws):
    parser = write_parser(rws.root, "x = 1\n")
    r = edit(rws, "timelog/parser.py", "x = 1", "\ud800")  # 孤立的 surrogate 不能編成 UTF-8
    assert not r.ok and "UTF-8" in r.output
    assert parser.read_text() == "x = 1\n"


def test_edit_missing_directory_and_binary_files_are_errors(rws):
    (rws.root / "pkg").mkdir()
    (rws.root / "blob.bin").write_bytes(b"\xff\xfe\x00\x80")
    for path, message in [("nope.py", "file not found"), ("pkg", "directory"), ("blob.bin", "UTF-8")]:
        r = edit(rws, path, "a", "b")
        assert not r.ok and message in r.output and "blocked" not in r.flags


def test_edit_outside_workspace_is_blocked(rws):
    r = edit(rws, "../secret.txt", "a", "b")
    assert not r.ok and r.flags == {"blocked": True}


def test_edit_file_is_offered_to_the_model(rws):
    spec = {s["function"]["name"]: s["function"] for s in rws.tool_specs()}["edit_file"]
    assert spec["parameters"]["required"] == ["path", "old_string", "new_string"]
    assert "line numbers" in spec["description"]  # read_file 的輸出有行號，提醒模型別把行號抄進 old_string


def test_edit_file_applies_the_real_fix_to_the_fixture(tmp_path):
    project = copy_fixture(tmp_path)
    assert "1 failed" in run_pytest(project).stdout
    w = Workspace(project)
    register_tools(w)

    assert edit(w, "timelog/parser.py", BUGGY, FIXED).ok

    result = run_pytest(project)
    assert result.returncode == 0, result.stdout


# ---- run_tests：對應規格的 run_tests runs pytest in the workspace ----


@pytest.fixture
def tws(tmp_path):
    """timelog 範例專案的複本，登記了真的工具。未修時恰好 1 個測試失敗。"""
    w = Workspace(copy_fixture(tmp_path))
    register_tools(w)
    return w


def run_tests(w, **args):
    return w.call("run_tests", args)


def write_test(w, name, body):
    path = w.root / "tests" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(body)


# Scenario: Failing fixture project
def test_run_tests_reports_a_failing_project(tws):
    r = run_tests(tws)
    assert r.ok  # 測試失敗不是工具錯誤
    assert r.flags == {"tests_passed": False, "timed_out": False}
    assert "1 failed" in r.output and "3.75 != 4.25" in r.output


def test_run_tests_passes_after_the_fix(tws):
    assert tws.call("edit_file", {"path": "timelog/parser.py", "old_string": BUGGY, "new_string": FIXED}).ok
    r = run_tests(tws)
    assert r.ok and r.flags["tests_passed"] is True and "5 passed" in r.output


# Scenario: Target a single test file
def test_run_tests_can_target_one_file(tws):
    r = run_tests(tws, target="tests/test_report.py")
    assert "1 failed, 1 passed" in r.output  # 這個檔案只有 2 個測試；全部是 5 個


# Scenario: Target that looks like an option
def test_run_tests_option_like_target_is_a_path(tws):
    r = run_tests(tws, target="--version")
    assert r.flags["tests_passed"] is False
    assert "not found" in r.output  # 當成路徑找不到，pytest 沒有印出版本


# Scenario: Target outside the workspace
def test_run_tests_target_outside_the_workspace_is_blocked(tws):
    r = run_tests(tws, target="../other")
    assert not r.ok and r.flags == {"blocked": True}


# Scenario: Infinite loop in the code under test
def test_run_tests_stops_an_endless_test(rws, monkeypatch):
    monkeypatch.setattr("fixlab.tools.RUN_TESTS_TIMEOUT_S", 1)  # 規格是 10 秒，測試不想真的等
    write_test(rws, "test_forever.py", "def test_forever():\n    while True:\n        pass\n")
    r = run_tests(rws)
    assert r.ok and r.flags == {"tests_passed": False, "timed_out": True}
    assert "timed out after 1s" in r.output


# Scenario: No cache directory left behind
def test_run_tests_leaves_no_cache_directories(tws):
    run_tests(tws)
    assert not list(tws.root.rglob(".pytest_cache"))
    assert not list(tws.root.rglob("__pycache__"))


def test_run_tests_shortens_long_output_but_keeps_the_summary(rws):
    write_test(rws, "test_big.py", 'def test_big():\n    print("x" * 10000)\n    assert False\n')
    r = run_tests(rws)
    assert len(r.output) < 4300
    assert "[truncated: " in r.output
    assert "1 failed" in r.output.splitlines()[-1]  # 最後一行的結果沒有被截掉


def test_run_tests_is_offered_to_the_model(rws):
    spec = {s["function"]["name"]: s["function"] for s in rws.tool_specs()}["run_tests"]
    assert spec["parameters"]["required"] == []
    assert set(spec["parameters"]["properties"]) == {"target"}


# ---- run_tests 擋住意外與簡單的偽造結果（code review 發現；同一行程內的蓄意竄改擋不住，見 design）----

def failing_project(rws):
    write_test(rws, "test_bad.py", "from timelog import parser\n\ndef test_bad():\n    assert 1 == 2\n")
    (rws.root / "timelog").mkdir(exist_ok=True)
    (rws.root / "timelog" / "__init__.py").write_text("")
    (rws.root / "timelog" / "parser.py").write_text("x = 1\n")
    assert run_tests(rws).flags["tests_passed"] is False  # 先確認真的是失敗的專案
    return rws


def test_a_fake_pytest_module_in_the_workspace_is_not_loaded(rws):
    failing_project(rws)
    (rws.root / "pytest.py").write_text('print("1 passed in 0.00s")\n')
    r = run_tests(rws)
    assert r.flags["tests_passed"] is False
    assert "1 failed" in r.output


def test_a_fake_internal_pytest_package_in_the_workspace_is_not_loaded(rws):
    failing_project(rws)
    (rws.root / "_pytest").mkdir()
    (rws.root / "_pytest" / "__init__.py").write_text("import os\nos._exit(0)\n")
    r = run_tests(rws)
    assert r.flags["tests_passed"] is False
    assert "1 failed" in r.output


def test_exiting_with_zero_before_pytest_reports_anything_is_not_a_pass(rws):
    failing_project(rws)
    (rws.root / "timelog" / "parser.py").write_text("import os\nos._exit(0)\n")
    r = run_tests(rws)
    assert r.flags["tests_passed"] is False  # 結束碼是 0，但輸出裡沒有 pytest 的 passed 摘要


def test_workspace_modules_can_still_be_imported_by_the_tests(rws):
    write_test(rws, "test_ok.py", "from timelog import parser\n\ndef test_ok():\n    assert parser.x == 1\n")
    (rws.root / "timelog").mkdir()
    (rws.root / "timelog" / "__init__.py").write_text("")
    (rws.root / "timelog" / "parser.py").write_text("x = 1\n")
    assert run_tests(rws).flags["tests_passed"] is True


def test_a_passing_project_that_prints_after_pytest_finishes_is_still_a_pass(rws):
    write_test(rws, "test_ok.py", "from timelog import parser\n\ndef test_ok():\n    assert parser.x == 1\n")
    (rws.root / "timelog").mkdir()
    (rws.root / "timelog" / "__init__.py").write_text("")
    (rws.root / "timelog" / "parser.py").write_text("import atexit\nx = 1\natexit.register(lambda: print('bye'))\n")
    r = run_tests(rws)
    assert r.output.strip().splitlines()[-1] == "bye"
    assert r.flags["tests_passed"] is True


def test_a_line_that_only_mentions_passed_is_not_a_summary(rws):
    failing_project(rws)
    (rws.root / "timelog" / "parser.py").write_text("print('all tests passed')\nimport os\nos._exit(0)\n")
    assert run_tests(rws).flags["tests_passed"] is False


def test_a_run_where_every_test_is_skipped_is_not_a_pass(rws):
    write_test(rws, "test_skip.py", "import pytest\n\n@pytest.mark.skip\ndef test_skipped():\n    pass\n")
    r = run_tests(rws)
    assert r.flags["tests_passed"] is False  # 什麼都沒驗證到


# ---- grep：對應規格的 grep searches file contents ----


def grep(w, pattern, **args):
    return w.call("grep", {"pattern": pattern, **args})


# Scenario: Find a definition
def test_grep_finds_a_definition(tws):
    r = grep(tws, "def parse_duration")
    assert r.ok and r.output == "timelog/parser.py:7:def parse_duration(text):"


def test_grep_results_are_sorted_by_path_then_line(rws):
    touch(rws.root, "b/two.py", "a/one.py")
    (rws.root / "a" / "one.py").write_text("x = 1\nx = 2\n")
    (rws.root / "b" / "two.py").write_text("x = 3\n")
    assert grep(rws, "x =").output.splitlines() == ["a/one.py:1:x = 1", "a/one.py:2:x = 2", "b/two.py:1:x = 3"]


# Scenario: Invalid pattern
def test_grep_invalid_pattern_is_an_error(rws):
    r = grep(rws, "(")
    assert not r.ok and "invalid regular expression" in r.output and "blocked" not in r.flags


def test_grep_empty_pattern_is_an_error(rws):
    r = grep(rws, "")
    assert not r.ok and "must not be empty" in r.output


# Scenario: Output cap
def test_grep_shows_100_lines_and_counts_the_rest(rws):
    (rws.root / "many.txt").write_text("hit\n" * 120)
    lines = grep(rws, "hit").output.splitlines()
    assert len(lines) == 101
    assert lines[0] == "many.txt:1:hit" and lines[99] == "many.txt:100:hit"
    assert lines[100].startswith("[20 more matches omitted")


# Scenario: Catastrophic backtracking
def test_grep_gives_up_on_a_pattern_that_backtracks_forever(rws):
    # (a+)+$ 是經典例子，但 regex 套件對它有最佳化，40 個 a 一下子就比完；(a|aa)+$ 才會真的卡住（見設計文件）
    (rws.root / "slow.txt").write_text("a" * 40 + "!\n")
    started = time.monotonic()
    r = grep(rws, "(a|aa)+$")
    assert time.monotonic() - started < 5
    assert not r.ok and "pattern too slow" in r.output


# Scenario: Symbolic link to a file outside the workspace
def test_grep_does_not_read_through_symbolic_links(rws):
    (rws.root.parent / "secret").write_text("password\n")
    (rws.root / "link_secret").symlink_to("../secret")
    assert grep(rws, "password").output == "no matches"
    r = grep(rws, "password", path="link_secret")  # 明確指定連結本身，路徑守門會擋
    assert not r.ok and r.flags == {"blocked": True}


def test_grep_skips_files_that_are_not_utf8_text(rws):
    (rws.root / "blob.bin").write_bytes(b"needle \xff\xfe\x00")
    (rws.root / "note.txt").write_text("needle\n")
    assert grep(rws, "needle").output == "note.txt:1:needle"


def test_grep_skips_ignored_directories(rws):
    touch(rws.root, ".git/config", "pkg/__pycache__/x.py", "pkg/real.py")
    for rel in (".git/config", "pkg/__pycache__/x.py", "pkg/real.py"):
        (rws.root / rel).write_text("needle\n")
    assert grep(rws, "needle").output == "pkg/real.py:1:needle"


def test_grep_can_be_limited_to_a_directory_or_a_file(tws):
    assert grep(tws, "text", path="tests").output == "no matches"
    assert grep(tws, "def parse_duration", path="timelog/parser.py").output == "timelog/parser.py:7:def parse_duration(text):"


def test_grep_path_errors(rws):
    assert not grep(rws, "x", path="nope").ok and "path not found" in grep(rws, "x", path="nope").output
    r = grep(rws, "x", path="..")
    assert not r.ok and r.flags == {"blocked": True}


# Scenario: 整體時間上限（測試中把上限縮短來驗證）
def test_grep_stops_after_the_overall_time_limit(rws, monkeypatch):
    monkeypatch.setattr("fixlab.tools.GREP_TOTAL_TIMEOUT_S", 0)
    (rws.root / "many.txt").write_text("hit\n" * 50)
    r = grep(rws, "hit")
    assert r.ok and "search stopped after 0s" in r.output
    assert r.output.startswith("many.txt:1:hit")  # 已經找到的結果還在
    assert len(r.output.splitlines()) < 50


def test_grep_shortens_long_lines_in_the_output(rws):
    (rws.root / "long.txt").write_text("needle " + "x" * 500 + "\n")
    shown = grep(rws, "needle").output
    assert shown == "long.txt:1:needle " + "x" * 193 + "..."  # 前 200 字元加 ...


def test_grep_only_matches_the_first_2000_characters_of_a_line(rws):
    (rws.root / "wide.txt").write_text("x" * 2500 + "needle\n")
    assert grep(rws, "needle").output == "no matches"


def test_grep_is_case_sensitive_unless_asked_otherwise(rws):
    (rws.root / "a.txt").write_text("Hello\n")
    assert grep(rws, "hello").output == "no matches"
    assert grep(rws, "(?i)hello").output == "a.txt:1:Hello"


def test_grep_is_offered_to_the_model(rws):
    spec = {s["function"]["name"]: s["function"] for s in rws.tool_specs()}["grep"]
    assert spec["parameters"]["required"] == ["pattern"]
    assert set(spec["parameters"]["properties"]) == {"pattern", "path"}


# ---- write_file：對應規格的 write_file creates files and guards overwrites ----


def write(w, path, content):
    return w.call("write_file", {"path": path, "content": content})


# Scenario: Create a new file
def test_write_creates_a_new_file_and_its_parent_directories(rws):
    r = write(rws, "notes/deep/summary.txt", "hello\n")
    assert r.ok and r.output == "created notes/deep/summary.txt (6 characters)"
    assert (rws.root / "notes" / "deep" / "summary.txt").read_text() == "hello\n"


# Scenario: Overwrite without reading
def test_write_refuses_to_overwrite_a_file_that_was_never_read(rws):
    target = write_parser(rws.root, "x = 1\n")
    r = write(rws, "timelog/parser.py", "x = 2\n")
    assert not r.ok and "read the file first" in r.output and "blocked" not in r.flags
    assert target.read_text() == "x = 1\n"


# Scenario: Overwrite after a full read
def test_write_overwrites_after_a_full_read(rws):
    target = write_parser(rws.root, "x = 1\n")
    read(rws, "timelog/parser.py")
    r = write(rws, "timelog/parser.py", "x = 2\n")
    assert r.ok and r.output == "overwrote timelog/parser.py (6 characters)"
    assert target.read_text() == "x = 2\n"


# Scenario: Partial read does not count
def test_write_does_not_accept_a_partial_read(rws):
    target = write_parser(rws.root, "a = 1\nb = 2\nc = 3\n")
    read(rws, "timelog/parser.py", start_line=1, end_line=2)
    assert not write(rws, "timelog/parser.py", "x = 2\n").ok
    assert target.read_text() == "a = 1\nb = 2\nc = 3\n"


# Scenario: Truncated read does not count
def test_write_does_not_accept_a_truncated_read(rws):
    big = rws.root / "big.txt"
    big.write_text("".join(f"{i:04d} {'x' * 70}\n" for i in range(1000)))  # 超過 20000 字元，讀會被截斷
    read(rws, "big.txt")
    r = write(rws, "big.txt", "replaced\n")
    assert not r.ok and "read the file first" in r.output
    assert big.read_text().startswith("0000 ")


# Scenario: Edit makes the earlier read stale
def test_write_after_an_edit_needs_a_new_read(rws):
    write_parser(rws.root, "x = 1\n")
    read(rws, "timelog/parser.py")
    assert edit(rws, "timelog/parser.py", "x = 1", "x = 5").ok
    r = write(rws, "timelog/parser.py", "x = 9\n")
    assert not r.ok and "read the file first" in r.output


# Scenario: File changed behind the model's back
def test_write_refuses_when_the_file_changed_after_it_was_read(rws):
    target = write_parser(rws.root, "x = 1\n")
    read(rws, "timelog/parser.py")
    target.write_text("x = 1\n# 使用者在編輯器裡加的註解\n")  # 讀過之後，被別人改了
    r = write(rws, "timelog/parser.py", "x = 2\n")
    assert not r.ok and "changed since you read it" in r.output and "read the file first" in r.output
    assert "使用者" in target.read_text()  # 別人的修改沒有被蓋掉
    # 重新讀過之後就可以了
    read(rws, "timelog/parser.py")
    assert write(rws, "timelog/parser.py", "x = 2\n").ok


def test_a_successful_write_counts_as_having_read_the_file(rws):
    write_parser(rws.root, "x = 1\n")
    read(rws, "timelog/parser.py")
    assert write(rws, "timelog/parser.py", "x = 2\n").ok
    assert write(rws, "timelog/parser.py", "x = 3\n").ok  # 模型知道自己剛寫了什麼，不用再讀


def test_a_new_file_created_by_write_can_be_overwritten_again(rws):
    assert write(rws, "new.txt", "one\n").ok
    assert write(rws, "new.txt", "two\n").ok
    assert (rws.root / "new.txt").read_text() == "two\n"


def test_a_failed_read_records_nothing(rws):
    assert not read(rws, "missing.py").ok
    (rws.root / "pkg").mkdir()
    assert not read(rws, "pkg").ok
    assert rws.files_read == {}


def test_write_to_a_directory_is_an_error(rws):
    (rws.root / "pkg").mkdir()
    r = write(rws, "pkg", "x")
    assert not r.ok and "directory" in r.output


def test_write_content_that_cannot_be_encoded_creates_nothing(rws):
    r = write(rws, "new.txt", "\ud800")  # 孤立的 surrogate 不能編成 UTF-8
    assert not r.ok and "UTF-8" in r.output
    assert not (rws.root / "new.txt").exists()


def test_write_outside_the_workspace_is_blocked(rws):
    r = write(rws, "../evil.txt", "x")
    assert not r.ok and r.flags == {"blocked": True}


def test_write_keeps_windows_line_endings_as_given(rws):
    assert write(rws, "crlf.txt", "a\r\nb\r\n").ok
    assert (rws.root / "crlf.txt").read_bytes() == b"a\r\nb\r\n"


def test_write_file_is_offered_to_the_model(rws):
    spec = {s["function"]["name"]: s["function"] for s in rws.tool_specs()}["write_file"]
    assert spec["parameters"]["required"] == ["path", "content"]
    assert "read all of it" in spec["description"]
