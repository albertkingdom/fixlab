# 互動模式的測試：對應 interactive-session 規格。輸入用假的 input() 注入，模型用假 client，不碰真的終端機與 LLM。
import json

import pytest

from fixlab.cli import main
from fixlab.loop import SYSTEM_PROMPT
from test_fixture import copy_fixture
from test_loop import FakeClient, native


@pytest.fixture
def project(tmp_path):
    return copy_fixture(tmp_path)


@pytest.fixture(autouse=True)
def home(tmp_path_factory, monkeypatch):
    """事件檔預設寫在 ~/.fixlab/runs：測試把家目錄換成暫存目錄。與 project 是兄弟，不是上下層。"""
    folder = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(folder))
    return folder


@pytest.fixture
def session(project, monkeypatch):
    """session(client, ["第一句", "第二句"], "--meta", ...)：依序輸入這幾行，輸入用完就是 EOF（Ctrl-D）。
    輸入也可以是例外物件（例如 KeyboardInterrupt），輸入到那一行時就丟出來。"""
    def run(client, inputs, *extra):
        lines = iter(inputs)

        def fake_input(prompt=""):
            print(prompt, end="")  # 真的 input() 會把提示字元印到 stdout
            try:
                line = next(lines)
            except StopIteration:
                raise EOFError from None
            if isinstance(line, BaseException):
                raise line
            return line

        monkeypatch.setattr("builtins.input", fake_input)
        return main([str(project), "--model", "m", "-i", *extra], client=client)
    return run


def event_lines(home):
    (path,) = (home / ".fixlab" / "runs").glob("*/events.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ── Interactive mode is entered with -i ───────────────────────────────────


# Scenario: Without -i nothing changes
def test_without_dash_i_it_is_the_one_shot_command(project, monkeypatch, capsys):
    def no_input(prompt=""):
        raise AssertionError("one-shot mode must not read from the keyboard")

    monkeypatch.setattr("builtins.input", no_input)
    main([str(project), "--model", "m"], client=FakeClient([("Done.", None)]))

    out = capsys.readouterr().out
    assert "fixlab> " not in out and out.rstrip().endswith("RESULT: tests FAILED")


# Scenario: Missing model
def test_interactive_mode_checks_the_model_first(project, monkeypatch, capsys):
    monkeypatch.delenv("FIXLAB_MODEL", raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("the prompt must not be shown"))

    exit_code = main([str(project), "-i"], client=FakeClient([]))

    assert exit_code == 2
    assert "no model" in capsys.readouterr().err


def test_the_prompt_is_shown_and_a_session_ends_with_exit_code_0(session, capsys):
    assert session(FakeClient([]), ["/exit"]) == 0
    assert capsys.readouterr().out.startswith("fixlab> ")


# ── The conversation is kept for the session ──────────────────────────────


# Scenario: A follow-up refers to earlier work
def test_a_follow_up_task_sees_the_earlier_conversation(session):
    client = FakeClient([("Fixed parse_duration.", None), ("Added a docstring.", None)])
    session(client, ["fix the failing test", "add a docstring to that function"])

    assert client.sent[1] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "fix the failing test"},
        {"role": "assistant", "content": "Fixed parse_duration."},
        {"role": "user", "content": "add a docstring to that function"},
    ]


# Scenario: A new session starts empty
def test_a_new_session_does_not_remember_the_old_one(session):
    first = FakeClient([("One.", None)])
    session(first, ["first session task"])
    second = FakeClient([("Two.", None)])
    session(second, ["second session task"])

    assert second.sent[0] == [{"role": "system", "content": SYSTEM_PROMPT},
                              {"role": "user", "content": "second session task"}]


# ── Slash commands and empty lines ────────────────────────────────────────


# Scenario: Reset
def test_reset_clears_the_conversation_but_task_numbers_keep_counting(session, home, capsys):
    client = FakeClient([("First.", None), ("Second.", None)])
    session(client, ["task one", "/reset", "task two"])

    assert client.sent[1] == [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "task two"}]
    assert "conversation cleared" in capsys.readouterr().out
    starts = [line for line in event_lines(home) if line["event"] == "task_start"]
    assert [(s["task"], s["text"]) for s in starts] == [(1, "task one"), (2, "task two")]


# Scenario: Empty line
def test_empty_lines_send_nothing_to_the_model(session):
    client = FakeClient([])
    assert session(client, ["", "   ", "/exit"]) == 0
    assert client.sent == []


def test_end_of_input_ends_the_session_with_exit_code_0(session):
    assert session(FakeClient([]), []) == 0


def test_ctrl_c_at_the_prompt_ends_the_session_with_exit_code_0(session):
    assert session(FakeClient([]), [KeyboardInterrupt()]) == 0


