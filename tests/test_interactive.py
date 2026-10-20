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
            print(line)  # 真的終端機會把你打的字和換行留在畫面上
            return line

        monkeypatch.setattr("builtins.input", fake_input)
        return main([str(project), "--model", "m", "-i", *extra], client=client)
    return run


def event_lines(home):
    (path,) = (home / ".fixlab" / "runs").glob("*/events.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ── Interactive mode is entered with -i ───────────────────────────────────


@pytest.mark.parametrize("extra", [[], ["-i"], ["--model", "m"], ["-i", "--task", "ignored"]])
def test_omitted_path_starts_interactive_in_current_directory(project, home, monkeypatch, capsys, extra):
    monkeypatch.chdir(project)
    monkeypatch.setenv("FIXLAB_MODEL", "m")
    client = FakeClient([])

    def eof(prompt=""):
        print(prompt, end="")
        raise EOFError

    def no_tests(*args, **kwargs):
        raise AssertionError("interactive startup must not run tests")

    monkeypatch.setattr("builtins.input", eof)
    monkeypatch.setattr("fixlab.cli.run_once", no_tests)
    assert main(extra, client=client) == 0

    out, err = capsys.readouterr()
    assert "fixlab> " in out and "RESULT:" not in out
    assert f"editing in place: {project.resolve()}" in err
    assert client.sent == []
    events = event_lines(home)
    assert events[0]["mode"] == "interactive"
    assert events[0]["path"] == str(project.resolve())
    assert not any(event["event"] == "task_start" for event in events)


def test_omitted_path_still_checks_model(project, monkeypatch, capsys):
    monkeypatch.chdir(project)
    monkeypatch.delenv("FIXLAB_MODEL", raising=False)
    client = FakeClient([])
    assert main([], client=client) == 2
    out, err = capsys.readouterr()
    assert "no model" in err and "fixlab> " not in out
    assert client.sent == []


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
    assert out.index("Fixed parse_duration.") < out.index("(1 step")  # 先印答案，再印結尾的用量行


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


# ── Interrupting a task keeps what was completed ─────────────────────────

INTERRUPT_MESSAGE = "interrupted; what was done so far is kept (files may already have been changed; use /reset to start over)"
INTERRUPT_NOTE = {"role": "assistant", "content": "[The user interrupted this task.]"}
REQUEST_FAILED_NOTE = {"role": "assistant", "content": "[The task stopped because the request failed.]"}


# Scenario: Interrupted at a permission question
def test_ctrl_c_at_a_question_keeps_the_work_and_seals_the_unfinished_call(session, project, capsys):
    client = FakeClient([(None, [native("read_file", path=PARSER), an_edit()]), ("Next done.", None)])
    session(client, ["fix it", KeyboardInterrupt(), "try again"])

    assert INTERRUPT_MESSAGE in capsys.readouterr().out
    assert BUGGY in parser_text(project)  # 還沒改
    # Scenario: The next task sees the interrupted one
    next_request = client.sent[1]
    assert [m["role"] for m in next_request] == ["system", "user", "assistant", "tool", "tool", "assistant", "user"]
    assert next_request[4]["content"].startswith("error: interrupted by the user")  # 被打斷的 edit_file 有結果了
    assert next_request[5] == INTERRUPT_NOTE
    assert next_request[6] == {"role": "user", "content": "try again"}


# Scenario: Interrupted while waiting for the model
def test_ctrl_c_while_waiting_for_the_model_leaves_a_well_formed_conversation(session, home):
    client = FakeClient([KeyboardInterrupt(), ("Second done.", None)])
    session(client, ["first task", "second task"])

    assert client.sent[1] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "first task"},
        INTERRUPT_NOTE,
        {"role": "user", "content": "second task"},
    ]
    ends = [line for line in event_lines(home) if line["event"] == "task_end"]
    assert ends[0]["task"] == 1 and ends[0]["stop_reason"] == "interrupted"
    assert ends[0]["steps"] is None and ends[0]["counters"] is None
    assert ends[0]["prompt_tokens"] is None and ends[0]["completion_tokens"] is None
    assert ends[0]["seconds"] >= 0 and ends[0]["final_tests"] is None and ends[0]["changed_files"] is None
    assert ends[1]["task"] == 2 and ends[1]["stop_reason"] == "done"


def test_an_interrupt_keeps_earlier_tasks_too(session):
    client = FakeClient([("First done.", None), (None, [native("list_files")]), KeyboardInterrupt(), ("Third done.", None)])
    session(client, ["one", "two", "three"])

    roles = [m["role"] for m in client.sent[3]]
    # 任務一的完整對話、任務二已完成的部分（工具呼叫與結果）、中斷說明，最後才是任務三
    assert roles == ["system", "user", "assistant", "user", "assistant", "tool", "assistant", "user"]
    assert client.sent[3][6] == INTERRUPT_NOTE and client.sent[3][-1]["content"] == "three"


