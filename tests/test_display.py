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
# edit_diff_lines(改前整個檔案, 改後整個檔案)：只列有變的地方，前後各帶 3 行上下文，行號是改前的檔案

def numbered(count, changes=None):
    """count 行的檔案，每行是 "line N"；changes 是 {行號: 新文字}，回傳（改前, 改後）。"""
    before = [f"line {n}" for n in range(1, count + 1)]
    after = [(changes or {}).get(n, text) for n, text in enumerate(before, start=1)]
    return "\n".join(before) + "\n", "\n".join(after) + "\n"


def test_a_one_line_edit_shows_the_region_with_one_removed_and_one_added_line():
    assert edit_diff_lines("x = 1\n", "x = 2\n") == ["    @@ line 1", "    1 - x = 1", "      + x = 2"]


def test_multi_line_text_is_shown_line_by_line_with_its_indentation():
    assert edit_diff_lines("if a:\n    b()\n", "if a:\n    c()\n") == [
        "    @@ line 1", "    1   if a:", "    2 -     b()", "      +     c()"]


# Scenario: Context around a change
def test_a_change_comes_with_three_unchanged_lines_before_and_after():
    before, after = numbered(20, {8: "changed"})
    assert edit_diff_lines(before, after) == [
        "    @@ line 5",
        "     5   line 5", "     6   line 6", "     7   line 7",
        "     8 - line 8",
        "       + changed",
        "     9   line 9", "    10   line 10", "    11   line 11",
    ]


def test_two_changes_far_apart_are_two_regions():
    before, after = numbered(30, {5: "a", 25: "b"})
    lines = edit_diff_lines(before, after)
    assert [line for line in lines if "@@" in line] == ["    @@ line 2", "    @@ line 22"]


def test_two_changes_close_together_share_one_region():
    before, after = numbered(30, {10: "a", 14: "b"})
    assert len([line for line in edit_diff_lines(before, after) if "@@" in line]) == 1


# Scenario: A long edit
def test_a_long_edit_is_cut_to_ten_lines_each_with_the_count_left_out():
    old = "\n".join(f"old {n}" for n in range(25)) + "\n"
    new = "\n".join(f"new {n}" for n in range(12)) + "\n"
    lines = edit_diff_lines(old, new)

    removed = [line for line in lines if " - old" in line]
    added = [line for line in lines if " + new" in line]
    assert len(removed) == 10 and len(added) == 10
    assert lines[11].strip() == "… 15 more lines"  # 標題一行，再 10 行刪掉的，然後是少了幾行
    assert lines[-1].strip() == "… 2 more lines"


# Scenario: A change that a long edit would hide
def test_a_second_change_is_still_shown_after_a_long_one():
    before = 'def f(x):\n    """doc"""\n    a = 1\n    b = 2\n    c = 3\n    return [x.groups()]\n'
    docstring = '    """doc\n' + "".join(f"    note {n}\n" for n in range(13)) + '    """\n'   # 15 行
    after = before.replace('    """doc"""\n', docstring).replace("[x.groups()]", "x.findall()")
    shown = "\n".join(edit_diff_lines(before, after))

    assert "… 5 more lines" in shown                    # 長的那段被截了
    assert "- " + "    return [x.groups()]" in shown   # 但後面那處變動看得到
    assert "+ " + "    return x.findall()" in shown


def test_at_most_eight_regions_are_shown_then_how_many_more():
    changes = {n: "changed" for n in range(5, 101, 10)}  # 10 處，彼此相距 10 行，不共用上下文
    before, after = numbered(100, changes)
    lines = edit_diff_lines(before, after)

    assert len([line for line in lines if "@@" in line]) == 8
    assert lines[-1].strip() == "… 2 more changes"


def test_a_very_long_line_is_cut_to_200_characters():
    removed = edit_diff_lines("x" * 500 + "\n", "y\n")[1]
    assert removed == "    1 - " + "x" * 200 + "…" and "x" * 201 not in removed


def test_deleting_text_shows_no_added_lines():
    assert edit_diff_lines("keep\ngone\n", "keep\n") == ["    @@ line 1", "    1   keep", "    2 - gone"]


def test_identical_files_show_nothing():
    assert edit_diff_lines("same\n", "same\n") == []


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
    assert "\x1b[" in edit_diff_lines("a\n", "b\n")[0]
    assert "(3 steps" in footer_line(agent_result())


def test_error_text_cannot_put_control_characters_on_the_screen(monkeypatch):
    # 外部工具的錯誤可能回顯模型給的參數：跳脫序列不能原樣印到終端機，否則能遮住下一次的確認畫面。
    monkeypatch.setenv("NO_COLOR", "1")
    line = result_line(ToolResult("error: no such file '\x1b[1;1r‮secret\x9b2J'", False))
    assert "\x1b" not in line and "‮" not in line and "\x9b" not in line
    assert "\\x1b[1;1r" in line and "secret" in line
