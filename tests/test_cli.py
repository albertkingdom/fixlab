# fixlab 最小入口的測試：用假 client，不需要真的 LLM。
# 目前只涵蓋參數與錯誤、每步輸出、快照 diff。結束後再跑 run_tests 的部分，等 run_tests 完成後再補。
# 一律先把 fixture 複製到暫存目錄再當 PATH：fixlab 會直接修改指定的目錄。
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from fixlab.cli import DEFAULT_TASK, changed_files, diff_report, fixlab_commit, main, take_snapshot
from fixlab.loop import SYSTEM_PROMPT
from fixlab.sandbox import sandbox_available
from fixlab.tools import START_PYTEST
from fixlab.workspace import Workspace
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


# Scenario: Explicit task without a path
@pytest.mark.parametrize("task", ["explain parser", ""])
def test_task_without_path_is_refused(project, home, monkeypatch, capsys, task):
    # 一次性模式寫檔不會詢問，所以要明確指定目標目錄，不能默默用目前目錄。
    monkeypatch.chdir(project)
    before = take_snapshot(project)
    client = FakeClient([("Done.", None)])

    assert main(["--model", "m", "--task", task], client=client) == 2

    out, err = capsys.readouterr()
    assert "--task needs PATH" in err and "fixlab> " not in out
    assert not re.search(r"(?<![\w-])-i\b", err)  # -i 會忽略 --task 的文字，不能拿來當替代做法
    assert client.sent == []
    assert take_snapshot(project) == before
    assert not (home / ".fixlab").exists()


# Scenario: Started from the home directory
@pytest.mark.parametrize("where", ["home", "above"])
@pytest.mark.parametrize("log_dir", [False, True])
def test_start_from_home_or_above_without_path_is_refused(home, tmp_path, monkeypatch, capsys, where, log_dir):
    # 沒給 PATH 時，家目錄或它的上層不能當工作區；另外指定 --log-dir 也一樣，否則加個參數就能繞過。
    monkeypatch.chdir(home if where == "home" else home.parent)
    client = FakeClient([])
    extra = ["--log-dir", str(tmp_path / "logs")] if log_dir else []

    assert main(["--model", "m", *extra], client=client) == 2

    err = capsys.readouterr().err
    assert "is your home directory or above; run fixlab from a project directory or pass PATH" in err
    assert str(home / ".fixlab" / "runs") not in err  # 原因是目錄位置，不是事件檔放在哪
    assert "use --log-dir" not in err
    assert client.sent == []


def test_start_below_home_falls_back_to_the_log_dir_check(home, monkeypatch, capsys):
    # ~/.fixlab 在家目錄底下，不是家目錄規則的範圍；它包住預設事件檔目錄，由原本的檢查擋下並建議 --log-dir。
    (home / ".fixlab").mkdir()
    monkeypatch.chdir(home / ".fixlab")

    assert main(["--model", "m"], client=FakeClient([])) == 2

    err = capsys.readouterr().err
    assert "use --log-dir" in err and "home directory" not in err


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


# ── One-shot mode never asks（對應 tool-permissions 規格）──────────────────


# Scenario: Unattended run
def test_one_shot_never_asks_and_nothing_is_denied(project, home, monkeypatch):
    def no_input(prompt=""):
        raise AssertionError("one-shot mode must not ask the user anything")

    monkeypatch.setattr("builtins.input", no_input)
    exit_code = run_fix(project, FakeClient(FIX_SCRIPT))

    assert exit_code == 0
    flags = [call["flags"] for line in event_lines(home) if line["event"] == "trace"
             for call in line["record"].get("tool_calls", [])]
    assert all("denied" not in f for f in flags)


# ── 實驗條件：fixlab_commit 只認 fixlab 自己的 git repo ────────────────────

