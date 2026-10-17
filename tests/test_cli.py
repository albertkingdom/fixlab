# fixlab 最小入口的測試：用假 client，不需要真的 LLM。
# 目前只涵蓋參數與錯誤、每步輸出、快照 diff。結束後再跑 run_tests 的部分，等 run_tests 完成後再補。
# 一律先把 fixture 複製到暫存目錄再當 PATH：fixlab 會直接修改指定的目錄。
import json

import pytest

from fixlab.cli import DEFAULT_TASK, changed_files, diff_report, main, take_snapshot
from fixlab.sandbox import sandbox_available
from test_fixture import BUGGY, FIXED, copy_fixture  # 把 timelog 複製到暫存目錄；bug 與修法
from test_loop import FakeClient, native  # 依序回傳劇本回覆的假 client


@pytest.fixture
def project(tmp_path):
    return copy_fixture(tmp_path)


@pytest.fixture(autouse=True)
def home(tmp_path_factory, monkeypatch):
    """事件檔預設寫在 ~/.fixlab/runs：CLI 的測試一律把家目錄換成暫存目錄，不能寫進真的。
    這個資料夾和 project 是兄弟，不是上下層，沙箱擋家目錄時才不會連 project 一起擋掉。"""
    folder = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(folder))
    return folder


def event_lines(home):
    """這次執行寫出的事件檔，每行解析成 dict。"""
    (path,) = (home / ".fixlab" / "runs").glob("*/events.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def run_fix(project, client, *extra):
    return main([str(project), "--model", "m", *extra], client=client)


# ── main：端到端 ──────────────────────────────────────────────────────────


def test_read_only_run_leaves_directory_unchanged(project, capsys):
    before = take_snapshot(project)
    client = FakeClient([(None, [native("read_file", path="timelog/parser.py")]), ("Done.", None)])

    code = run_fix(project, client)

    out, err = capsys.readouterr()
    assert code == 1  # 沒有人修 bug，最後那次測試還是失敗
    assert take_snapshot(project) == before
    assert "no changes" in out
    assert "stop reason: done  steps: 2" in out
    assert f"editing in place: {project}" in err


def test_each_tool_call_prints_one_line_with_name_and_ok(project, capsys):
    client = FakeClient([
        (None, [native("list_files")]),
        (None, [native("read_file", path="timelog/missing.py")]),
        ("Done.", None),
    ])

    run_fix(project, client)

    step_lines = [line for line in capsys.readouterr().err.splitlines() if "ok=" in line]
    assert step_lines == ["list_files  ok=True  flags={}", "read_file  ok=False  flags={}"]


def test_symlink_pointing_outside_is_blocked(project, tmp_path, capsys):
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret-value\n")
    (project / "link.txt").symlink_to(secret)
    client = FakeClient([(None, [native("read_file", path="link.txt")]), ("Done.", None)])

    run_fix(project, client)

    err = capsys.readouterr().err
    assert "read_file  ok=False  flags={'blocked': True}" in err
    tool_message = client.sent[1][-1]["content"]  # 模型第二次請求看到的工具結果
    assert "top-secret-value" not in tool_message


def test_agent_cannot_edit_test_files(project, capsys):
    before = take_snapshot(project)
    client = FakeClient([
        (None, [native("edit_file", path="tests/test_report.py", old_string="assert", new_string="pass")]),
        ("Done.", None),
    ])

    run_fix(project, client)

    assert "edit_file  ok=False  flags={'blocked': True, 'protected_write': True}" in capsys.readouterr().err
    assert take_snapshot(project) == before  # 測試檔沒被動到


def test_default_task_can_be_overridden(project):
    default_client = FakeClient([("Done.", None)])
    run_fix(project, default_client)
    assert default_client.sent[0][1] == {"role": "user", "content": DEFAULT_TASK}

    custom_client = FakeClient([("Done.", None)])
    run_fix(project, custom_client, "--task", "Look at report.py")
    assert custom_client.sent[0][1] == {"role": "user", "content": "Look at report.py"}


# ── main：結束後自己再跑一次測試 ──────────────────────────────────────────


def test_done_without_testing_still_shows_the_failing_tests(project, capsys):
    client = FakeClient([("Fixed it!", None)])  # 模型直接宣稱完成，什麼都沒做

    code = run_fix(project, client)

    out = capsys.readouterr().out
    assert code == 1
    assert "1 failed" in out
    assert out.rstrip().splitlines()[-1] == "RESULT: tests FAILED"  # 結論在最後一行


def test_fixed_project_shows_passing_tests_and_only_the_fix_in_the_diff(project, capsys):
    client = FakeClient([
        (None, [native("edit_file", path="timelog/parser.py", old_string=BUGGY, new_string=FIXED)]),
        ("Fixed it!", None),
    ])

    code = run_fix(project, client)

    out = capsys.readouterr().out
    assert code == 0
    assert out.rstrip().splitlines()[-1] == "RESULT: tests passed"
    assert out.count("--- a/") == 1 and "--- a/timelog/parser.py" in out  # 差異裡只有 parser.py


def test_a_model_that_keeps_failing_is_stopped_and_the_result_says_so(project, capsys):
    client = FakeClient([(None, [native("read_file", path="nope.py")])] * 4)

    code = run_fix(project, client)

    out = capsys.readouterr().out
    assert "stop reason: stuck  steps: 3" in out
    assert out.rstrip().splitlines()[-1] == "RESULT: tests FAILED" and code == 1


@pytest.mark.skipif(not sandbox_available(), reason="sandbox-exec is only available on macOS")
def test_a_source_edit_that_rewrites_the_tests_cannot_fake_a_pass(project, capsys):
    cheat = 'import pathlib\npathlib.Path("tests/test_report.py").write_text("def test_ok():\\n    assert True\\n")\n'
    before = take_snapshot(project)
    client = FakeClient([
        (None, [native("edit_file", path="timelog/parser.py", old_string="import re\n", new_string="import re\n" + cheat)]),
        (None, [native("run_tests")]),
        ("Done.", None),
    ])

    code = run_fix(project, client)

    out = capsys.readouterr().out
    assert code == 1
    assert out.rstrip().splitlines()[-1] == "RESULT: tests FAILED"
    assert take_snapshot(project)["tests/test_report.py"] == before["tests/test_report.py"]  # 測試檔沒被改寫


def test_files_touched_by_the_final_test_run_show_up_in_the_diff(project, capsys):
    (project / "tests" / "test_side_effect.py").write_text(
        "def test_writes_a_file():\n    open('side_effect.txt', 'w').write('hi')\n")

    run_fix(project, FakeClient([("Done.", None)]))

    assert "new file: side_effect.txt" in capsys.readouterr().out


# ── main：錯誤情境 ────────────────────────────────────────────────────────


def test_missing_api_key_is_an_error(project, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    code = main([str(project), "--model", "m"])  # 沒有注入 client，會走建立真 client 的路

    assert code == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_missing_model_is_an_error(project, monkeypatch, capsys):
    monkeypatch.delenv("FIXLAB_MODEL", raising=False)
    client = FakeClient([])

    code = main([str(project)], client=client)

    assert code == 2
    assert "no model" in capsys.readouterr().err
    assert client.sent == []  # agent 沒有被啟動


def test_path_that_is_not_a_directory_is_an_error(tmp_path, capsys):
    client = FakeClient([])

    code = run_fix(tmp_path / "nope", client)

    assert code == 2
    assert "not a directory" in capsys.readouterr().err
    assert client.sent == []


# ── take_snapshot ─────────────────────────────────────────────────────────


def test_snapshot_skips_ignored_dirs_and_symlinks(tmp_path):
    (tmp_path / "a.py").write_bytes(b"x = 1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_bytes(b"y = 2\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_bytes(b"[core]\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    (tmp_path / "link.py").symlink_to(tmp_path / "a.py")

    assert take_snapshot(tmp_path) == {"a.py": b"x = 1\n", "sub/b.py": b"y = 2\n"}


# ── diff_report ───────────────────────────────────────────────────────────


def test_diff_shows_modified_file():
    out = diff_report({"a.py": b"x = 1\n"}, {"a.py": b"x = 2\n"})
    assert "--- a/a.py" in out and "+++ b/a.py" in out
    assert "-x = 1" in out and "+x = 2" in out


def test_diff_shows_new_file():
    out = diff_report({}, {"new.py": b"hi\n"})
    assert "new file: new.py" in out and "+hi" in out


def test_diff_shows_deleted_file():
    out = diff_report({"gone.py": b"bye\n"}, {})
    assert "deleted file: gone.py" in out and "-bye" in out


def test_diff_marks_non_utf8_file_as_binary():
    out = diff_report({"blob.bin": b"\xff\xfe"}, {"blob.bin": b"\x00\xff"})
    assert out == "binary file changed: blob.bin"


def test_diff_shows_tampered_test_file():
    out = diff_report({"tests/test_report.py": b"assert 1 == 2\n"}, {"tests/test_report.py": b"assert True\n"})
    assert "tests/test_report.py" in out and "+assert True" in out


def test_diff_skips_unchanged_files():
    out = diff_report({"a.py": b"x = 1\n", "b.py": b"y\n"}, {"a.py": b"x = 2\n", "b.py": b"y\n"})
    assert "b.py" not in out


def test_diff_says_no_changes_when_nothing_changed():
    assert diff_report({"a.py": b"x\n"}, {"a.py": b"x\n"}) == "no changes"


def test_diff_explains_final_newline_only_change():
    out = diff_report({"a.py": b"x\n"}, {"a.py": b"x"})
    assert out == "a.py: only line endings or the final newline changed"


def test_the_sandbox_status_is_printed_at_the_start(project, capsys):
    run_fix(project, FakeClient([("Done.", None)]))
    assert "sandbox: " in capsys.readouterr().err  # 沙箱是安全功能，開或沒開都要讓使用者看得到


# ── 事件檔：對應 run-telemetry 規格（一次性模式）──────────────────────────────

FIX_SCRIPT = [
    (None, [native("read_file", path="timelog/parser.py")]),
    (None, [native("edit_file", path="timelog/parser.py", old_string=BUGGY, new_string=FIXED)]),
    ("Fixed.", None),
]


# Scenario: A one-task run
def test_one_shot_run_writes_run_start_task_start_traces_and_task_end(project, home, capsys):
    exit_code = run_fix(project, FakeClient(FIX_SCRIPT))

    assert exit_code == 0
    lines = event_lines(home)
    assert [line["event"] for line in lines] == ["run_start", "task_start", "trace", "trace", "trace", "task_end"]
    run_start, task_start, *traces, task_end = lines

    assert run_start["schema"] == 1 and run_start["mode"] == "once" and run_start["model"] == "m"
    assert run_start["path"] == str(project.resolve()) and run_start["max_steps"] == 20
    assert run_start["max_tokens"] == 8192 and run_start["meta"] == {}
    assert run_start["sandbox"].startswith(("on", "OFF"))
    assert {"fixlab_commit", "python", "openai", "base_url"} <= run_start.keys()

    assert task_start["task"] == 1 and task_start["text"] == DEFAULT_TASK
    assert [t["record"]["step"] for t in traces] == [1, 2, 3] and all(t["task"] == 1 for t in traces)
    assert traces[2]["record"]["event"] == "done"

    assert task_end["task"] == 1 and task_end["stop_reason"] == "done" and task_end["steps"] == 3
    assert task_end["prompt_tokens"] == 30 and task_end["completion_tokens"] == 15
    assert task_end["counters"] == {}  # 這個劇本沒有 parse 錯誤、沒被擋、也沒跑 run_tests
    assert "log: " in capsys.readouterr().err


# Scenario: The model fixed the bug
def test_task_end_has_the_final_test_result_and_the_changed_files(project, home):
    run_fix(project, FakeClient(FIX_SCRIPT))

    task_end = event_lines(home)[-1]
    assert task_end["final_tests"] == {"tests_passed": True, "timed_out": False}
    assert task_end["changed_files"] == {"added": [], "modified": ["timelog/parser.py"], "deleted": []}


def test_a_run_that_fixes_nothing_reports_failing_tests_and_no_changes(project, home):
    exit_code = run_fix(project, FakeClient([("I give up.", None)]))

    assert exit_code == 1
    task_end = event_lines(home)[-1]
    assert task_end["final_tests"]["tests_passed"] is False
    assert task_end["changed_files"] == {"added": [], "modified": [], "deleted": []}


# Scenario: Request failure is a trace line too
def test_a_request_error_is_a_trace_line_and_the_task_ends_with_error(project, home):
    run_fix(project, FakeClient([RuntimeError("boom")]))

    lines = event_lines(home)
    assert [line["event"] for line in lines] == ["run_start", "task_start", "trace", "task_end"]
    assert lines[2]["record"]["event"] == "request_error"
    assert lines[3]["stop_reason"] == "error"


def test_the_log_line_names_the_event_file(project, home, capsys):
    run_fix(project, FakeClient([("Done.", None)]))

    (path,) = (home / ".fixlab" / "runs").glob("*/events.jsonl")
    assert f"log: {path}" in capsys.readouterr().err


def test_changed_files_lists_added_modified_and_deleted_sorted():
    before = {"a.py": b"1", "b.py": b"1", "c.py": b"1"}
    after = {"a.py": b"2", "c.py": b"1", "z.py": b"9", "d.py": b"9"}

    assert changed_files(before, after) == {"added": ["d.py", "z.py"], "modified": ["a.py"], "deleted": ["b.py"]}


# ── --meta 與 --log-dir：對應 Experiment conditions come from --meta、The event log stays outside the target directory ──


def test_meta_values_are_recorded_as_strings_in_run_start(project, home):
    run_fix(project, FakeClient([("Done.", None)]), "--meta", "quantization=Q4_K_M", "--meta", "context_length=32768")

    run_start = event_lines(home)[0]
    assert run_start["meta"] == {"quantization": "Q4_K_M", "context_length": "32768"}


def test_a_meta_value_keeps_any_equals_signs_after_the_first(project, home):
    run_fix(project, FakeClient([("Done.", None)]), "--meta", "note=a=b")
    assert event_lines(home)[0]["meta"] == {"note": "a=b"}


# Scenario: Missing equals sign
def test_meta_without_an_equals_sign_exits_2_and_writes_nothing(project, home, capsys):
    client = FakeClient([("Done.", None)])
    exit_code = run_fix(project, client, "--meta", "quantization")

    assert exit_code == 2
    assert "--meta" in capsys.readouterr().err
    assert not (home / ".fixlab").exists()
    assert client.sent == []  # agent 沒有啟動


# Scenario: Custom log directory
def test_log_dir_option_moves_the_event_file(project, home, tmp_path):
    exp = tmp_path / "exp1"
    run_fix(project, FakeClient([("Done.", None)]), "--log-dir", str(exp))

    assert len(list(exp.glob("*/events.jsonl"))) == 1
    assert not (home / ".fixlab").exists()


# Scenario: Log directory inside the target
def test_a_log_dir_inside_the_target_is_refused(project, home, capsys):
    before = take_snapshot(project)
    exit_code = run_fix(project, FakeClient([("Done.", None)]), "--log-dir", str(project / "logs"))

    assert exit_code == 2
    assert "log directory" in capsys.readouterr().err
    assert take_snapshot(project) == before and not (project / "logs").exists()


def test_the_target_itself_cannot_be_the_log_dir(project):
    assert run_fix(project, FakeClient([("Done.", None)]), "--log-dir", str(project)) == 2


def test_a_symbolic_link_cannot_hide_a_log_dir_inside_the_target(project, tmp_path):
    (project / "inside").mkdir()
    link = tmp_path / "link"
    link.symlink_to(project / "inside")

    assert run_fix(project, FakeClient([("Done.", None)]), "--log-dir", str(link / "logs")) == 2


# Scenario: PATH is the home directory
def test_when_the_target_is_the_home_directory_the_default_log_dir_is_inside_it(home, capsys):
    exit_code = main([str(home), "--model", "m"], client=FakeClient([("Done.", None)]))

    assert exit_code == 2
    assert "log directory" in capsys.readouterr().err


# Scenario: Snapshot diff is not polluted
def test_the_printed_diff_never_lists_the_event_file(project, capsys):
    run_fix(project, FakeClient([("Done.", None)]))

    out = capsys.readouterr().out
    assert ".fixlab" not in out and "events.jsonl" not in out

