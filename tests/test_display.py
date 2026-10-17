# 互動模式畫面的格式函式測試：對應 interactive-session 規格的 Tool calls are shown as readable blocks、
# Each task ends with a footer line、Colors only on a terminal。這些函式只回傳字串，所以不需要假 client。
import pytest

from fixlab.display import call_header, color_enabled, edit_diff_lines, footer_line, paint, result_line
from fixlab.loop import AgentResult
from fixlab.workspace import ToolResult


# ── 標題行 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, args, expected", [
    ("read_file", {"path": "timelog/parser.py"}, "  ▸ read_file timelog/parser.py"),
    ("read_file", {"path": "a.py", "start_line": 10, "end_line": 20}, "  ▸ read_file a.py lines 10-20"),
    ("read_file", {"path": "a.py", "start_line": 10}, "  ▸ read_file a.py lines 10-end"),
    ("read_file", {"path": "a.py", "end_line": 20}, "  ▸ read_file a.py lines 1-20"),
    ("list_files", {}, "  ▸ list_files ."),
    ("list_files", {"path": "timelog"}, "  ▸ list_files timelog"),
    ("grep", {"pattern": "parse_duration"}, "  ▸ grep 'parse_duration'"),
    ("grep", {"pattern": "re", "path": "timelog"}, "  ▸ grep 're' in timelog"),
    ("edit_file", {"path": "timelog/parser.py", "old_string": "a", "new_string": "b"}, "  ▸ edit_file timelog/parser.py"),
    ("write_file", {"path": "notes.txt", "content": "hello"}, "  ▸ write_file notes.txt (5 characters)"),
    ("run_tests", {}, "  ▸ run_tests ."),
    ("run_tests", {"target": "tests"}, "  ▸ run_tests tests"),
    ("bash", {"cmd": "ls"}, "  ▸ bash"),
])
def test_header_line_per_tool(name, args, expected):
    assert call_header(name, args) == expected


# ── 改檔的差異 ────────────────────────────────────────────────────────────

def test_a_one_line_edit_shows_one_removed_and_one_added_line():
    assert edit_diff_lines("x = 1", "x = 2") == ["    - x = 1", "    + x = 2"]


def test_multi_line_text_is_shown_line_by_line_with_its_indentation():
    assert edit_diff_lines("if a:\n    b()\n", "if a:\n    c()\n") == [
        "    - if a:", "    -     b()", "    + if a:", "    +     c()"]


# Scenario: A long edit
def test_a_long_edit_is_cut_to_ten_lines_each_with_the_count_left_out():
    old = "\n".join(f"old {n}" for n in range(25))
    new = "\n".join(f"new {n}" for n in range(12))
    lines = edit_diff_lines(old, new)

    removed = [line for line in lines if line.startswith("    - ")]
    added = [line for line in lines if line.startswith("    + ")]
    assert len(removed) == 10 and len(added) == 10
    assert lines[10] == "    … 15 more lines"  # 25 行只顯示 10 行，少了 15 行
    assert lines[-1] == "    … 2 more lines"


def test_a_very_long_line_is_cut_to_200_characters():
    (removed, added) = edit_diff_lines("x" * 500, "y")
    assert removed == "    - " + "x" * 200 + "…" and "x" * 201 not in removed


def test_deleting_text_shows_no_added_lines():
    assert edit_diff_lines("gone", "") == ["    - gone"]


# ── 結果行 ────────────────────────────────────────────────────────────────

PYTEST_FAILED = ".F...  [100%]\nFAILED tests/test_report.py::test_mixed - AssertionError\n1 failed, 4 passed in 0.01s"


@pytest.mark.parametrize("result, expected", [
    (ToolResult("1\tx", True), "    ✓"),
    (ToolResult(".....\n5 passed in 0.01s", True, {"tests_passed": True, "timed_out": False}), "    ✓ 5 passed in 0.01s"),
    (ToolResult(PYTEST_FAILED, True, {"tests_passed": False, "timed_out": False}), "    ✗ 1 failed, 4 passed in 0.01s"),
    (ToolResult("hang\n[tests timed out after 10s]", True, {"tests_passed": False, "timed_out": True}), "    ✗ timed out"),
    (ToolResult("no output", True, {"tests_passed": False, "timed_out": False}), "    ✗ tests failed"),
    (ToolResult("error: the user declined this call. Do not retry it.", False, {"denied": True}), "    ✗ declined"),
    (ToolResult("error: 'tests/a.py' is read-only and cannot be modified.\nmore", False,
                {"blocked": True, "protected_write": True}), "    ✗ blocked: 'tests/a.py' is read-only and cannot be modified."),
    (ToolResult("error: file not found: 'nope.py'", False), "    ✗ file not found: 'nope.py'"),
])
def test_result_line(result, expected):
    assert result_line(result) == expected


# ── 結尾的用量行 ─────────────────────────────────────────────────────────

def agent_result(reason="done", steps=3, prompt=11766, completion=677, seconds=18.4):
    return AgentResult(stop_reason=reason, steps=steps, prompt_tokens=prompt, completion_tokens=completion, seconds=seconds)


# Scenario: Three steps
def test_footer_for_a_finished_task():
    assert footer_line(agent_result()) == "(3 steps · 11,766 + 677 tokens · 18 s)"


def test_footer_uses_the_singular_for_one_step():
    assert footer_line(agent_result(steps=1, prompt=10, completion=5, seconds=0.2)) == "(1 step · 10 + 5 tokens · 0 s)"


# Scenario: Stuck
def test_footer_says_why_a_task_stopped_early():
    assert footer_line(agent_result("stuck")).startswith("(stopped: stuck · 3 steps")
    assert footer_line(agent_result("max_steps", steps=20)).startswith("(stopped: max_steps · 20 steps")


# ── 顏色 ──────────────────────────────────────────────────────────────────

class FakeStream:
    def __init__(self, tty):
        self.tty = tty

    def isatty(self):
        return self.tty


# Scenario: Output is captured
def test_no_color_when_the_output_is_not_a_terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_enabled(FakeStream(False)) is False


# Scenario: NO_COLOR on a terminal
def test_no_color_when_no_color_is_set(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert color_enabled(FakeStream(True)) is False


def test_color_on_a_terminal_without_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_enabled(FakeStream(True)) is True


def test_paint_adds_escape_codes_only_when_color_is_on(monkeypatch):
    monkeypatch.setattr("fixlab.display.color_enabled", lambda stream=None: True)
    assert paint("✓", "green") == "\x1b[32m✓\x1b[0m"
    monkeypatch.setattr("fixlab.display.color_enabled", lambda stream=None: False)
    assert paint("✓", "green") == "✓"


def test_colored_lines_keep_their_text(monkeypatch):
    monkeypatch.setattr("fixlab.display.color_enabled", lambda stream=None: True)
    assert "5 passed in 0.01s" in result_line(ToolResult("5 passed in 0.01s", True, {"tests_passed": True}))
    assert "\x1b[" in edit_diff_lines("a", "b")[0]
    assert "(3 steps" in footer_line(agent_result())