def git_repo_with_a_commit(folder):
    import subprocess
    folder.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(folder)], check=True)
    subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "-m", "first"], check=True)
    done = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def test_fixlab_commit_is_the_commit_of_the_fixlab_repo_itself(tmp_path, monkeypatch):
    commit = git_repo_with_a_commit(tmp_path / "fixlab")
    monkeypatch.setattr("fixlab.cli.FIXLAB_ROOT", tmp_path / "fixlab")
    assert fixlab_commit() == commit


def test_fixlab_commit_is_none_when_fixlab_sits_inside_someone_elses_repo(tmp_path, monkeypatch):
    git_repo_with_a_commit(tmp_path / "project")
    nested = tmp_path / "project" / ".venv" / "site-packages"
    nested.mkdir(parents=True)
    monkeypatch.setattr("fixlab.cli.FIXLAB_ROOT", nested)
    assert fixlab_commit() is None  # 不能把別人專案的 commit 記成 fixlab 的版本


# ── 隱藏工具與請求選項：對應 agent-tools 的 Tools can be hidden from the model 與 run-telemetry 的 run_start records the request options ──

def test_a_hidden_tool_is_not_offered_and_a_call_to_it_is_rejected(project, home, capsys):
    client = FakeClient([(None, [native("run_tests")]), ("Done.", None)])
    run_fix(project, client, "--hide-tool", "run_tests")

    out = capsys.readouterr().out
    assert "run_tests" not in [spec["function"]["name"] for spec in client.tools[0]]
    traces = [line["record"] for line in event_lines(home) if line["event"] == "trace"]
    assert traces[0]["event"] == "invalid_tool_call" and "run_tests" in str(traces[0]["parse_errors"])
    assert "final test run:" in out and "RESULT:" in out  # fixlab 自己結束時跑的最終測試不受隱藏影響


def test_hiding_an_unknown_tool_exits_2_and_creates_no_event_file(project, home, capsys):
    assert run_fix(project, FakeClient([]), "--hide-tool", "bash") == 2

    assert "bash" in capsys.readouterr().err
    assert not list(home.glob("**/events.jsonl"))


def test_run_start_records_the_request_options_and_hidden_tools(project, home):
    extra = '{"provider": {"order": ["Venice"], "allow_fallbacks": false}}'
    run_fix(project, FakeClient([("Done.", None)]),
            "--hide-tool", "run_tests", "--temperature", "0.2", "--extra-body", extra)

    run_start = event_lines(home)[0]
    assert run_start["hidden_tools"] == ["run_tests"]
    assert run_start["temperature"] == 0.2
    assert run_start["extra_body"] == {"provider": {"order": ["Venice"], "allow_fallbacks": False}}
    assert run_start["schema"] == 1


def test_run_start_options_default_to_empty(project, home):
    run_fix(project, FakeClient([("Done.", None)]))

    run_start = event_lines(home)[0]
    assert run_start["hidden_tools"] == [] and run_start["temperature"] is None and run_start["extra_body"] is None


@pytest.mark.parametrize("text", ["[1, 2]", "not json", '"a string"'])
def test_an_extra_body_that_is_not_a_json_object_exits_2_and_creates_no_file(project, home, capsys, text):
    assert run_fix(project, FakeClient([]), "--extra-body", text) == 2

    assert "--extra-body" in capsys.readouterr().err
    assert not list(home.glob("**/events.jsonl"))


def test_temperature_and_extra_body_reach_every_request(project):
    client = FakeClient([(None, [native("list_files")]), ("Done.", None)])
    run_fix(project, client, "--temperature", "0.2", "--extra-body", '{"seed": 7}')

    assert len(client.kwargs) == 2
    assert all(kw["temperature"] == 0.2 and kw["extra_body"] == {"seed": 7} for kw in client.kwargs)


# ── 額外的 system prompt：對應 run-telemetry 的 The system prompt can be extended from the command line ──

# Scenario: The option is recorded
def test_the_extra_system_prompt_is_recorded_and_sent(project, home):
    client = FakeClient([("Done.", None)])
    run_fix(project, client, "--system-prompt-extra", "Finish once the fix is made.")

    assert event_lines(home)[0]["system_prompt_extra"] == "Finish once the fix is made."
    assert client.sent[0][0] == {"role": "system", "content": SYSTEM_PROMPT + "\n\nFinish once the fix is made."}