def test_an_unknown_slash_line_is_a_task(session):
    client = FakeClient([("OK.", None)])
    session(client, ["/foo bar"])
    assert client.sent[0][-1] == {"role": "user", "content": "/foo bar"}


# ── No automatic final test run; the final reply is shown ────────────────


# Scenario: A task ends
def test_a_finished_task_shows_the_reply_and_the_summary_but_no_result_line(session, capsys):
    session(FakeClient([("Fixed parse_duration.", None)]), ["fix it"])

    out = capsys.readouterr().out
    assert "Fixed parse_duration." in out and "RESULT:" not in out
    assert out.index("Fixed parse_duration.") < out.index("stop reason: done")  # 先印答案，再印摘要


def test_interactive_events_have_the_interactive_mode_and_no_final_tests(session, home):
    session(FakeClient([("Done.", None)]), ["look around"])

    lines = event_lines(home)
    assert [line["event"] for line in lines] == ["run_start", "task_start", "trace", "task_end"]
    assert lines[0]["mode"] == "interactive"
    assert lines[3]["task"] == 1 and lines[3]["stop_reason"] == "done"
    assert lines[3]["final_tests"] is None and lines[3]["changed_files"] is None


def test_a_task_can_use_the_tools_and_edit_the_project(session, project):
    from test_fixture import BUGGY, FIXED
    client = FakeClient([
        (None, [native("edit_file", path="timelog/parser.py", old_string=BUGGY, new_string=FIXED)]),
        ("Fixed.", None),
    ])
    session(client, ["fix it", "y"])  # edit_file 會先問，回答 y 才執行

    assert FIXED in (project / "timelog" / "parser.py").read_text()


# ── Interrupting a task discards its messages ─────────────────────────────

INTERRUPT_MESSAGE = "interrupted; this task was discarded; files may already have been changed (use /reset to start over)"


# Scenario: Interrupted between a tool call and its result
def test_ctrl_c_in_the_middle_of_a_task_leaves_no_dangling_tool_call(session, home, capsys):
    # 第一個任務：第一次請求回了工具呼叫（已加進對話），第二次請求時使用者按 Ctrl-C
    client = FakeClient([(None, [native("list_files")]), KeyboardInterrupt(), ("Second done.", None)])
    session(client, ["first task", "second task"])

    assert INTERRUPT_MESSAGE in capsys.readouterr().out
    # 對話被截回任務開始前（空的），第二個任務從系統提示重新開始，沒有缺少結果的 tool_calls
    assert client.sent[2] == [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "second task"}]
    ends = [line for line in event_lines(home) if line["event"] == "task_end"]
    assert ends[0]["task"] == 1 and ends[0]["stop_reason"] == "interrupted"
    assert ends[0]["steps"] is None and ends[0]["counters"] is None
    assert ends[0]["prompt_tokens"] is None and ends[0]["completion_tokens"] is None
    assert ends[0]["seconds"] >= 0 and ends[0]["final_tests"] is None
    assert ends[1]["task"] == 2 and ends[1]["stop_reason"] == "done"


def test_an_interrupt_only_discards_the_interrupted_task(session):
    client = FakeClient([("First done.", None), (None, [native("list_files")]), KeyboardInterrupt(), ("Third done.", None)])
    session(client, ["one", "two", "three"])

    assert client.sent[3] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "First done."},
        {"role": "user", "content": "three"},
    ]


# ── A task that fails with a request error is discarded ──────────────────


# Scenario: A request fails after an earlier task succeeded
def test_a_failed_request_discards_its_task_and_the_next_one_is_well_formed(session, capsys):
    client = FakeClient([("Done.", None), RuntimeError("boom"), ("Documented.", None)])
    session(client, ["fix it", "add a comment", "add a docstring"])

    out = capsys.readouterr().out
    assert "stop reason: error" in out and "this task was discarded because the request failed" in out
    assert client.sent[2] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "fix it"},
        {"role": "assistant", "content": "Done."},
        {"role": "user", "content": "add a docstring"},
    ]


def test_a_failure_in_the_first_task_leaves_the_session_empty(session):
    client = FakeClient([RuntimeError("boom"), ("OK.", None)])
    session(client, ["first", "second"])

    assert client.sent[1] == [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "second"}]


# Scenario: A task runs out of steps
def test_a_task_that_runs_out_of_steps_keeps_its_messages(session):
    client = FakeClient([(None, [native("list_files")]), ("Continued.", None)])
    session(client, ["look around", "keep going"], "--max-steps", "1")

    roles = [m["role"] for m in client.sent[1]]
    assert roles == ["system", "user", "assistant", "tool", "user"]  # 工具呼叫與結果都還在