# ── A task that fails with a request error is discarded ──────────────────


# Scenario: A request fails after an earlier task succeeded
def test_a_failed_request_discards_its_task_and_the_next_one_is_well_formed(session, capsys):
    client = FakeClient([("Done.", None), RuntimeError("boom"), ("Documented.", None)])
    session(client, ["fix it", "add a comment", "add a docstring"])

    out = capsys.readouterr().out
    assert "(stopped: error" in out and "this task was discarded because the request failed" in out
    assert client.sent[2] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "fix it"},
        {"role": "assistant", "content": "Done."},
        {"role": "user", "content": "add a docstring"},
    ]


# Scenario: A request fails after the task already changed something
def test_a_failed_request_after_progress_keeps_what_was_done(session, capsys):
    client = FakeClient([(None, [an_edit()]), RuntimeError("boom"), ("Documented.", None)])
    session(client, ["fix it", "y", "add a docstring"])

    out = capsys.readouterr().out
    assert "the request failed; what was done so far is kept" in out and "discarded" not in out
    roles = [m["role"] for m in client.sent[2]]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "user"]  # 編輯與結果都還在，後面接一則說明
    assert client.sent[2][4] == REQUEST_FAILED_NOTE
    assert client.sent[2][-1]["content"] == "add a docstring"


# 只收到空回覆就失敗：迴圈會加一則 assistant 與一則回饋，但沒有執行過任何工具，不算做過事
def test_a_failure_after_only_an_empty_reply_discards_the_task(session, capsys):
    client = FakeClient([(None, None), RuntimeError("boom"), ("Documented.", None)])
    session(client, ["fix it", "add a docstring"])

    out = capsys.readouterr().out
    assert "this task was discarded because the request failed" in out and "files may already have been changed" not in out
    assert client.sent[2] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "add a docstring"},
    ]


def test_a_failure_in_a_later_task_keeps_that_tasks_work_and_the_earlier_ones(session):
    client = FakeClient([("Done.", None), (None, [an_edit()]), RuntimeError("boom"), ("OK.", None)])
    session(client, ["first", "fix it", "y", "third"])

    roles = [m["role"] for m in client.sent[3]]
    assert roles == ["system", "user", "assistant", "user", "assistant", "tool", "assistant", "user"]
    assert client.sent[3][6] == REQUEST_FAILED_NOTE


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
    ("yes", True), ("YES", True), ("always", True), ("no", False),
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
def test_long_strings_are_cut_in_the_summary(session, project, capsys):
    (project / "long.txt").write_text("x" * 500 + "\n")
    long_edit = native("edit_file", path="long.txt", old_string="x" * 500, new_string="y")
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


def test_three_refused_rounds_in_a_row_end_the_task_as_stuck(session, capsys):
    client = FakeClient([(None, [an_edit()])] * 3)
    session(client, ["fix it", "n", "n", "n"])

    assert "(stopped: stuck" in capsys.readouterr().out


# ── 畫面：Tool calls are shown as readable blocks ─────────────────────────

import re  # noqa: E402


def without_timing(text):
    """耗時每次都不一樣，比對前換成固定字樣。"""
    return re.sub(r"· \d+ s\)", "· X s)", text)


# Scenario: A read followed by a confirmed edit
def test_a_whole_session_looks_like_this(session, capsys):
    client = FakeClient([(None, [native("read_file", path=PARSER)]), (None, [an_edit()]), ("Fixed.", None)])
    session(client, ["fix it", "y"])

    assert without_timing(capsys.readouterr().out) == (
        "fixlab> fix it\n"
        "\n"
        "  ▸ read_file timelog/parser.py\n"
        "    ✓\n"
        "  ▸ edit_file timelog/parser.py\n"
        "    @@ line 9\n"
        "     9       text = text.strip()\n"
        '    10       if not re.fullmatch(r"(\\d+[hm])+", text):\n'
        '    11           raise ValueError(f"invalid duration: {text!r}")\n'
        '    12 -     units = [re.match(r"(\\d+)([hm])", text).groups()]\n'
        '       +     units = re.findall(r"(\\d+)([hm])", text)\n'
        '    13       return sum(int(number) * (60 if unit == "h" else 1) for number, unit in units)\n'
        "    Allow? [y]es / [a]lways for this tool / [N]o: y\n"
        "    ✓\n"
        "\n"
        "Fixed.\n"
        "\n"
        "(3 steps · 30 + 15 tokens · X s)\n"
        "fixlab> \n"
    )