# Scenario: The option is not given
def test_without_the_option_the_system_prompt_is_the_default_and_the_key_is_null(project, home):
    client = FakeClient([("Done.", None)])
    run_fix(project, client)

    assert event_lines(home)[0]["system_prompt_extra"] is None
    assert client.sent[0][0] == {"role": "system", "content": SYSTEM_PROMPT}


# Scenario: An empty value is refused
@pytest.mark.parametrize("text", ["", "   "])
def test_an_empty_extra_system_prompt_exits_2_and_creates_no_file(project, home, capsys, text):
    assert run_fix(project, FakeClient([]), "--system-prompt-extra", text) == 2

    assert "--system-prompt-extra" in capsys.readouterr().err
    assert not list(home.glob("**/events.jsonl"))


def test_an_extra_system_prompt_with_a_visible_character_is_accepted_as_it_is(project, home):
    run_fix(project, FakeClient([("Done.", None)]), "--system-prompt-extra", " a ")

    assert event_lines(home)[0]["system_prompt_extra"] == " a "


# ── test-interpreter：The test interpreter is checked before the run starts ──


def fake_python(folder, body):
    """一個假的直譯器：shell 腳本，照 body 回應啟動前的檢查。"""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "python"
    script.write_text("#!/bin/sh\n" + body + "\n")
    script.chmod(0o755)
    # 基底指向真的 Python 安裝（有標準函式庫），檢查才會走到執行這支腳本的那一步
    (folder.parent / "pyvenv.cfg").write_text(f"home = {Path(sys.executable).resolve().parent}\n")
    return script


def assert_refused_before_start(home, capsys, client, *words):
    err = capsys.readouterr().err
    for word in words:
        assert word in err, err
    assert client.sent == []
    assert not (home / ".fixlab").exists()  # 沒有事件檔


# Scenario: Interpreter path does not exist
def test_missing_interpreter_is_refused(project, home, capsys):
    client = FakeClient([("Done.", None)])
    assert main([str(project), "--model", "m", "--python", "/no/such/python"], client=client) == 2
    assert_refused_before_start(home, capsys, client, "/no/such/python")


# Scenario: Interpreter older than 3.11
def test_old_interpreter_is_refused(project, home, tmp_path, capsys):
    python = fake_python(tmp_path / "old" / "bin", "echo FIXLAB-CHECK 3.10")
    client = FakeClient([("Done.", None)])
    assert main([str(project), "--model", "m", "--python", str(python)], client=client) == 2
    assert_refused_before_start(home, capsys, client, str(python), "3.10", "3.11")


# Scenario: Environment without pytest
def test_interpreter_without_pytest_is_refused(project, home, tmp_path, capsys):
    python = fake_python(tmp_path / "nopytest" / "bin", "echo FIXLAB-CHECK 3.12; echo \"ModuleNotFoundError: No module named 'pytest'\" >&2; exit 1")
    client = FakeClient([("Done.", None)])
    assert main([str(project), "--model", "m", "--python", str(python)], client=client) == 2
    assert_refused_before_start(home, capsys, client, str(python), "pytest")


# Scenario: A virtual environment in the project is not used by itself
def test_a_project_venv_is_neither_used_nor_executed(project, home, capsys):
    # 專案裡的 .venv/bin/python 是一支會留下記號的腳本：它被執行過，記號檔就會出現。
    marker = project.parent / "venv-was-executed"
    fake_python(project / ".venv" / "bin", f"touch {marker}; echo 3.12")
    main([str(project), "--model", "m"], client=FakeClient([("Done.", None)]))
    assert not marker.exists()
    start = event_lines(home)[0]
    assert start["test_python"] == {"path": sys.executable, "source": "default",
                                    "base": str(Workspace(project).base)}