# ── 權限提示：對應 tool-permissions 規格 ─────────────────────────────────

from test_fixture import BUGGY, FIXED  # noqa: E402  edit_file 要用的舊字串與新字串

PARSER = "timelog/parser.py"


def an_edit():
    return native("edit_file", path=PARSER, old_string=BUGGY, new_string=FIXED)


def parser_text(project):
    return (project / "timelog" / "parser.py").read_text()


# Scenario: Reading is not asked
def test_reading_tools_run_without_a_question(session, capsys):
    client = FakeClient([(None, [native("read_file", path=PARSER), native("list_files"), native("grep", pattern="re")]),
                         ("Done.", None)])
    session(client, ["look around"])

    assert "Allow?" not in capsys.readouterr().out
    assert [m["role"] for m in client.sent[1][-4:]] == ["assistant", "tool", "tool", "tool"]  # 三個讀取都執行了


# Example: answers
@pytest.mark.parametrize("answer, runs", [
    ("y", True), ("a", True), ("n", False), ("", False), ("yes please", False), ("Y", True), (" y ", True),
])
def test_answers_to_the_question(session, project, capsys, answer, runs):
    session(FakeClient([(None, [an_edit()]), ("Done.", None)]), ["fix it", answer])

    assert (FIXED in parser_text(project)) is runs
    assert "Allow? [y]es / [a]lways for this tool / [N]o: " in capsys.readouterr().out


def test_end_of_input_at_the_question_denies_the_call(session, project):
    session(FakeClient([(None, [an_edit()]), ("Done.", None)]), ["fix it"])  # 輸入在問題這裡用完
    assert BUGGY in parser_text(project)


def test_a_denied_call_tells_the_model_the_user_declined(session):
    client = FakeClient([(None, [an_edit()]), ("OK, leaving it.", None)])
    session(client, ["fix it", "n"])

    tool_result = client.sent[1][-1]
    assert tool_result["role"] == "tool" and tool_result["content"].startswith("error: the user declined this call")


# Scenario: Always applies per tool
def test_always_applies_to_that_tool_only(session, project, capsys):
    client = FakeClient([
        (None, [an_edit()]),                                              # 問，回答 a
        (None, [native("edit_file", path=PARSER, old_string=FIXED, new_string=BUGGY)]),  # 不再問
        (None, [native("write_file", path="notes.txt", content="x")]),    # 另一個工具，還是要問，回答 n
        ("Done.", None),
    ])
    session(client, ["fix it", "a", "n"])

    assert capsys.readouterr().out.count("Allow?") == 2           # 只問了 edit_file 一次、write_file 一次
    assert BUGGY in parser_text(project)                           # 第二個 edit_file 在沒問的情況下執行了（改回去）
    assert not (project / "notes.txt").exists()                    # write_file 被拒絕


# Scenario: Long strings are cut
def test_long_strings_are_cut_in_the_summary(session, capsys):
    long_edit = native("edit_file", path=PARSER, old_string="x" * 500, new_string="y")
    session(FakeClient([(None, [long_edit]), ("Done.", None)]), ["fix it", "n"])

    out = capsys.readouterr().out
    assert "x" * 200 in out and "x" * 201 not in out


def test_the_summary_names_the_tool_and_what_it_will_touch(session, capsys):
    client = FakeClient([(None, [native("write_file", path="notes.txt", content="hello")]),
                         (None, [native("run_tests", target="tests")]),
                         (None, [native("run_tests")]), ("Done.", None)])
    session(client, ["go", "n", "n", "n"])

    out = capsys.readouterr().out
    assert "write_file notes.txt (5 characters)" in out
    assert "run_tests tests" in out and "run_tests ." in out


def test_the_edit_summary_shows_the_path_and_both_strings(session, capsys):
    session(FakeClient([(None, [an_edit()]), ("Done.", None)]), ["fix it", "n"])

    out = capsys.readouterr().out
    assert PARSER in out and "re.match" in out and "re.findall" in out


# Ctrl-C 在問題上：當作中斷，丟掉這個任務
def test_ctrl_c_at_the_question_discards_the_task(session, project, capsys):
    client = FakeClient([(None, [an_edit()]), ("Next done.", None)])
    session(client, ["fix it", KeyboardInterrupt(), "next"])

    assert INTERRUPT_MESSAGE in capsys.readouterr().out
    assert BUGGY in parser_text(project)
    assert client.sent[1] == [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "next"}]


def test_three_refused_rounds_in_a_row_end_the_task_as_stuck(session, capsys):
    client = FakeClient([(None, [an_edit()])] * 3)
    session(client, ["fix it", "n", "n", "n"])

    assert "stop reason: stuck" in capsys.readouterr().out

