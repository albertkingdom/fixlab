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
    session(client, ["fix it"])

    assert FIXED in (project / "timelog" / "parser.py").read_text()