def venv_like_fixlab_s(folder):
    """一個指向 fixlab 自己 venv 的「環境」：裡面有 pytest，又能驗證 run_tests 用的是指定的路徑。"""
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.symlink_to(Path(sys.executable).parent.parent)
    return folder / "bin" / "python"


def spy_on_pytest_runs(monkeypatch):
    used = []
    real_run = subprocess.run

    def spy(command, *args, **kwargs):
        used.append(command)
        return real_run(command, *args, **kwargs)

    # monkeypatch 換掉的是共用的 subprocess.run，git 與啟動前檢查也會經過；只看啟動 pytest 的那幾次。
    monkeypatch.setattr("fixlab.tools.subprocess.run", spy)
    return lambda: [command for command in used if START_PYTEST in command]


# Scenario: Interpreter given on the command line，以及 run_start records the test interpreter
def test_given_interpreter_runs_the_tests_and_is_recorded(project, home, tmp_path, monkeypatch):
    python = venv_like_fixlab_s(tmp_path / "envs" / "proj")
    pytest_runs = spy_on_pytest_runs(monkeypatch)
    main([str(project), "--model", "m", "--python", str(python)], client=FakeClient([("Done.", None)]))
    assert pytest_runs() and all(str(python) in command for command in pytest_runs()), pytest_runs()
    start = event_lines(home)[0]
    assert start["test_python"]["path"] == str(python)
    assert start["test_python"]["source"] == "option"
    assert start["test_python"]["base"] == str(Workspace(project, python=str(python)).base)


# Scenario: Relative interpreter path
def test_relative_interpreter_path_is_made_absolute(project, home, tmp_path, monkeypatch):
    python = venv_like_fixlab_s(tmp_path / "envs" / "proj")
    monkeypatch.chdir(tmp_path)
    pytest_runs = spy_on_pytest_runs(monkeypatch)
    main([str(project), "--model", "m", "--python", "envs/proj/bin/python"], client=FakeClient([("Done.", None)]))
    assert pytest_runs() and all(str(python) in command for command in pytest_runs()), pytest_runs()
    assert event_lines(home)[0]["test_python"]["path"] == str(python)


# Scenario: Environment that contains the workspace
def test_an_environment_that_contains_the_project_is_refused(project, home, capsys):
    python = fake_python(project / "bin", "echo FIXLAB-CHECK 3.12")
    client = FakeClient([("Done.", None)])
    assert main([str(project), "--model", "m", "--python", str(python)], client=client) == 2
    assert_refused_before_start(home, capsys, client, "contains the project")


# 沒有沙箱的平台：不計算、不檢查基底（標準函式庫的位置因平台而異，而且沒有沙箱要放行它）
def test_without_a_sandbox_the_base_is_not_checked(project, home, tmp_path, monkeypatch):
    monkeypatch.setattr("fixlab.sandbox.SANDBOX_EXEC", None)
    python = tmp_path / "odd" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(f'#!/bin/sh\nexec {sys.executable} "$@"\n')
    python.chmod(0o755)
    assert main([str(project), "--model", "m", "--python", str(python)], client=FakeClient([("Done.", None)])) != 2
    assert event_lines(home)[0]["test_python"]["base"] is None


# Scenario: Interpreter that goes through a link inside the project（第三輪 review 重現的攻擊）
def test_an_interpreter_that_hops_through_the_project_is_refused(project, home, capsys):
    (project / "scripts").mkdir()
    (project / "scripts" / "py").symlink_to(Path(sys.executable).resolve())
    (project / ".venv" / "bin").mkdir(parents=True)
    (project / ".venv" / "pyvenv.cfg").write_text(f"home = {Path(sys.executable).resolve().parent}\n")
    (project / ".venv" / "bin" / "python").symlink_to(Path("../../scripts/py"))
    client = FakeClient([("Done.", None)])
    assert main([str(project), "--model", "m", "--python", str(project / ".venv" / "bin" / "python")], client=client) == 2
    assert_refused_before_start(home, capsys, client, "scripts/py")