# Scenario: A refused call
def test_a_refused_call_ends_its_block_with_declined(session, capsys):
    session(FakeClient([(None, [native("run_tests")]), ("OK.", None)]), ["run them", "n"])

    out = capsys.readouterr().out
    assert "  ▸ run_tests .\n    Allow? [y]es / [a]lways for this tool / [N]o: n\n    ✗ declined\n" in out


# Scenario: Failing tests
def test_failing_tests_end_their_block_with_the_pytest_summary(session, capsys):
    session(FakeClient([(None, [native("run_tests")]), ("Still failing.", None)]), ["run them", "y"])

    assert re.search(r"    ✗ 1 failed, 4 passed in [\d.]+s\n", capsys.readouterr().out)


# Scenario: A read-only file is not asked about
def test_a_blocked_call_ends_with_the_reason_and_is_not_asked(session, capsys):
    edit_test = native("edit_file", path="tests/test_report.py", old_string="assert", new_string="pass")
    session(FakeClient([(None, [edit_test]), ("OK.", None)]), ["edit the test"])

    out = capsys.readouterr().out
    assert "    ✗ blocked: 'tests/test_report.py' is read-only" in out
    assert "Allow?" not in out


# Scenario: Calls the tool would refuse are not asked about
def test_a_call_with_an_empty_target_fails_without_a_question(session, capsys):
    session(FakeClient([(None, [native("run_tests", target="")]), ("OK.", None)]), ["run them"])

    out = capsys.readouterr().out
    assert "Allow?" not in out
    assert "    ✗ path must be a non-empty string\n" in out


# Scenario: An edit that cannot be applied
def test_an_edit_that_cannot_be_applied_shows_no_difference_and_no_question(session, capsys):
    missing = native("edit_file", path=PARSER, old_string="this text is not in the file", new_string="x")
    session(FakeClient([(None, [missing]), ("OK.", None)]), ["fix it"])

    out = capsys.readouterr().out
    assert "Allow?" not in out and "@@ line" not in out  # 沒有提問，也沒有差異
    assert "    ✗ old_string occurs 0 times" in out


# Scenario: A change that a long edit would hide
def test_a_change_after_a_long_one_is_still_shown(session, capsys):
    docstring = '    """doc\n' + "".join(f"    note {n}\n" for n in range(13)) + '    """\n'  # 把一行的說明換成 15 行
    middle = ('    text = text.strip()\n    if not re.fullmatch(r"(\\d+[hm])+", text):\n'
              '        raise ValueError(f"invalid duration: {text!r}")\n    units = ')
    old = '    """回傳 text 代表的分鐘數，格式不對時拋 ValueError。"""\n' + middle + BUGGY
    new = docstring + middle + FIXED
    edit = native("edit_file", path=PARSER, old_string=old, new_string=new)
    session(FakeClient([(None, [edit]), ("OK.", None)]), ["fix it", "n"])

    out = capsys.readouterr().out
    assert "… 5 more lines" in out                                   # 長的那段被截了
    assert '+     units = re.findall(r"(\\d+)([hm])", text)' in out   # 但後面那處變動看得到


# Scenario: A reply that starts with blank lines
def test_blank_lines_at_the_start_of_the_reply_are_not_printed(session, capsys):
    session(FakeClient([(None, [native("list_files")]), ("\n\nFixed it.\n", None)]), ["fix it"])

    out = capsys.readouterr().out
    assert "    ✓\n\nFixed it.\n\n(2 steps" in out  # 結果行、一個空行、答案、一個空行、結尾那一行


def test_the_per_call_lines_do_not_go_to_standard_error(session, capsys):
    session(FakeClient([(None, [native("list_files")]), ("Done.", None)]), ["look"])

    err = capsys.readouterr().err
    assert "ok=True" not in err and "flags=" not in err


def test_a_request_error_is_shown_to_the_user(session, capsys):
    session(FakeClient([RuntimeError("boom")]), ["go"])

    out = capsys.readouterr().out
    assert "  ! request failed" in out and "boom" in out



# ── 額外的 system prompt：對應 run-telemetry 的 The system prompt can be extended from the command line ──

def test_the_extra_system_prompt_is_in_every_request_of_an_interactive_session(session):
    client = FakeClient([("Done.", None), ("Done.", None)])
    session(client, ["first", "second"], "--system-prompt-extra", "Finish once the fix is made.")

    expected = {"role": "system", "content": SYSTEM_PROMPT + "\n\nFinish once the fix is made."}
    assert client.sent[0][0] == expected and client.sent[1][0] == expected
    assert [m["role"] for m in client.sent[1]].count("system") == 1
